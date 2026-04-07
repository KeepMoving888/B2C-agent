"""
知识库初始化脚本 - 将文档导入向量数据库
Python3.11 环境兼容

使用方法：
1. 准备知识库文件（.txt, .md, .pdf等格式）
2. 把文件放到 data/knowledge_base/ 目录下
3. 运行本脚本：python init_knowledge_base.py

注意：您需要配置有效的嵌入模型API密钥才能使用此功能！
"""

import os
from pathlib import Path
import structlog
from typing import List, Dict, Any

from src.config import settings
from src.rag.retriever import RAGRetriever

logger = structlog.get_logger()

# 从目录加载所有文档
def load_documents_from_directory(directory: str) -> List[Dict[str, Any]]:
    """从目录加载所有文档"""
    documents = []
    dir_path = Path(directory)
    
    if not dir_path.exists():
        logger.warning("knowledge_base_dir_not_found", path=str(dir_path))
        return documents
    
    # 支持的文件格式
    supported_extensions = ['.txt', '.md', '.pdf', '.docx', '.html']
    
    for file_path in dir_path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            try:
                content = ""
                if file_path.suffix.lower() == '.txt' or file_path.suffix.lower() == '.md':
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                elif file_path.suffix.lower() == '.pdf':
                    logger.warning("pdf_support_limited", file=str(file_path))
                    logger.info("For PDF files, consider converting to text first")
                    continue
                else:
                    logger.warning("unsupported_file_format", file=str(file_path))
                    continue
                
                if content.strip():
                    documents.append({
                        "content": content,
                        "source": str(file_path),
                        "filename": file_path.name
                    })
                    logger.info("document_loaded", file=str(file_path), length=len(content))
                    
            except Exception as e:
                logger.error("failed_to_load_file", file=str(file_path), error=str(e))
    
    return documents

# 主函数
def main():
    """主函数：初始化知识库"""
    logger.info("=" * 60)
    logger.info("知识库初始化脚本")
    logger.info("=" * 60)
    
    # 检查目录是否存在
    knowledge_base_dir = settings.docs_dir
    if not knowledge_base_dir.exists():
        logger.info("creating_knowledge_base_dir", path=str(knowledge_base_dir))
        knowledge_base_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建示例文件
        sample_file = knowledge_base_dir / "amazon_guide.txt"
        sample_content = """亚马逊CarPlay配件销售指南

产品信息：
- 我们的CarPlay配件兼容所有2016年后的车型
- 支持无线和有线连接
- 提供1年亚马逊保修服务

亚马逊退换货政策：
- 30天无理由退换货
- 商品需保持原包装
- 亚马逊承担退货运费（质量问题）

物流配送：
- Prime会员享受2日达
- 标准配送3-5个工作日
- 国际配送7-14个工作日

亚马逊A-to-Z保障：
- 覆盖所有亚马逊订单
- 如商品不符描述可申请退款
- 最长90天保障期"""
        
        with open(sample_file, 'w', encoding='utf-8') as f:
            f.write(sample_content)
        logger.info("sample_file_created", file=str(sample_file))
    
    # 加载文档
    logger.info("loading_documents", path=str(knowledge_base_dir))
    documents = load_documents_from_directory(str(knowledge_base_dir))
    
    if not documents:
        logger.warning("no_documents_found")
        logger.info("请将您的知识库文件放到 data/knowledge_base/ 目录下")
        logger.info("支持的格式：.txt, .md")
        return
    
    logger.info("documents_loaded", count=len(documents))
    
    # 初始化RAG检索器并添加文档
    logger.info("initializing_rag_retriever")
    try:
        retriever = RAGRetriever()
        retriever.add_documents(documents)
        logger.info("=" * 60)
        logger.info("知识库初始化完成！")
        logger.info(f"共导入 {len(documents)} 个文档")
        logger.info("向量数据库已保存到: " + str(settings.chroma_persist_dir))
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error("failed_to_initialize_rag", error=str(e))
        logger.info("")
        logger.info("注意：您需要配置有效的嵌入模型API密钥！")
        logger.info("目前RAG检索需要OpenAI的embedding模型（text-embedding-3-small）")
        logger.info("或者您可以：")
        logger.info("1. 配置 OPENAI_API_KEY 环境变量")
        logger.info("2. 或者暂时不使用RAG功能（系统仍可正常运行）")


if __name__ == "__main__":
    main()
