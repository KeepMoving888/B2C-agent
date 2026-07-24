"""Pydantic 数据模型"""
from typing import Optional, Any
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """对话消息"""
    role: str = Field(..., description="user / assistant")
    content: str


class ChatRequest(BaseModel):
    """多智能体会话请求"""
    platform: str = Field("amazon", description="平台标识")
    lang: str = Field("en", description="客户语言码")
    message: str = Field(..., description="客服输入消息（中文）")
    conv_id: Optional[str] = Field(None, description="会话ID")
    history: list[ChatMessage] = Field(default_factory=list, description="历史消息")


class ChatResponse(BaseModel):
    """多智能体会话响应"""
    reply: str = Field(..., description="目标语言回复")
    reply_zh: str = Field(..., description="中文回译")
    agent: str = Field(..., description="处理该消息的智能体")
    route: str = Field("", description="条件路由说明")
    intent: str = Field("", description="意图识别结果")
    sentiment: dict = Field(default_factory=dict, description="情感分析")
    sources: list[dict] = Field(default_factory=list, description="RAG 检索来源")
    agent_chain: list[str] = Field(default_factory=list, description="处理链路（协作路径）")
    trace: list[dict] = Field(default_factory=list, description="状态流转 trace（可视化用）")
    handoff_reason: str = Field("", description="转交原因（capability_exceeded / sentiment_escalation / complaint / ...）")
    capability_check: dict = Field(default_factory=dict, description="能力边界检测结果")
    anti_hallucination_report: dict = Field(default_factory=dict, description="反幻觉校验报告（置信度/一致性/风险等级）")


class SuggestRequest(BaseModel):
    """AI建议回复请求"""
    platform: str = "amazon"
    lang: str = "en"
    conv_id: Optional[str] = None
    history: list[ChatMessage] = Field(default_factory=list)


class SuggestResponse(BaseModel):
    """AI建议回复响应"""
    text: str


class TranslateRequest(BaseModel):
    """翻译请求"""
    text: str
    from_lang: str = "zh"
    to_lang: str = "en"


class TranslateResponse(BaseModel):
    """翻译响应"""
    text: str = Field(..., description="原文")
    translated: str = Field(..., description="译文")


class StatsResponse(BaseModel):
    """统计数据响应（基于真实运行指标）"""
    conversations: int
    avg_response_sec: int
    satisfaction: int
    ai_ratio: int
    # 扩展指标（向后兼容，前端可选择消费）
    total_requests: int = 0
    avg_response_ms: float = 0
    intent_distribution: dict = Field(default_factory=dict)
    agent_distribution: dict = Field(default_factory=dict)
    lang_distribution: dict = Field(default_factory=dict)
    avg_rag_confidence: float = 0
    anti_hallucination_pass_rate: float = 100.0
    anti_hallucination_risk_distribution: dict = Field(default_factory=dict)
    handoff_rate: float = 0
    total_handoffs: int = 0
    handoff_reasons: dict = Field(default_factory=dict)
    negative_sentiment_count: int = 0
    uptime_sec: float = 0


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    mode: str = "rule"  # rule / vllm / openai / deepseek / qwen / custom
    version: str = "1.0.0"
