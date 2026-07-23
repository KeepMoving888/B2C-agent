"""RAG 质量评估器

对 RAG 检索质量进行系统化评估，覆盖以下 IR 标准指标：
    - Recall@K    （K=1,3,5） 检索召回率：top-K 内是否覆盖了相关文档
    - MRR         （Mean Reciprocal Rank） 第一个相关文档排名的倒数均值
    - Precision@K （K=1,3,5） top-K 中相关文档的占比
    - NDCG@K      （K=1,3,5） 归一化折损累积增益，考虑排序质量与位置折损
    - Context Relevance 检索上下文与查询的相关性评分（基于 token 覆盖率）

评估流程：
    1. 加载标注的评估测试集（query + 相关文档 ID 列表）
    2. 对每个 query 调用 retriever.retrieve 执行检索
    3. 计算 Recall@K / MRR / Precision@K / NDCG@K / Context Relevance
    4. 聚合为评估报告（含 per-query 分析）

设计原则：
    - 不依赖 Milvus / GPU：所有指标仅基于检索返回的 doc_id 与标注对比
    - 遵循现有代码风格：loguru 日志 + Pydantic 模型 + 类型注解
    - 指标实现严格遵循 IR 学术定义（NDCG 使用 log2 位置折损，MRR 取倒数）
"""
import json
import math
import os
import re
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field


# ----------------------------------------------------------------------
# 数据模型
# ----------------------------------------------------------------------

class EvalQuery(BaseModel):
    """评估测试集中的单条样本"""
    query: str = Field(..., description="查询文本")
    intent: str = Field("", description="标注意图（用于检索时 intent 过滤）")
    relevant_docs: list[str] = Field(default_factory=list, description="相关文档 ID 列表（顺序表示相关度优先级）")
    lang: str = Field("zh", description="查询语言")
    note: str = Field("", description="标注备注")


class RetrievedDoc(BaseModel):
    """检索返回的单条文档（与 retriever.retrieve 返回结构对齐）"""
    id: str = ""
    content: str = ""
    category: str = ""
    score: float = 0.0
    source: str = ""


class QueryEvalResult(BaseModel):
    """单条 query 的评估结果"""
    query: str
    intent: str
    lang: str
    relevant_docs: list[str]
    retrieved_ids: list[str] = Field(default_factory=list, description="实际检索返回的 doc_id 顺序列表")
    retrieved_scores: list[float] = Field(default_factory=list, description="与 retrieved_ids 对应的检索分数")
    hit: bool = Field(False, description="top-K 内是否命中任一相关文档（K=5）")
    first_rel_rank: Optional[int] = Field(None, description="第一个相关文档的 1-based 排名；未命中为 None")
    recall: dict[int, float] = Field(default_factory=dict, description="Recall@K，K→值")
    precision: dict[int, float] = Field(default_factory=dict, description="Precision@K，K→值")
    ndcg: dict[int, float] = Field(default_factory=dict, description="NDCG@K，K→值")
    mrr: float = Field(0.0, description="本条 query 的倒数排名（即 1/first_rel_rank）")
    context_relevance: float = Field(0.0, description="检索上下文与 query 的相关性评分 [0,1]")


class EvalReport(BaseModel):
    """整体评估报告"""
    dataset_size: int = Field(0, description="评估样本数")
    ks: list[int] = Field(default_factory=lambda: [1, 3, 5], description="评估使用的 K 值列表")
    # 聚合指标
    recall: dict[int, float] = Field(default_factory=dict, description="整体 Recall@K")
    precision: dict[int, float] = Field(default_factory=dict, description="整体 Precision@K")
    ndcg: dict[int, float] = Field(default_factory=dict, description="整体 NDCG@K")
    mrr: float = Field(0.0, description="MRR")
    context_relevance: float = Field(0.0, description="平均 Context Relevance")
    hit_rate: float = Field(0.0, description="top-5 命中率")
    # per-query
    per_query: list[QueryEvalResult] = Field(default_factory=list)
    # 按意图分组的聚合
    by_intent: dict[str, dict] = Field(default_factory=dict, description="intent -> 指标 dict")
    # 元信息
    milvus_used: bool = Field(False, description="评估时是否使用 Milvus")
    notes: list[str] = Field(default_factory=list, description="评估过程中的备注/告警")


# ----------------------------------------------------------------------
# 评估器
# ----------------------------------------------------------------------

class RAGEvaluator:
    """RAG 质量评估器

    用法::

        evaluator = RAGEvaluator()
        report = evaluator.evaluate()
        print(evaluator.format_report(report))
    """

    # 默认 K 列表
    DEFAULT_KS: list[int] = [1, 3, 5]
    # 默认评估数据集路径
    DEFAULT_DATASET_PATH: str = os.path.join(
        os.path.dirname(__file__), "..", "data", "eval", "rag_eval_dataset.json"
    )

    def __init__(
        self,
        dataset_path: Optional[str] = None,
        ks: Optional[list[int]] = None,
        top_k: int = 5,
    ):
        """
        Args:
            dataset_path: 评估数据集 JSON 路径；None 时使用默认路径
            ks: 评估 K 值列表；None 时使用 [1,3,5]
            top_k: 检索时拉取的 top_k 数量（应 >= max(ks)）
        """
        self.dataset_path = os.path.abspath(dataset_path or self.DEFAULT_DATASET_PATH)
        self.ks = list(ks or self.DEFAULT_KS)
        self.top_k = max(top_k, max(self.ks))
        self._dataset: list[EvalQuery] = []
        self._notes: list[str] = []

    # ------------------------------------------------------------------
    # 数据加载
    # ------------------------------------------------------------------

    def load_dataset(self) -> list[EvalQuery]:
        """加载评估测试集"""
        if not os.path.exists(self.dataset_path):
            msg = f"评估数据集不存在: {self.dataset_path}"
            logger.error(msg)
            raise FileNotFoundError(msg)

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        self._dataset = [EvalQuery(**item) for item in raw]
        logger.info(f"加载评估数据集 {len(self._dataset)} 条: {self.dataset_path}")
        return self._dataset

    @property
    def dataset(self) -> list[EvalQuery]:
        if not self._dataset:
            self.load_dataset()
        return self._dataset

    # ------------------------------------------------------------------
    # 指标计算（静态方法，便于单独单测）
    # ------------------------------------------------------------------

    @staticmethod
    def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """Recall@K：top-K 内命中的相关文档数 / 全部相关文档数

        - 分母取 min(|relevant|, k) 还是 |relevant| 是 IR 的两种口径。
        - 这里采用学术标准定义：分母为 |relevant|（衡量是否召回"所有"相关文档），
          同时对 k 截断的结果有意义：当相关文档数 > k 时，Recall@K ≤ 1 是合理的。
        """
        if not relevant_ids:
            return 0.0
        topk = retrieved_ids[:k]
        hit = len(set(topk) & set(relevant_ids))
        return hit / len(set(relevant_ids))

    @staticmethod
    def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """Precision@K：top-K 内相关文档数 / K"""
        if k <= 0:
            return 0.0
        topk = retrieved_ids[:k]
        hit = len(set(topk) & set(relevant_ids))
        return hit / k

    @staticmethod
    def first_relevant_rank(retrieved_ids: list[str], relevant_ids: list[str]) -> Optional[int]:
        """返回第一个相关文档的 1-based 排名；未命中返回 None"""
        rel_set = set(relevant_ids)
        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in rel_set:
                return i + 1
        return None

    @staticmethod
    def reciprocal_rank(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
        """RR = 1 / first_relevant_rank；未命中为 0"""
        rank = RAGEvaluator.first_relevant_rank(retrieved_ids, relevant_ids)
        return 1.0 / rank if rank else 0.0

    @staticmethod
    def ndcg_at_k(
        retrieved_ids: list[str],
        relevant_ids: list[str],
        k: int,
        graded: bool = False,
    ) -> float:
        """NDCG@K：归一化折损累积增益

        二元相关性（graded=False）:
            rel_i = 1 if retrieved_ids[i] in relevant_ids else 0
            DCG@K  = sum_{i=1..K}  rel_i / log2(i + 1)
            IDCG@K = sum_{i=1..min(K, |relevant|)} 1 / log2(i + 1)
            NDCG@K = DCG@K / IDCG@K    （IDCG=0 时返回 0）

        分级相关性（graded=True）:
            用 relevant_ids 的顺序作为相关度等级。
            例如 relevant_ids=[faq_007, faq_003] 时，faq_007 的 grade=2，faq_003 的 grade=1。
            DCG 使用 2^rel - 1 折损。
        """
        if not relevant_ids or k <= 0:
            return 0.0

        # 构建 doc_id -> grade 映射
        if graded:
            # 顺序越靠前等级越高
            grade_map = {doc_id: len(relevant_ids) - idx for idx, doc_id in enumerate(relevant_ids)}
        else:
            grade_map = {doc_id: 1 for doc_id in relevant_ids}

        # DCG@K
        dcg = 0.0
        for i, doc_id in enumerate(retrieved_ids[:k]):
            rel = grade_map.get(doc_id, 0)
            if rel > 0:
                # 位置折损：1-based 位置 i+1，分母 log2(i+1+1) = log2(i+2)
                # 标准定义：DCG = sum rel_i / log2(i+1) 其中 i 从 1 开始
                if graded:
                    gain = (2 ** rel - 1)
                else:
                    gain = rel
                dcg += gain / math.log2(i + 2)  # i+2 因为 i 是 0-based

        # IDCG@K：理想情况下，按 grade 降序排列
        ideal_grades = sorted(grade_map.values(), reverse=True)[:k]
        idcg = 0.0
        for i, rel in enumerate(ideal_grades):
            if rel > 0:
                if graded:
                    gain = (2 ** rel - 1)
                else:
                    gain = rel
                idcg += gain / math.log2(i + 2)

        if idcg <= 0:
            return 0.0
        return dcg / idcg

    @staticmethod
    def context_relevance(query: str, retrieved_docs: list[dict]) -> float:
        """检索上下文与 query 的相关性评分

        采用 token 覆盖率（Coverage Ratio）作为相关性代理：
            score = |query_tokens ∩ union(retrieved_tokens)| / |query_tokens|

        - 不依赖 embedding 模型，可在无 GPU 环境下运行
        - 取值范围 [0, 1]，1 表示查询所有 token 都能在检索上下文中找到
        - 当 retrieved_docs 为空时返回 0

        Args:
            query: 查询文本
            retrieved_docs: 检索返回的文档列表 [{"content": ...}, ...]
        """
        if not query or not retrieved_docs:
            return 0.0

        query_tokens = set(_tokenize(query.lower()))
        if not query_tokens:
            return 0.0

        context_tokens: set[str] = set()
        for doc in retrieved_docs:
            content = (doc.get("content") or "") + " " + " ".join(doc.get("keywords", []) or [])
            context_tokens.update(_tokenize(content.lower()))

        covered = query_tokens & context_tokens
        return len(covered) / len(query_tokens)

    # ------------------------------------------------------------------
    # 单条评估
    # ------------------------------------------------------------------

    def evaluate_query(self, sample: EvalQuery) -> QueryEvalResult:
        """对单条 query 执行检索并计算指标"""
        # 延迟导入，避免循环依赖
        from app.rag.retriever import retrieve

        # 拉取 top_k 个文档（>= max(ks) 以保证所有 K 值可计算）
        results = retrieve(sample.query, intent=sample.intent, top_k=self.top_k)

        retrieved_ids = [r.get("id", "") for r in results]
        retrieved_scores = [float(r.get("score", 0.0)) for r in results]

        # 计算 Recall@K / Precision@K / NDCG@K
        recall = {k: self.recall_at_k(retrieved_ids, sample.relevant_docs, k) for k in self.ks}
        precision = {k: self.precision_at_k(retrieved_ids, sample.relevant_docs, k) for k in self.ks}
        ndcg = {k: self.ndcg_at_k(retrieved_ids, sample.relevant_docs, k, graded=False) for k in self.ks}

        # MRR（单条为 RR）
        rr = self.reciprocal_rank(retrieved_ids, sample.relevant_docs)
        first_rank = self.first_relevant_rank(retrieved_ids, sample.relevant_docs)

        # Context Relevance
        ctx_rel = self.context_relevance(sample.query, results)

        # 命中判定（top-5 内命中即视为 hit）
        hit = first_rank is not None and first_rank <= 5

        if not hit:
            logger.debug(
                f"[eval-miss] query='{sample.query}' relevant={sample.relevant_docs} retrieved={retrieved_ids}"
            )

        return QueryEvalResult(
            query=sample.query,
            intent=sample.intent,
            lang=sample.lang,
            relevant_docs=sample.relevant_docs,
            retrieved_ids=retrieved_ids,
            retrieved_scores=retrieved_scores,
            hit=hit,
            first_rel_rank=first_rank,
            recall=recall,
            precision=precision,
            ndcg=ndcg,
            mrr=rr,
            context_relevance=ctx_rel,
        )

    # ------------------------------------------------------------------
    # 整体评估
    # ------------------------------------------------------------------

    def evaluate(self) -> EvalReport:
        """对全部样本执行评估，返回整体报告"""
        self._notes = []

        # 确保索引已构建（触发内存回退，避免单测报错）
        try:
            from app.rag.indexer import build_index, is_milvus_available
            build_index()
            milvus_used = is_milvus_available()
        except Exception as e:  # pragma: no cover - 仅在异常环境下触发
            logger.warning(f"索引构建失败，继续评估: {e}")
            milvus_used = False

        if milvus_used:
            self._notes.append("评估在 Milvus 模式下运行")
        else:
            self._notes.append("评估在内存回退模式下运行（无 Milvus / 无 GPU）")

        samples = self.dataset
        per_query: list[QueryEvalResult] = []
        for sample in samples:
            try:
                per_query.append(self.evaluate_query(sample))
            except Exception as e:
                logger.exception(f"评估 query 失败: {sample.query} -> {e}")
                self._notes.append(f"评估失败 query='{sample.query}': {e}")

        # 聚合
        n = len(per_query)
        if n == 0:
            logger.warning("无有效评估结果")
            return EvalReport(dataset_size=0, milvus_used=milvus_used, notes=self._notes)

        agg_recall = {k: sum(r.recall[k] for r in per_query) / n for k in self.ks}
        agg_precision = {k: sum(r.precision[k] for r in per_query) / n for k in self.ks}
        agg_ndcg = {k: sum(r.ndcg[k] for r in per_query) / n for k in self.ks}
        agg_mrr = sum(r.mrr for r in per_query) / n
        agg_ctx = sum(r.context_relevance for r in per_query) / n
        hit_rate = sum(1 for r in per_query if r.hit) / n

        # 按意图分组聚合
        by_intent: dict[str, dict] = {}
        for r in per_query:
            intent = r.intent or "unknown"
            bucket = by_intent.setdefault(intent, {"count": 0, "mrr": 0.0, "hit_rate": 0.0, "ctx_rel": 0.0,
                                                    "recall@3": 0.0, "ndcg@3": 0.0})
            bucket["count"] += 1
            bucket["mrr"] += r.mrr
            bucket["hit_rate"] += 1.0 if r.hit else 0.0
            bucket["ctx_rel"] += r.context_relevance
            bucket["recall@3"] += r.recall.get(3, 0.0)
            bucket["ndcg@3"] += r.ndcg.get(3, 0.0)

        for intent, bucket in by_intent.items():
            c = bucket["count"]
            if c > 0:
                for key in ("mrr", "hit_rate", "ctx_rel", "recall@3", "ndcg@3"):
                    bucket[key] = round(bucket[key] / c, 4)
            bucket["count"] = c

        report = EvalReport(
            dataset_size=n,
            ks=list(self.ks),
            recall={k: round(v, 4) for k, v in agg_recall.items()},
            precision={k: round(v, 4) for k, v in agg_precision.items()},
            ndcg={k: round(v, 4) for k, v in agg_ndcg.items()},
            mrr=round(agg_mrr, 4),
            context_relevance=round(agg_ctx, 4),
            hit_rate=round(hit_rate, 4),
            per_query=per_query,
            by_intent=by_intent,
            milvus_used=milvus_used,
            notes=self._notes,
        )

        logger.info(
            f"RAG 评估完成: n={n} | "
            f"Recall@5={report.recall.get(5, 0):.3f} | "
            f"MRR={report.mrr:.3f} | "
            f"NDCG@5={report.ndcg.get(5, 0):.3f} | "
            f"HitRate@5={report.hit_rate:.3f}"
        )
        return report

    # ------------------------------------------------------------------
    # 报告格式化
    # ------------------------------------------------------------------

    @staticmethod
    def format_report(report: EvalReport) -> str:
        """格式化报告为可读文本（命令行输出）"""
        lines: list[str] = []
        sep = "=" * 70
        lines.append(sep)
        lines.append("RAG 质量评估报告 (RAG Quality Evaluation Report)")
        lines.append(sep)
        lines.append(f"数据集样本数 (Dataset Size) : {report.dataset_size}")
        lines.append(f"评估 K 值 (K Values)        : {report.ks}")
        lines.append(f"Milvus 模式 (Milvus Used)   : {report.milvus_used}")
        for note in report.notes:
            lines.append(f"  - 备注: {note}")
        lines.append("")

        lines.append("-" * 70)
        lines.append("【整体聚合指标 / Aggregate Metrics】")
        lines.append("-" * 70)
        lines.append(f"Hit Rate @5        : {report.hit_rate:.4f}")
        lines.append(f"MRR                : {report.mrr:.4f}")
        lines.append(f"Context Relevance  : {report.context_relevance:.4f}")
        for k in report.ks:
            lines.append(
                f"  Recall@{k:<2}  : {report.recall.get(k, 0):.4f}   "
                f"Precision@{k:<2}: {report.precision.get(k, 0):.4f}   "
                f"NDCG@{k:<2}    : {report.ndcg.get(k, 0):.4f}"
            )
        lines.append("")

        lines.append("-" * 70)
        lines.append("【按意图分组 / By Intent】")
        lines.append("-" * 70)
        header = f"{'Intent':<14}{'Count':<8}{'HitRate':<10}{'MRR':<10}{'Recall@3':<12}{'NDCG@3':<10}{'CtxRel':<10}"
        lines.append(header)
        for intent, m in report.by_intent.items():
            lines.append(
                f"{intent:<14}{m.get('count', 0):<8}{m.get('hit_rate', 0):<10.4f}"
                f"{m.get('mrr', 0):<10.4f}{m.get('recall@3', 0):<12.4f}"
                f"{m.get('ndcg@3', 0):<10.4f}{m.get('ctx_rel', 0):<10.4f}"
            )
        lines.append("")

        lines.append("-" * 70)
        lines.append("【Per-Query 分析 / Per-Query Details】")
        lines.append("-" * 70)
        for i, r in enumerate(report.per_query, 1):
            rank_str = r.first_rel_rank if r.first_rel_rank is not None else "—"
            hit_str = "HIT " if r.hit else "MISS"
            lines.append(f"[{i:>2}] {hit_str} | lang={r.lang} | intent={r.intent} | first_rank={rank_str}")
            lines.append(f"     Q: {r.query}")
            lines.append(f"     期望相关: {r.relevant_docs}")
            lines.append(f"     检索返回: {r.retrieved_ids}")
            lines.append(
                f"     R@1={r.recall.get(1, 0):.2f} R@3={r.recall.get(3, 0):.2f} R@5={r.recall.get(5, 0):.2f} "
                f"| P@1={r.precision.get(1, 0):.2f} P@3={r.precision.get(3, 0):.2f} "
                f"| NDCG@3={r.ndcg.get(3, 0):.2f} | MRR={r.mrr:.2f} | CtxRel={r.context_relevance:.2f}"
            )
        lines.append(sep)
        return "\n".join(lines)


# ----------------------------------------------------------------------
# 工具函数：与 retriever._tokenize 保持一致的中英文混合分词
# ----------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """简易分词（中英文混合）

    与 app.rag.retriever._tokenize 保持一致：
    - 英文按字母连续序列切分（小写化）
    - 中文按单字切分
    """
    if not text:
        return []
    en_tokens = re.findall(r"[a-zA-Z]+", text.lower())
    zh_tokens = re.findall(r"[\u4e00-\u9fa5]", text)
    return en_tokens + zh_tokens


# ----------------------------------------------------------------------
# 模块级便捷接口
# ----------------------------------------------------------------------

def run_evaluation(dataset_path: Optional[str] = None, ks: Optional[list[int]] = None) -> EvalReport:
    """便捷入口：执行一次完整评估

    Args:
        dataset_path: 评估数据集路径
        ks: K 值列表
    """
    evaluator = RAGEvaluator(dataset_path=dataset_path, ks=ks)
    return evaluator.evaluate()
