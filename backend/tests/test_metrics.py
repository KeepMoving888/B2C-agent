"""监控指标采集测试

覆盖模块④核心能力：
- 指标记录（请求/意图/Agent/时延/RAG/反幻觉/转交）
- 统计摘要聚合
- Prometheus exposition format 生成
- 满意度 / AI占比 计算
"""
import pytest
from app.services.metrics import MetricsCollector


class TestMetricsCollector:
    """指标采集器测试"""

    def test_record_chat_basic(self):
        mc = MetricsCollector()
        mc.record_chat(
            intent="商品咨询",
            agent_name="咨询Agent",
            latency_ms=350.5,
            rag_sources=[{"id": "doc1"}],
            lang="en",
        )
        stats = mc.get_stats()
        assert stats["total_requests"] == 1
        assert stats["conversations"] == 1
        assert stats["intent_distribution"]["商品咨询"] == 1
        assert stats["agent_distribution"]["咨询Agent"] == 1
        assert stats["avg_response_ms"] == 350.5

    def test_record_multiple_chats(self):
        mc = MetricsCollector()
        for i in range(10):
            mc.record_chat(
                intent="物流查询" if i % 2 == 0 else "售后退款",
                agent_name="订单Agent" if i % 2 == 0 else "售后Agent",
                latency_ms=200 + i * 10,
                lang="en" if i % 2 == 0 else "ja",
            )
        stats = mc.get_stats()
        assert stats["total_requests"] == 10
        assert stats["intent_distribution"]["物流查询"] == 5
        assert stats["intent_distribution"]["售后退款"] == 5
        assert stats["lang_distribution"]["en"] == 5

    def test_anti_hallucination_metrics(self):
        mc = MetricsCollector()
        mc.record_chat(
            intent="商品咨询",
            agent_name="咨询Agent",
            anti_hallucination_report={
                "hallucination_risk": "low",
                "should_escalate": False,
                "confidence": 0.85,
            },
        )
        mc.record_chat(
            intent="售后退款",
            agent_name="人工转接Agent",
            anti_hallucination_report={
                "hallucination_risk": "high",
                "should_escalate": True,
                "confidence": 0.15,
            },
        )
        stats = mc.get_stats()
        assert stats["anti_hallucination_pass_rate"] == 50.0
        assert stats["anti_hallucination_risk_distribution"]["low"] == 1
        assert stats["anti_hallucination_risk_distribution"]["high"] == 1

    def test_handoff_metrics(self):
        mc = MetricsCollector()
        mc.record_chat(
            intent="投诉处理",
            agent_name="人工转接Agent",
            handoff_reason="sentiment_escalation",
        )
        mc.record_chat(
            intent="商品咨询",
            agent_name="咨询Agent",
            handoff_reason="",
        )
        stats = mc.get_stats()
        assert stats["total_handoffs"] == 1
        assert stats["handoff_rate"] == 50.0
        assert stats["handoff_reasons"]["sentiment_escalation"] == 1

    def test_satisfaction_calculation(self):
        """满意度 = 反幻觉通过率*0.7 + (100-转交率)*0.3"""
        mc = MetricsCollector()
        # 无转交 + 无反幻觉数据 → 默认 100% 通过率
        mc.record_chat(intent="商品咨询", agent_name="咨询Agent")
        stats = mc.get_stats()
        assert stats["satisfaction"] >= 90  # 100*0.7 + 100*0.3 = 100

    def test_ai_ratio_calculation(self):
        """AI占比 = 100 - 转交率"""
        mc = MetricsCollector()
        mc.record_chat(intent="商品咨询", agent_name="咨询Agent", handoff_reason="")
        mc.record_chat(intent="投诉", agent_name="人工转接Agent", handoff_reason="complaint")
        stats = mc.get_stats()
        assert stats["ai_ratio"] == 50  # 100 - 50% = 50

    def test_prometheus_format(self):
        mc = MetricsCollector()
        mc.record_chat(intent="商品咨询", agent_name="咨询Agent", latency_ms=300)
        text = mc.format_prometheus()
        assert "cs_total_requests 1" in text
        assert "cs_avg_response_ms" in text
        assert "# HELP" in text
        assert "# TYPE" in text
        assert "cs_intent_count" in text

    def test_empty_stats(self):
        mc = MetricsCollector()
        stats = mc.get_stats()
        assert stats["total_requests"] == 0
        assert stats["conversations"] == 0
        assert stats["anti_hallucination_pass_rate"] == 100.0
