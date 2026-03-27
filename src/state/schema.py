"""多轮对话状态 Schema - 结构化状态替代全量上下文，解决长会话信息丢失、意图偏移、窗口超限"""

from typing import Annotated, Literal, TypedDict
from langgraph.graph.message import add_messages

# 单轮对话摘要
class TurnSummary(TypedDict):
    """单轮对话摘要 - 用于压缩长会话"""
    role: Literal["user", "assistant"]
    intent: str | None
    key_entities: dict[str, str]  # order_id, product_sku, etc.
    summary: str
    timestamp: str

# 会话状态
class ConversationState(TypedDict, total=False):
    """
    会话状态 - 结构化存储，避免全量消息传入 LLM
    - messages: 仅保留最近 N 轮原始消息（如 10 轮）
    - summaries: 更早轮次的摘要列表
    - current_intent: 当前识别意图
    - current_agent: 当前负责 Agent
    - user_context: 用户画像（订单数、偏好语言、历史问题类型等）
    - session_metadata: 会话元数据（平台、语言、来源等）
    """
    messages: Annotated[list, add_messages]
    turn_summaries: list[TurnSummary]
    current_intent: str | None
    current_agent: str | None
    user_context: dict
    session_metadata: dict
    tool_calls_pending: list[dict]
    escalation_reason: str | None  # 转人工原因
