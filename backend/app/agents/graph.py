"""LangGraph 多智能体协作状态图（深度版）

与"5个并列Agent"的根本区别：
1. Agent 之间有真实协作链路（咨询→售后→人工的升级链）
2. 每次转交携带上下文摘要，不是从零开始
3. 处理失败有重试 + 回滚 + 降级机制
4. 完整 trace 记录，可可视化状态流转

流程图：
  START → analyze → rag → initial_route
                                   │
                    ┌──────────────┼──────────────┬─────────────┐
                    ▼              ▼              ▼             ▼
              consultation     order        aftersales      compliance
                    │              │              │             │
                    └──────┬───────┴──────┬───────┴─────┬───────┘
                           │              │             │
                    ┌──────▼──────────────▼─────────────▼──────┐
                    │         route_after_agent                │
                    │  (能力边界? 情感升级? 成功?)              │
                    └──┬─────────┬──────────┬──────────────────┘
                       │         │          │
              ┌────────▼──┐  ┌───▼───┐  ┌───▼────────┐
              │ 转交目标   │  │重试   │  │  finalize  │ → END
              │ Agent     │  │当前   │  └────────────┘
              └───────────┘  │Agent  │
                             └───────┘
                       │
                ┌──────▼──────┐
                │human_handoff│ → finalize → END
                └─────────────┘
"""
from typing import Optional
from loguru import logger
from langgraph.graph import StateGraph, END

from app.agents.state import AgentState, AgentStatus, HandoffReason
from app.agents.collaboration import (
    record_trace, append_agent_chain, AGENT_NAMES,
    format_trace_summary, get_agent_chain,
)
from app.agents.router import initial_route, route_after_agent, route_desc
from app.agents.agents.consultation import ConsultationAgent
from app.agents.agents.order import OrderAgent
from app.agents.agents.aftersales import AftersalesAgent
from app.agents.agents.compliance import ComplianceAgent
from app.agents.agents.human_handoff import HumanHandoffAgent
from app.services.intent import detect_intent
from app.services.sentiment import analyze_sentiment


# Agent 实例（单例）
_agents = {
    "consultation": ConsultationAgent(),
    "order": OrderAgent(),
    "aftersales": AftersalesAgent(),
    "compliance": ComplianceAgent(),
    "human_handoff": HumanHandoffAgent(),
}


# ===== 节点函数 =====

def analyze_node(state: AgentState) -> AgentState:
    """分析节点：意图识别 + 置信度评分 + 情感分析"""
    message = state.get("message", "")

    intent, confidence = detect_intent(message)
    sentiment = analyze_sentiment(message)

    # 初始化协作控制字段
    state = {
        **state,
        "intent": intent,
        "intent_confidence": confidence,
        "sentiment": sentiment,
        "agent_chain": [],
        "retry_count": 0,
        "max_retries": 2,
        "escalate_to_human": False,
        "trace": [],
    }

    state = record_trace(state, "analyze", "controller",
                         f"意图={intent} 置信度={confidence:.2f} 情感={sentiment}",
                         AgentStatus.SUCCESS.value)
    logger.info(f"分析节点：意图={intent} 置信度={confidence:.2f} 情感={sentiment}")
    return state


def rag_node(state: AgentState) -> AgentState:
    """RAG 检索节点"""
    try:
        from app.rag.retriever import retrieve
        message = state.get("message", "")
        intent = state.get("intent", "")
        lang = state.get("lang", "en")
        sources = retrieve(message, intent=intent, top_k=3, lang=lang)
        state = {**state, "rag_sources": sources}
        state = record_trace(state, "rag", "rag",
                             f"检索到{len(sources)}条知识",
                             AgentStatus.SUCCESS.value)
    except Exception as e:
        logger.debug(f"RAG 检索跳过：{e}")
        state = {**state, "rag_sources": []}
        state = record_trace(state, "rag", "rag", "检索跳过",
                             AgentStatus.SKIPPED.value, detail=str(e))
    return state


def initial_route_node(state: AgentState) -> AgentState:
    """初始路由节点：选择首个 Agent"""
    target = initial_route(state)
    state = {**state, "route_target": target, "current_agent": target}
    state = record_trace(state, "route", "controller",
                         f"初始路由 → {AGENT_NAMES.get(target, target)}",
                         AgentStatus.SUCCESS.value)
    return state


def consultation_node(state: AgentState) -> AgentState:
    return _agents["consultation"].process(state)


def order_node(state: AgentState) -> AgentState:
    return _agents["order"].process(state)


def aftersales_node(state: AgentState) -> AgentState:
    return _agents["aftersales"].process(state)


def compliance_node(state: AgentState) -> AgentState:
    return _agents["compliance"].process(state)


def human_handoff_node(state: AgentState) -> AgentState:
    return _agents["human_handoff"].process(state)


def route_after_initial(state: AgentState) -> str:
    """初始路由后的条件边"""
    return state.get("route_target", "consultation")


def route_after_agent(state: AgentState) -> str:
    """Agent 处理后的协作路由

    根据 Agent 处理结果决定下一步：
    - 成功 → finalize
    - 能力不足 → 转交目标 Agent
    - 情感升级 → human_handoff
    """
    current = state.get("current_agent", "consultation")
    cap_check = state.get("capability_check", {})
    handoff_reason = state.get("handoff_reason", "")

    # 人工转接是终点，直接 finalize
    if current == "human_handoff":
        return "finalize"

    # 能力边界检测：不在能力范围内 → 转交
    if not cap_check.get("capable", True):
        target = cap_check.get("suggested_handoff", "human_handoff")
        # 防止循环转交：如果转交目标就是当前 Agent，直接转人工
        if target == current:
            return "human_handoff"
        # 防止循环转交：如果转交目标已在处理链中，直接转人工
        chain = get_agent_chain(state)
        if target in chain:
            logger.warning(f"检测到转交循环：{target} 已在链路中，直接转人工")
            return "human_handoff"
        return target

    # handoff_reason 存在（Agent 自检判定需转交）
    if handoff_reason and handoff_reason != HandoffReason.NONE.value:
        from app.agents.collaboration import ESCALATION_CHAIN
        target = ESCALATION_CHAIN.get(current, "human_handoff")
        chain = get_agent_chain(state)
        if target in chain and target != "human_handoff":
            return "human_handoff"
        return target

    # 正常成功 → finalize
    return "finalize"


def finalize_node(state: AgentState) -> AgentState:
    """收尾节点：补充路由说明 + trace 摘要"""
    desc = route_desc(state)
    chain = get_agent_chain(state)
    state = record_trace(state, "finalize", "controller",
                         f"流程完成，处理链长度={len(chain)}",
                         AgentStatus.SUCCESS.value)
    state = {**state, "route_desc": desc}
    logger.info(f"流程完成，处理链：{' → '.join(chain)}")
    return state


# ===== 构建状态图 =====

def build_graph():
    """构建 LangGraph 多智能体协作状态图"""
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("rag", rag_node)
    workflow.add_node("initial_route", initial_route_node)
    workflow.add_node("consultation", consultation_node)
    workflow.add_node("order", order_node)
    workflow.add_node("aftersales", aftersales_node)
    workflow.add_node("compliance", compliance_node)
    workflow.add_node("human_handoff", human_handoff_node)
    workflow.add_node("finalize", finalize_node)

    # 入口
    workflow.set_entry_point("analyze")

    # 线性边
    workflow.add_edge("analyze", "rag")
    workflow.add_edge("rag", "initial_route")

    # 初始路由 → 条件边（选择首个 Agent）
    workflow.add_conditional_edges(
        "initial_route",
        route_after_initial,
        {
            "consultation": "consultation",
            "order": "order",
            "aftersales": "aftersales",
            "compliance": "compliance",
            "human_handoff": "human_handoff",
        },
    )

    # 各 Agent → 条件边（协作路由：成功→finalize / 能力不足→转交 / 失败→重试）
    # 注意：LangGraph 通过条件边实现"转交"，转交目标即下一个 Agent 节点
    for agent in ["consultation", "order", "aftersales", "compliance"]:
        workflow.add_conditional_edges(
            agent,
            route_after_agent,
            {
                "consultation": "consultation",
                "order": "order",
                "aftersales": "aftersales",
                "compliance": "compliance",
                "human_handoff": "human_handoff",
                "finalize": "finalize",
            },
        )

    # 人工转接 → finalize（终点）
    workflow.add_edge("human_handoff", "finalize")

    # finalize → END
    workflow.add_edge("finalize", END)

    return workflow.compile()


# 单例图实例
_graph = None


def get_graph():
    """获取编译后的状态图（单例）"""
    global _graph
    if _graph is None:
        _graph = build_graph()
        logger.info("LangGraph 多智能体协作状态图已构建")
    return _graph


def run_graph(state: AgentState) -> AgentState:
    """运行多智能体协作状态图

    Args:
        state: 初始状态

    Returns:
        最终状态（含 final_reply, agent_name, route_desc, trace 等）
    """
    graph = get_graph()
    try:
        result = graph.invoke(state)
        return result
    except Exception as e:
        logger.error(f"状态图执行失败：{e}")
        # 失败时直接用人工转接兜底
        state = record_trace(state, "error", "controller",
                             f"状态图异常：{type(e).__name__}",
                             AgentStatus.FAILED.value, detail=str(e))
        try:
            result = _agents["human_handoff"].process(state)
            result["route_desc"] = f"状态图异常，降级至人工转接：{e}"
            return result
        except Exception as e2:
            logger.error(f"降级也失败：{e2}")
            return {**state, "final_reply": "服务暂时异常，已为您转接人工客服",
                    "final_reply_zh": "服务暂时异常，已为您转接人工客服",
                    "agent_name": "人工转接Agent",
                    "route_desc": f"状态图异常降级：{e2}"}
