"""
高可用 RAG 检索系统
- 产品手册、物流规则、平台政策、售后流程等 10w+ 非结构化数据
- 清洗 -> 语义分块 -> 嵌入 -> 索引
- 混合检索（向量 + BM25）+ 重排序
"""

from pathlib import Path
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from rank_bm25 import BM25Okapi
import structlog

from src.config import settings

logger = structlog.get_logger()


_rag_instance = None


def get_rag_retriever() -> 'RAGRetriever':
    """获取RAGRetriever实例（使用模块级单例缓存）"""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGRetriever()
    return _rag_instance


class RAGRetriever:
    """混合检索 + 重排序 RAG"""

    def __init__(
        self,
        persist_dir: str | Path | None = None,
        embedding_model: str | None = None,
        top_k: int = 5,
        rerank_top_n: int = 3,
    ):
        self.persist_dir = Path(persist_dir or settings.chroma_persist_dir)
        self.embedding_model = embedding_model or settings.embedding_model
        self.top_k = top_k
        self.rerank_top_n = rerank_top_n

        self.embeddings = OpenAIEmbeddings(
            model=self.embedding_model,
            api_key=settings.openai_api_key,
        )
        self._vectorstore: Chroma | None = None
        self._bm25: BM25Okapi | None = None
        self._bm25_corpus: list[str] = []

    @property
    def vectorstore(self) -> Chroma:
        if self._vectorstore is None:
            self._vectorstore = Chroma(
                persist_directory=str(self.persist_dir),
                embedding_function=self.embeddings,
                collection_name="b2c_knowledge",
            )
        return self._vectorstore

    def add_documents(
        self,
        documents: list[dict[str, Any]],
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> None:
        """清洗后的文档 -> 语义分块 -> 嵌入 -> 写入向量库"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", ".", " "],
        )
        texts = []
        metadatas = []
        for doc in documents:
            content = doc.get("content", doc.get("text", ""))
            meta = {k: v for k, v in doc.items() if k not in ("content", "text")}
            for chunk in splitter.split_text(content):
                texts.append(chunk)
                metadatas.append(meta)

        self.vectorstore.add_texts(texts, metadatas)
        self._bm25_corpus = texts
        self._bm25 = BM25Okapi([t.split() for t in texts])
        logger.info("rag_documents_added", count=len(texts))

    def hybrid_search(
        self,
        query: str,
        filter_meta: dict | None = None,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """混合检索 + 重排序"""
        k = top_k or self.top_k
        vector_docs: list[dict[str, Any]] = []

        # 1. 向量检索（空库时跳过）
        try:
            vs_results = self.vectorstore.similarity_search_with_score(
                query, k=k * 2, filter=filter_meta
            )
            vector_docs = [
                {"content": d.page_content, "metadata": d.metadata, "score": 1 - s / 2}
                for d, s in vs_results
            ]
        except Exception as e:
            logger.warning("rag_vector_search_failed", error=str(e))

        # 2. BM25 检索（若有语料）
        bm25_docs: list[dict] = []
        if self._bm25 and self._bm25_corpus:
            tokenized = query.split()
            bm25_scores = self._bm25.get_scores(tokenized)
            top_idx = bm25_scores.argsort()[-k:][::-1]
            for i in top_idx:
                if bm25_scores[i] > 0:
                    bm25_docs.append({
                        "content": self._bm25_corpus[i],
                        "metadata": {},
                        "score": float(bm25_scores[i]) / (bm25_scores.max() or 1),
                    })

        # 3. 简单融合：向量为主，BM25 补充
        seen = set()
        combined = []
        for d in vector_docs:
            key = d["content"][:100]
            if key not in seen:
                seen.add(key)
                combined.append(d)
        for d in bm25_docs:
            key = d["content"][:100]
            if key not in seen:
                seen.add(key)
                combined.append(d)

        # 4. 按分数重排，取 top_n
        if not combined:
            return []
        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined[: self.rerank_top_n]
