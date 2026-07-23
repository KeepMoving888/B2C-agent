"""全局上下文总线

长会话优化的核心模块，解决长会话意图偏移问题：

1. 滑动窗口：基于 context_window_size 保留最近 N 轮对话，截断远古历史
2. 意图聚焦：在滑动窗口内，过滤与当前意图无关的历史消息，减少噪声干扰
3. 上下文总线：统一管理会话状态，跨 Agent 同步，转交时携带聚焦上下文

设计动机：
    长会话中用户意图会偏移（如先咨询商品→再查物流→再申请退款），
    若将全部历史注入 Agent prompt，无关历史信息会干扰当前意图判断，
    导致路由准确率下降。通过"滑动窗口 + 意图聚焦"两阶段过滤，
    仅保留与当前意图强相关的近期对话，显著提升路由与回复质量。
"""
from typing import Optional

from loguru import logger

from app.agents.state import AgentState
from app.config import settings


# 意图 → 关键词映射（用于意图聚焦：判断历史消息是否与当前意图相关）
# 覆盖全部 10 类客服意图
INTENT_FOCUS_KEYWORDS: dict[str, list[str]] = {
    "物流查询": [
        "物流", "快递", "配送", "tracking", "delivery", "签收", "送达",
        "delivered", "verfolgen", "seguimiento", "追跡", "配達",
    ],
    "售后退款": [
        "退款", "退货", "refund", "损坏", "破损", "damaged", "broken",
        "发错", "质量", "Rückerstattung", "reembolso", "返金",
    ],
    "催发货": [
        "发货", "ship", "催", "何时", "when", "発送", "versandt",
    ],
    "地址修改": [
        "地址", "address", "修改", "change", "住所", "Lieferadresse",
    ],
    "商品咨询": [
        "商品", "产品", "规格", "product", "stock", "库存", "现货",
        "蓝牙", "耳机", "手表", "续航", "防水", "兼容", "保修",
    ],
    "缺货询问": [
        "库存", "现货", "有货", "stock", "availability", "在庫", "Lager",
    ],
    "技术支持": [
        "使用", "教程", "怎么用", "故障", "不能", "不工作",
        "how to", "malfunction", "设置", "连接",
    ],
    "退换货": [
        "退货", "换货", "return", "exchange", "退回", "rückgabe",
        "devolución", "退换",
    ],
    "支付问题": [
        "支付", "付款", "payment", "paypal", "信用卡", "扣款",
        "failed", "失败", "支払い", "Zahlung", "pago",
    ],
    "投诉处理": [
        "投诉", "complain", "律师", "起诉", "差评", "曝光",
        "维权", "lawyer", "sue", "法院", "court",
    ],
}


def get_focused_history(
    state: AgentState,
    window_size: Optional[int] = None,
) -> list[dict]:
    """获取意图聚焦的滑动窗口历史

    两阶段过滤策略：
        Stage 1 — 滑动窗口：取最近 window_size 轮对话（默认 context_window_size=6），
                  截断远古历史，控制 prompt 长度。
        Stage 2 — 意图聚焦：在滑动窗口内，优先保留与当前意图相关的用户消息，
                  同时保留全部 assistant 回复以维持对话连贯性。

    回退策略：
        若聚焦后历史过少（< 2 条），回退至滑动窗口结果，避免上下文丢失。

    Args:
        state: 当前会话状态
        window_size: 滑动窗口大小，默认使用 settings.context_window_size

    Returns:
        聚焦后的历史消息列表 [{role, content}, ...]
    """
    history = state.get("history", [])
    if not history:
        return []

    if window_size is None:
        window_size = settings.context_window_size

    intent = state.get("intent", "")

    # Stage 1: 滑动窗口
    if len(history) > window_size:
        windowed = history[-window_size:]
    else:
        windowed = list(history)

    # Stage 2: 意图聚焦
    keywords = INTENT_FOCUS_KEYWORDS.get(intent, [])
    if not keywords:
        logger.debug(
            f"上下文总线：意图={intent} 无聚焦关键词，"
            f"返回滑动窗口 {len(windowed)} 条"
        )
        return windowed

    kw_lower = [kw.lower() for kw in keywords]
    focused: list[dict] = []
    for msg in windowed:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        # 保留所有 assistant 回复（维持对话连贯性）
        # 保留与当前意图相关的用户消息
        if role == "assistant":
            focused.append(msg)
        elif any(kw in content.lower() for kw in kw_lower):
            focused.append(msg)

    # 回退：聚焦后历史过少时，使用滑动窗口结果
    if len(focused) < 2:
        logger.debug(
            f"上下文总线：意图={intent} 聚焦后仅 {len(focused)} 条，"
            f"回退至滑动窗口 {len(windowed)} 条"
        )
        return windowed

    logger.debug(
        f"上下文总线：历史 {len(history)} 条 → "
        f"滑动窗口 {len(windowed)} 条 → 意图聚焦 {len(focused)} 条 "
        f"(意图={intent})"
    )
    return focused


def build_context_summary(state: AgentState) -> str:
    """构建全局上下文总线摘要

    用于 Agent 间转交时同步会话状态，避免下一 Agent 从零开始。
    包含：当前意图 + 置信度、情感趋势、已处理 Agent 链路、近期核心诉求。

    Returns:
        多行摘要文本
    """
    intent = state.get("intent", "")
    confidence = state.get("intent_confidence", 0.0)
    sentiment = state.get("sentiment", {})
    agent_chain = state.get("agent_chain", [])
    focused = get_focused_history(state)

    recent_user_msgs = [
        m.get("content", "")[:80]
        for m in focused
        if m.get("role") == "user"
    ]

    parts = [
        f"当前意图：{intent}（置信度 {confidence:.2f}）",
        f"客户情绪：不满 {sentiment.get('negative', 0)}%",
        f"已处理链路：{' → '.join(agent_chain) if agent_chain else '无'}",
    ]
    if recent_user_msgs:
        parts.append(f"近期诉求：{recent_user_msgs[-1]}")

    return "\n".join(parts)


def format_history_for_prompt(history: list[dict]) -> str:
    """格式化历史对话供 prompt 注入

    Args:
        history: 历史消息列表 [{role, content}, ...]

    Returns:
        格式化后的文本；空列表返回 "无"
    """
    if not history:
        return "无"
    lines = [
        f"{m.get('role', 'user')}: {m.get('content', '')}"
        for m in history
    ]
    return "\n".join(lines) or "无"