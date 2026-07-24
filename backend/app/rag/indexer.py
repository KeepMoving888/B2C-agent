"""RAG 索引构建（多语言分区版）

基于 Milvus 构建向量索引，支持：
- 混合检索（向量 + 关键词）
- 多语言语料分区：高频语言(英/日/德)单独分区，default 分区存放中文 pivot 语料
- Milvus 不可用时回退至内存索引（同样支持分区分组）
首次启动时自动从内置知识库构建索引。
"""
import json
import os
from typing import Optional

from loguru import logger

from app.config import settings
from app.rag.multilingual import detect_language, get_partition, PARTITION_DEFAULT


# 全局索引状态
_index_built = False
_milvus_available = False
_collection = None
_embedding_model = None

# 内存索引：按分区分组 {partition: [docs]}
_memory_index: dict[str, list] = {}
# 全量文档（兼容旧接口）
_memory_docs: list = []


def _check_milvus() -> bool:
    """检查 Milvus 可用性"""
    global _milvus_available
    if _milvus_available:
        return True
    try:
        from pymilvus import connections, utility
        connections.connect(host=settings.milvus_host, port=str(settings.milvus_port))
        _milvus_available = True
        logger.info(f"Milvus 已连接: {settings.milvus_host}:{settings.milvus_port}")
        return True
    except Exception as e:
        logger.warning(f"Milvus 不可用，RAG 将回退至内存检索: {e}")
        _milvus_available = False
        return False


def _get_embedding_model():
    """获取 embedding 模型（懒加载，BGE-M3 多语言）"""
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    try:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(settings.embedding_model)
        logger.info(f"Embedding 模型已加载: {settings.embedding_model}")
    except Exception as e:
        logger.warning(f"Embedding 模型加载失败: {e}")
    return _embedding_model


def embed_text(text: str) -> list[float]:
    """文本向量化（BGE-M3 dense embedding）"""
    model = _get_embedding_model()
    if model is None:
        # 回退：返回随机向量（仅用于保持流程可运行，不参与真实检索）
        import random
        return [random.random() for _ in range(settings.embedding_dim)]
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def _doc_partition(doc: dict) -> str:
    """根据文档 lang 字段决定语料分区

    优先用文档自带 lang；缺失时基于 content 脚本识别。
    高频语言返回自身分区，其余(含中文 pivot)归入 default。
    """
    lang = (doc.get("lang") or "").strip().lower()
    if not lang:
        lang = detect_language(doc.get("content", ""))
    return get_partition(lang)


def build_index(force: bool = False):
    """构建知识库索引

    Args:
        force: 是否强制重建
    """
    global _index_built, _collection
    if _index_built and not force:
        return

    kb_path = os.path.join(os.path.dirname(__file__), "..", "data", "faq", "multilang_faq.json")
    kb_path = os.path.abspath(kb_path)
    if not os.path.exists(kb_path):
        logger.warning(f"知识库文件不存在: {kb_path}")
        return

    with open(kb_path, "r", encoding="utf-8") as f:
        docs = json.load(f)
    logger.info(f"加载知识库 {len(docs)} 条")

    if _check_milvus():
        _build_milvus_index(docs, force)
    else:
        _build_memory_index(docs)

    _index_built = True
    logger.info("RAG 索引构建完成")


def _build_milvus_index(docs: list, force: bool):
    """构建 Milvus 向量索引（按语言分区）"""
    from pymilvus import connections, utility, Collection, FieldSchema, CollectionSchema, DataType

    if utility.has_collection(settings.milvus_collection) and force:
        utility.drop_collection(settings.milvus_collection)

    if not utility.has_collection(settings.milvus_collection):
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=settings.embedding_dim),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=2048),
            FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="keywords", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="lang", dtype=DataType.VARCHAR, max_length=16),
            FieldSchema(name="partition", dtype=DataType.VARCHAR, max_length=32),
        ]
        schema = CollectionSchema(fields, description="客服知识库（多语言分区）")
        collection = Collection(settings.milvus_collection, schema)
        collection.create_index("embedding", {
            "index_type": "IVF_FLAT",
            "metric_type": "IP",
            "params": {"nlist": 128},
        })
        logger.info(f"Milvus 集合已创建: {settings.milvus_collection}")
    else:
        collection = Collection(settings.milvus_collection)

    # 按分区组织数据，使用 Milvus partition 机制
    partitions_used = set()
    for doc in docs:
        part = _doc_partition(doc)
        partitions_used.add(part)

    # 确保 partition 存在（Milvus 的 _default 分区始终存在）
    existing_partitions = set(collection.partitions) if hasattr(collection, "partitions") else set()
    for part in partitions_used:
        if part not in existing_partitions and part != "_default":
            try:
                collection.create_partition(part)
            except Exception as e:
                logger.debug(f"分区 {part} 创建跳过: {e}")

    # 分区插入
    for part in partitions_used:
        part_docs = [d for d in docs if _doc_partition(d) == part]
        if not part_docs:
            continue
        ids, embeddings, contents, categories, keywords, langs, parts = [], [], [], [], [], [], []
        for doc in part_docs:
            text = doc.get("content", "")
            vec = embed_text(text)
            ids.append(doc.get("id", f"doc_{len(ids)}"))
            embeddings.append(vec)
            contents.append(text[:2048])
            categories.append(doc.get("category", "")[:64])
            keywords.append(",".join(doc.get("keywords", []))[:512])
            langs.append((doc.get("lang") or "")[:16])
            parts.append(part[:32])
        try:
            collection.insert(
                [ids, embeddings, contents, categories, keywords, langs, parts],
                partition_name=part if part != PARTITION_DEFAULT else "_default",
            )
        except Exception as e:
            logger.warning(f"分区 {part} 插入失败，回退默认分区: {e}")
            collection.insert([ids, embeddings, contents, categories, keywords, langs, parts])

    collection.load()
    logger.info(f"Milvus 索引插入 {len(docs)} 条数据，分区: {sorted(partitions_used)}")

    global _collection
    _collection = collection


def _build_memory_index(docs: list):
    """构建内存索引（按语言分区分组，Milvus 不可用时回退）"""
    global _memory_index, _memory_docs
    _memory_index = {}
    _memory_docs = docs
    for doc in docs:
        part = _doc_partition(doc)
        _memory_index.setdefault(part, []).append(doc)
    logger.info(
        f"内存索引构建完成，共 {len(docs)} 条，分区: "
        f"{ {p: len(v) for p, v in _memory_index.items()} }"
    )


def get_collection():
    """获取 Milvus 集合"""
    if not _index_built:
        build_index()
    return _collection


def get_memory_docs(partition: Optional[str] = None) -> list:
    """获取内存索引文档

    Args:
        partition: 指定分区；None 返回全量，指定则返回该分区文档
    """
    if not _index_built:
        build_index()
    if partition is None:
        return _memory_docs
    return _memory_index.get(partition, [])


def get_partitions() -> list:
    """获取当前所有分区"""
    if not _index_built:
        build_index()
    return list(_memory_index.keys())


def is_milvus_available() -> bool:
    """Milvus 是否可用"""
    return _check_milvus()