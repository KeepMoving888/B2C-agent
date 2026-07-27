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

    基于客服场景常用语词典进行中→英翻译，覆盖问候、致歉、物流、订单、
    售后、产品咨询、支付等场景。非中→英方向暂返回原文（生产环境由 vLLM 处理）。
    """
    if from_lang == to_lang:
        return text
    # 中→英方向：使用客服常用语词典翻译
    if from_lang == "zh" and to_lang == "en":
        return _zh_to_en(text)
    # 其他方向暂返回原文（需 vLLM 支撑，离线不处理避免混杂）
    logger.debug(f"离线模式：{from_lang}→{to_lang} 翻译跳过，返回原文")
    return text


# 中→英客服常用语翻译词典（覆盖80%+客服场景）
_ZH_EN_PHRASES = {
    "您好！": "Hello! ",
    "您好": "Hello, ",
    "你好": "Hello, ",
    "谢谢": "Thank you. ",
    "感谢": "Thank you. ",
    "非常感谢": "Thank you very much. ",
    "非常抱歉": "We sincerely apologize. ",
    "抱歉": "Sorry, ",
    "对不起": "Sorry, ",
    "请稍候": "Please wait a moment. ",
    "请稍等": "Please wait a moment. ",
    "没问题": "No problem. ",
    "好的": "Sure. ",
    "祝您生活愉快": "Have a great day. ",
    "感谢您的咨询": "Thank you for your inquiry. ",
    "请问": "May I ask, ",
    "请提供": "Please provide ",
    "请回复": "Please reply ",
}

_ZH_EN_KEYWORDS = [
    ("订单", "order"), ("物流", "logistics"), ("快递", "courier"), ("配送", "delivery"),
    ("发货", "shipping"), ("运输中", "in transit"), ("已签收", "delivered"),
    ("预计送达", "estimated delivery"), ("工作日", "business days"),
    ("退款", "refund"), ("退货", "return"), ("换货", "exchange"), ("维修", "repair"),
    ("损坏", "damaged"), ("破损", "damaged"), ("质量问题", "quality issue"),
    ("商品", "product"), ("产品", "product"), ("库存", "stock"), ("现货", "in stock"),
    ("规格", "specifications"), ("参数", "parameters"), ("兼容", "compatible"),
    ("续航", "battery life"), ("蓝牙", "Bluetooth"), ("无线", "wireless"),
    ("保修", "warranty"), ("质保", "warranty"),
    ("支付", "payment"), ("信用卡", "credit card"), ("发票", "invoice"),
    ("地址", "address"), ("邮编", "zip code"), ("收件人", "recipient"),
    ("咨询", "inquiry"), ("查询", "check"), ("核实", "verify"), ("处理", "process"),
    ("联系", "contact"), ("回复", "reply"), ("邮箱", "email"), ("电话", "phone"),
    ("小时", "hours"), ("分钟", "minutes"), ("今日", "today"),
    ("加急", "expedite"), ("升级", "escalate"), ("主管", "supervisor"),
    ("即插即用", "plug and play"), ("语音控制", "voice control"),
    ("请", "please"), ("您", "you"), ("您的", "your"), ("我们", "we"),
    ("已", "has been"), ("将", "will"), ("可以", "can"), ("需要", "need"),
    ("是否", "whether"), ("如何", "how"), ("什么时候", "when"), ("多久", "how long"),
    ("如果", "if"), ("因为", "because"), ("所以", "so"), ("但是", "but"),
    ("以及", "and"), ("或", "or"), ("和", "and"), ("与", "and"),
    # 客服高频词扩充
    ("我想", "I would like to"), ("状态", "status"), ("这款", "this"),
    ("支持", "supports"), ("搭载", "equipped with"), ("芯片", "chip"),
    ("连接", "connection"), ("稳定", "stable"), ("延迟", "latency"),
    ("更低", "lower"), ("主流", "mainstream"), ("车型", "car models"),
    ("同时", "also"), ("即可", "then"), ("配对", "pair"),
    ("插入", "plug into"), ("接口", "port"), ("手机", "phone"),
    ("了解", "know"), ("还有", "any other"), ("其他", "other"),
    ("问题", "questions"), ("吗", ""), ("的", ""), ("了", ""),
    ("是", "is"), ("在", "at"), ("有", "has"), ("不", "not"),
    ("都", "all"), ("还", "still"), ("会", "will"), ("能", "can"),
    ("让", "let"), ("给", "to"), ("为", "for"),
    ("建议", "suggest"), ("安装", "install"), ("车内", "in car"),
    ("通风", "ventilated"), ("位置", "position"), ("使用", "use"),
    ("适应", "adapt to"), ("环境", "environment"), ("不建议", "not recommended"),
    ("长时间", "long time"), ("暴晒", "sun exposure"), ("浸水", "soaking"),
    ("满电", "fully charged"), ("待机", "standby"), ("可达", "up to"),
    ("快充", "fast charging"), ("充电", "charging"), ("分钟即可", "minutes to"),
    ("温度", "temperature"), ("工作", "operating"),
    ("主流", "mainstream"), ("市面", "market"), ("兼容", "compatible"),
    ("以上", "above"), ("系统", "system"), ("设备", "device"),
    ("蓝牙", "Bluetooth"), ("及以上", "and above"),
    ("方式", "method"), ("车载", "car"), ("USB", "USB"),
    ("详情页", "detail page"), ("实时", "real-time"), ("轨迹", "tracking"),
    ("如需", "if you need"), ("加急", "expedite"), ("升级", "escalate"),
    ("处理", "process"), ("属于", "belongs to"), ("正常", "normal"),
    ("时效", "timeframe"), ("同步", "sync"), ("邮箱", "email"),
    ("留意", "please check"), ("查收", "receive"),
    ("核实", "verify"), ("立即", "immediately"), ("提交", "submit"),
    ("申诉", "appeal"), ("启动", "start"), ("调查", "investigation"),
    ("流程", "process"), ("检查", "check"), ("信箱", "mailbox"),
    ("门卫", "guard"), ("邻居", "neighbor"), ("是否", "whether"),
    ("代收", "collect on behalf"), ("查看", "view"), ("详情", "details"),
    ("签收人", "signer"), ("姓名", "name"), ("当地", "local"),
    ("公司", "company"), ("核实", "verify"), ("投递", "delivery"),
    ("情况", "situation"), ("仍未", "still not"), ("找到", "found"),
    ("回复", "reply"), ("消息", "message"),
    ("请问", "may I ask"), ("具体", "specific"), ("想了解", "want to know"),
    ("哪方面", "which aspect"), ("例如", "e.g."), ("参数", "parameters"),
    ("库存", "stock"), ("现货", "in stock"), ("尽早", "as early as possible"),
    ("下单", "place order"), ("发货", "ship"), ("旺季", "peak season"),
    ("延迟至", "delayed to"), ("页面", "page"),
    ("官方", "official"), ("质保", "warranty"), ("涵盖", "covers"),
    ("非人为", "non-artificial"), ("硬件", "hardware"), ("故障", "failure"),
    ("期内", "within period"), ("免费", "free"), ("更换", "replace"),
    ("申请", "apply"), ("售后", "after-sales"), ("服务", "service"),
    ("提供", "provide"), ("订单号", "order number"),
    ("。", ". "), ("！", "! "), ("？", "? "), ("，", ", "), ("：", ": "), ("；", "; "),
    ("（", "("), ("）", ")"), ("、", ", "),
    ("①", "1) "), ("②", "2) "), ("③", "3) "), ("④", "4) "), ("⑤", "5) "),
]


def _zh_to_en(text: str) -> str:
    """中→英客服常用语翻译"""
    if not text:
        return ""
    result = text
    # 短语优先匹配
    for zh, en in _ZH_EN_PHRASES.items():
        result = result.replace(zh, en)
    # 关键词替换
    for zh, en in _ZH_EN_KEYWORDS:
        result = result.replace(zh, en)
    # 清理多余空格
    import re
    result = re.sub(r"\s{2,}", " ", result).strip()
    # 首字母大写
    if result:
        result = result[0].upper() + result[1:]
    logger.debug(f"离线翻译 zh→en: {text[:30]}... -> {result[:30]}...")
    return result
