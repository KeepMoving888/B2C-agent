"""pytest 公共夹具"""
import sys
import os

# 确保 backend/ 在 Python 路径中
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import pytest


@pytest.fixture
def sample_faq_docs():
    """示例 FAQ 文档（用于反幻觉 / 检索测试）"""
    return [
        {
            "id": "faq_001",
            "content": "蓝牙耳机 Pro 支持蓝牙5.3，续航32小时，IPX5防水。保修期12个月。",
            "category": "商品咨询",
            "keywords": ["蓝牙5.3", "续航32小时", "IPX5", "保修期12个月"],
            "lang": "zh",
            "score": 0.92,
        },
        {
            "id": "faq_002",
            "content": "智能手表 Series 7 兼容iOS 12及以上、Android 6及以上。续航7天，IP68防水。",
            "category": "商品咨询",
            "keywords": ["兼容iOS 12+", "Android 6+", "续航7天", "IP68"],
            "lang": "zh",
            "score": 0.85,
        },
        {
            "id": "faq_003",
            "content": "退款3-5个工作日原路退回。支持7天无理由退货，非质量问题需承担运费。",
            "category": "售后退款",
            "keywords": ["退款3-5个工作日", "原路退回", "7天无理由退货"],
            "lang": "zh",
            "score": 0.78,
        },
    ]


@pytest.fixture
def sample_state():
    """示例 AgentState"""
    return {
        "platform": "amazon",
        "lang": "en",
        "message": "How long does the battery last?",
        "history": [
            {"role": "user", "content": "Hello, I have a question about the earphone."},
            {"role": "assistant", "content": "Hello! How can I help you with the earphone?"},
            {"role": "user", "content": "Does it support Bluetooth 5.3?"},
            {"role": "assistant", "content": "Yes, it supports Bluetooth 5.3."},
            {"role": "user", "content": "What about battery life?"},
            {"role": "assistant", "content": "The battery lasts about 32 hours."},
            {"role": "user", "content": "Is it waterproof?"},
            {"role": "assistant", "content": "Yes, IPX5 waterproof rating."},
            {"role": "user", "content": "How long is the warranty?"},
            {"role": "assistant", "content": "12 months warranty period."},
        ],
        "conv_id": "test-conv-001",
        "intent": "商品咨询",
        "intent_confidence": 0.88,
        "sentiment": {"joy": 10, "neutral": 80, "negative": 10},
    }
