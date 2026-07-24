"""重排序器

基于 Cross-Encoder（bge-reranker）对混合检索结果进行重排序。
模型不可用时回退至简单打分。
"""
from typing import Optional
from loguru import logger

from app.config import settings


_reranker = None
_reranker_inited = False


def _get_reranker():
    """获取重排序模型（懒加载）"""
    global _reranker, _reranker_inited
    if _reranker_inited:
        return _reranker
    _reranker_inited = True
    try:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(settings.reranker_model)
        logger.info(f"重排序模型已加载: {settings.reranker_model}")
    except Exception as e:
        logger.debug(f"重排序模型不可用，回退至简单打分: {e}")
    return _reranker


def rerank(query: str, documents: list[dict], top_k: int = 3) -> list[dict]:
    """对检索结果重排序

    Args:
        query: 查询文本
        documents: 待重排序文档 [{"content","score",...}]
        top_k: 返回数量

    Returns:
        重排序后的文档列表
    """
    if not documents:
        return []

    reranker = _get_reranker()
    if reranker is None:
        return _simple_rerank(query, documents, top_k)

    try:
        pairs = [(query, d.get("content", "")) for d in documents]
        scores = reranker.predict(pairs)
        for d, s in zip(documents, scores):
            d["rerank_score"] = float(s)
        documents.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        return documents[:top_k]
    except Exception as e:
        logger.debug(f"重排序失败，回退: {e}")
        return _simple_rerank(query, documents, top_k)


def _simple_rerank(query: str, documents: list[dict], top_k: int) -> list[dict]:
    """简单重排序（基于关键词重叠度）"""
    query_words = set(query.lower().split())
    for d in documents:
        content_words = set(d.get("content", "").lower().split())
        overlap = len(query_words & content_words)
        d["rerank_score"] = overlap + d.get("score", 0)
    documents.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    return documents[:top_k]
