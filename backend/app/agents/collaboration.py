"""多智能体协作控制核心

实现 Agent 间协作的三大机制：
1. 能力边界检测：Agent 处理前先判断是否在自己能力范围内
2. 转交机制：超界时携带上下文摘要转交给合适的 Agent
3. 错误恢复：处理失败时重试，超限后回滚并降级转人工

这是区别于"5个并列Agent"的关键——Agent 之间是真实协作关系。
"""
import time
from typing import Callable
from loguru import logger

from app.agents.state import AgentState, AgentStatus, HandoffReason, TraceStep
from app.config import settings


# ===== Agent 能力边界定义 =====

# 每个 Agent 能处理的意图集合（能力边界）
AGENT_CAPABILITIES: dict[str, set[str]] = {
    "consultation": {
        "商品咨询", "缺货询问", "技术支持",
    },
    "order": {
        "物流查询", "催发货", "地址修改",
    },
    "aftersales": {
        "售后退款", "退换货",
    },
    "compliance": {
        "支付问题",
    },
    "human_handoff": {
        "投诉处理",  # 人工是兜底，理论上能处理所有
    },
}

# Agent 升级转交目标（当 Agent 能力不足时转给谁）
# 体现"咨询→售后→人工"的升级链
ESCALATION_CHAIN: dict[str, str] = {
    "consultation": "order",       # 咨询发现是订单问题 → 转订单
    "order": "aftersales",         # 订单发现要退款 → 转售后
    "aftersales": "human_handoff", # 售后处理不了 → 转人工
    "compliance": "human_handoff", # 合规涉及法律 → 转人工
    "human_handoff": "human_handoff",  # 人工是终点
}

# Agent 中文名
AGENT_NAMES = {
    "consultation": "咨询Agent",
    "order": "订单Agent",
    "aftersales": "售后Agent",
    "compliance": "合规Agent",
    "human_handoff": "人工转接Agent",
}


# ===== Trace 记录 =====

def record_trace(state: AgentState, node: str, agent: str, action: str,
                 status: str, reason: str = "", detail: str = "") -> AgentState:
    """记录一条状态流转 trace

    Args:
        state: 当前状态
        node: 图节点名
        agent: Agent 名
        action: 动作描述
        status: AgentStatus
        reason: 转交/降级/失败原因
        detail: 调试详情

    Returns:
        更新后的状态
    """
    trace = state.get("trace", [])
    step: TraceStep = {
        "node": node,
        "agent": agent,
        "action": action,
        "status": status,
        "reason": reason,
        "retry": state.get("retry_count", 0),
        "timestamp": time.time(),
        "detail": detail,
    }
    trace.append(step)
    return {**state, "trace": trace}


# ===== 能力边界检测 =====

def check_capability(state: AgentState, agent: str) -> dict:
    """检测 Agent 是否有能力处理当前意图

    Returns:
        {
            "capable": bool,
            "reason": str,
            "suggested_handoff": str,  # 建议转交的 Agent
        }
    """
    intent = state.get("intent", "商品咨询")
    capabilities = AGENT_CAPABILITIES.get(agent, set())

    if intent in capabilities:
        return {"capable": True, "reason": "", "suggested_handoff": ""}

    # 不在能力范围内，找合适的转交目标
    for target, caps in AGENT_CAPABILITIES.items():
        if intent in caps and target != agent:
            return {
                "capable": False,
                "reason": HandoffReason.INTENT_MISMATCH.value,
                "suggested_handoff": target,
            }

    # 找不到匹配的，转人工
    return {
        "capable": False,
        "reason": HandoffReason.CAPABILITY_EXCEEDED.value,
        "suggested_handoff": "human_handoff",
    }


# ===== 情感升级判断 =====

def should_escalate_by_sentiment(state: AgentState) -> tuple[bool, str]:
    """根据情感判断是否需要升级转人工

    Returns:
        (是否升级, 原因)
    """
    sentiment = state.get("sentiment", {})
    negative = sentiment.get("negative", 0)
    threshold = settings.human_handoff_sentiment_threshold

    if negative >= threshold:
        return True, HandoffReason.SENTIMENT_ESCALATION.value
    return False, ""


# ===== 转交机制 =====

def create_handoff_context(state: AgentState, from_agent: str, to_agent: str,
                           reason: str) -> str:
    """生成转交上下文摘要（传递给下一 Agent）

    这是 Agent 协作的关键：下一 Agent 不是从零开始，而是带着上一 Agent 的上下文继续。
    """
    intent = state.get("intent", "")
    sentiment = state.get("sentiment", {})
    message = state.get("message", "")[:100]
    current_reply = (
        state.get("consultation_reply") or
        state.get("order_reply") or
        state.get("aftersales_reply") or
        state.get("compliance_reply") or
        ""
    )

    context = f"""【转交接班】{AGENT_NAMES.get(from_agent, from_agent)} → {AGENT_NAMES.get(to_agent, to_agent)}
转交原因：{reason}
客户意图：{intent}
客户情绪：不满 {sentiment.get('negative', 0)}%
客户消息摘要：{message}
前序 Agent 处理结果：{current_reply[:80] if current_reply else '无（能力边界检测阶段即转交）'}
请基于以上上下文继续处理。"""

    return context


# ===== 回滚机制 =====

def save_rollback_snapshot(state: AgentState) -> AgentState:
    """保存回滚快照（在 Agent 处理前调用）

    保存上一成功状态的关键字段，失败时可回滚。
    """
    snapshot = {
        "final_reply": state.get("final_reply", ""),
        "final_reply_zh": state.get("final_reply_zh", ""),
        "agent_name": state.get("agent_name", ""),
        "rag_sources": state.get("rag_sources", []),
        "consultation_reply": state.get("consultation_reply", ""),
        "order_reply": state.get("order_reply", ""),
        "aftersales_reply": state.get("aftersales_reply", ""),
        "compliance_reply": state.get("compliance_reply", ""),
    }
    return {**state, "rollback_snapshot": snapshot}


def rollback(state: AgentState) -> AgentState:
    """回滚至上一成功状态"""
    snapshot = state.get("rollback_snapshot", {})
    logger.warning(f"状态回滚：恢复至上一成功状态")
    return {**state, **snapshot, "retry_count": state.get("retry_count", 0) + 1}


# ===== 重试控制 =====

def should_retry(state: AgentState) -> bool:
    """判断是否还能重试"""
    retry = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)
    return retry < max_retries


def force_escalate_to_human(state: AgentState, reason: str) -> AgentState:
    """强制升级至人工"""
    logger.warning(f"强制升级人工：{reason}")
    state = record_trace(state, "escalate", "controller", "强制升级人工",
                         AgentStatus.HANDOFF.value, reason)
    return {
        **state,
        "current_agent": "human_handoff",
        "handoff_reason": reason,
        "escalate_to_human": True,
        "handoff_context": create_handoff_context(
            state, state.get("current_agent", "consultation"), "human_handoff", reason
        ),
    }


# ===== 协作路由决策 =====

def decide_next_action(state: AgentState, agent: str, success: bool,
                       handoff_target: str = "") -> str:
    """Agent 处理后，决定下一步动作

    Returns:
        "success"      - 处理成功，进入 finalize
        "retry"        - 失败但可重试，回到当前 Agent
        "handoff"      - 转交给 handoff_target
        "escalate"     - 强制升级人工
        "finalize"     - 直接收尾
    """
    if success:
        return "success"

    # 失败处理
    if should_retry(state):
        return "retry"

    # 重试超限
    if handoff_target and handoff_target != agent:
        return "handoff"
    return "escalate"


# ===== 工具函数 =====

def get_agent_chain(state: AgentState) -> list[str]:
    """获取 Agent 处理链"""
    return state.get("agent_chain", [])


def append_agent_chain(state: AgentState, agent: str) -> AgentState:
    """追加 Agent 到处理链"""
    chain = state.get("agent_chain", [])
    if not chain or chain[-1] != agent:
        chain.append(agent)
    return {**state, "agent_chain": chain}


def format_trace_summary(state: AgentState) -> str:
    """格式化 trace 摘要（供 API 返回）"""
    trace = state.get("trace", [])
    if not trace:
        return ""
    lines = []
    for i, step in enumerate(trace, 1):
        arrow = " → " if i < len(trace) else ""
        agent = step.get("agent", "")
        action = step.get("action", "")
        status = step.get("status", "")
        reason = step.get("reason", "")
        suffix = f"（{reason}）" if reason else ""
        lines.append(f"{i}. [{agent}] {action} → {status}{suffix}")
    return "\n".join(lines)
