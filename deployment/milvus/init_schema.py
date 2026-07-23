"""Milvus 集合初始化脚本

创建知识库所需的 Collection 与索引。
首次部署时运行，或在知识库结构变更后运行。
"""
import sys
import os

# 添加 backend 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from app.config import settings


def init_milvus():
    """初始化 Milvus 集合"""
    from pymilvus import connections, utility, Collection, FieldSchema, CollectionSchema, DataType

    # 连接
    connections.connect(host=settings.milvus_host, port=str(settings.milvus_port))
    print(f"已连接 Milvus: {settings.milvus_host}:{settings.milvus_port}")

    # 删除旧集合（如存在）
    if utility.has_collection(settings.milvus_collection):
        print(f"删除旧集合: {settings.milvus_collection}")
        utility.drop_collection(settings.milvus_collection)

    # 定义字段
    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=settings.embedding_dim),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="keywords", dtype=DataType.VARCHAR, max_length=512),
    ]
    schema = CollectionSchema(fields, description="多语言客服知识库")
    collection = Collection(settings.milvus_collection, schema)
    print(f"创建集合: {settings.milvus_collection}")

    # 创建向量索引
    collection.create_index("embedding", {
        "index_type": "IVF_FLAT",
        "metric_type": "IP",
        "params": {"nlist": 128},
    })
    print("创建向量索引: IVF_FLAT / IP")

    # 加载集合
    collection.load()
    print("集合已加载")

    print("=" * 50)
    print("Milvus 初始化完成")
    print(f"集合名: {settings.milvus_collection}")
    print(f"向量维度: {settings.embedding_dim}")
    print("后续可运行 seed_data.py 灌入知识库数据")
    print("=" * 50)


if __name__ == "__main__":
    init_milvus()
