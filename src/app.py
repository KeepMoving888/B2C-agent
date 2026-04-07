"""
基于Flask的简单web界面，用于测试多Agent智能客服系统
"""

import sys
import os
import re
import hashlib
# 添加项目根目录到sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify, Response
import json
import time
from langchain_core.messages import HumanMessage
from src.agents import create_customer_service_graph
from src.state.schema import ConversationState
from src.agents.fast_routing import check_faq_response  # 导入FAQ快速回复

app = Flask(__name__)

# 轻量会话上下文（进程内缓存）
_SESSION_CONTEXT: dict[str, dict[str, str]] = {}


def _get_session_key(data: dict, remote_addr: str | None) -> str:
    """优先使用前端传入 session_id；没有则退化到 IP。"""
    sid = (data or {}).get("session_id")
    if sid:
        return str(sid)
    return remote_addr or "default"


def _explicit_platform_in_text(user_text: str) -> str | None:
    text = (user_text or "").lower()
    if "amazon" in text or "亚马逊" in text:
        return "amazon"
    if "shopify" in text:
        return "shopify"
    if "官网" in text or "website" in text:
        return "website"
    return None


def _resolve_platform(session_key: str, requested_platform: str, user_text: str) -> str:
    """平台锁定：首次确认后沿用，除非用户在文本里显式切换平台。"""
    ctx = _SESSION_CONTEXT.get(session_key, {})
    locked = ctx.get("platform")
    explicit = _explicit_platform_in_text(user_text)

    if explicit:
        final_platform = explicit
        platform_explicit = True
    elif locked:
        final_platform = locked
        platform_explicit = bool(ctx.get("platform_explicit", False))
    else:
        final_platform = requested_platform or "website"
        platform_explicit = final_platform != "website"

    _SESSION_CONTEXT[session_key] = {**ctx, "platform": final_platform, "platform_explicit": platform_explicit}
    return final_platform


def _detect_input_language(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return "zh"
    if re.search(r'[\u4e00-\u9fff]', s):
        return "zh"
    if re.search(r'[\u3040-\u30ff]', s):
        return "ja"
    if re.search(r'[\u0e00-\u0e7f]', s):
        return "th"
    if re.search(r'[áéíóúüñ¿¡]', s.lower()):
        return "es"
    if re.search(r'[äöüß]', s.lower()):
        return "de"
    if re.search(r'[àâçéèêëîïôûùüÿœæ]', s.lower()):
        return "fr"
    if re.search(r'[ăâđêôơưÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬĐÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴ]', s):
        return "vi"
    return "en"


def _resolve_response_language(session_key: str, requested_language: str, user_text: str) -> str:
    ctx = _SESSION_CONTEXT.get(session_key, {})
    detected = _detect_input_language(user_text)
    # 用户输入优先，避免出现“西语提问+中文承接”
    final_lang = detected or requested_language or ctx.get("language", "zh")
    _SESSION_CONTEXT[session_key] = {**ctx, "language": final_lang}
    return final_lang


def detect_user_emotion(user_text: str) -> str:
    """基于关键词做轻量情绪识别：angry/anxious/urgent/polite/neutral。"""
    if not user_text:
        return "neutral"

    text = user_text.lower()

    angry_keywords = [
        "生气", "愤怒", "气死", "投诉", "太差", "垃圾", "骗人", "差评", "立刻处理", "不满意",
        "angry", "furious", "outrage", "terrible", "awful", "bad service", "complaint"
    ]
    anxious_keywords = [
        "担心", "焦虑", "害怕", "怎么办", "急", "紧张", "不知道", "帮帮我",
        "worried", "anxious", "nervous", "what should i do", "help me"
    ]
    urgent_keywords = [
        "马上", "立刻", "尽快", "现在", "今天必须", "来不及", "紧急",
        "urgent", "asap", "immediately", "right now", "rush"
    ]
    polite_keywords = [
        "谢谢", "麻烦", "请", "辛苦", "感谢",
        "thanks", "thank you", "please", "appreciate"
    ]

    def hit(keywords: list[str]) -> bool:
        return any(k in text for k in keywords)

    if hit(angry_keywords):
        return "angry"
    if hit(anxious_keywords):
        return "anxious"
    if hit(urgent_keywords):
        return "urgent"
    if hit(polite_keywords):
        return "polite"
    return "neutral"


def _tone_prefix(emotion: str, platform: str, user_text: str, session_key: str = "", language: str = "zh") -> str:
    ctx = _SESSION_CONTEXT.get(session_key, {}) if session_key else {}
    platform_explicit = bool(ctx.get("platform_explicit", False))

    platform_alias_zh = {"amazon": "Amazon", "shopify": "Shopify", "website": "官网"}
    platform_alias_en = {"amazon": "Amazon", "shopify": "Shopify", "website": "official store"}

    platform_alias = platform_alias_zh.get(platform, "店铺") if language == "zh" else platform_alias_en.get(platform, "store")

    if language == "zh":
        variants = {
            "angry": ["我理解您现在很着急，这边优先给您处理。", "抱歉影响了您的体验，我先把这件事快速推进。"],
            "anxious": ["别担心，我陪您一步一步来。", "我理解您的顾虑，我们先把关键点理清再处理。"],
            "urgent": ["收到紧急需求，我先给您最短可执行方案。", "明白时间紧，我先走最直接的处理路径。"],
            "polite": ["感谢您的耐心与配合，我这边给您整理清晰步骤。", "收到，我马上帮您理清处理路径。"],
            "neutral": ["收到，我先帮您把步骤梳理清楚。", "我看到了，下面给您一版可直接执行的方案。"],
        }
    else:
        variants = {
            "angry": ["I understand your frustration. I’ll prioritize this right away.", "I’m sorry for the experience. Let me move this forward quickly."],
            "anxious": ["No worries, I’ll guide you step by step.", "I understand your concern. Let’s clarify the key points first."],
            "urgent": ["Got it. I’ll give you the shortest executable path.", "Understood—time matters. I’ll go with the fastest route."],
            "polite": ["Thanks for your patience. I’ll keep this clear and practical.", "Appreciate it. Let me organize the steps for you."],
            "neutral": ["Got it. I’ll make this clear and actionable.", "Sure—here’s the practical way to handle this."],
        }

    options = variants.get(emotion, variants["neutral"])
    seed = int(hashlib.md5((user_text or "").encode("utf-8")).hexdigest(), 16)
    preferred = options[seed % len(options)]

    if platform_explicit:
        preferred += f"（{platform_alias}）" if language == "zh" else f" ({platform_alias})"

    if session_key:
        ctx = _SESSION_CONTEXT.get(session_key, {})
        last_prefix = ctx.get("last_prefix", "")
        if last_prefix == preferred and len(options) > 1:
            preferred = options[(seed + 1) % len(options)]
        _SESSION_CONTEXT[session_key] = {**ctx, "last_prefix": preferred}

    if emotion in {"neutral", "polite"} and (seed % 5 == 0):
        preferred += " 放心，这类问题通常都能很快处理好。" if language == "zh" else " This is usually solved quickly with a couple of confirmations."

    return preferred


def _is_summary_style(user_text: str, response_text: str) -> bool:
    combined = f"{user_text}\n{response_text}".lower()
    summary_signals = [
        "步骤", "流程", "如何", "怎么", "查询", "退货", "退款", "物流", "订单", "兼容", "保修",
        "step", "steps", "process", "how to", "track", "return", "refund", "warranty"
    ]
    return any(s in combined for s in summary_signals)


def _extract_numbered_items(text: str) -> list[str]:
    inline_numbered_pattern = r'(\d+)[.、)）:：]\s*(.+?)(?=\s*\d+[.、)）:：]\s*|$)'
    inline_matches = re.findall(inline_numbered_pattern, text)

    items: list[str] = []
    if inline_matches:
        for _, item in inline_matches:
            cleaned = re.sub(r'^[·•\-–—]\s*', '', item.strip())
            if cleaned:
                items.append(cleaned)
        return items

    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^(\d+)[.、)）:：\s]\s*(.+)$', line)
        if match:
            cleaned = re.sub(r'^[·•\-–—]\s*', '', match.group(2).strip())
            if cleaned:
                items.append(cleaned)
    return items


def _detect_missing_info_prompt(user_text: str, language: str = "zh") -> str:
    text = (user_text or "").lower()

    has_order_no = bool(re.search(r'\b\d{3}-\d{7}-\d{7}\b', text) or re.search(r'\b(order|订单)\s*[:#：-]?\s*[a-z0-9\-]{6,}\b', text))
    has_tracking_no = bool(re.search(r'\b(track|tracking|运单|快递)\s*[:#：-]?\s*[a-z0-9\-]{8,}\b', text) or re.search(r'\b[a-z]{2}\d{8,}[a-z]{0,2}\b', text))
    has_vehicle_info = bool(re.search(r'\b(19\d{2}|20\d{2})\b', text) and any(k in text for k in ["车型", "car", "model", "vin", "车"]))

    order_or_logistics = any(k in text for k in ["订单", "物流", "包裹", "快递", "track", "order", "配送"])
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
            "\n\n为了我能马上帮您查询进度，您提供任意一项即可：\n"
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
            "\n\n我可以帮您快速判断兼容性，请补充这三项：\n"
            "- 车型品牌 + 车系\n"
            "- 年份\n"
            "- 中控系统版本（如方便）"
        )

    return ""


def _handoff_bridge(language: str, user_text: str, session_key: str = "") -> str:
    text = (user_text or "").lower()

    if language == "zh":
        if any(k in text for k in ["退款", "退货"]):
            options = ["我先把退款相关信息接上，马上继续帮您推进。", "收到，这里我先衔接到售后流程，继续为您处理。"]
        elif any(k in text for k in ["订单", "物流", "包裹", "track", "order"]):
            options = ["我先把订单进度这块接起来，马上继续给您处理。", "好的，我先衔接到订单查询流程，继续帮您跟进。"]
        elif any(k in text for k in ["兼容", "carplay", "车型"]):
            options = ["我先接着兼容性这块给您处理，马上继续。", "收到，我先衔接到适配确认流程，给您继续说明。"]
        else:
            options = ["我先接着您刚才的问题继续处理。", "好的，我把上下文接上，继续为您推进。"]
    else:
        if any(k in text for k in ["refund", "return"]):
            options = ["Got it, I’ll continue from the refund/return part now.", "Understood, I’ll bridge this into the after-sales flow now."]
        elif any(k in text for k in ["order", "tracking", "package", "shipping"]):
            options = ["I’ll continue from the order/tracking part now.", "Got it, I’ll bridge this into the order follow-up flow."]
        elif any(k in text for k in ["compatible", "carplay", "model", "vin"]):
            options = ["I’ll continue from the compatibility check part now.", "Understood, I’ll bridge this into fitment verification now."]
        else:
            options = ["I’ll continue from your previous context now.", "Got it, I’ll pick this up from where we left off."]

    seed = int(hashlib.md5((session_key + user_text).encode("utf-8")).hexdigest(), 16)
    return options[seed % len(options)]


def _is_greeting_or_offtopic(user_text: str) -> bool:
    t = (user_text or "").lower().strip()
    greetings = ["你好", "您好", "hi", "hello", "hey", "hola", "bonjour", "hallo", "こんにちは", "สวัสดี", "xin chào"]
    ecommerce_terms = [
        "订单", "物流", "退款", "退货", "兼容", "amazon", "shopify", "ebay", "官网",
        "order", "tracking", "refund", "return", "warranty", "carplay", "android auto",
        "vin", "fitment", "配送", "a-to-z"
    ]
    is_greeting = any(g == t for g in greetings) or t in ["你好呀", "在吗", "hey there"]
    is_offtopic = not any(k in t for k in ecommerce_terms)
    return is_greeting or (len(t) <= 20 and is_offtopic)


def _enforce_cross_border_terminology(text: str, platform: str, language: str) -> str:
    """硬性术语守卫：去国内电商表述，统一为跨境电商语境。"""
    if not text:
        return text

    cleaned = text

    # 1) 直接替换国内平台词
    replacements = {
        "淘宝": "Amazon/Shopify",
        "天猫": "Amazon/Shopify",
        "京东": "Amazon/Shopify",
        "拼多多": "Amazon/Shopify",
        "小红书": "cross-border store",
        "品牌官网": "official website store",
        "国内平台": "cross-border platform",
    }
    for k, v in replacements.items():
        cleaned = cleaned.replace(k, v)

    # 2) 去掉明显偏题的泛品类示例
    cleaned = re.sub(r"（例如：[^）]*(手机|图书|护肤品|食品)[^）]*）", "", cleaned)
    cleaned = re.sub(r"(例如|比如)\s*[:：]?\s*[^。\n]*(手机|图书|护肤|食品)[^。\n]*", "", cleaned)

    # 3) 统一无法访问系统的表述，避免机械AI口吻
    cleaned = re.sub(
        r"我无法直接(处理|访问|连接)[^。\n]*",
        "我可以先按跨境平台标准流程帮您定位下一步，并指导您快速完成操作",
        cleaned,
    )

    # 4) 平台术语轻量对齐
    if language == "zh":
        if platform == "amazon":
            cleaned = cleaned.replace("我的订单", "Your Orders")
        elif platform == "shopify":
            cleaned = cleaned.replace("我的订单", "Shopify Orders")

    # 清理多余空白
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def format_response(
    response_text: str,
    user_text: str = "",
    platform: str = "website",
    session_key: str = "",
    language: str = "zh",
    current_agent: str = "",
) -> str:
    """回复格式化：跨境语境、多语言、长度自适应，并保留自然段。"""
    if not response_text:
        return response_text

    emotion = detect_user_emotion(user_text)
    prefix = _tone_prefix(emotion, platform, user_text, session_key, language)

    text = response_text.strip()
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 跨境术语硬守卫（避免国内电商措辞回流）
    text = _enforce_cross_border_terminology(text, platform, language)

    # 清理模型兜底错误句，避免展示“系统技术问题”原文
    text = re.sub(r'抱歉[，,]?\s*系统出现技术问题[。！!]?\s*请稍后重试[或及]?联系(我们)?(的)?客服(团队)?[。！!]?','', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()

    # 路由切换平滑衔接（仅业务场景才加，不在问候/闲聊里加）
    bridge = ""
    if session_key and current_agent:
        ctx = _SESSION_CONTEXT.get(session_key, {})
        last_agent = ctx.get("last_agent", "")
        if last_agent and last_agent != current_agent and not _is_greeting_or_offtopic(user_text):
            bridge = _handoff_bridge(language, user_text, session_key)
        _SESSION_CONTEXT[session_key] = {**ctx, "last_agent": current_agent}

    numbered_items = _extract_numbered_items(text)
    use_summary = _is_summary_style(user_text, text)

    complex_hits = sum(1 for k in ["退货", "退款", "物流", "订单", "兼容", "warranty", "return", "refund", "tracking", "order"] if k in (user_text or "").lower())
    max_items = 4 if complex_hits >= 2 else 3
    item_len = 34 if complex_hits >= 2 else 26

    chunks = [c for c in [bridge] if c]

    # 问候/闲聊：不加转接语，不强制“接手”类前缀
    if _is_greeting_or_offtopic(user_text):
        friendly = {
            "zh": "您好，我是跨境电商多平台多语言智能客服，专注CarPlay/Android Auto车载产品。",
            "en": "Hi, I’m your multilingual cross-border e-commerce support for CarPlay/Android Auto products.",
            "es": "Hola, soy tu soporte multilingüe de e-commerce transfronterizo para productos CarPlay/Android Auto.",
            "de": "Hallo, ich bin Ihr mehrsprachiger Cross-Border-E-Commerce-Support für CarPlay/Android Auto-Produkte.",
            "fr": "Bonjour, je suis votre support e-commerce transfrontalier multilingue pour les produits CarPlay/Android Auto.",
            "ja": "こんにちは。私はCarPlay/Android Auto製品に特化した越境ECの多言語カスタマーサポートです。",
            "th": "สวัสดี ฉันคือฝ่ายบริการลูกค้าอีคอมเมิร์ซข้ามพรมแดนหลายภาษา สำหรับสินค้า CarPlay/Android Auto",
            "vi": "Xin chào, mình là CSKH TMĐT xuyên biên giới đa ngôn ngữ cho sản phẩm CarPlay/Android Auto.",
        }.get(language, "Hi, I’m your multilingual cross-border e-commerce support for CarPlay/Android Auto products.")
        chunks.append(friendly)
        chunks.append(text[:180] + ('...' if len(text) > 180 else ''))
        return '\n\n'.join([c for c in chunks if c])

    chunks.append(prefix)

    if use_summary and len(numbered_items) >= 2:
        result_items = [item[:item_len] + ('...' if len(item) > item_len else '') for item in numbered_items[:max_items]]
        steps = '\n'.join([f"{i + 1}. {item}" for i, item in enumerate(result_items)])
        chunks.append(steps)
    else:
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        merged = '\n\n'.join(paragraphs[:2])
        chunks.append(merged[:220] + ('...' if len(merged) > 220 else ''))

    guidance = _detect_missing_info_prompt(user_text, language)
    return '\n\n'.join(chunks) + guidance

# 创建客服图实例
customer_service_graph = create_customer_service_graph()
# 首页路由
@app.route('/')
def index():
    """首页"""
    return render_template('index.html')
# 聊天路由
@app.route('/chat', methods=['POST'])
def chat():
    """处理聊天请求（秒回版）"""
    import time
    total_start_time = time.time()
    
    data = request.json
    session_key = _get_session_key(data or {}, request.remote_addr)
    user_message = data.get('message')
    language = data.get('language', 'zh')
    response_language = _resolve_response_language(session_key, language, user_message or "")
    requested_platform = data.get('platform', 'website')
    platform = _resolve_platform(session_key, requested_platform, user_message or "")
    
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    
    print(f"\n{'='*60}")
    print(f"[请求] 用户消息: {user_message[:50]}...")
    print(f"[请求] 平台: {platform}, 语言: {response_language}")
    
    # 阶段1: 检查FAQ快速回复（毫秒级）
    faq_start_time = time.time()
    faq_response = check_faq_response(user_message, user_message, platform, response_language)
    faq_time = time.time() - faq_start_time
    
    if faq_response:
        total_time = time.time() - total_start_time
        print(f"[FAQ快速回复] 匹配成功! 耗时: {faq_time*1000:.2f}毫秒")
        print(f"[性能监控] 总响应时间: {total_time:.3f}秒 (FAQ秒回)")
        print(f"{'='*60}\n")
        return jsonify({
            'response': faq_response,
            'agent': 'faq_fast',
            'model': 'faq_cache'
        })
    
    print(f"[FAQ检查] 未匹配，耗时: {faq_time*1000:.2f}毫秒")
    
    # 阶段2: 构建对话状态
    state: ConversationState = {
        "messages": [HumanMessage(content=user_message)],
        "session_metadata": {
            "platform": platform,
            "language": language
        },
    }
    
    # 阶段3: 调用客服图
    try:
        graph_start_time = time.time()
        print(f"[图执行] 开始...")
        
        result = customer_service_graph.invoke(state)
        
        graph_time = time.time() - graph_start_time
        print(f"[图执行] 完成，耗时: {graph_time:.2f}秒")
        
        # 获取最后一条回复
        last_msg = result["messages"][-1]
        response = last_msg.content

        # 获取路由信息
        current_agent = result.get("current_agent", "unknown")

        # 格式化回复（情绪语气/多语言/平滑衔接）
        response = format_response(response, user_message, platform, session_key, response_language, current_agent)
        
        # 强制使用国内模型名称
        from src.config import settings
        if settings.qwen_api_key:
            selected_model = "qwen-plus"
        else:
            selected_model = result.get("selected_model", "unknown")
        
        total_time = time.time() - total_start_time
        print(f"[性能监控] 总响应时间: {total_time:.3f}秒")
        print(f"{'='*60}\n")
        
        return jsonify({
            'response': response,
            'agent': current_agent,
            'model': selected_model
        })
    except Exception as e:
        total_time = time.time() - total_start_time
        print(f"[错误] {str(e)}")
        print(f"[性能监控] 总响应时间: {total_time:.3f}秒 (出错)")
        print(f"{'='*60}\n")
        return jsonify({
            'response': '抱歉，系统出现技术问题，请稍后重试。',
            'error': str(e)
        }), 500

# 流式聊天接口
@app.route('/chat/stream', methods=['POST'])
def chat_stream():
    """流式处理聊天请求"""
    data = request.json
    session_key = _get_session_key(data or {}, request.remote_addr)
    user_message = data.get('message')
    language = data.get('language', 'zh')
    response_language = _resolve_response_language(session_key, language, user_message or "")
    requested_platform = data.get('platform', 'website')
    platform = _resolve_platform(session_key, requested_platform, user_message or "")
    
    if not user_message:
        def generate_error():
            yield f"data: {json.dumps({'error': 'Message is required'})}\n\n"
        return Response(generate_error(), mimetype='text/event-stream')
    
    print(f"\n{'='*60}")
    print(f"[流式请求] 用户消息: {user_message[:50]}...")
    print(f"[流式请求] 平台: {platform}, 语言: {response_language}")
    
    # 1. 检查FAQ快速回复
    faq_response = check_faq_response(user_message, user_message, platform, response_language)
    
    if faq_response:
        print("[流式FAQ] 匹配成功!")
        print(f"{'='*60}\n")
        
        def generate_faq():
            # 流式输出FAQ回复
            for i in range(0, len(faq_response), 10):
                chunk = faq_response[i:i+10]
                done = i+10 >= len(faq_response)
                yield f"data: {json.dumps({'chunk': chunk, 'done': done, 'agent': 'faq_fast', 'model': 'faq_cache'})}\n\n"
                time.sleep(0.05)  # 控制输出速度
        
        return Response(generate_faq(), mimetype='text/event-stream')
    
    # 2. 构建对话状态
    state: ConversationState = {
        "messages": [HumanMessage(content=user_message)],
        "session_metadata": {
            "platform": platform,
            "language": language
        },
    }
    
    # 3. 调用客服图获取完整响应
    try:
        print(f"[图执行] 开始...")
        result = customer_service_graph.invoke(state)
        
        # 获取最后一条回复
        last_msg = result["messages"][-1]
        response = last_msg.content
        
        # 强制格式化为简洁的1234格式（支持情绪语气）
        current_agent = result.get("current_agent", "unknown")
        response = format_response(response, user_message, platform, session_key, response_language, current_agent)
        
        # 强制使用国内模型名称
        from src.config import settings
        if settings.qwen_api_key:
            selected_model = "qwen-plus"
        else:
            selected_model = result.get("selected_model", "unknown")
        
        print("[流式输出] 开始...")
        print(f"{'='*60}\n")
        
        # 4. 流式输出响应
        def generate():
            for i in range(0, len(response), 15):
                chunk = response[i:i+15]
                done = i+15 >= len(response)
                yield f"data: {json.dumps({'chunk': chunk, 'done': done, 'agent': current_agent, 'model': selected_model})}\n\n"
                time.sleep(0.08)  # 控制输出速度
        
        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        print(f"[错误] {str(e)}")
        print(f"{'='*60}\n")
        
        def generate_error():
            error_msg = '抱歉，系统出现技术问题，请稍后重试。'
            yield f"data: {json.dumps({'chunk': error_msg, 'done': True, 'error': str(e)})}\n\n"
        
        return Response(generate_error(), mimetype='text/event-stream')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
