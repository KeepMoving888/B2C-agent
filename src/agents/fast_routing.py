"""快速路由模块 - 基于关键词匹配，秒回级响应"""

from typing import List, Dict, Tuple
from langchain_core.messages import BaseMessage, HumanMessage

# 关键词到意图的映射
_KEYWORD_INTENT_MAP = {
    # 订单相关
    "order": "order_status",
    "订单": "order_status",
    "订单号": "order_status",
    "order_id": "order_status",
    "物流": "logistics_tracking",
    "物流信息": "logistics_tracking",
    "tracking": "logistics_tracking",
    "包裹": "logistics_tracking",
    "配送": "shipping_info",
    "发货": "shipping_info",
    
    # 售后相关
    "退货": "return_exchange",
    "return": "return_exchange",
    "退款": "refund",
    "refund": "refund",
    "换货": "return_exchange",
    "exchange": "return_exchange",
    "投诉": "complaint",
    "complaint": "complaint",
    "问题": "complaint",
    "issue": "complaint",
    
    # 产品咨询
    "产品": "product_inquiry",
    "product": "product_inquiry",
    "兼容": "product_inquiry",
    "compatible": "product_inquiry",
    "价格": "price_discount",
    "price": "price_discount",
    "折扣": "price_discount",
    "discount": "price_discount",
    
    # 政策合规
    "政策": "policy_compliance",
    "policy": "policy_compliance",
    "规则": "platform_rules",
    "rules": "platform_rules",
    "保障": "warranty",
    "warranty": "warranty",
    "保修": "warranty",
    
    # FAQ
    "什么": "faq",
    "what": "faq",
    "怎么": "faq",
    "how": "faq",
    "吗": "faq",
}

# 意图到Agent的映射
_INTENT_TO_AGENT = {
    "product_inquiry": "consultation",
    "price_discount": "consultation",
    "faq": "consultation",
    "order_status": "order_fulfillment",
    "logistics_tracking": "order_fulfillment",
    "shipping_info": "order_fulfillment",
    "return_exchange": "after_sales",
    "refund": "after_sales",
    "complaint": "after_sales",
    "policy_compliance": "compliance",
    "platform_rules": "compliance",
    "warranty": "compliance",
    "complex_escalation": "human_handoff",
}

# 常见问题快速回复（增强版 - 更多变体）
_FAQ_RESPONSES = {
    # 中文FAQ - 退货相关
    "如何退货": "在亚马逊上退货很简单：1. 进入我的订单 2. 找到要退货的订单 3. 点击退货或退款 4. 按照指引操作。通常30天内可免费退货。",
    "怎么退货": "在亚马逊上退货很简单：1. 进入我的订单 2. 找到要退货的订单 3. 点击退货或退款 4. 按照指引操作。通常30天内可免费退货。",
    "怎样退货": "在亚马逊上退货很简单：1. 进入我的订单 2. 找到要退货的订单 3. 点击退货或退款 4. 按照指引操作。通常30天内可免费退货。",
    "在亚马逊上退货": "在亚马逊上退货很简单：1. 进入我的订单 2. 找到要退货的订单 3. 点击退货或退款 4. 按照指引操作。通常30天内可免费退货。",
    "退货流程": "在亚马逊上退货很简单：1. 进入我的订单 2. 找到要退货的订单 3. 点击退货或退款 4. 按照指引操作。通常30天内可免费退货。",
    "如何在亚马逊上退货": "在亚马逊上退货很简单：1. 进入我的订单 2. 找到要退货的订单 3. 点击退货或退款 4. 按照指引操作。通常30天内可免费退货。",
    "怎么在亚马逊上退货": "在亚马逊上退货很简单：1. 进入我的订单 2. 找到要退货的订单 3. 点击退货或退款 4. 按照指引操作。通常30天内可免费退货。",
    
    # 中文FAQ - 退款相关
    "如何退款": "退款流程：1. 提交退货申请 2. 寄回商品 3. 商家收到后 4. 3-5个工作日内退款到原支付方式。",
    "怎么退款": "退款流程：1. 提交退货申请 2. 寄回商品 3. 商家收到后 4. 3-5个工作日内退款到原支付方式。",
    "退款流程": "退款流程：1. 提交退货申请 2. 寄回商品 3. 商家收到后 4. 3-5个工作日内退款到原支付方式。",
    
    # 中文FAQ - 物流查询
    "物流查询": "您可以在亚马逊订单详情页查看物流信息，输入订单号或追踪号即可实时追踪包裹状态。",
    "物流信息": "您可以在亚马逊订单详情页查看物流信息，输入订单号或追踪号即可实时追踪包裹状态。",
    "包裹查询": "您可以在亚马逊订单详情页查看物流信息，输入订单号或追踪号即可实时追踪包裹状态。",
    "追踪包裹": "您可以在亚马逊订单详情页查看物流信息，输入订单号或追踪号即可实时追踪包裹状态。",
    "快递查询": "您可以在亚马逊订单详情页查看物流信息，输入订单号或追踪号即可实时追踪包裹状态。",
    
    # 中文FAQ - 订单查询
    "我的订单": "请登录亚马逊账户，在「我的订单」中查看您的订单状态和详细信息。",
    "订单查询": "请登录亚马逊账户，在「我的订单」中查看您的订单状态和详细信息。",
    "查看订单": "请登录亚马逊账户，在「我的订单」中查看您的订单状态和详细信息。",
    
    # 中文FAQ - 其他
    "A-to-Z": "亚马逊A-to-Z保障为您提供全面的购物保护，包括商品质量保障、准时配送保障和30天退款保障。",
    "A-to-Z保障": "亚马逊A-to-Z保障为您提供全面的购物保护，包括商品质量保障、准时配送保障和30天退款保障。",
    "兼容吗": "我们的CarPlay产品兼容大部分车型，建议您查看商品详情页的具体兼容列表或提供您的车型年份。",
    "是否兼容": "我们的CarPlay产品兼容大部分车型，建议您查看商品详情页的具体兼容列表或提供您的车型年份。",
    "支持吗": "我们的CarPlay产品兼容大部分车型，建议您查看商品详情页的具体兼容列表或提供您的车型年份。",
    
    # 英文FAQ
    "how to return": "To return on Amazon: 1. Go to Your Orders 2. Find the order 3. Click Return or Refund 4. Follow the instructions. Free returns within 30 days.",
    "return policy": "Amazon offers free returns within 30 days for most items. Please check the product detail page for specific return information.",
    "track order": "You can track your order in Your Orders on Amazon, or use the tracking number provided in your shipping confirmation email.",
    "where is my order": "Please check Your Orders on Amazon for real-time tracking information and delivery estimates.",
    "warranty": "This product comes with a manufacturer warranty. Please check the product details or contact us for specific warranty information.",
    "compatible": "Our CarPlay products are compatible with most vehicles. Please check the compatibility list on the product detail page.",
}


def fast_route_intent(messages: List[BaseMessage]) -> str:
    """快速路由 - 基于关键词匹配，毫秒级响应"""
    # 获取最后一条用户消息
    last_user = None
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            last_user = m.content
            break
    
    if not last_user:
        return "consultation"
    
    # 检查常见问题快速回复
    lower_msg = last_user.lower()
    for faq_key in _FAQ_RESPONSES:
        if faq_key.lower() in lower_msg:
            return "consultation"  # 咨询Agent处理
    
    # 关键词匹配
    matched_intent = None
    for keyword, intent in _KEYWORD_INTENT_MAP.items():
        if keyword.lower() in lower_msg:
            matched_intent = intent
            break
    
    # 如果匹配到，返回对应的Agent
    if matched_intent:
        return _INTENT_TO_AGENT.get(matched_intent, "consultation")
    
    # 默认返回咨询
    return "consultation"


def check_faq_response(message: str) -> str | None:
    """检查是否有常见问题的快速回复"""
    if not message:
        return None
    
    lower_msg = message.lower()
    for faq_key, faq_answer in _FAQ_RESPONSES.items():
        if faq_key.lower() in lower_msg:
            return faq_answer
    
    return None