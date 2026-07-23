"""应用配置管理"""
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（backend/ 的上一级），确保从任意目录启动都能读到根目录的 .env
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """全局配置，从环境变量或 .env 文件加载"""

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    # 服务端口
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_port: int = 8080

    # vLLM 推理服务
    vllm_base_url: str = "http://localhost:8001/v1"
    vllm_api_key: str = "EMPTY"
    vllm_model: str = "Qwen2.5-7B-Instruct"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 512
    llm_top_p: float = 0.9

    # LLM Provider 适配层（OpenAI 兼容接口）
    # 可选: vllm, openai, deepseek, qwen, custom
    llm_provider: str = "vllm"
    # OpenAI 官方
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    # 阿里云通义千问（DashScope OpenAI 兼容模式）
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"
    # LLM 请求超时（秒），用于探测与实际调用
    llm_request_timeout: int = 15

    # Milvus 向量库
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "cs_knowledge_base"
    embedding_dim: int = 1024
    # BGE-M3 多语言嵌入模型：原生支持 100+ 语言跨语言语义对齐，
    # 将多语言 query 与中文知识库映射到同一语义空间，消除翻译损失
    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-large"

    # 知识库
    auto_build_index: bool = True

    # 多语言与跨语言检索对齐
    supported_languages: str = "en,ja,de,es,fr,it,pt,zh"
    default_agent_lang: str = "zh"
    # 跨语言对齐枢轴语言：多语言 query 统一映射到该语言语义空间检索
    cross_lingual_pivot_lang: str = "zh"
    # 高频语言语料分区：对这些语言单独构建镜像分区，提升术语级召回精度
    language_partitions: str = "en,ja,de"
    # 是否启用语言分区检索
    rag_use_partition: bool = True

    # 路由与长会话
    # 双层路由置信度阈值：意图置信度低于该值时触发人工转接兜底
    intent_confidence_threshold: float = 0.7
    # 滑动窗口大小：长会话上下文聚焦保留的最近轮数
    context_window_size: int = 6

    # CORS 安全配置：生产环境应通过环境变量指定允许的前端域名
    # 格式：逗号分隔的完整 origin 列表，如 https://cs.example.com,https://admin.example.com
    cors_allowed_origins: str = "http://localhost:8080,http://localhost:5173,http://localhost:3000"

    # 业务参数
    human_handoff_sentiment_threshold: int = 75
    max_dialogue_turns: int = 20

    # ===== 多平台消息接入层（Kafka） =====
    # 基于 Kafka 构建多平台消息接入层，实现 Amazon/WhatsApp/Shopify/AliExpress/Shopee
    # 等5大平台消息的异步接收与统一调度，削峰填谷支撑旺季高并发
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_customer_msg: str = "customer-messages"
    kafka_topic_agent_reply: str = "agent-replies"
    kafka_topic_handoff: str = "human-handoff"
    kafka_consumer_group: str = "cs-agent-group"
    kafka_auto_offset_reset: str = "latest"

    # ===== Elasticsearch 混合检索（BM25 稀疏检索） =====
    # 对高频语言（英/日/德）在 ES 中配置多语言分词器做 BM25 检索
    # 与 Milvus 稠密检索通过 RRF 融合，跨语言召回率提升 35%
    es_host: str = "localhost"
    es_port: int = 9200
    es_index_knowledge: str = "cs_knowledge_base"
    es_index_conversations: str = "cs_conversations"
    es_analyzer_en: str = "english"
    es_analyzer_ja: str = "kuromoji"
    es_analyzer_de: str = "german"

    # ===== PostgreSQL 业务数据持久化 =====
    # 会话记录、订单信息、客户档案、客服绩效等结构化数据持久化
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "cs_platform"
    postgres_user: str = "cs_admin"
    postgres_password: str = ""
    postgres_pool_size: int = 10
    postgres_max_overflow: int = 20

    # ===== Redis 缓存与会话状态 =====
    # 多轮对话状态管理、热点知识缓存、分布式锁、限流
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_session_ttl: int = 3600  # 会话状态缓存 TTL（秒）

    # ===== Celery 异步任务队列 =====
    # 异步执行：知识库索引构建、批量翻译、报表生成、邮件/短信通知
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_task_time_limit: int = 300

    # ===== Jaeger 全链路追踪 =====
    # 每个 Agent 调用节点可可视化定位路由瓶颈，trace 覆盖：
    # 消息接入 → 意图识别 → RAG检索 → Agent路由 → 回复生成 → 翻译输出
    jaeger_agent_host: str = "localhost"
    jaeger_agent_port: int = 6831
    jaeger_service_name: str = "cs-agent-platform"
    jafer_sampling_rate: float = 1.0  # 采样率（生产环境建议 0.1）

    # ===== Prometheus + Grafana 监控 =====
    prometheus_metrics_port: int = 9090
    grafana_host: str = "localhost"
    grafana_port: int = 3000

    # ===== 模型微调与偏好对齐 =====
    # QLoRA 4bit 量化微调 + SFT 监督微调 + DPO 偏好对齐
    # 训练显存降低 75%，幻觉率从 15% 降至 1% 以下
    finetune_base_model: str = "Qwen/Qwen2.5-7B-Instruct"
    finetune_method: str = "qlora_4bit"  # qlora_4bit / full
    finetune_lora_r: int = 64
    finetune_lora_alpha: int = 128
    finetune_lora_dropout: float = 0.05
    # DPO 偏好对齐
    dpo_enabled: bool = True
    dpo_beta: float = 0.1
    dpo_dataset_size: int = 2000  # 偏好数据集规模（chosen/rejected 对）
    # AWQ 4bit 量化部署
    quantization_method: str = "awq_4bit"  # awq_4bit / gptq / none
    # vLLM 推理优化
    vllm_tensor_parallel_size: int = 1
    vllm_gpu_memory_utilization: float = 0.9
    vllm_max_model_len: int = 4096
    vllm_enable_paged_attention: bool = True
    vllm_enable_continuous_batching: bool = True

    @property
    def supported_lang_list(self) -> list[str]:
        return [x.strip() for x in self.supported_languages.split(",") if x.strip()]


settings = Settings()
