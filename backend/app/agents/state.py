"""对话状态定义（深度版）

LangGraph StateGraph 的状态对象，贯穿多智能体协作链路的全流程。

设计要点：
- 支持多智能体协作：Agent 处理后可"升级转交"至另一个 Agent
- 支持状态回滚：Agent 处理失败时回滚至上一状态，触发降级
- 支持错误恢复：记录重试次数，超限后强制转人工
- 支持 trace：记录完整状态流转路径，供可视化
"""
from typing import TypedDict, Optional, Annotated
from enum import Enum


class HandoffReason(str, Enum):
    """Agent 转交原因"""
    NONE = ""                              # 无转交
    INTENT_MISMATCH = "intent_mismatch"    # 意图与 Agent 能力不匹配
    CAPABILITY_EXCEEDED = "capability_exceeded"  # 超出 Agent 能力边界
    SENTIMENT_ESCALATION = "sentiment_escalation"  # 情绪升级
    COMPLAINT = "complaint"                # 投诉
    USER_REQUEST = "user_request"          # 用户主动要求
    ERROR_FALLBACK = "error_fallback"      # 错误降级
    RETRY_EXCEEDED = "retry_exceeded"      # 重试超限
    ANTI_HALLUCINATION = "anti_hallucination"  # 反幻觉校验未通过


class AgentStatus(str, Enum):
    """单个 Agent 的处理状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    HANDOFF = "handoff"       # 转交其他 Agent
    FAILED = "failed"          # 处理失败
    SKIPPED = "skipped"        # 跳过


class TraceStep(TypedDict, total=False):
    """状态流转记录的一步"""
    node: str                 # 节点名
    agent: str                # Agent 名
    action: str               # 动作描述
    status: str               # AgentStatus
    reason: str               # 转交/降级/失败原因
    retry: int                # 重试次数
    timestamp: float          # 时间戳
    detail: str               # 详情（debug 用）


class AgentState(TypedDict, total=False):
    """多智能体协作状态（深度版）

    分为五组：
    1. 输入：用户消息、历史、会话ID
    2. 分析：意图、情感、路由目标
    3. 协作控制：当前Agent、转交链、重试、回滚
    4. RAG：检索结果、引用溯源
    5. 输出：最终回复、trace
    """

    # ===== 1. 输入 =====
    platform: str
    lang: str
    message: str
    history: list[dict]
    conv_id: Optional[str]

    # ===== 2. 分析 =====
    intent: str
    intent_confidence: float         # 意图置信度 0-1
    sentiment: dict                  # {joy, neutral, negative}
    sentiment_trend: str             # "improving"/"stable"/"worsening"
    route_target: str                # 初始路由目标

    # ===== 3. 协作控制（核心） =====
    current_agent: str               # 当前正在处理的 Agent
    agent_chain: list[str]           # Agent 处理链（如 ["consultation","aftersales","human"]）
    handoff_reason: str              # 本次转交原因
    handoff_context: str             # 转交时传递给下一 Agent 的上下文摘要
    retry_count: int                 # 当前 Agent 重试次数
    max_retries: int                 # 最大重试次数（默认 2）
    rollback_snapshot: dict          # 回滚快照（保存上一成功状态）
    capability_check: dict           # 能力边界检测结果
    escalate_to_human: bool          # 是否强制升级人工

    # ===== 4. RAG =====
    rag_sources: list[dict]
    rag_quality: dict                # 检索质量 {recall, mrr, confidence}
    anti_hallucination_report: dict  # 反幻觉校验报告 {confidence, faithfulness, risk}
    citation: list[dict]             # 引用溯源 [{doc_id, content, used_in_reply}]

    # ===== 5. 各 Agent 输出 =====
    consultation_reply: str
    order_reply: str
    aftersales_reply: str
    compliance_reply: str
    human_handoff_reply: str

    # ===== 6. 最终输出 =====
    final_reply: str
    final_reply_zh: str
    agent_name: str
    route_desc: str
    trace: list[TraceStep]           # 完整状态流转记录
