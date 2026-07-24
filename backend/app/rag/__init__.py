"""RAG 检索增强包

包含以下子模块：
    - indexer          : Milvus 向量索引 + 内存回退
    - retriever        : 向量检索 + BM25 混合检索 + RRF 融合
    - reranker         : Cross-Encoder 重排序
    - prompts          : CoT 思维链 Prompt
    - evaluator        : RAG 质量评估器（Recall@K / MRR / Precision@K / NDCG@K / Context Relevance）
    - anti_hallucination : 反幻觉机制（引用溯源 + 置信度阈值 + 答案一致性校验）
"""
from .indexer import build_index, is_milvus_available
from .retriever import retrieve
from .reranker import rerank
from .prompts import build_cot_prompt, build_suggest_prompt

# RAG 质量评估
from .evaluator import (
    RAGEvaluator,
    EvalReport,
    EvalQuery,
    QueryEvalResult,
    run_evaluation,
)

# 反幻觉机制
from .anti_hallucination import (
    AntiHallucinationChecker,
    AntiHallucinationReport,
    Citation,
    check_reply,
    annotate_reply,
    get_checker,
)

__all__ = [
    # 基础 RAG
    "build_index",
    "is_milvus_available",
    "retrieve",
    "rerank",
    "build_cot_prompt",
    "build_suggest_prompt",
    # RAG 质量评估
    "RAGEvaluator",
    "EvalReport",
    "EvalQuery",
    "QueryEvalResult",
    "run_evaluation",
    # 反幻觉机制
    "AntiHallucinationChecker",
    "AntiHallucinationReport",
    "Citation",
    "check_reply",
    "annotate_reply",
    "get_checker",
]
