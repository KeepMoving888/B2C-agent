"""条件路由（深度版）

支持多智能体协作链路的路由决策：
- 初始路由：意图 + 情感 → 选择首个 Agent
- 协作路由：Agent 处理后根据成功/失败/转交决策下一步
- 降级路由：重试超限或异常 → 强制转人工
"""
from loguru import logger

from app.config import settings
from app.agents.state import AgentState, AgentStatus, HandoffReason
from app.agents.collaboration import (
    check_capability, should_escalate_by_sentiment,
    AGENT_CAPABILITIES, ESCALATION_CHAIN, AGENT_NAMES,
)


# 意图 → 初始 Agent 路由映射
INTENT_TO_AGENT = {
    "物流查询": "order",
    "售后退款": "aftersales",
    "催发货": "order",
    "地址修改": "order",
    "商品咨询": "consultation",
    "缺货询问": "consultation",
    "技术支持": "consultation",
    "退换货": "aftersales",
    "支付问题": "compliance",
    "投诉处理": "human_handoff",
}


def initial_route(state: AgentState) -> str:
    """初始路由：双层路由策略

    Layer 1: 情感升级（最高优先级）—— 不满情绪超阈值 → 人工转接
    Layer 2: 意图置信度兜底 —— 置信度 < 阈值 → 人工转接兜底
    Layer 3: 意图路由 —— 按意图映射选择 Agent

    Returns:
        Agent 节点名
    """
    intent = state.get("intent", "商品咨询")
    confidence = state.get("intent_confidence", 0.5)
    threshold = settings.intent_confidence_threshold

    # Layer 1: 情感升级（最高优先级）
    should_escalate, reason = should_escalate_by_sentiment(state)
    if should_escalate:
        logger.info(f"初始路由：情感升级({reason}) → human_handoff")
        return "human_handoff"

    # Layer 2: 置信度低于阈值 → 人工兜底
    if confidence < threshold:
        logger.info(
            f"初始路由：意图置信度 {confidence:.2f} < {threshold} → human_handoff 兜底"
        )
        return "human_handoff"

    # Layer 3: 按意图路由
    agent = INTENT_TO_AGENT.get(intent, "consultation")
    logger.info(f"初始路由：意图={intent} 置信度={confidence:.2f} → {agent}")
    return agent


def route_after_agent(state: AgentState) -> str:
    """Agent 处理后的协作路由

    根据 Agent 处理结果决定下一步：
    - success → finalize
    - handoff → 转交目标 Agent
    - retry → 回到当前 Agent 重试
    - escalate → 强制转人工

    Returns:
        下一个节点名
    """
    current = state.get("current_agent", "consultation")
    cap_check = state.get("capability_check", {})
    handoff_reason = state.get("handoff_reason", "")

    # 能力边界检测：不在能力范围内
    if not cap_check.get("capable", True):
        target = cap_check.get("suggested_handoff", "human_handoff")
        logger.info(f"协作路由：{current} 能力不足({cap_check.get('reason')}) → 转交 {target}")
        return target

    # 情感升级
    should_escalate, reason = should_escalate_by_sentiment(state)
    if should_escalate and current != "human_handoff":
        logger.info(f"协作路由：情感升级({reason}) → human_handoff")
        return "human_handoff"

    # 正常成功 → finalize
    logger.info(f"协作路由：{current} 处理完成 → finalize")
    return "finalize"


def route_desc(state: AgentState) -> str:
    """生成路由说明文本（供前端展示）"""
    from app.agents.collaboration import format_trace_summary, get_agent_chain

    chain = get_agent_chain(state)
    intent = state.get("intent", "")
    confidence = state.get("intent_confidence", 0.0)
    sentiment = state.get("sentiment", {})
    negative = sentiment.get("negative", 0)

    parts = []

    # 路由链路
    if len(chain) > 1:
        chain_names = [AGENT_NAMES.get(a, a) for a in chain]
        parts.append("协作链路：" + " → ".join(chain_names))
    else:
        agent_name = AGENT_NAMES.get(chain[0], "咨询Agent") if chain else "咨询Agent"
        parts.append(f"条件路由：意图={intent}(置信度{confidence:.2f}) → {agent_name}")

    # 置信度兜底说明
    threshold = settings.intent_confidence_threshold
    if confidence < threshold:
        parts.append(f"意图置信度{confidence:.2f}<{threshold}触发人工转接兜底")

    if negative >= settings.human_handoff_sentiment_threshold:
        parts.append(f"不满情绪({negative}%)≥阈值触发人工转接")

    # trace 摘要
    trace_summary = format_trace_summary(state)
    if trace_summary and len(chain) > 1:
        parts.append("状态流转：\n" + trace_summary)

    return "\n".join(parts)
