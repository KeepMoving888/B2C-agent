"""Agent 路由与意图常量"""

# 意图类型 -> 目标 Agent
INTENT_TO_AGENT = {
    "product_inquiry": "consultation",      # 产品咨询
    "price_discount": "consultation",       # 价格/优惠
    "faq": "consultation",                  # 常见问题
    "order_status": "order_fulfillment",    # 订单状态
    "logistics_tracking": "order_fulfillment",  # 物流追踪
    "shipping_info": "order_fulfillment",   # 发货信息
    "return_exchange": "after_sales",       # 退换货
    "refund": "after_sales",                # 退款
    "complaint": "after_sales",             # 投诉
    "policy_compliance": "compliance",      # 政策合规
    "platform_rules": "compliance",         # 平台规则
    "warranty": "compliance",               # 保修
    "complex_escalation": "human_handoff",  # 复杂场景需人工
}

# Agent 名称
AGENT_NAMES = {
    "consultation": "咨询接待Agent",
    "order_fulfillment": "订单履约Agent",
    "after_sales": "售后处理Agent",
    "compliance": "合规解答Agent",
    "human_handoff": "人工转接Agent",
}
