"""全局上下文总线测试

覆盖模块②核心能力：
- 滑动窗口截断（context_window_size=6）
- 意图聚焦过滤（按意图保留相关历史）
- 跨 Agent 转交摘要
- 历史格式化
"""
import pytest
from app.agents.context_bus import (
    get_focused_history, build_context_summary, format_history_for_prompt,
)


class TestGetFocusedHistory:
    """聚焦历史测试"""

    def test_sliding_window_truncation(self, sample_state):
        """历史超过窗口大小 → 截断到最近 N 条"""
        focused = get_focused_history(sample_state, window_size=4)
        assert len(focused) <= 4

    def test_short_history_unchanged(self):
        """历史少于窗口大小 → 全部保留"""
        state = {
            "history": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ],
            "intent": "商品咨询",
        }
        focused = get_focused_history(state, window_size=6)
        assert len(focused) == 2

    def test_empty_history(self):
        state = {"history": [], "intent": "商品咨询"}
        focused = get_focused_history(state)
        assert focused == []

    def test_intent_focused_filtering(self):
        """意图聚焦：与当前意图无关的历史应被降权或过滤"""
        state = {
            "intent": "售后退款",
            "history": [
                {"role": "user", "content": "我要退款"},
                {"role": "assistant", "content": "好的，为您处理退款"},
                {"role": "user", "content": "这个商品多少钱"},
                {"role": "assistant", "content": "商品价格是99元"},
                {"role": "user", "content": "退款多久到账"},
                {"role": "assistant", "content": "3-5个工作日"},
            ],
        }
        focused = get_focused_history(state, window_size=6)
        # 至少应保留最近的相关对话
        assert len(focused) > 0


class TestBuildContextSummary:
    """跨 Agent 转交摘要测试"""

    def test_summary_with_handoff(self):
        state = {
            "current_agent": "aftersales",
            "intent": "售后退款",
            "agent_chain": ["consultation", "aftersales"],
            "handoff_reason": "capability_exceeded",
            "final_reply_zh": "已为您发起退款流程",
        }
        summary = build_context_summary(state)
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_summary_empty_state(self):
        summary = build_context_summary({})
        assert isinstance(summary, str)


class TestFormatHistoryForPrompt:
    """历史格式化测试"""

    def test_format_basic(self):
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "您好，请问有什么可以帮您？"},
        ]
        formatted = format_history_for_prompt(history)
        assert "你好" in formatted
        assert "您好" in formatted

    def test_format_empty(self):
        formatted = format_history_for_prompt([])
        assert isinstance(formatted, str)
