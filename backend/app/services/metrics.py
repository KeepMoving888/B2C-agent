"""系统监控指标采集

采集多智能体客服系统的核心运行指标：
- 请求维度：总数、按意图分布、按 Agent 分布
- 性能维度：响应时延（滑动平均）
- RAG 维度：检索置信度、结果数量
- 反幻觉维度：校验通过率、风险分布
- 协作维度：转交次数、转交原因分布

支持两种消费方式：
1. /api/stats   → JSON 摘要（供前端仪表盘）
2. /metrics     → Prometheus exposition format（供 Grafana/Prometheus 拉取）

不依赖 prometheus_client，自行生成 exposition format 文本，
降低部署门槛；若已安装 prometheus_client 也可平滑替换。
"""
import time
import threading
from collections import defaultdict
from typing import Optional

from loguru import logger


class MetricsCollector:
    """线程安全的指标采集器（单例）"""

    def __init__(self):
        self._lock = threading.Lock()
        self._reset()

    def _reset(self):
        """初始化所有指标"""
        self._total_requests = 0
        self._start_time = time.time()

        # 意图分布
        self._intent_counts: dict[str, int] = defaultdict(int)

        # Agent 分布
        self._agent_counts: dict[str, int] = defaultdict(int)

        # 响应时延（毫秒，滑动窗口）
        self._latencies_ms: list[float] = []

        # RAG 检索质量
        self._rag_confidences: list[float] = []
        self._rag_source_counts: list[int] = []

        # 反幻觉校验
        self._anti_halluc_total = 0
        self._anti_halluc_passed = 0
        self._anti_halluc_risk_counts: dict[str, int] = defaultdict(int)

        # 协作转交
        self._total_handoffs = 0
        self._handoff_reasons: dict[str, int] = defaultdict(int)

        # 情感
        self._sentiment_negative_count = 0

        # 多语言分布
        self._lang_counts: dict[str, int] = defaultdict(int)

    def record_chat(
        self,
        intent: str = "",
        agent_name: str = "",
        latency_ms: float = 0,
        rag_sources: Optional[list] = None,
        anti_hallucination_report: Optional[dict] = None,
        handoff_reason: str = "",
        sentiment: Optional[dict] = None,
        agent_chain: Optional[list] = None,
        lang: str = "",
    ):
        """记录一次会话的指标

        Args:
            intent: 意图标签
            agent_name: 最终处理 Agent 名称
            latency_ms: 端到端时延（毫秒）
            rag_sources: RAG 检索结果列表
            anti_hallucination_report: 反幻觉校验报告
            handoff_reason: 转交原因（空串表示无转交）
            sentiment: 情感分析结果 {joy, neutral, negative}
            agent_chain: Agent 处理链
            lang: 客户语言码
        """
        with self._lock:
            self._total_requests += 1

            if intent:
                self._intent_counts[intent] += 1
            if agent_name:
                self._agent_counts[agent_name] += 1
            if lang:
                self._lang_counts[lang] += 1

            if latency_ms > 0:
                self._latencies_ms.append(latency_ms)
                if len(self._latencies_ms) > 1000:
                    self._latencies_ms = self._latencies_ms[-1000:]

            # RAG 质量
            if rag_sources is not None:
                self._rag_source_counts.append(len(rag_sources))
                if len(self._rag_source_counts) > 1000:
                    self._rag_source_counts = self._rag_source_counts[-1000:]

            # 反幻觉校验
            if anti_hallucination_report:
                self._anti_halluc_total += 1
                risk = anti_hallucination_report.get("hallucination_risk", "unknown")
                self._anti_halluc_risk_counts[risk] += 1
                if not anti_hallucination_report.get("should_escalate", False):
                    self._anti_halluc_passed += 1
                conf = anti_hallucination_report.get("confidence", 0)
                if conf > 0:
                    self._rag_confidences.append(conf)
                    if len(self._rag_confidences) > 1000:
                        self._rag_confidences = self._rag_confidences[-1000:]

            # 转交
            if handoff_reason and handoff_reason != "":
                self._total_handoffs += 1
                self._handoff_reasons[handoff_reason] += 1

            # 情感
            if sentiment and sentiment.get("negative", 0) >= 50:
                self._sentiment_negative_count += 1

    def get_stats(self) -> dict:
        """获取统计摘要（供 /api/stats）"""
        with self._lock:
            avg_latency = (
                sum(self._latencies_ms) / len(self._latencies_ms)
                if self._latencies_ms else 0
            )
            avg_rag_conf = (
                sum(self._rag_confidences) / len(self._rag_confidences)
                if self._rag_confidences else 0
            )
            anti_halluc_rate = (
                self._anti_halluc_passed / self._anti_halluc_total * 100
                if self._anti_halluc_total > 0 else 100.0
            )
            handoff_rate = (
                self._total_handoffs / self._total_requests * 100
                if self._total_requests > 0 else 0
            )

            return {
                # 向后兼容原有字段
                "conversations": self._total_requests,
                "avg_response_sec": int(avg_latency / 1000) if avg_latency > 0 else 2,
                "satisfaction": self._compute_satisfaction(anti_halluc_rate, handoff_rate),
                "ai_ratio": self._compute_ai_ratio(handoff_rate),
                # 扩展指标
                "total_requests": self._total_requests,
                "avg_response_ms": round(avg_latency, 1),
                "intent_distribution": dict(self._intent_counts),
                "agent_distribution": dict(self._agent_counts),
                "lang_distribution": dict(self._lang_counts),
                "avg_rag_confidence": round(avg_rag_conf, 3),
                "anti_hallucination_pass_rate": round(anti_halluc_rate, 1),
                "anti_hallucination_risk_distribution": dict(self._anti_halluc_risk_counts),
                "handoff_rate": round(handoff_rate, 1),
                "total_handoffs": self._total_handoffs,
                "handoff_reasons": dict(self._handoff_reasons),
                "negative_sentiment_count": self._sentiment_negative_count,
                "uptime_sec": round(time.time() - self._start_time, 0),
            }

    @staticmethod
    def _compute_satisfaction(anti_halluc_rate: float, handoff_rate: float) -> int:
        """基于反幻觉通过率和转交率估算满意度（0-100）"""
        base = anti_halluc_rate * 0.7 + (100 - handoff_rate) * 0.3
        return int(max(60, min(99, base)))

    @staticmethod
    def _compute_ai_ratio(handoff_rate: float) -> int:
        """AI 自动处理占比 = 100 - 转交率"""
        return int(max(50, min(95, 100 - handoff_rate)))

    def format_prometheus(self) -> str:
        """生成 Prometheus exposition format 文本"""
        stats = self.get_stats()
        lines = [
            "# HELP cs_total_requests Total chat requests processed",
            "# TYPE cs_total_requests counter",
            f"cs_total_requests {stats['total_requests']}",
            "",
            "# HELP cs_avg_response_ms Average response latency in milliseconds",
            "# TYPE cs_avg_response_ms gauge",
            f"cs_avg_response_ms {stats['avg_response_ms']}",
            "",
            "# HELP cs_anti_hallucination_pass_rate Anti-hallucination check pass rate (percent)",
            "# TYPE cs_anti_hallucination_pass_rate gauge",
            f"cs_anti_hallucination_pass_rate {stats['anti_hallucination_pass_rate']}",
            "",
            "# HELP cs_handoff_rate Agent handoff rate (percent)",
            "# TYPE cs_handoff_rate gauge",
            f"cs_handoff_rate {stats['handoff_rate']}",
            "",
            "# HELP cs_total_handoffs Total agent handoffs",
            "# TYPE cs_total_handoffs counter",
            f"cs_total_handoffs {stats['total_handoffs']}",
            "",
            "# HELP cs_avg_rag_confidence Average RAG retrieval confidence",
            "# TYPE cs_avg_rag_confidence gauge",
            f"cs_avg_rag_confidence {stats['avg_rag_confidence']}",
            "",
            "# HELP cs_uptime_seconds System uptime in seconds",
            "# TYPE cs_uptime_seconds gauge",
            f"cs_uptime_seconds {stats['uptime_sec']}",
            "",
            "# HELP cs_satisfaction Estimated satisfaction score",
            "# TYPE cs_satisfaction gauge",
            f"cs_satisfaction {stats['satisfaction']}",
            "",
            "# HELP cs_ai_ratio AI auto-resolution ratio (percent)",
            "# TYPE cs_ai_ratio gauge",
            f"cs_ai_ratio {stats['ai_ratio']}",
            "",
            "# HELP cs_intent_count Request count by intent",
            "# TYPE cs_intent_count counter",
        ]
        for intent, count in sorted(stats["intent_distribution"].items()):
            safe = intent.replace('"', '\\"')
            lines.append(f'cs_intent_count{{intent="{safe}"}} {count}')

        lines += [
            "",
            "# HELP cs_agent_count Request count by agent",
            "# TYPE cs_agent_count counter",
        ]
        for agent, count in sorted(stats["agent_distribution"].items()):
            safe = agent.replace('"', '\\"')
            lines.append(f'cs_agent_count{{agent="{safe}"}} {count}')

        lines += [
            "",
            "# HELP cs_handoff_reason_count Handoff count by reason",
            "# TYPE cs_handoff_reason_count counter",
        ]
        for reason, count in sorted(stats["handoff_reasons"].items()):
            safe = reason.replace('"', '\\"')
            lines.append(f'cs_handoff_reason_count{{reason="{safe}"}} {count}')

        lines += [
            "",
            "# HELP cs_anti_hallucination_risk_count Anti-hallucination risk distribution",
            "# TYPE cs_anti_hallucination_risk_count counter",
        ]
        for risk, count in sorted(stats["anti_hallucination_risk_distribution"].items()):
            safe = risk.replace('"', '\\"')
            lines.append(f'cs_anti_hallucination_risk_count{{risk="{safe}"}} {count}')

        lines += [
            "",
            "# HELP cs_lang_count Request count by language",
            "# TYPE cs_lang_count counter",
        ]
        for lang, count in sorted(stats["lang_distribution"].items()):
            safe = lang.replace('"', '\\"')
            lines.append(f'cs_lang_count{{lang="{safe}"}} {count}')

        return "\n".join(lines) + "\n"


# 全局单例
_collector = MetricsCollector()


def record_chat(**kwargs):
    """便捷接口：记录一次会话指标"""
    _collector.record_chat(**kwargs)


def get_stats() -> dict:
    """便捷接口：获取统计摘要"""
    return _collector.get_stats()


def format_prometheus() -> str:
    """便捷接口：生成 Prometheus exposition format 文本"""
    return _collector.format_prometheus()
