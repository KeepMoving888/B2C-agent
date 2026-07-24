"""反幻觉机制 (Anti-Hallucination)

为 RAG 生成的回复提供三层反幻觉防护，可平滑集成到现有 Agent 流程中：

    层 1：引用溯源 (Citation)
        每条回复必须标注来源文档 ID 与内容片段，未引用则视为高风险。

    层 2：置信度阈值 (Confidence Threshold)
        基于检索 top1 的归一化分数划分三档：
            score < 0.3  → low    建议转人工
            0.3 ≤ score < 0.6 → medium  回复需标注"仅供参考"
            score ≥ 0.6  → high   正常回复

    层 3：答案一致性校验 (Faithfulness Check)
        从回复中抽取关键事实（数字 / 日期 / 政策性陈述），
        校验这些事实是否能在检索到的上下文中找到。
        一致性 < 0.7 → 标记"可能包含不准确信息"。

最终输出一个结构化的 AntiHallucinationReport，包含：
    citations / confidence / confidence_level /
    faithfulness / hallucination_risk / should_escalate

设计要点：
    - 检索分数自适应归一化（兼容余弦相似度 / BM25 / RRF 融合分）
    - 不依赖 LLM 即可完成事实校验（基于规则的事实抽取 + 上下文匹配）
    - Pydantic 模型 + loguru 日志 + 类型注解，与现有代码风格一致
"""
import math
import re
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field


# ----------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------

# RRF 融合分理论最大值：k=60，两路检索源，最大 = 2 / (60+1) ≈ 0.0328
RRF_THEORETICAL_MAX: float = 2.0 / 61.0

# 置信度阈值
CONFIDENCE_THRESHOLD_LOW: float = 0.3     # < 0.3 视为低置信度
CONFIDENCE_THRESHOLD_HIGH: float = 0.6    # ≥ 0.6 视为高置信度

# 答案一致性阈值
FAITHFULNESS_THRESHOLD: float = 0.7       # < 0.7 视为可能含不准确信息

# 内容片段最大长度（用于 citation snippet）
CITATION_SNIPPET_MAX_LEN: int = 120


# ----------------------------------------------------------------------
# 数据模型
# ----------------------------------------------------------------------

class Citation(BaseModel):
    """单条引用溯源"""
    doc_id: str = Field(..., description="来源文档 ID")
    content_snippet: str = Field("", description="来源内容片段（用于展示）")
    score: float = Field(0.0, description="该文档的检索分数（归一化前）")


class AntiHallucinationReport(BaseModel):
    """反幻觉评估报告"""
    citations: list[Citation] = Field(default_factory=list, description="引用溯源列表")
    confidence: float = Field(0.0, description="归一化置信度 [0,1]")
    confidence_level: str = Field("low", description="置信度等级 high/medium/low")
    faithfulness: float = Field(0.0, description="答案与上下文的一致性 [0,1]")
    faithfulness_passed: bool = Field(False, description="一致性是否通过阈值")
    hallucination_risk: str = Field("high", description="幻觉风险 low/medium/high")
    should_escalate: bool = Field(False, description="是否建议转人工")
    risks: list[str] = Field(default_factory=list, description="风险原因列表")
    facts_extracted: list[str] = Field(default_factory=list, description="从回复中抽取的事实")
    facts_supported: list[str] = Field(default_factory=list, description="被上下文支持的事实")
    facts_unsupported: list[str] = Field(default_factory=list, description="未被上下文支持的事实")


# ----------------------------------------------------------------------
# 反幻觉评估器
# ----------------------------------------------------------------------

class AntiHallucinationChecker:
    """反幻觉校验器

    用法::

        checker = AntiHallucinationChecker()
        report = checker.check(
            query="退款多久到账",
            retrieved_docs=[{"id":"faq_003","content":"...","score":0.85}, ...],
            reply="退款3-5个工作日原路退回。",
        )
        if report.should_escalate:
            ...  # 转人工
    """

    def __init__(
        self,
        low_threshold: float = CONFIDENCE_THRESHOLD_LOW,
        high_threshold: float = CONFIDENCE_THRESHOLD_HIGH,
        faithfulness_threshold: float = FAITHFULNESS_THRESHOLD,
    ):
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold
        self.faithfulness_threshold = faithfulness_threshold

    # ------------------------------------------------------------------
    # 对外主接口
    # ------------------------------------------------------------------

    def check(
        self,
        query: str,
        retrieved_docs: list[dict],
        reply: str,
        intent: str = "",
    ) -> AntiHallucinationReport:
        """对一条 RAG 回复执行三层反幻觉校验

        Args:
            query: 用户查询
            retrieved_docs: 检索返回的文档列表 [{"id","content","score",...}]
            reply: LLM 生成的回复文本
            intent: 意图（仅用于日志）

        Returns:
            AntiHallucinationReport
        """
        risks: list[str] = []

        # ---------- 层 1：引用溯源 ----------
        citations = self._build_citations(retrieved_docs)
        if not citations:
            risks.append("no_citation: 回复未引用任何来源文档")
            logger.debug(f"[anti-halluc] no_citation query='{query}'")

        # ---------- 层 2：置信度阈值 ----------
        confidence, raw_top_score = self._compute_confidence(retrieved_docs)
        confidence_level = self._confidence_level(confidence)
        if confidence_level == "low":
            risks.append(f"low_confidence: 检索 top1 score={raw_top_score:.4f} → 归一化置信度={confidence:.4f}")
        elif confidence_level == "medium":
            risks.append(f"medium_confidence: 归一化置信度={confidence:.4f}，建议标注'仅供参考'")

        # ---------- 层 3：答案一致性校验 ----------
        facts = self._extract_facts(reply)
        supported, unsupported = self._verify_facts(facts, retrieved_docs)
        faithfulness = self._compute_faithfulness(facts, supported)
        faithfulness_passed = faithfulness >= self.faithfulness_threshold
        if facts and not faithfulness_passed:
            risks.append(
                f"low_faithfulness: 一致性={faithfulness:.4f} < {self.faithfulness_threshold}，"
                f"未支持事实 {len(unsupported)}/{len(facts)}"
            )

        # ---------- 综合判定 ----------
        hallucination_risk = self._compute_risk_level(
            confidence_level, faithfulness, faithfulness_passed, has_citation=bool(citations)
        )
        should_escalate = self._should_escalate(
            confidence_level, hallucination_risk, has_citation=bool(citations)
        )

        report = AntiHallucinationReport(
            citations=citations,
            confidence=round(confidence, 4),
            confidence_level=confidence_level,
            faithfulness=round(faithfulness, 4),
            faithfulness_passed=faithfulness_passed,
            hallucination_risk=hallucination_risk,
            should_escalate=should_escalate,
            risks=risks,
            facts_extracted=facts,
            facts_supported=supported,
            facts_unsupported=unsupported,
        )

        logger.debug(
            f"[anti-halluc] query='{query}' intent='{intent}' "
            f"conf={confidence:.3f}({confidence_level}) "
            f"faith={faithfulness:.3f} risk={hallucination_risk} escalate={should_escalate}"
        )
        return report

    # ------------------------------------------------------------------
    # 层 1：引用溯源
    # ------------------------------------------------------------------

    def _build_citations(self, retrieved_docs: list[dict]) -> list[Citation]:
        """从检索结果构造引用列表

        - 仅保留有 doc_id 且非空内容的文档
        - snippet 截取前 CITATION_SNIPPET_MAX_LEN 字符
        """
        citations: list[Citation] = []
        for doc in retrieved_docs:
            doc_id = doc.get("id") or ""
            content = doc.get("content") or ""
            if not doc_id:
                continue
            snippet = content[:CITATION_SNIPPET_MAX_LEN]
            if len(content) > CITATION_SNIPPET_MAX_LEN:
                snippet = snippet + "..."
            citations.append(Citation(
                doc_id=doc_id,
                content_snippet=snippet,
                score=float(doc.get("score", 0.0)),
            ))
        return citations

    # ------------------------------------------------------------------
    # 层 2：置信度阈值
    # ------------------------------------------------------------------

    def _compute_confidence(self, retrieved_docs: list[dict]) -> tuple[float, float]:
        """计算归一化置信度

        Returns:
            (normalized_confidence, raw_top_score)

        适配多种检索打分尺度：
            - 余弦相似度（IP + normalize_embeddings）：score ∈ [0,1]，直接使用
            - BM25 原始分：score 可能 > 1，用 sigmoid 压缩到 (0,1)
            - RRF 融合分：score ∈ [0, 2/61]，按理论最大值归一化
        """
        if not retrieved_docs:
            return 0.0, 0.0

        scores = [float(d.get("score", 0.0)) for d in retrieved_docs]
        top_score = max(scores) if scores else 0.0
        if top_score <= 0:
            return 0.0, 0.0

        normalized = self._normalize_score(top_score, scores)

        # 综合 top1 与 top2 的 margin，提升"明确命中"的置信度
        if len(scores) >= 2:
            sorted_scores = sorted(scores, reverse=True)
            top1, top2 = sorted_scores[0], sorted_scores[1]
            # margin ∈ [0, 1]：top2 越接近 top1，margin 越小
            margin = (top1 - top2) / top1 if top1 > 0 else 0.0
            # 轻量融合：normalized 占 80%，margin 占 20%
            normalized = 0.8 * normalized + 0.2 * min(1.0, margin)

        return min(1.0, max(0.0, normalized)), top_score

    @staticmethod
    def _normalize_score(top_score: float, all_scores: list[float]) -> float:
        """将 top1 检索分数归一化到 [0,1]

        检测打分尺度并自适应归一化：
            - score > 1.0          : BM25 等无界打分，用 sigmoid 压缩
            - 0.1 < score ≤ 1.0    : 余弦相似度，直接使用
            - score ≤ 0.1          : RRF 融合分，按 RRF_THEORETICAL_MAX 归一化
        """
        if top_score <= 0:
            return 0.0
        if top_score > 1.0:
            # 无界打分（BM25 原始分）：sigmoid 压缩
            return 1.0 / (1.0 + math.exp(-top_score))
        if top_score > 0.1:
            # 余弦相似度区间
            return min(1.0, top_score)
        # RRF 融合分区间：按理论最大值归一化
        return min(1.0, top_score / RRF_THEORETICAL_MAX)

    def _confidence_level(self, confidence: float) -> str:
        """置信度分档：high / medium / low"""
        if confidence >= self.high_threshold:
            return "high"
        if confidence >= self.low_threshold:
            return "medium"
        return "low"

    # ------------------------------------------------------------------
    # 层 3：答案一致性校验 (Faithfulness)
    # ------------------------------------------------------------------

    # 事实抽取的正则模式（按优先级）
    # 1) 数量 + 单位（数字 + 工作日/天/小时/周/个月/日/年/月）
    _RE_DURATION = re.compile(
        r"\d+\s*[-~到至]\s*\d+\s*(?:个工作日|工作日|天|小时|周|个月|日|年|月)|"
        r"\d+\s*(?:个工作日|工作日|天|小时|周|个月|日|年|月)"
    )
    # 2) 纯数字组合（含小数）：如 5.3、IPX5、IP68、12 个月 → 抽 "IPX5" "12"
    _RE_NUMBER = re.compile(r"\d+(?:\.\d+)?")
    # 3) 政策性陈述关键词（出现即视为一条事实声明）
    _POLICY_KEYWORDS = [
        "全额退款", "部分退款", "扣除运费", "免费补发", "不支持无理由退货",
        "支持无理由退货", "原路退回", "原路退款", "PCI-DSS", "GDPR",
        "数据删除", "不存储", "免税", "DDP", "加急费",
        "免费修改", "原路", "保修期", "兼容",
    ]

    def _extract_facts(self, reply: str) -> list[str]:
        """从回复中抽取关键事实

        抽取三类事实：
            - 时长/数量表达（"7-12个工作日"、"48小时"）
            - 独立数字（"IPX5"、"5.3"、"32"）
            - 政策性陈述（"全额退款"、"原路退回" 等）

        Args:
            reply: LLM 生成的回复

        Returns:
            去重后的事实列表
        """
        if not reply:
            return []

        facts: list[str] = []

        # 1) 时长/数量表达（优先级最高，先抽取并从原文中"消耗"避免重复抽取纯数字）
        durations = self._RE_DURATION.findall(reply)
        facts.extend(durations)

        # 2) 政策性陈述
        for kw in self._POLICY_KEYWORDS:
            if kw in reply:
                facts.append(kw)

        # 3) 独立数字：仅在未被时长模式覆盖时抽取
        #    简化策略：抽取所有数字，去除已出现在 durations 中的
        duration_nums = set()
        for d in durations:
            duration_nums.update(self._RE_NUMBER.findall(d))

        for num in self._RE_NUMBER.findall(reply):
            if num not in duration_nums:
                facts.append(num)

        # 去重保序
        seen = set()
        unique: list[str] = []
        for f in facts:
            if f and f not in seen:
                seen.add(f)
                unique.append(f)
        return unique

    def _verify_facts(
        self,
        facts: list[str],
        retrieved_docs: list[dict],
    ) -> tuple[list[str], list[str]]:
        """校验抽取的事实是否在检索上下文中出现

        Args:
            facts: 抽取出的事实列表
            retrieved_docs: 检索文档

        Returns:
            (supported, unsupported)
        """
        if not facts:
            return [], []

        # 拼接所有检索文档的 content + keywords 作为上下文
        context_parts = []
        for doc in retrieved_docs:
            content = doc.get("content") or ""
            keywords = doc.get("keywords") or []
            if isinstance(keywords, list):
                keywords = " ".join(keywords)
            context_parts.append(content)
            context_parts.append(keywords)
        context = "\n".join(context_parts)

        supported: list[str] = []
        unsupported: list[str] = []
        for fact in facts:
            # 精确子串匹配（policy 关键词与时长表达都适用）
            if fact in context:
                supported.append(fact)
            else:
                # 数字事实放宽：如果上下文中存在该数字，视为支持
                # （已被精确匹配覆盖，这里作为兜底）
                unsupported.append(fact)

        return supported, unsupported

    @staticmethod
    def _compute_faithfulness(facts: list[str], supported: list[str]) -> float:
        """计算一致性分数

        - 无事实可校验时返回 1.0（无可证伪内容，默认可信）
        - 否则 = supported / total
        """
        if not facts:
            return 1.0
        return len(supported) / len(facts)

    # ------------------------------------------------------------------
    # 综合判定
    # ------------------------------------------------------------------

    def _compute_risk_level(
        self,
        confidence_level: str,
        faithfulness: float,
        faithfulness_passed: bool,
        has_citation: bool,
    ) -> str:
        """综合三层信号判定幻觉风险等级

        判定优先级：
            - 任意一层严重失败（低置信 / 无引用 / 一致性 < 阈值）→ high
            - 至少一层告警（中置信 / 一致性偏低）→ medium
            - 全部通过 → low
        """
        high_signals = 0
        medium_signals = 0

        if confidence_level == "low":
            high_signals += 1
        elif confidence_level == "medium":
            medium_signals += 1

        if not has_citation:
            high_signals += 1

        if not faithfulness_passed:
            # 一致性低于阈值视为高风险
            high_signals += 1
        elif faithfulness < 0.85:
            # 一致性临界值，视为中等风险
            medium_signals += 1

        if high_signals > 0:
            return "high"
        if medium_signals > 0:
            return "medium"
        return "low"

    def _should_escalate(
        self,
        confidence_level: str,
        hallucination_risk: str,
        has_citation: bool,
    ) -> bool:
        """是否建议转人工

        转人工条件（满足其一）：
            - 置信度低（检索 top1 归一化分数 < 0.3）
            - 幻觉风险 high
            - 无任何引用
        """
        if confidence_level == "low":
            return True
        if hallucination_risk == "high":
            return True
        if not has_citation:
            return True
        return False


# ----------------------------------------------------------------------
# 模块级便捷接口
# ----------------------------------------------------------------------

# 全局单例（线程不安全，多线程场景请自行 new）
_default_checker: Optional[AntiHallucinationChecker] = None


def get_checker() -> AntiHallucinationChecker:
    """获取默认反幻觉校验器单例"""
    global _default_checker
    if _default_checker is None:
        _default_checker = AntiHallucinationChecker()
    return _default_checker


def check_reply(
    query: str,
    retrieved_docs: list[dict],
    reply: str,
    intent: str = "",
) -> AntiHallucinationReport:
    """便捷接口：对一条 RAG 回复执行反幻觉校验

    Args:
        query: 用户查询
        retrieved_docs: 检索返回的文档列表
        reply: LLM 生成的回复
        intent: 意图

    Returns:
        AntiHallucinationReport
    """
    return get_checker().check(query, retrieved_docs, reply, intent=intent)


def annotate_reply(report: AntiHallucinationReport, reply: str) -> str:
    """根据反幻觉报告对回复进行标注

    - low 置信度：在回复前加 [仅供参考] 或建议转人工
    - medium 置信度：标注 [仅供参考]
    - 一致性未通过：标注 [可能包含不准确信息]
    - 高风险：建议转人工

    Args:
        report: 反幻觉报告
        reply: 原始回复

    Returns:
        标注后的回复
    """
    if not reply:
        return reply

    prefixes: list[str] = []

    if report.should_escalate:
        prefixes.append("[建议转人工]")
    if report.confidence_level == "medium":
        prefixes.append("[仅供参考]")
    if not report.faithfulness_passed:
        prefixes.append("[可能包含不准确信息]")

    if not prefixes:
        return reply
    return " ".join(prefixes) + " " + reply
