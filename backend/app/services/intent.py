"""意图识别服务

基于大模型 + 关键词规则双路识别用户意图，并输出置信度评分。
支持 10 类常见客服意图。

置信度评分策略：
- LLM 严格匹配（输出即为意图标签）：0.88
- LLM 模糊匹配（输出含意图标签）：0.78
- 规则多模式命中（≥2 个模式）：0.80
- 规则单模式命中：0.65（低于阈值，触发人工兜底）
- 无命中（默认咨询）：0.30
"""
import re
from loguru import logger

from app.services.llm_service import chat_completion, is_vllm_available

# 意图标签
INTENTS = [
    "物流查询", "售后退款", "商品咨询", "投诉处理", "地址修改",
    "退换货", "支付问题", "技术支持", "催发货", "缺货询问",
]

# 多语言关键词规则
INTENT_KEYWORDS = {
    "物流查询": [
        r"haven't received|not received|配達状況|Bestellung noch nicht|no he recibido|n'ai pas reçu|没收到|未收到",
        r"tracking|追跡|verfolgen|seguimiento|suivi|物流|快递",
        r"delivered|配達完了|zugestellt|entregado|livré|签收|已送达",
    ],
    "售后退款": [
        r"refund|返金|Rückerstattung|reembolso|remboursement|退款|退货",
        r"damaged|破損|beschädigt|dañado|endommagé|损坏|破损",
        r"wrong color|間違|falsche|color equivocado|错误|发错",
    ],
    "催发货": [
        r"when.*ship|発送|versandt|enviar|expédiée|什么时候发货|催发货|催促",
    ],
    "地址修改": [
        r"address|住所|Lieferadresse|dirección|adresse|地址|改地址",
    ],
    "商品咨询": [
        r"stock|在庫|Lager|existencias|库存|现货",
        r"product|商品|produkt|producto",
        r"how long|何日|wie lange|cuánto|多久|时效",
    ],
    "支付问题": [
        r"payment|支払い|Zahlung|pago|paiement|支付|付款",
    ],
    "投诉处理": [
        r"complain|クレーム|beschweren|queja|plainte|投诉|不满|差评",
    ],
}


def detect_intent(message: str) -> tuple[str, float]:
    """识别用户消息意图并输出置信度评分

    采用双层识别策略：
    1. LLM 识别（优先）：输出意图标签 + 基于输出稳定度评估置信度
    2. 规则识别（回退）：基于关键词命中数评估置信度

    Args:
        message: 用户消息（任意语言）

    Returns:
        (intent, confidence) —— intent 为意图标签，confidence 为 0-1 置信度
    """
    if not message:
        return "商品咨询", 0.3

    # 优先使用大模型识别
    if is_vllm_available():
        intent, confidence = _llm_detect(message)
        if intent:
            return intent, confidence

    # 回退至关键词规则
    return _rule_detect(message)


def _llm_detect(message: str) -> tuple[str, float]:
    """基于大模型的意图识别 + 置信度评分

    置信度策略：
    - 输出严格等于意图标签（无多余文字）：0.88（LLM 稳定输出）
    - 输出包含意图标签但有额外文字：0.78
    - 输出无法解析：("", 0.0)
    """
    prompt = f"""请识别以下客服消息的意图，从下列选项中选择最匹配的一个，仅输出意图标签，不要其他文字：
{', '.join(INTENTS)}

消息：{message}

意图："""
    messages = [
        {"role": "system", "content": "你是一个客服意图识别助手，仅输出意图标签。"},
        {"role": "user", "content": prompt},
    ]
    result = chat_completion(messages, temperature=0.1, max_tokens=20)
    if result:
        result = result.strip()
        for intent in INTENTS:
            if intent in result:
                # 严格匹配（输出即为意图标签）→ 高置信度
                if result == intent:
                    return intent, 0.88
                # 模糊匹配（含意图标签但有额外文字）→ 中高置信度
                return intent, 0.78
    return "", 0.0


def _rule_detect(message: str) -> tuple[str, float]:
    """基于关键词规则的意图识别 + 置信度评分

    置信度策略：
    - 多模式命中（≥2 个模式）：0.80（强信号）
    - 单模式命中：0.65（弱信号，低于阈值触发人工兜底）
    - 无命中（默认咨询）：0.30
    """
    best_intent = "商品咨询"
    best_hits = 0

    for intent, patterns in INTENT_KEYWORDS.items():
        hits = sum(1 for p in patterns if re.search(p, message, re.IGNORECASE))
        if hits > best_hits:
            best_hits = hits
            best_intent = intent

    if best_hits == 0:
        return "商品咨询", 0.3
    if best_hits >= 2:
        return best_intent, 0.8
    return best_intent, 0.65