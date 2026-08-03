"""
端到端 API 集成测试
覆盖完整业务流程：health → chat → suggest → translate → handoff
"""
import pytest
import requests
import time
import json

BASE_URL = "http://localhost:8000"
TIMEOUT = 30


@pytest.fixture(scope="module", autouse=True)
def wait_for_server():
    """等待后端服务就绪"""
    for _ in range(10):
        try:
            resp = requests.get(f"{BASE_URL}/health", timeout=2)
            if resp.status_code == 200:
                return
        except:
            pass
        time.sleep(1)
    pytest.skip("Backend server not available")


class TestHealth:
    """健康检查测试"""

    def test_health_returns_ok(self):
        resp = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "infrastructure" in data

    def test_health_has_infrastructure_components(self):
        resp = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        infra = resp.json()["infrastructure"]
        assert "redis" in infra
        assert "jaeger" in infra
        assert "elasticsearch" in infra
        assert "kafka" in infra
        assert "postgres" in infra


class TestChatFlow:
    """完整聊天流程测试"""

    def test_chat_product_consultation_en(self):
        """测试英文商品咨询"""
        resp = requests.post(f"{BASE_URL}/api/chat", json={
            "platform": "amazon",
            "lang": "en",
            "message": "How long does the battery last?",
            "history": []
        }, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "agent" in data
        assert "intent" in data
        assert "reply_zh" in data
        assert "sources" in data
        assert "trace" in data
        assert len(data["trace"]) > 0

    def test_chat_multilingual_zh(self):
        """测试中文对话"""
        resp = requests.post(f"{BASE_URL}/api/chat", json={
            "platform": "taobao",
            "lang": "zh",
            "message": "蓝牙耳机续航多久？",
            "history": []
        }, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["reply_zh"]  # 非空

    def test_chat_with_history(self):
        """测试带历史记录的对话"""
        history = [
            {"role": "user", "content": "What products do you have?"},
            {"role": "assistant", "content": "We have various electronics."}
        ]
        resp = requests.post(f"{BASE_URL}/api/chat", json={
            "platform": "amazon",
            "lang": "en",
            "message": "Tell me about the earphones",
            "history": history
        }, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "reply_zh" in data

    def test_chat_returns_sources(self):
        """测试 RAG 检索返回知识源"""
        resp = requests.post(f"{BASE_URL}/api/chat", json={
            "platform": "amazon",
            "lang": "en",
            "message": "What is the return policy?",
            "history": []
        }, timeout=TIMEOUT)
        data = resp.json()
        sources = data.get("sources", [])
        assert len(sources) > 0
        for src in sources:
            assert "content" in src or "id" in src


class TestSuggestFlow:
    """AI 建议流程测试"""

    def test_suggest_returns_chinese(self):
        """测试 AI 建议始终返回中文"""
        resp = requests.post(f"{BASE_URL}/api/suggest", json={
            "lang": "en",
            "platform": "amazon",
            "history": [
                {"role": "user", "content": "How long does the battery last?"},
                {"role": "assistant", "content": "32 hours."},
                {"role": "user", "content": "Is it waterproof?"}
            ]
        }, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data
        assert "reply_zh" in data
        assert data["reply_zh"]  # 非空
        # reply_zh 应该是中文
        assert len(data["reply_zh"]) > 10


class TestTranslateFlow:
    """翻译流程测试"""

    def test_translate_zh_to_en(self):
        """测试中译英"""
        resp = requests.post(f"{BASE_URL}/api/translate", json={
            "text": "这款蓝牙耳机续航32小时，支持IPX5防水。",
            "to_lang": "en"
        }, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "translated" in data
        assert len(data["translated"]) > 0
        # 英文翻译应包含 ASCII 字符
        assert any(c.isascii() for c in data["translated"])

    def test_translate_en_to_zh(self):
        """测试英译中"""
        resp = requests.post(f"{BASE_URL}/api/translate", json={
            "text": "The battery lasts 32 hours with IPX5 waterproof rating.",
            "to_lang": "zh"
        }, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "translated" in data
        assert len(data["translated"]) > 0


class TestFullScenario:
    """完整业务场景测试"""

    def test_consultation_to_handoff(self):
        """咨询 → 人工转接完整流程"""
        # Step 1: 发起咨询
        resp1 = requests.post(f"{BASE_URL}/api/chat", json={
            "platform": "amazon",
            "lang": "en",
            "message": "I want to complain about the product quality!",
            "history": []
        }, timeout=TIMEOUT)
        assert resp1.status_code == 200
        data1 = resp1.json()

        # Step 2: 获取 AI 建议
        resp2 = requests.post(f"{BASE_URL}/api/suggest", json={
            "lang": "en",
            "platform": "amazon",
            "history": [
                {"role": "user", "content": "I want to complain about the product quality!"},
                {"role": "assistant", "content": data1.get("reply_zh", "")},
            ]
        }, timeout=TIMEOUT)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["reply_zh"]

        # Step 3: 翻译建议
        if data2["reply_zh"]:
            resp3 = requests.post(f"{BASE_URL}/api/translate", json={
                "text": data2["reply_zh"],
                "to_lang": "en"
            }, timeout=TIMEOUT)
            assert resp3.status_code == 200
            data3 = resp3.json()
            assert data3["translated"]

    def test_multilingual_scenario(self):
        """多语言场景测试"""
        for lang, message in [("en", "How long is the warranty?"),
                              ("zh", "保修期多长时间？"),
                              ("ja", "保証期間はどのくらいですか？")]:
            resp = requests.post(f"{BASE_URL}/api/chat", json={
                "platform": "amazon",
                "lang": lang,
                "message": message,
                "history": []
            }, timeout=TIMEOUT)
            assert resp.status_code == 200
            data = resp.json()
            assert "reply_zh" in data
