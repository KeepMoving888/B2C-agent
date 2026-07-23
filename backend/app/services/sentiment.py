"""情感分析服务

基于大模型 + 关键词规则识别客户情绪。
输出三类情绪概率：喜悦 / 中性 / 不满。

规则引擎采用分级关键词 + 强度修饰词组合策略：
- 强负面词（垃圾/愤怒/投诉/律师）：直接 +35
- 一般负面词（退款/损坏/错误）：+25
- 强度修饰词（非常/极其/简直/太）：负面分 ×1.5
"""
import re
import random
from loguru import logger

from app.services.llm_service import chat_completion, is_vllm_available

# 强负面情绪关键词（直接高分）
STRONG_NEGATIVE_KEYWORDS = [
    r"garbage|trash|rubbish|クズ|垃圾|废物|烂|差劲",
    r"angry|furious|怒|憤り|wütend|enojado|愤怒|气愤|气死|生气",
    r"disappointed|失望|绝望|心寒",
    r"complain|クレーム|beschweren|queja|plainte|投诉|控告|维权",
    r"lawyer|弁護士|anwalt|abogado|avocat|律师|起诉|诉讼|法院|报案",
    r"terrible|horrible|awful|最悪|schrecklich|可怕|糟糕|恐怖",
    r"unreasonable|理不尽|unvernünftig|irrazonable|不可理喻|荒谬|无语",
    r"差评|曝光|黑心|骗子|欺诈",
    r"never again|二度と|nie wieder|nunca más|再也不会|绝对不",
]

# 一般负面情绪关键词
NEGATIVE_KEYWORDS = [
    r"damaged|破損|beschädigt|dañado|endommagé|损坏|破损|坏",
    r"wrong|間違|falsche|equivocado|错误|不对|发错",
    r"refund|返金|Rückerstattung|reembolso|remboursement|退款|退货",
    r"help!|助けて|Hilfe|ayuda|帮助|快|急",
    r"slow|遅い|langsam|lento|lent|慢|延迟|太久",
    r"missing|lost|紛失|verloren|perdido|丢失|没收到|缺失",
    r"broken|壊れた|kaputt|roto|cassé|坏了|不能用",
]

# 强度修饰词（出现时放大负面分）
INTENSIFIERS = [
    r"very|extremely|so|すごく|sehr|muy|très|非常|极其|太|超级|简直|绝对",
]

# 正面情绪关键词
POSITIVE_KEYWORDS = [
    r"thank|ありがとう|danke|gracias|merci|感谢|谢谢",
    r"great|素晴らしい|toll|genial|super|棒|好|不错",
    r"happy|嬉しい|glücklich|feliz|content|开心|满意|喜欢",
    r"perfect|完璧|perfekt|perfecto|parfait|完美",
]


def analyze_sentiment(message: str) -> dict:
    """分析客户消息情感

    Args:
        message: 客户消息

    Returns:
        {"joy": int, "neutral": int, "negative": int} 0-100
    """
    if not message:
        return {"joy": 50, "neutral": 40, "negative": 10}

    if is_vllm_available():
        result = _llm_sentiment(message)
        if result:
            return result

    return _rule_sentiment(message)


def _llm_sentiment(message: str) -> dict:
    """基于大模型的情感分析"""
    prompt = f"""请分析以下客服消息的情感倾向，输出 JSON 格式，包含三个字段：joy(喜悦), neutral(中性), negative(不满)，取值0-100，三者之和为100。

消息：{message}

仅输出 JSON，不要其他文字。"""
    messages = [
        {"role": "system", "content": "你是情感分析助手，仅输出 JSON。"},
        {"role": "user", "content": prompt},
    ]
    result = chat_completion(messages, temperature=0.2, max_tokens=60)
    if result:
        try:
            import json
            # 提取 JSON
            match = re.search(r'\{[^}]+\}', result)
            if match:
                data = json.loads(match.group())
                joy = int(data.get("joy", 0))
                neutral = int(data.get("neutral", 0))
                negative = max(0, 100 - joy - neutral)
                return {"joy": joy, "neutral": neutral, "negative": negative}
        except Exception as e:
            logger.debug(f"情感分析结果解析失败: {e}")
    return {}


def _rule_sentiment(message: str) -> dict:
    """基于关键词的情感分析（分级关键词 + 强度修饰词）"""
    # 强负面词：每个 +35
    strong_neg_count = sum(
        1 for p in STRONG_NEGATIVE_KEYWORDS if re.search(p, message, re.IGNORECASE)
    )
    # 一般负面词：每个 +20
    normal_neg_count = sum(
        1 for p in NEGATIVE_KEYWORDS if re.search(p, message, re.IGNORECASE)
    )
    # 正面词：每个 +30
    positive_count = sum(
        1 for p in POSITIVE_KEYWORDS if re.search(p, message, re.IGNORECASE)
    )
    # 强度修饰词：存在则负面分 ×1.5
    has_intensifier = any(
        re.search(p, message, re.IGNORECASE) for p in INTENSIFIERS
    )

    negative_score = strong_neg_count * 35 + normal_neg_count * 20
    # 强度修饰词仅放大强负面词部分（避免正常投诉被过度放大）
    if has_intensifier and strong_neg_count > 0:
        strong_part = int(strong_neg_count * 35 * 1.5)
        negative_score = strong_part + normal_neg_count * 20

    positive_score = positive_count * 30

    negative_score = min(negative_score, 90)
    positive_score = min(positive_score, 80)

    if negative_score > 0 and positive_score == 0:
        joy = max(5, 25 - negative_score // 3 + random.randint(0, 5))
        negative = negative_score
        neutral = 100 - joy - negative
    elif positive_score > 0 and negative_score == 0:
        joy = positive_score + random.randint(10, 20)
        negative = max(5, 15 - positive_score // 5)
        neutral = 100 - joy - negative
    elif negative_score > 0 and positive_score > 0:
        # 正负混合：以负面为主
        joy = positive_score // 2 + random.randint(5, 10)
        negative = negative_score
        neutral = 100 - joy - negative
    else:
        joy = 40 + random.randint(-10, 10)
        neutral = 40 + random.randint(-5, 10)
        negative = 100 - joy - neutral

    return {
        "joy": max(0, min(100, joy)),
        "neutral": max(0, min(100, neutral)),
        "negative": max(0, min(100, negative)),
    }
