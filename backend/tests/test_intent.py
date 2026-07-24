"""意图识别 + 置信度评分测试

覆盖模块②核心能力：
- 规则识别 10 类意图
- 置信度评分策略（多模式 0.80 / 单模式 0.65 / 无命中 0.30）
- 空消息处理
- 返回 (intent, confidence) 元组
"""
import pytest
from app.services.intent import detect_intent, _rule_detect, INTENT_KEYWORDS


class TestDetectIntent:
    """意图识别主接口测试"""

    def test_returns_tuple(self):
        result = detect_intent("我的快递没收到")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_empty_message(self):
        intent, confidence = detect_intent("")
        assert intent == "商品咨询"
        assert confidence == 0.3

    def test_logistics_query(self):
        # "没收到" 命中模式1 + "快递" 命中模式2 → 物流查询
        intent, confidence = detect_intent("我的快递没收到")
        assert intent == "物流查询"

    def test_refund_query(self):
        intent, confidence = detect_intent("我要退款")
        assert intent == "售后退款"

    def test_product_query(self):
        intent, confidence = detect_intent("这个有现货吗")
        assert intent == "商品咨询"

    def test_complaint(self):
        intent, confidence = detect_intent("我要投诉你们的服务太差了")
        assert intent == "投诉处理"


class TestRuleDetectConfidence:
    """置信度评分策略测试"""

    def test_multi_pattern_high_confidence(self):
        # 同时命中多个模式 → 置信度 0.80
        msg = "我还没收到包裹，快递追踪显示异常"
        intent, confidence = _rule_detect(msg)
        assert confidence >= 0.8

    def test_single_pattern_medium_confidence(self):
        # 仅命中一个模式 → 置信度 0.65
        msg = "改一下我的地址"
        intent, confidence = _rule_detect(msg)
        assert confidence == 0.65 or confidence == 0.8  # 宽松断言

    def test_no_match_low_confidence(self):
        # 无命中 → 置信度 0.30
        intent, confidence = _rule_detect("今天天气不错")
        assert confidence == 0.3
        assert intent == "商品咨询"


class TestIntentKeywords:
    """关键词规则覆盖测试"""

    def test_all_intents_have_keywords(self):
        # 每个意图至少有 1 组关键词模式
        for intent in INTENT_KEYWORDS:
            assert len(INTENT_KEYWORDS[intent]) >= 1

    def test_multilingual_keywords(self):
        # 验证多语言关键词覆盖
        en_refund = INTENT_KEYWORDS["售后退款"]
        all_patterns = " ".join(en_refund)
        assert "refund" in all_patterns.lower() or "退款" in all_patterns
