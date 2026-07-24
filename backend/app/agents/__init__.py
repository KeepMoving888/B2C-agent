"""多智能体协作编排包

设计要点：
- Agent 之间通过 capability_check + handoff_reason 形成真实协作链
- 协作链路：consultation → order → aftersales → human_handoff
- 每次转交携带 handoff_context，避免下一个 Agent 从零开始
- 处理失败有 retry_count + rollback_snapshot 兜底
- 全程 trace 记录，支持状态流转可视化
"""
from .state import (
    AgentState,
    AgentStatus,
    HandoffReason,
    TraceStep,
)
from .collaboration import (
    record_trace,
    check_capability,
    should_escalate_by_sentiment,
    create_handoff_context,
    save_rollback_snapshot,
    rollback,
    should_retry,
    force_escalate_to_human,
    decide_next_action,
    append_agent_chain,
    get_agent_chain,
    format_trace_summary,
    AGENT_CAPABILITIES,
    ESCALATION_CHAIN,
    AGENT_NAMES,
)
from .agent_base import AgentBase
from .router import initial_route, route_after_agent, route_desc
from .graph import build_graph, get_graph, run_graph

__all__ = [
    # 状态
    "AgentState", "AgentStatus", "HandoffReason", "TraceStep",
    # 协作机制
    "record_trace", "check_capability", "should_escalate_by_sentiment",
    "create_handoff_context", "save_rollback_snapshot", "rollback",
    "should_retry", "force_escalate_to_human", "decide_next_action",
    "append_agent_chain", "get_agent_chain", "format_trace_summary",
    "AGENT_CAPABILITIES", "ESCALATION_CHAIN", "AGENT_NAMES",
    # 基类
    "AgentBase",
    # 路由
    "initial_route", "route_after_agent", "route_desc",
    # 图
    "build_graph", "get_graph", "run_graph",
]
