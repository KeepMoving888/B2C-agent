"""5大核心智能体（深度版）

每个 Agent 继承 AgentBase，统一通过 process() 方法处理：
- 能力边界检测 → 回滚快照 → _do_process → 成功/重试/转交
- 业务逻辑在 _do_process 中实现，协作机制由基类统一处理
"""
from .consultation import ConsultationAgent
from .order import OrderAgent
from .aftersales import AftersalesAgent
from .compliance import ComplianceAgent
from .human_handoff import HumanHandoffAgent

__all__ = [
    "ConsultationAgent", "OrderAgent", "AftersalesAgent",
    "ComplianceAgent", "HumanHandoffAgent",
]
