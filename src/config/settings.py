"""全局配置与常量 - Python3.11 """

import os
from pathlib import Path
from typing import Dict, Any, Optional

# Python3.11+ 兼容：typing 模块中已有 Literal
try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置 - Python3.11+ 优化"""

    # LLM
    llm_provider: Literal["openai", "anthropic"] = "openai"
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    
    # 多模型配置
    llm_models: Dict[str, str] = {
        "default": "gpt-4o-mini",            # 常规任务（主模型）
        "complex": "gpt-4o",                  # 复杂任务（兜底）
        "local": "qwen2.5-7b",                # 本地部署
        "small_language": "qwen2.5-7b-instruct",  # 小语种兜底
        "domestic": "qwen-plus"              # 国内大模型（替代方案：qwen）
    }
    
    # 国内大模型配置
    qwen_api_key: str = Field(default="", env="QWEN_API_KEY")
    
    # 模型切换策略
    use_domestic_model: bool = Field(default=False, env="USE_DOMESTIC_MODEL")
    
    embedding_model: str = "text-embedding-3-small"

    # 模型选择策略配置
    model_selection_thresholds: Dict[str, float] = {
        "complexity_high": 0.7,  # 复杂度阈值
        "language_rare": 0.5,    # 小语种阈值
    }

    # RAG - 支持多种向量数据库
    chroma_persist_dir: str = Field(
        default="./data/chroma_db", env="CHROMA_PERSIST_DIR"
    )
    pinecone_api_key: str = Field(default="", env="PINECONE_API_KEY")
    pinecone_index: str = Field(default="", env="PINECONE_INDEX")
    milvus_host: str = Field(default="localhost", env="MILVUS_HOST")
    milvus_port: int = Field(default=19530, env="MILVUS_PORT")
    milvus_collection: str = Field(default="b2c_knowledge", env="MILVUS_COLLECTION")
    faiss_index_dir: str = Field(default="./data/faiss_index", env="FAISS_INDEX_DIR")
    vector_db_provider: Literal["chromadb", "pinecone", "milvus", "faiss"] = "chromadb"
    rag_top_k: int = 5
    rag_rerank_top_n: int = 3

    # 状态存储
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # 支持语言 (12 国 8 种)
    supported_languages: tuple[str, ...] = (
        "zh", "en", "es", "de", "fr", "ja", "th", "vi"
    )
    default_language: str = "zh"  # 默认为中文
    
    # 语言复杂度映射
    language_complexity: Dict[str, float] = {
        "zh": 1.0,  # 核心语言
        "en": 1.0,  # 核心语言
        "ja": 1.0,  # 核心语言
        "es": 0.8,  # 次要语言
        "de": 0.8,  # 次要语言
        "fr": 0.8,  # 次要语言
        "th": 0.6,  # 小语种
        "vi": 0.6,  # 小语种
    }

    # 电商平台支持
    supported_platforms: tuple[str, ...] = (
        "website", "amazon", "shopify", "ebay"
    )
    default_platform: str = "amazon"
    
    # 平台特定配置
    platform_configs: Dict[str, Dict[str, Any]] = {
        "amazon": {
            "name": "Amazon",
            "currency": "USD",
            "shipping_policy": "Amazon Prime 2-day shipping",
            "return_policy": "30-day return policy"
        },
        "shopify": {
            "name": "Shopify",
            "currency": "USD",
            "shipping_policy": "3-5 business days",
            "return_policy": "14-day return policy"
        },
        "ebay": {
            "name": "eBay",
            "currency": "USD",
            "shipping_policy": "Varies by seller",
            "return_policy": "Varies by seller"
        },
        "website": {
            "name": "Official Website",
            "currency": "CNY",
            "shipping_policy": "7-14 business days",
            "return_policy": "7-day return policy"
        }
    }

    # 第三方应用集成配置
    integration_configs: Dict[str, Dict[str, Any]] = {
        "feishu": {
            "enabled": False,
            "app_id": "",
            "app_secret": ""
        },
        "dingtalk": {
            "enabled": False,
            "app_key": "",
            "app_secret": ""
        },
        "wecom": {
            "enabled": False,
            "corpid": "",
            "corpsecret": ""
        },
        "whatsapp": {
            "enabled": False,
            "phone_number_id": "",
            "access_token": ""
        },
        "erp": {
            "enabled": False,
            "api_url": "",
            "api_key": ""
        }
    }

    # 项目路径
    project_root: Path = Path(__file__).resolve().parent.parent.parent
    data_dir: Path = project_root / "data"
    docs_dir: Path = project_root / "data" / "knowledge_base"
    local_model_dir: Path = project_root / "models" / "local_model"

    # 性能优化配置 - 确保响应时效 < 2秒
    enable_cache: bool = True
    cache_ttl: int = 3600  # 缓存过期时间（秒）
    max_concurrent_requests: int = 100  # 最大并发请求数
    request_timeout: int = 10  # 请求超时（秒）
    enable_streaming: bool = True  # 是否启用流式响应（可选）

    # 架构优化配置
    architecture_configs: Dict[str, Any] = {
        "microservices_enabled": False,  # 微服务化开关
        "containerization": "docker",  # 容器化方案：docker/k8s
        "distributed_processing": False,  # 分布式处理
        "auto_scaling": False,  # 弹性伸缩
        "health_check_enabled": True,  # 健康检查
        "metrics_enabled": True  # 监控指标
    }

    # 异常处理配置
    fallback_enabled: bool = True
    fallback_response: str = "抱歉，系统出现技术问题，请稍后重试或联系我们的客服团队。"

    @field_validator("vector_db_provider", mode="before")
    @classmethod
    def normalize_vector_db_provider(cls, v):
        """兼容 .env 中带注释或大小写不一致的值。"""
        if isinstance(v, str):
            value = v.split("#", 1)[0].strip().lower()
            alias_map = {
                "chroma": "chromadb",
                "chroma_db": "chromadb",
                "pine": "pinecone",
            }
            value = alias_map.get(value, value)
            return value
        return v

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
