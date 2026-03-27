"""
知识库导入脚本 - 将产品手册、物流规则、平台政策等导入 RAG

用法:
  python -m scripts.ingest_knowledge --input-dir ./data/knowledge_base
"""

import argparse
from pathlib import Path
from src.rag import RAGRetriever
from src.config import settings

# 从目录加载文档
def load_docs_from_dir(dir_path: Path) -> list[dict]:
    """从目录加载文档（支持 txt, md）"""
    docs = []
    for ext in ("*.txt", "*.md"):
        for f in dir_path.rglob(ext):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                docs.append({
                    "content": content,
                    "source": str(f.relative_to(dir_path)),
                    "type": f.parent.name,
                })
            except Exception as e:
                print(f"Skip {f}: {e}")
    return docs

# 主函数
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default=None, help="知识库目录")
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--chunk-overlap", type=int, default=150)
    args = parser.parse_args()

    input_dir = Path(args.input_dir or settings.docs_dir)
    if not input_dir.exists():
        input_dir.mkdir(parents=True, exist_ok=True)
        # 写入示例文档
        (input_dir / "product_faq.txt").write_text(
            "CarPlay 适配器兼容性：支持 2016 年后大多数车型。"
            "支持有线 CarPlay 和无线 CarPlay 两种模式。\n"
            "保修政策：1 年质保，非人为损坏可免费换新。",
            encoding="utf-8",
        )
        print(f"Created sample doc at {input_dir}")

    docs = load_docs_from_dir(input_dir)
    if not docs:
        print("No documents found.")
        return

    retriever = RAGRetriever()
    retriever.add_documents(
        docs,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    print(f"Ingested {len(docs)} documents.")


if __name__ == "__main__":
    main()
