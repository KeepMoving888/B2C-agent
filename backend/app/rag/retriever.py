"""混合检索器（多语言分区 + 重排序版）

检索链路：
1. 多语言预处理：语言识别 → 归一化 → 跨语言语义对齐 → 分区路由
2. 分区混合检索：向量(BGE-M3) + BM25，先查语言分区，不足回退 default
3. RRF 融合：Reciprocal Rank Fusion 合并两路结果
4. Cross-Encoder 重排序：bge-reranker 精排，消除向量检索的语义偏移
"""
import re
from typing import Optional
from loguru import logger

from app.config import settings
from app.rag.indexer import (
    embed_text, get_collection, get_memory_docs, get_partitions, is_milvus_available,
)
from app.rag.multilingual import preprocess_query, PARTITION_DEFAULT
from app.rag.reranker import rerank


# CoT 查询扩展：问题词与停用词
_COT_QUESTION_WORDS = [
    "怎么", "如何", "为什么", "为何", "怎样", "哪里", "请问", "麻烦",
    "能不能", "可以吗", "需要吗", "是不是",
    "could you", "how to", "how do", "how can", "what is", "what are",
    "why is", "why does", "where can", "can i", "i want to", "i need to",
]


def _cot_expand_query(query: str) -> list[str]:
    """CoT 查询扩展：生成检索变体以提升跨语言召回率

    策略（无 LLM 调用，纯规则）：
    1. 原始查询（始终保留）
    2. 去除问题词的精简版（提升 BM25 关键词匹配率）
    3. 实体提取版（中文 2-6 字连续片段 + 英文 3+ 字母词）

    Returns:
        去重后的查询列表（至少含原始查询）
    """
    variants = [query]

    # 变体1：去除问题词
    cleaned = query
    for qw in _COT_QUESTION_WORDS:
        cleaned = cleaned.replace(qw, "")
    cleaned = cleaned.strip(" ?？!！,，。.")
    if cleaned and cleaned != query and len(cleaned) >= 2:
        variants.append(cleaned)

    # 变体2：提取中文实体（2-6字连续中文）
    zh_entities = re.findall(r"[\u4e00-\u9fa5]{2,6}", query)
    if zh_entities:
        entity_query = " ".join(zh_entities[:3])
        if entity_query and entity_query != query:
            variants.append(entity_query)

    # 变体3：提取英文关键词（3+字母）
    en_keywords = re.findall(r"[a-zA-Z]{3,}", query)
    if en_keywords:
        en_query = " ".join(en_keywords[:3])
        if en_query and en_query not in variants:
            variants.append(en_query)

    # 去重保序
    seen = set()
    unique = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def _dedup_results(results: list[dict]) -> list[dict]:
    """按 doc_id 去重，保留分数更高的""" 
    best = {}
    for r in results:
        doc_id = r.get("id", "")
        if not doc_id:
            continue
        if doc_id not in best or r.get("score", 0) > best[doc_id].get("score", 0):
            best[doc_id] = r
    return list(best.values())


def retrieve(query: str, intent: str = "", top_k: int = 3, lang: str = "") -> list[dict]:
    """多语言混合检索 + 重排序

    Args:
        query: 查询文本（任意语言）
        intent: 意图标签（用于过滤加权）
        top_k: 返回数量
        lang: 前端业务语言码（优先于脚本识别）

    Returns:
        [{"id","content","category","score","rerank_score","source","partition"}]
    """
    if not query:
        return []

    # 1. 多语言预处理：语言识别 → 归一化 → 跨语言对齐 → 分区路由
    pre = preprocess_query(query, lang=lang)
    aligned = pre["aligned"] or query
    partition = pre["partition"]

    # 1.5 CoT 查询扩展：生成检索变体以提升召回率
    query_variants = _cot_expand_query(aligned)

    # 2. 分区混合检索：对每个变体检索向量路，BM25 用原始查询
    use_partition = settings.rag_use_partition and partition != PARTITION_DEFAULT
    vec_results = []
    for v in query_variants:
        vec_results.extend(_vector_search(v, partition=partition if use_partition else None, top_k=top_k * 2))
    vec_results = _dedup_results(vec_results)
    bm25_results = _bm25_search(aligned, intent=intent, partition=partition if use_partition else None, top_k=top_k * 3)

    # 分区结果不足时回退 default 全库
    if use_partition and (len(vec_results) + len(bm25_results)) < top_k:
        logger.debug(f"分区 {partition} 结果不足，回退全库检索")
        vec_results += _vector_search(aligned, partition=None, top_k=top_k * 2)
        bm25_results += _bm25_search(aligned, intent=intent, partition=None, top_k=top_k * 2)

    # 3. RRF 融合
    fused = _rrf_fusion(vec_results, bm25_results)

    # 4. Cross-Encoder 重排序（消除向量检索语义偏移）
    if fused:
        fused = rerank(aligned, fused, top_k=top_k)

    # 标注检索元信息
    for d in fused:
        d.setdefault("partition", partition)
        d.setdefault("query_lang", pre["lang"])
        d.setdefault("aligned_translated", pre["translated"])

    logger.info(
        f"[retrieve] lang={pre['lang']} partition={partition} cot_variants={len(query_variants)} "
        f"vec={len(vec_results)} bm25={len(bm25_results)} fused={len(fused)} "
        f"top1_score={fused[0].get('rerank_score', fused[0].get('score', 0)):.4f}"
        if fused else f"[retrieve] lang={pre['lang']} cot_variants={len(query_variants)} no results"
    )
    return fused[:top_k]


def _vector_search(query: str, partition: Optional[str] = None, top_k: int = 6) -> list[dict]:
    """向量检索（BGE-M3 跨语言语义检索）"""
    if is_milvus_available():
        try:
            collection = get_collection()
            if collection is None:
                return _memory_vector_search(query, partition, top_k)
            vec = embed_text(query)
            search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
            # 分区检索：指定 partition_names
            partition_names = None
            if partition and partition != PARTITION_DEFAULT:
                partition_names = [partition]
            results = collection.search(
                data=[vec], anns_field="embedding",
                limit=top_k,
                partition_names=partition_names,
                output_fields=["id", "content", "category", "lang"],
                param=search_params,
            )
            out = []
            for hit in results[0]:
                entity = hit.entity
                out.append({
                    "id": entity.get("id", ""),
                    "content": entity.get("content", ""),
                    "category": entity.get("category", ""),
                    "lang": entity.get("lang", ""),
                    "score": float(hit.score),
                    "source": "vector",
                })
            return out
        except Exception as e:
            logger.debug(f"Milvus 向量检索失败，回退内存: {e}")

    return _memory_vector_search(query, partition, top_k)


def _memory_vector_search(query: str, partition: Optional[str], top_k: int) -> list[dict]:
    """内存向量检索（基于关键词相似度的简化实现，按分区过滤）"""
    docs = get_memory_docs(partition) if partition else get_memory_docs()
    if not docs and partition:
        # 分区为空回退全库
        docs = get_memory_docs()
    if not docs:
        return []
    query_words = set(_tokenize(query.lower()))
    scored = []
    for doc in docs:
        kw = set(k.lower() for k in doc.get("keywords", []))
        content_words = set(_tokenize(doc.get("content", "").lower()))
        all_words = kw | content_words
        overlap = len(query_words & all_words)
        score = overlap / max(len(query_words), 1) if query_words else 0
        scored.append({
            "id": doc.get("id", ""),
            "content": doc.get("content", ""),
            "category": doc.get("category", ""),
            "lang": doc.get("lang", ""),
            "score": float(score),
            "source": "memory_vector",
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def _bm25_search(query: str, intent: str = "", partition: Optional[str] = None, top_k: int = 6) -> list[dict]:
    """BM25 关键词检索（按分区过滤）"""
    docs = get_memory_docs(partition) if partition else get_memory_docs()
    if not docs and partition:
        docs = get_memory_docs()
    if not docs:
        return []

    try:
        from rank_bm25 import BM25Okapi
        corpus = [_tokenize(d.get("content", "") + " " + " ".join(d.get("keywords", []))) for d in docs]
        bm25 = BM25Okapi(corpus)
        tokenized_query = _tokenize(query)
        scores = bm25.get_scores(tokenized_query)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        out = []
        for idx, score in ranked[:top_k]:
            doc = docs[idx]
            # 意图过滤加权
            weight = 1.5 if (intent and doc.get("category", "") == intent) else 1.0
            out.append({
                "id": doc.get("id", ""),
                "content": doc.get("content", ""),
                "category": doc.get("category", ""),
                "lang": doc.get("lang", ""),
                "score": float(score * weight),
                "source": "bm25",
            })
        return out
    except Exception as e:
        logger.debug(f"BM25 检索失败: {e}")
        return []


def _rrf_fusion(vec_results: list[dict], bm25_results: list[dict], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion 融合两路检索结果

    Args:
        k: RRF 平滑常数
    """
    scores: dict[str, float] = {}
    docs: dict[str, dict] = {}

    for rank, r in enumerate(vec_results):
        doc_id = r["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
        docs[doc_id] = r

    for rank, r in enumerate(bm25_results):
        doc_id = r["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
        if doc_id not in docs:
            docs[doc_id] = r

    fused = []
    for doc_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        item = docs[doc_id].copy()
        item["score"] = score
        fused.append(item)
    return fused


def _tokenize(text: str) -> list[str]:
    """简易分词（中英文混合）"""
    if not text:
        return []
    en_tokens = re.findall(r'[a-zA-Z]+', text.lower())
    zh_tokens = re.findall(r'[\u4e00-\u9fa5]', text)
    return en_tokens + zh_tokens