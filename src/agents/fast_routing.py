"""快速路由模块 - 基于关键词匹配，秒回级响应"""

import hashlib
import re
from typing import List

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

# FAQ 主题库（跨境电商 + 多平台）
_FAQ_TOPICS = {
    "return": {
        "keys": ["如何退货", "怎么退货", "怎样退货", "在亚马逊上退货", "退货流程", "return", "how to return", "return policy"],
        "steps": {
            "amazon": ["打开 Amazon 的 Your Orders", "找到目标订单点击 Return or Replace", "选择退货原因并确认方式", "按标签寄回后等待 3-5 天退款"],
            "shopify": ["登录商家 Shopify 后台进入 Orders", "打开对应订单并创建退货", "确认退款金额与库存回收", "同步通知买家退货进度"],
            "website": ["进入官网“我的订单”", "选择订单后发起退货申请", "按页面提示寄回商品", "仓库签收后原路退款"],
        },
    },
    "refund": {
        "keys": ["如何退款", "怎么退款", "退款流程", "refund"],
        "steps": {
            "amazon": ["先在订单页提交退款/退货请求", "按页面要求完成寄回或凭证上传", "卖家/仓库审核收货状态", "通常 3-5 个工作日退回原支付方式"],
            "shopify": ["后台打开订单并点击 Refund", "核对商品、运费与税费退款项", "确认退款并记录备注", "系统会通知买家到账进度"],
            "website": ["在官网订单中心提交退款申请", "客服审核订单与售后条件", "确认通过后进入退款流程", "预计 3-7 个工作日到账"],
        },
    },
    "tracking": {
        "keys": ["物流查询", "物流信息", "包裹查询", "追踪包裹", "快递查询", "什么时候到", "where is my order", "track order", "在哪里"],
        "steps": {
            "amazon": ["进入 Amazon 的 Your Orders", "点击订单右侧 Track Package", "查看预计送达时间与物流轨迹", "若超时可直接发起物流问题反馈"],
            "shopify": ["后台进入 Orders 打开该订单", "查看 fulfillment 与 tracking number", "核对承运商官网最新节点", "必要时给买家发送延迟说明"],
            "website": ["在官网“订单追踪”输入订单号", "查看物流公司与运单号", "关注预计签收时间", "异常包裹可一键联系在线客服"],
        },
    },
    "order": {
        "keys": ["我的订单", "订单查询", "查看订单", "shopify订单", "shopify 订单"],
        "steps": {
            "amazon": ["登录 Amazon 后进入 Your Orders", "按日期或关键词筛选订单", "点击订单查看状态与明细", "需要发票/售后可在订单页直接操作"],
            "shopify": ["登录 Shopify 后台进入 Orders", "按付款/发货状态筛选订单", "打开订单查看客户与商品详情", "可直接处理发货、备注与售后"],
            "website": ["登录官网账号进入“我的订单”", "按订单号或时间搜索", "查看支付、发货与签收状态", "支持在线申请售后"],
        },
    },
    "compatibility": {
        "keys": ["兼容吗", "是否兼容", "支持吗", "compatible", "这个产品兼容apple carplay吗", "carplay"],
        "steps": {
            "amazon": ["打开商品详情页查看 Fitment/Compatibility", "核对车型年份、排量与配置", "对照 CarPlay/Android Auto 支持范围", "不确定可把车型发我帮您二次确认"],
            "shopify": ["打开商品页查看兼容列表", "确认车型年份与中控系统版本", "核对接口与电源规格", "可提交车型信息让客服人工确认"],
            "website": ["在官网商品页查看“适配车型”", "按品牌-车型-年份逐项匹配", "确认是否支持原车协议", "若不确定可提交 VIN 码协助判断"],
        },
    },
    "warranty": {
        "keys": ["a-to-z", "a-to-z保障", "warranty", "保修", "保障"],
        "steps": {
            "amazon": ["先确认订单在 Amazon A-to-Z 保障范围", "准备订单号与沟通记录", "在订单页发起保障申诉", "平台审核后会给出退款/补偿结果"],
            "shopify": ["查看店铺保修政策与期限", "提供订单号与问题视频/照片", "客服确认后安排维修或换新", "按政策执行退款或补发"],
            "website": ["查看官网保修条款与时效", "提交订单号及故障凭证", "客服评估后给出处理方案", "支持维修、换货或退款"],
        },
    },
}


def _detect_platform(user_text: str) -> str:
    text = (user_text or "").lower()
    if "amazon" in text or "亚马逊" in text:
        return "amazon"
    if "shopify" in text:
        return "shopify"
    return "website"


def _detect_user_emotion(user_text: str) -> str:
    if not user_text:
        return "neutral"
    text = user_text.lower()

    if any(k in text for k in ["生气", "愤怒", "气死", "投诉", "太差", "垃圾", "差评", "不满意", "angry", "furious", "complaint"]):
        return "angry"
    if any(k in text for k in ["担心", "焦虑", "害怕", "怎么办", "紧张", "帮帮我", "worried", "anxious", "help me"]):
        return "anxious"
    if any(k in text for k in ["马上", "立刻", "尽快", "紧急", "urgent", "asap", "immediately"]):
        return "urgent"
    if any(k in text for k in ["谢谢", "麻烦", "请", "感谢", "thanks", "thank you", "please"]):
        return "polite"
    return "neutral"


def _tone_prefix(emotion: str, platform: str, user_text: str, language: str = "zh") -> str:
    if language != "zh":
        platform_alias = {
            "amazon": "Amazon",
            "shopify": "Shopify",
            "website": "official store",
        }.get(platform, "store")
        variants = {
            "angry": [
                f"I understand your frustration. I’ll prioritize this with {platform_alias} cross-border workflow.",
                f"I’m sorry for the experience. Let me move this quickly under {platform_alias} policy.",
            ],
            "anxious": [
                f"No worries—I'll guide you step by step under {platform_alias} process.",
                f"I understand your concern. I’ll keep this clear and practical for {platform_alias}.",
            ],
            "urgent": [
                f"Got it. I’ll use the shortest path in {platform_alias} workflow.",
                f"Understood—time matters. Here is the fastest executable route for {platform_alias}.",
            ],
            "polite": [
                f"Thanks for your patience. I’ll keep this concise for the {platform_alias} scenario.",
                f"Appreciate it. Let me walk you through practical {platform_alias} steps.",
            ],
            "neutral": [
                f"Sure—here’s the practical flow for {platform_alias}.",
                f"Got it. I’ll explain this clearly in {platform_alias} context.",
            ],
        }
    else:
        platform_alias = {
            "amazon": "Amazon",
            "shopify": "Shopify",
            "website": "官网",
        }.get(platform, "店铺")

        variants = {
            "angry": [
                f"我理解您现在很着急，这边会按 {platform_alias} 跨境订单流程优先处理。",
                f"抱歉影响了您的体验，我先按 {platform_alias} 的国际履约规则帮您快速推进。",
            ],
            "anxious": [
                f"别担心，我按 {platform_alias} 的跨境流程一步步带您处理。",
                f"我理解您的顾虑，先把关键步骤理清，再按 {platform_alias} 流程推进。",
            ],
            "urgent": [
                f"收到，我按 {platform_alias} 最短处理路径给您可执行步骤。",
                f"明白时间紧，我先给您 {platform_alias} 场景下最直接的处理方案。",
            ],
            "polite": [
                f"感谢您的耐心，我结合 {platform_alias} 的跨境场景为您整理步骤。",
                f"收到，我这边按 {platform_alias} 实际流程给您简洁说明。",
            ],
            "neutral": [
                f"好的，我按 {platform_alias} 场景给您清晰说明。",
                f"收到，下面我按 {platform_alias} 的实际流程来处理。",
            ],
        }

    options = variants.get(emotion, variants["neutral"])
    seed = int(hashlib.md5((user_text or "").encode("utf-8")).hexdigest(), 16)
    chosen = options[seed % len(options)]

    if emotion in {"neutral", "polite"} and seed % 6 == 0:
        chosen += " 我们配合一下，通常很快就能处理好。" if language == "zh" else " With your quick confirmation, this is usually resolved fast."

    return chosen


def _format_steps(steps: list[str]) -> str:
    return "\n".join([f"{i + 1}. {step}" for i, step in enumerate(steps[:4])])


def _sanitize_cross_border_text(text: str) -> str:
    cleaned = text or ""
    cleaned = cleaned.replace("淘宝", "Amazon/Shopify")
    cleaned = cleaned.replace("天猫", "Amazon/Shopify")
    cleaned = cleaned.replace("京东", "Amazon/Shopify")
    cleaned = cleaned.replace("拼多多", "Amazon/Shopify")
    cleaned = cleaned.replace("小红书", "cross-border store")
    cleaned = re.sub(r"（例如：[^）]*(手机|图书|护肤品|食品)[^）]*）", "", cleaned)
    cleaned = re.sub(r"(例如|比如)\s*[:：]?\s*[^。\n]*(手机|图书|护肤|食品)[^。\n]*", "", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _missing_info_hint(user_text: str, language: str = "zh") -> str:
    text = (user_text or "").lower()

    has_order_no = bool(re.search(r'\b\d{3}-\d{7}-\d{7}\b', text) or re.search(r'\b(order|订单)\s*[:#：-]?\s*[a-z0-9\-]{6,}\b', text))
    has_tracking_no = bool(re.search(r'\b(track|tracking|运单|快递)\s*[:#：-]?\s*[a-z0-9\-]{8,}\b', text) or re.search(r'\b[a-z]{2}\d{8,}[a-z]{0,2}\b', text))
    has_vehicle_info = bool(re.search(r'\b(19\d{2}|20\d{2})\b', text) and any(k in text for k in ["车型", "car", "model", "vin", "车"]))

    order_or_logistics = any(k in text for k in ["订单", "物流", "包裹", "快递", "track", "order", "shipping"])
    refund_or_return = any(k in text for k in ["退款", "退货", "refund", "return"])
    compatibility = any(k in text for k in ["兼容", "carplay", "android auto", "车型", "vin", "compatible"])

    if language != "zh":
        if order_or_logistics and not (has_order_no or has_tracking_no):
            return "\n\nTo check this quickly, please share one of these: order number / tracking number / last 4 digits of phone + receiver last name."
        if refund_or_return and not has_order_no:
            return "\n\nTo proceed with return/refund, please share: order number, short reason, and product condition (sealed/used)."
        if compatibility and not has_vehicle_info:
            return "\n\nTo confirm compatibility, please share: vehicle model, year, and head unit/system version (if available)."
        return ""

    if order_or_logistics and not (has_order_no or has_tracking_no):
        return (
            "\n\n为了我能立刻帮您查询进度，您提供任意一项即可：\n"
            "- 订单号（例如 123-1234567-1234567）\n"
            "- 运单号/快递单号\n"
            "- 下单手机号后四位 + 收件人姓氏"
        )

    if refund_or_return and not has_order_no:
        return (
            "\n\n为了直接帮您发起售后，请补充：\n"
            "- 订单号\n"
            "- 退货/退款原因（1 句话即可）\n"
            "- 商品当前状态（未拆封/已使用）"
        )

    if compatibility and not has_vehicle_info:
        return (
            "\n\n我可以继续帮您判断兼容性，请补充：\n"
            "- 车型品牌 + 车系\n"
            "- 年份\n"
            "- 中控系统版本（如方便）"
        )

    return ""


def _match_faq_topic(lower_msg: str) -> str | None:
    for topic, data in _FAQ_TOPICS.items():
        for k in data["keys"]:
            if k.lower() in lower_msg:
                return topic
    return None


def fast_route_intent(messages: List[BaseMessage]) -> str:
    """快速路由 - 基于关键词匹配，毫秒级响应"""
    last_user = None
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            last_user = m.content
            break

    if not last_user:
        return "consultation"

    lower_msg = last_user.lower()
    if _match_faq_topic(lower_msg):
        return "consultation"

    matched_intent = None
    for keyword, intent in _KEYWORD_INTENT_MAP.items():
        if keyword.lower() in lower_msg:
            matched_intent = intent
            break

    if matched_intent:
        return _INTENT_TO_AGENT.get(matched_intent, "consultation")
    return "consultation"


def check_faq_response(
    message: str,
    user_text: str | None = None,
    platform: str | None = None,
    language: str = "zh",
) -> str | None:
    """检查是否有常见问题的快速回复（跨境语境 + 多语言语气）。"""
    if not message:
        return None

    lower_msg = message.lower()
    topic = _match_faq_topic(lower_msg)
    if not topic:
        return None

    platform_value = platform or _detect_platform(user_text or message)
    emotion = _detect_user_emotion(user_text or message)
    prefix = _tone_prefix(emotion, platform_value, user_text or message, language)
    steps = _FAQ_TOPICS[topic]["steps"].get(platform_value) or _FAQ_TOPICS[topic]["steps"].get("website", [])

    if not steps:
        return None

    # 简短 / 标准长度自适应
    short_query = len((user_text or message).strip()) <= 18
    step_count = 3 if short_query else 4
    body = _format_steps(steps[:step_count])

    hint = _missing_info_hint(user_text or message, language)
    response = f"{prefix}\n\n{body}{hint}"
    return _sanitize_cross_border_text(response)
