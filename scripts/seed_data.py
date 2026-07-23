"""灌入知识库数据

将内置的多语言 FAQ 知识库灌入 Milvus 向量库。
首次部署后运行，或知识库更新后重新运行。
"""
import sys
import os

# 添加 backend 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.config import settings


def seed():
    """灌入知识库数据"""
    from app.rag.indexer import build_index, is_milvus_available
    import json

    # 加载知识库
    kb_path = os.path.join(os.path.dirname(__file__), "..", "backend", "app", "data", "faq", "multilang_faq.json")
    kb_path = os.path.abspath(kb_path)

    if not os.path.exists(kb_path):
        print(f"错误：知识库文件不存在: {kb_path}")
        return

    with open(kb_path, "r", encoding="utf-8") as f:
        docs = json.load(f)
    print(f"加载知识库 {len(docs)} 条")

    # 构建索引（会自动选择 Milvus 或内存模式）
    build_index(force=True)
    print(f"索引构建完成，Milvus 模式: {is_milvus_available()}")

    # 验证检索
    from app.rag.retriever import retrieve
    test_queries = [
        ("物流查询", "我的订单什么时候到"),
        ("售后退款", "商品损坏要退款"),
        ("商品咨询", "耳机续航多久"),
        ("合规政策", "支付安全吗"),
    ]
    print("\n检索验证：")
    for intent, query in test_queries:
        results = retrieve(query, intent=intent, top_k=2)
        print(f"\n  查询: {query}")
        for r in results:
            print(f"    - [{r.get('category','')}] {r.get('content','')[:60]}... (score={r.get('score',0):.4f})")

    print("\n" + "=" * 50)
    print("知识库数据灌入完成")
    print("=" * 50)


if __name__ == "__main__":
    seed()
