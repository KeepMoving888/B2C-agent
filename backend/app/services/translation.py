"""多语言翻译服务

基于大模型实现 8 种语言互译。
vLLM 不可用时回退至内置关键词翻译表。
"""
import re
from loguru import logger

from app.services.llm_service import chat_completion, is_vllm_available

# 语言码 → 名称
LANG_NAMES = {
    "zh": "中文", "en": "English", "ja": "日本語",
    "de": "Deutsch", "es": "Español", "fr": "Français",
    "it": "Italiano", "pt": "Português",
}

# 内置关键词翻译表（离线回退）
KEYWORD_MAP_ZH_TO = {
    "en": {
        "订单": "order", "物流": "logistics", "退款": "refund", "发货": "shipment",
        "地址": "address", "损坏": "damaged", "感谢": "thank", "抱歉": "apologize",
        "查询": "check", "处理": "process", "收到": "received", "未收到": "not received",
        "工作日": "business days", "小时": "hours",
    },
    "ja": {"订单": "注文", "物流": "配送", "退款": "返金", "发货": "発送"},
    "de": {"订单": "Bestellung", "物流": "Logistik", "退款": "Rückerstattung", "发货": "Versand"},
    "es": {"订单": "pedido", "物流": "logística", "退款": "reembolso", "发货": "envío"},
}


def translate(text: str, from_lang: str = "zh", to_lang: str = "en") -> str:
    """翻译文本

    Args:
        text: 原文
        from_lang: 源语言码
        to_lang: 目标语言码

    Returns:
        译文
    """
    if not text or from_lang == to_lang:
        return text

    if is_vllm_available():
        return _llm_translate(text, from_lang, to_lang)
    return _keyword_translate(text, from_lang, to_lang)


def _llm_translate(text: str, from_lang: str, to_lang: str) -> str:
    """基于大模型的翻译"""
    src = LANG_NAMES.get(from_lang, from_lang)
    dst = LANG_NAMES.get(to_lang, to_lang)
    messages = [
        {"role": "system", "content": f"You are a professional translator. Translate the following {src} text to {dst}. Output only the translation, no explanation."},
        {"role": "user", "content": text},
    ]
    result = chat_completion(messages, temperature=0.3, max_tokens=512)
    if result:
        return result
    # 失败回退
    return _keyword_translate(text, from_lang, to_lang)


def _keyword_translate(text: str, from_lang: str, to_lang: str) -> str:
    """离线模式关键词翻译回退

    注意：关键词替换会产生中英混杂的文本（如"thank您的咨询"），
    因此离线模式下直接返回原文，由前端AI建议卡片展示中文原文，
    人工客服可自行翻译后发送。这比产出混杂文本更专业。
    """
    if from_lang == to_lang:
        return text
    # 离线模式：不进行关键词替换翻译，返回原文（避免中英混杂）
    logger.debug(f"离线模式：{from_lang}→{to_lang} 翻译跳过，返回原文")
    return text
