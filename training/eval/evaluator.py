"""微调效果评估器

实现 QLoRA 微调前后模型效果的自动化评估，覆盖以下指标：
- BLEU Score: BLEU-1, BLEU-2, BLEU-4（含 brevity penalty 长度惩罚）
- ROUGE Score: ROUGE-1, ROUGE-2, ROUGE-L（Precision / Recall / F1）
- Response Quality: 多维度质量评分（相关性 / 准确性 / 完整性 / 语气 / 多语言）
- Latency: 首 token 延迟 + 完整生成时间

评估流程：
    1. 加载评估测试集（query + 参考答案 + 期望属性）
    2. 分别用基座模型和微调模型生成回复（live 模式调用 vLLM）
    3. 计算 BLEU / ROUGE / 质量评分 / 延迟
    4. 汇总输出对比报告

使用方式：
    from evaluator import Evaluator
    ev = Evaluator()
    report = ev.evaluate_batch(samples, responses_by_model)
    # 或者单独使用 BLEU / ROUGE 计算
    from evaluator import bleu_score, rouge_score
    print(bleu_score([ref_tokens], cand_tokens))
    print(rouge_score([ref_tokens], cand_tokens))

依赖：
    pip install loguru
    # 可选（live 评估，调用 vLLM）：
    pip install openai
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger


# ============================================================
# 多语言分词
# ============================================================

# CJK Unicode 范围：中文/日文/韩文
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")


def tokenize(text: str, lang: Optional[str] = None) -> list[str]:
    """多语言分词

    策略：
        - CJK 字符（中文/日文/韩文）：按字符切分（字符级 n-gram）
        - 拉丁文字：按词切分，统一小写化
        - 标点符号：忽略（不参与 n-gram 匹配）

    Args:
        text: 待分词文本
        lang: 语言代码（zh/en/ja/de/es/fr/...），主要用于调试，分词策略自适应

    Returns:
        token 列表
    """
    if not text:
        return []
    text = text.lower()
    tokens: list[str] = []
    current: list[str] = []
    for char in text:
        if _CJK_PATTERN.match(char):
            # CJK 字符独立成 token
            if current:
                tokens.append("".join(current))
                current = []
            tokens.append(char)
        elif char.isalnum():
            current.append(char)
        else:
            # 标点/空白：结束当前 token
            if current:
                tokens.append("".join(current))
                current = []
    if current:
        tokens.append("".join(current))
    return tokens


# ============================================================
# BLEU 实现
# ============================================================

def _ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    """生成 n-gram 列表"""
    if len(tokens) < n:
        return []
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def _modified_precision(
    references: list[list[str]],
    candidate: list[str],
    n: int,
) -> float:
    """修改后的 n-gram 精度（clipped precision）

    BLEU 核心思想：候选翻译中每个 n-gram 的计数不能超过其在任意参考答案中的最大计数。
    这避免了"重复生成同一个高频词刷分"的作弊行为。

    公式：
        p_n = sum(min(count_c(g), max_ref_count(g))) / sum(count_c(g))

    Args:
        references: 多个参考答案（已分词）
        candidate: 候选翻译（已分词）
        n: n-gram 阶数

    Returns:
        修改后的 n-gram 精度，[0, 1]
    """
    cand_ngrams = _ngrams(candidate, n)
    if not cand_ngrams:
        return 0.0
    cand_counts = Counter(cand_ngrams)

    # 取所有参考答案中各 n-gram 的最大计数
    max_ref_counts: dict[tuple[str, ...], int] = {}
    for ref in references:
        ref_counts = Counter(_ngrams(ref, n))
        for ngram, count in ref_counts.items():
            if count > max_ref_counts.get(ngram, 0):
                max_ref_counts[ngram] = count

    # 截断计数
    clipped = sum(min(c, max_ref_counts.get(g, 0)) for g, c in cand_counts.items())
    total = sum(cand_counts.values())
    return clipped / total if total > 0 else 0.0


def _brevity_penalty(references: list[list[str]], candidate: list[str]) -> float:
    """长度惩罚（Brevity Penalty, BP）

    防止模型生成极短回复来骗取高精度。

    公式：
        BP = 1                  if c > r
        BP = exp(1 - r/c)       if c <= r
        BP = 0                  if c == 0

    其中：
        c = 候选翻译长度
        r = 最接近候选长度的参考答案长度（best match length）

    Args:
        references: 多个参考答案（已分词）
        candidate: 候选翻译（已分词）

    Returns:
        BP 值，[0, 1]
    """
    c = len(candidate)
    if c == 0:
        return 0.0
    ref_lens = [len(r) for r in references if len(r) > 0]
    if not ref_lens:
        return 0.0
    # best match length：与候选长度最接近的参考长度
    r = min(ref_lens, key=lambda x: (abs(x - c), x))
    if c > r:
        return 1.0
    return math.exp(1 - r / c)


def bleu_score(
    references: list[list[str]],
    candidate: list[str],
    max_n: int = 4,
) -> dict[str, float]:
    """计算 BLEU 分数

    返回各阶 BLEU：
        bleu_1 = BP * p_1                              （unigram 几何平均 = 自身）
        bleu_2 = BP * (p_1 * p_2)^(1/2)
        bleu_3 = BP * (p_1 * p_2 * p_3)^(1/3)
        bleu_4 = BP * (p_1 * p_2 * p_3 * p_4)^(1/4)
        bleu   = bleu_4                                （综合分，等权 4-gram）

    任意一阶精度为 0 时，对应 BLEU 直接置 0（几何平均不允许 0 取对数）。

    Args:
        references: 参考答案列表（已分词）
        candidate: 候选翻译（已分词）
        max_n: 最大 n-gram 阶数，默认 4

    Returns:
        {"bleu_1": ..., "bleu_2": ..., "bleu_3": ..., "bleu_4": ..., "bleu": ...}
    """
    bp = _brevity_penalty(references, candidate)
    precisions = [
        _modified_precision(references, candidate, n) for n in range(1, max_n + 1)
    ]

    result: dict[str, float] = {}
    for n in range(1, max_n + 1):
        # 前 n 阶精度的几何平均
        head = precisions[:n]
        if any(p == 0.0 for p in head):
            result[f"bleu_{n}"] = 0.0
        else:
            geo_mean = math.exp(sum(math.log(p) for p in head) / n)
            result[f"bleu_{n}"] = bp * geo_mean

    # 综合分（等权 BLEU-4）
    result["bleu"] = result.get(f"bleu_{max_n}", 0.0)
    return result


# ============================================================
# ROUGE 实现
# ============================================================

def _lcs_length(a: list[str], b: list[str]) -> int:
    """最长公共子序列长度（动态规划）

    ROUGE-L 的核心。时间复杂度 O(m*n)，空间可优化为 O(min(m,n))，
    但评估数据规模不大，二维 DP 更清晰可读。

    Args:
        a, b: 两个 token 序列

    Returns:
        LCS 长度
    """
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return 0
    # dp[i][j] = a[:i] 与 b[:j] 的 LCS 长度
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]


def _prf(precision: float, recall: float) -> float:
    """计算 F1"""
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def rouge_n(
    references: list[list[str]],
    candidate: list[str],
    n: int,
) -> dict[str, float]:
    """计算 ROUGE-N（Precision / Recall / F1）

    ROUGE 是召回率导向的指标，衡量参考答案中被候选覆盖的比例。
    多个参考答案时取最高分（jackknifing 简化版）。

    Args:
        references: 参考答案列表（已分词）
        candidate: 候选翻译（已分词）
        n: n-gram 阶数

    Returns:
        {"precision": ..., "recall": ..., "f1": ...}
    """
    cand_ngrams = _ngrams(candidate, n)
    if not cand_ngrams:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    cand_counts = Counter(cand_ngrams)
    cand_total = sum(cand_counts.values())

    best = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    for ref in references:
        ref_ngrams = _ngrams(ref, n)
        if not ref_ngrams:
            continue
        ref_counts = Counter(ref_ngrams)
        ref_total = sum(ref_counts.values())

        overlap = sum(min(c, ref_counts.get(g, 0)) for g, c in cand_counts.items())
        p = overlap / cand_total if cand_total > 0 else 0.0
        r = overlap / ref_total if ref_total > 0 else 0.0
        f = _prf(p, r)
        if f > best["f1"]:
            best = {"precision": p, "recall": r, "f1": f}
    return best


def rouge_l(
    references: list[list[str]],
    candidate: list[str],
) -> dict[str, float]:
    """计算 ROUGE-L（基于 LCS 的 F1）

    ROUGE-L 使用最长公共子序列（LCS）衡量顺序匹配能力，
    相比 ROUGE-N 对词序更敏感，适合评估回复的连贯性。

    Args:
        references: 参考答案列表（已分词）
        candidate: 候选翻译（已分词）

    Returns:
        {"precision": ..., "recall": ..., "f1": ...}
    """
    if not candidate:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    best = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    for ref in references:
        if not ref:
            continue
        lcs = _lcs_length(candidate, ref)
        p = lcs / len(candidate)
        r = lcs / len(ref)
        f = _prf(p, r)
        if f > best["f1"]:
            best = {"precision": p, "recall": r, "f1": f}
    return best


def rouge_score(
    references: list[list[str]],
    candidate: list[str],
) -> dict[str, dict[str, float]]:
    """计算 ROUGE 全套指标

    Returns:
        {
            "rouge_1": {"precision":..., "recall":..., "f1":...},
            "rouge_2": {...},
            "rouge_l": {...},
        }
    """
    return {
        "rouge_1": rouge_n(references, candidate, 1),
        "rouge_2": rouge_n(references, candidate, 2),
        "rouge_l": rouge_l(references, candidate),
    }


# ============================================================
# 多维度质量评分
# ============================================================

# 各维度权重（总和为 1.0）
QUALITY_WEIGHTS = {
    "relevance": 0.3,    # 相关性：回复是否切题
    "accuracy": 0.3,     # 准确性：事实是否正确
    "completeness": 0.2, # 完整性：是否完整解答
    "tone": 0.1,         # 语气：客服语气得体性
    "multilingual": 0.1, # 多语言：目标语言表达正确性
}


# 客服常用礼貌用语（多语言）
_POLITE_PHRASES: dict[str, list[str]] = {
    "zh": ["请", "感谢", "谢谢", "抱歉", "对不起", "您好", "亲", "谅解", "协助"],
    "en": ["please", "thank", "sorry", "apolog", "hello", "regret", "appreciate", "assist", "help"],
    "ja": ["ください", "ありがとうござ", "申し訳", "すみません", "こんにちは", "ご確認"],
    "de": ["bitte", "danke", "entschuld", "hallo", "hilfe"],
    "es": ["por favor", "gracias", "disculpe", "hola", "ayuda"],
    "fr": ["s'il vous plaît", "merci", "excusez", "bonjour", "aide"],
    "it": ["per favore", "grazie", "scusa", "ciao", "aiuto"],
    "pt": ["por favor", "obrigado", "desculpe", "olá", "ajuda"],
}


@dataclass
class QualityScore:
    """质量评分结果"""
    relevance: float = 0.0       # 相关性 0-5
    accuracy: float = 0.0        # 准确性 0-5
    completeness: float = 0.0    # 完整性 0-5
    tone: float = 0.0            # 语气 0-5
    multilingual: float = 0.0    # 多语言正确性 0-5

    @property
    def overall(self) -> float:
        """加权总分（0-5）"""
        return (
            self.relevance * QUALITY_WEIGHTS["relevance"]
            + self.accuracy * QUALITY_WEIGHTS["accuracy"]
            + self.completeness * QUALITY_WEIGHTS["completeness"]
            + self.tone * QUALITY_WEIGHTS["tone"]
            + self.multilingual * QUALITY_WEIGHTS["multilingual"]
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "relevance": round(self.relevance, 2),
            "accuracy": round(self.accuracy, 2),
            "completeness": round(self.completeness, 2),
            "tone": round(self.tone, 2),
            "multilingual": round(self.multilingual, 2),
            "overall": round(self.overall, 2),
        }


class QualityScorer:
    """多维度质量评分器

    采用启发式规则进行评分（无需额外 LLM 作为评判官），
    适用于离线场景。在 live 模式下，可结合 vLLM 调用 LLM-as-Judge
    做更精准的语义评分（本框架预留扩展点）。

    评分范围统一为 0-5 分：
        - 5: 完美
        - 4: 良好
        - 3: 合格
        - 2: 较差
        - 1: 很差
        - 0: 完全不可用
    """

    def score(
        self,
        query: str,
        response: str,
        reference: str,
        lang: str = "zh",
        expected_relevance: int = 5,
        expected_accuracy: int = 5,
    ) -> QualityScore:
        """计算单条样本的质量评分

        Args:
            query: 用户问题
            response: 模型生成回复
            reference: 参考答案
            lang: 目标语言代码
            expected_relevance: 期望相关性（仅用于参考）
            expected_accuracy: 期望准确性（仅用于参考）

        Returns:
            QualityScore 对象
        """
        if not response or not response.strip():
            return QualityScore()

        return QualityScore(
            relevance=self._score_relevance(query, response),
            accuracy=self._score_accuracy(response, reference),
            completeness=self._score_completeness(response, reference),
            tone=self._score_tone(response, lang),
            multilingual=self._score_multilingual(response, lang),
        )

    def _score_relevance(self, query: str, response: str) -> float:
        """相关性评分：基于 query 与 response 的关键词重叠

        思路：回复中包含的问题关键词越多，越切题。
        """
        q_tokens = set(tokenize(query))
        r_tokens = set(tokenize(response))
        if not q_tokens:
            return 2.5
        overlap = len(q_tokens & r_tokens)
        # 覆盖率 [0,1]，映射到 [0,5]
        ratio = overlap / len(q_tokens)
        # 回复过短额外扣分
        if len(r_tokens) < 5:
            ratio *= 0.6
        return round(min(5.0, ratio * 5.0 + 0.5), 2)

    def _score_accuracy(self, response: str, reference: str) -> float:
        """准确性评分：基于与参考答案的语义重叠（ROUGE-L F1 近似）

        思路：与参考答案越接近，事实越准确。
        """
        ref_tokens = tokenize(reference)
        cand_tokens = tokenize(response)
        if not ref_tokens or not cand_tokens:
            return 1.0
        rl = rouge_l([ref_tokens], cand_tokens)
        # F1 [0,1] 映射到 [0,5]，加 0.5 基础分避免全 0
        return round(min(5.0, rl["f1"] * 4.5 + 0.5), 2)

    def _score_completeness(self, response: str, reference: str) -> float:
        """完整性评分：基于参考答案关键词覆盖率 + 长度合理性

        思路：回复应覆盖参考答案的关键信息点，且长度适中。
        """
        ref_tokens = set(tokenize(reference))
        cand_tokens = set(tokenize(response))
        if not ref_tokens:
            return 2.5
        coverage = len(ref_tokens & cand_tokens) / len(ref_tokens)
        # 长度合理性：太短扣分，过长也轻微扣分
        len_ratio = len(cand_tokens) / max(len(ref_tokens), 1)
        if len_ratio < 0.3:
            length_score = 0.5
        elif len_ratio > 3.0:
            length_score = 0.8
        else:
            length_score = 1.0
        score = coverage * 0.7 + length_score * 0.3
        return round(min(5.0, score * 5.0), 2)

    def _score_tone(self, response: str, lang: str) -> float:
        """语气评分：基于客服礼貌用语覆盖率

        思路：客服回复应包含礼貌用语（请/感谢/抱歉等）。
        """
        phrases = _POLITE_PHRASES.get(lang, _POLITE_PHRASES["en"])
        text_lower = response.lower()
        hits = sum(1 for p in phrases if p.lower() in text_lower)
        # 0 命中：1.5 分；1 命中：3 分；2+ 命中：4.5-5 分
        if hits == 0:
            return 1.5
        elif hits == 1:
            return 3.0
        elif hits == 2:
            return 4.5
        else:
            return 5.0

    def _score_multilingual(self, response: str, lang: str) -> float:
        """多语言正确性：检查回复语言是否与目标语言一致

        思路：通过 CJK 字符比例与拉丁字符比例判断语言一致性。
        """
        if not response:
            return 0.0
        cjk_count = sum(1 for c in response if _CJK_PATTERN.match(c))
        latin_count = sum(1 for c in response if c.isalpha() and not _CJK_PATTERN.match(c))
        total = cjk_count + latin_count
        if total == 0:
            return 2.0

        cjk_ratio = cjk_count / total
        is_cjk_lang = lang in ("zh", "ja", "ko")

        if is_cjk_lang:
            # 期望 CJK 占主导
            score = 2.0 + cjk_ratio * 3.0
        else:
            # 期望拉丁字符占主导
            score = 2.0 + (1 - cjk_ratio) * 3.0
        # 含少量目标语言即给基础分
        return round(min(5.0, max(0.5, score)), 2)


# ============================================================
# 延迟测量
# ============================================================

@dataclass
class Latency:
    """延迟测量结果（毫秒）"""
    time_to_first_token_ms: float = 0.0  # 首 token 延迟
    total_generation_ms: float = 0.0     # 完整生成时间
    tokens_generated: int = 0            # 生成 token 数

    @property
    def tokens_per_second(self) -> float:
        """生成吞吐量（token/秒）"""
        if self.total_generation_ms <= 0 or self.tokens_generated <= 0:
            return 0.0
        return self.tokens_generated / (self.total_generation_ms / 1000.0)


# ============================================================
# 评估样本与报告
# ============================================================

@dataclass
class EvalSample:
    """评估样本"""
    query: str
    lang: str
    intent: str
    reference_answer: str
    expected_relevance: int = 5
    expected_accuracy: int = 5

    @classmethod
    def from_dict(cls, d: dict) -> "EvalSample":
        return cls(
            query=d.get("query", ""),
            lang=d.get("lang", "zh"),
            intent=d.get("intent", ""),
            reference_answer=d.get("reference_answer", ""),
            expected_relevance=d.get("expected_relevance", 5),
            expected_accuracy=d.get("expected_accuracy", 5),
        )


@dataclass
class EvalResult:
    """单条样本评估结果"""
    query: str
    lang: str
    intent: str
    response: str
    reference: str
    bleu: dict[str, float] = field(default_factory=dict)
    rouge: dict[str, dict[str, float]] = field(default_factory=dict)
    quality: dict[str, float] = field(default_factory=dict)
    latency: Latency = field(default_factory=Latency)


def load_eval_dataset(path: str) -> list[EvalSample]:
    """加载评估数据集

    Args:
        path: JSON 文件路径

    Returns:
        EvalSample 列表
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"评估数据集不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    samples = [EvalSample.from_dict(item) for item in data]
    logger.info(f"加载评估数据集 {len(samples)} 条: {path}")
    return samples


class Evaluator:
    """评估器主类

    用法：
        ev = Evaluator()
        # 1) 离线评估：已有模型回复
        result = ev.evaluate_single(sample, response)
        # 2) 批量评估
        report = ev.evaluate_batch(samples, responses)
        # 3) live 模式：调用 vLLM 实时生成
        report = ev.evaluate_live(samples, vllm_base_url="http://localhost:8001/v1")
    """

    def __init__(self):
        self.quality_scorer = QualityScorer()

    def evaluate_single(
        self,
        sample: EvalSample,
        response: str,
        latency: Optional[Latency] = None,
    ) -> EvalResult:
        """评估单条样本

        Args:
            sample: 评估样本
            response: 模型生成回复
            latency: 延迟测量结果（可选）

        Returns:
            EvalResult
        """
        ref_tokens = tokenize(sample.reference_answer, sample.lang)
        cand_tokens = tokenize(response, sample.lang)

        bleu = bleu_score([ref_tokens], cand_tokens, max_n=4)
        rouge = rouge_score([ref_tokens], cand_tokens)
        quality = self.quality_scorer.score(
            query=sample.query,
            response=response,
            reference=sample.reference_answer,
            lang=sample.lang,
            expected_relevance=sample.expected_relevance,
            expected_accuracy=sample.expected_accuracy,
        ).to_dict()

        return EvalResult(
            query=sample.query,
            lang=sample.lang,
            intent=sample.intent,
            response=response,
            reference=sample.reference_answer,
            bleu=bleu,
            rouge=rouge,
            quality=quality,
            latency=latency or Latency(),
        )

    def evaluate_batch(
        self,
        samples: list[EvalSample],
        responses: list[str],
        latencies: Optional[list[Latency]] = None,
    ) -> dict:
        """批量评估并汇总

        Args:
            samples: 评估样本列表
            responses: 对应的模型回复列表
            latencies: 对应的延迟测量列表（可选）

        Returns:
            汇总报告 dict，包含：
                - per_sample: 每条样本的详细结果
                - aggregate: 聚合指标（BLEU/ROUGE/质量均值）
        """
        assert len(samples) == len(responses), "samples 与 responses 数量不一致"
        if latencies is None:
            latencies = [Latency() for _ in samples]

        per_sample: list[dict] = []
        for sample, response, lat in zip(samples, responses, latencies):
            result = self.evaluate_single(sample, response, lat)
            per_sample.append({
                "query": result.query,
                "lang": result.lang,
                "intent": result.intent,
                "response": result.response,
                "reference": result.reference,
                "bleu": result.bleu,
                "rouge": result.rouge,
                "quality": result.quality,
                "latency": {
                    "ttft_ms": round(result.latency.time_to_first_token_ms, 2),
                    "total_ms": round(result.latency.total_generation_ms, 2),
                    "tokens": result.latency.tokens_generated,
                    "tps": round(result.latency.tokens_per_second, 2),
                },
            })

        aggregate = self._aggregate(per_sample)
        return {"per_sample": per_sample, "aggregate": aggregate}

    def evaluate_live(
        self,
        samples: list[EvalSample],
        vllm_base_url: str = "http://localhost:8001/v1",
        vllm_api_key: str = "EMPTY",
        model: str = "Qwen2.5-7B-Instruct",
        system_prompt: str = "你是跨境电商客服助手，请用专业、有温度的语言回复客户。",
    ) -> dict:
        """实时调用 vLLM 进行评估

        Args:
            samples: 评估样本
            vllm_base_url: vLLM OpenAI 兼容接口地址
            vllm_api_key: API Key（vLLM 默认 EMPTY）
            model: 模型名
            system_prompt: 系统提示

        Returns:
            评估报告
        """
        try:
            from openai import OpenAI
        except ImportError:
            logger.error("缺少 openai 依赖，请安装: pip install openai")
            return {"error": "missing openai dependency"}

        client = OpenAI(base_url=vllm_base_url, api_key=vllm_api_key, timeout=30)

        responses: list[str] = []
        latencies: list[Latency] = []
        for i, sample in enumerate(samples):
            logger.info(f"[{i+1}/{len(samples)}] 评估: {sample.query[:30]}...")
            try:
                t0 = time.perf_counter()
                # 使用 stream 模式测量 TTFT
                stream = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": sample.query},
                    ],
                    temperature=0.3,
                    max_tokens=512,
                    stream=True,
                )
                first_token_time = None
                chunks: list[str] = []
                for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        if first_token_time is None:
                            first_token_time = time.perf_counter()
                        chunks.append(delta.content)
                t1 = time.perf_counter()
                response_text = "".join(chunks).strip()
                ttft = (first_token_time - t0) * 1000 if first_token_time else (t1 - t0) * 1000
                total = (t1 - t0) * 1000
                # 粗略 token 计数
                tokens = len(tokenize(response_text))
                responses.append(response_text)
                latencies.append(Latency(
                    time_to_first_token_ms=ttft,
                    total_generation_ms=total,
                    tokens_generated=tokens,
                ))
            except Exception as e:
                logger.error(f"vLLM 调用失败: {e}")
                responses.append("")
                latencies.append(Latency())

        return self.evaluate_batch(samples, responses, latencies)

    def _aggregate(self, per_sample: list[dict]) -> dict:
        """聚合所有样本的指标"""
        n = len(per_sample)
        if n == 0:
            return {}

        # BLEU 均值
        bleu_keys = ["bleu_1", "bleu_2", "bleu_3", "bleu_4", "bleu"]
        bleu_avg = {
            k: round(sum(s["bleu"].get(k, 0.0) for s in per_sample) / n, 4)
            for k in bleu_keys
        }

        # ROUGE 均值
        rouge_keys = ["rouge_1", "rouge_2", "rouge_l"]
        rouge_avg = {}
        for rk in rouge_keys:
            for metric in ["precision", "recall", "f1"]:
                key = f"{rk}_{metric}"
                rouge_avg[key] = round(
                    sum(s["rouge"].get(rk, {}).get(metric, 0.0) for s in per_sample) / n, 4
                )

        # 质量评分均值
        quality_keys = ["relevance", "accuracy", "completeness", "tone", "multilingual", "overall"]
        quality_avg = {
            k: round(sum(s["quality"].get(k, 0.0) for s in per_sample) / n, 2)
            for k in quality_keys
        }

        # 延迟均值
        latency_avg = {
            "ttft_ms": round(sum(s["latency"]["ttft_ms"] for s in per_sample) / n, 2),
            "total_ms": round(sum(s["latency"]["total_ms"] for s in per_sample) / n, 2),
            "tps": round(sum(s["latency"]["tps"] for s in per_sample) / n, 2),
        }

        return {
            "n_samples": n,
            "bleu": bleu_avg,
            "rouge": rouge_avg,
            "quality": quality_avg,
            "latency": latency_avg,
        }


# ============================================================
# CLI 入口（可独立运行做单条样例验证）
# ============================================================

if __name__ == "__main__":
    # 简单自测：验证 BLEU/ROUGE 实现正确性
    ref = tokenize("您好，您的订单已发货，预计3-5个工作日送达。")
    cand1 = tokenize("您好，您的订单已发货，预计3-5个工作日送达。")  # 完全匹配
    cand2 = tokenize("订单已经发出，差不多一周内到。")  # 部分匹配
    cand3 = tokenize("今天天气不错。")  # 完全不相关

    print("=== BLEU 自测 ===")
    for name, cand in [("完全匹配", cand1), ("部分匹配", cand2), ("完全不相关", cand3)]:
        b = bleu_score([ref], cand)
        print(f"  {name}: bleu_1={b['bleu_1']:.3f} bleu_2={b['bleu_2']:.3f} bleu_4={b['bleu_4']:.3f}")

    print("\n=== ROUGE 自测 ===")
    for name, cand in [("完全匹配", cand1), ("部分匹配", cand2), ("完全不相关", cand3)]:
        r = rouge_score([ref], cand)
        print(f"  {name}: rouge_1_f1={r['rouge_1']['f1']:.3f} "
              f"rouge_2_f1={r['rouge_2']['f1']:.3f} "
              f"rouge_l_f1={r['rouge_l']['f1']:.3f}")

    print("\n=== 质量评分自测 ===")
    scorer = QualityScorer()
    qs = scorer.score(
        query="我的包裹多久能到？",
        response="您好，您的订单已发货，预计3-5个工作日送达，请耐心等待。感谢您的支持！",
        reference="您好，您的订单已发货，预计3-5个工作日送达，请留意物流更新。",
        lang="zh",
    )
    print(f"  {qs.to_dict()}")
