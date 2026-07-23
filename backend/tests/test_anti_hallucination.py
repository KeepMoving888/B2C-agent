"""反幻觉三层校验测试

覆盖模块③核心能力：
- 层1 引用溯源：无引用 → 高风险
- 层2 置信度阈值：低置信 → 高风险
- 层3 答案一致性：事实不在上下文 → 未通过
- 综合判定：should_escalate
- 回复标注
"""
import pytest
from app.rag.anti_hallucination import (
    AntiHallucinationChecker, check_reply, annotate_reply,
    AntiHallucinationReport, Citation,
)


class TestAntiHallucinationChecker:
    """反幻觉校验器测试"""

    def test_high_confidence_supported_facts(self, sample_faq_docs):
        """高置信度 + 事实被支持 → 低风险"""
        checker = AntiHallucinationChecker()
        report = checker.check(
            query="蓝牙耳机续航多久",
            retrieved_docs=sample_faq_docs,
            reply="蓝牙耳机 Pro 支持蓝牙5.3，续航32小时，IPX5防水。",
            intent="商品咨询",
        )
        assert report.confidence_level in ("high", "medium")
        assert report.hallucination_risk in ("low", "medium")
        assert not report.should_escalate

    def test_no_citations_high_risk(self):
        """无引用 → 高风险 + should_escalate"""
        checker = AntiHallucinationChecker()
        report = checker.check(
            query="退款政策",
            retrieved_docs=[],
            reply="我们支持全额退款。",
        )
        assert report.hallucination_risk == "high"
        assert report.should_escalate

    def test_unsupported_facts(self, sample_faq_docs):
        """事实不在上下文 → 一致性未通过"""
        checker = AntiHallucinationChecker()
        report = checker.check(
            query="保修期",
            retrieved_docs=sample_faq_docs,
            reply="保修期24个月，全球联保。",
        )
        # "24" 不在上下文中（上下文为 "12个月"），应被标记为 unsupported
        assert "24" in report.facts_unsupported or not report.faithfulness_passed

    def test_low_confidence_escalate(self):
        """低置信度（检索分数极低）→ should_escalate"""
        checker = AntiHallucinationChecker()
        # score=0.005 在 RRF 区间(≤0.1)，归一化 = 0.005/(2/61) ≈ 0.15 < 0.3 → low
        low_score_docs = [
            {"id": "doc1", "content": "some content", "score": 0.005},
        ]
        report = checker.check(
            query="random query",
            retrieved_docs=low_score_docs,
            reply="This is a reply.",
        )
        assert report.confidence_level == "low"
        assert report.should_escalate


class TestExtractFacts:
    """事实抽取测试"""

    def test_extract_duration(self):
        checker = AntiHallucinationChecker()
        facts = checker._extract_facts("退款3-5个工作日原路退回")
        assert any("3" in f and "5" in f for f in facts) or any("工作日" in f for f in facts)

    def test_extract_numbers(self):
        checker = AntiHallucinationChecker()
        facts = checker._extract_facts("蓝牙5.3 IPX5 32小时")
        assert "5.3" in facts or "32" in facts

    def test_extract_policy_keywords(self):
        checker = AntiHallucinationChecker()
        facts = checker._extract_facts("支持全额退款和原路退回")
        assert "全额退款" in facts
        assert "原路退回" in facts

    def test_empty_reply(self):
        checker = AntiHallucinationChecker()
        assert checker._extract_facts("") == []


class TestAnnotateReply:
    """回复标注测试"""

    def test_annotate_medium_confidence(self):
        report = AntiHallucinationReport(
            confidence_level="medium",
            hallucination_risk="medium",
            should_escalate=False,
            faithfulness_passed=True,
        )
        annotated = annotate_reply(report, "原始回复")
        assert "[仅供参考]" in annotated
        assert "原始回复" in annotated

    def test_annotate_escalate(self):
        report = AntiHallucinationReport(
            confidence_level="low",
            hallucination_risk="high",
            should_escalate=True,
            faithfulness_passed=False,
        )
        annotated = annotate_reply(report, "原始回复")
        assert "[建议转人工]" in annotated

    def test_no_annotation_for_low_risk(self):
        report = AntiHallucinationReport(
            confidence_level="high",
            hallucination_risk="low",
            should_escalate=False,
            faithfulness_passed=True,
        )
        annotated = annotate_reply(report, "原始回复")
        assert annotated == "原始回复"
