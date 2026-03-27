"""
LangGraph 主图 - 5 核心 Agent 状态流转（性能优化版）

流程：route -> [consultation | order | after_sales | compliance | human_handoff] -> END
     咨询，订单，售后，合规，人工转接
"""

from typing import Dict, Any
from langgraph.graph import StateGraph, END

from src.state.schema import ConversationState
from src.agents.fast_routing import fast_route_intent  # 使用快速路由
from src.agents.consultation_agent import run_consultation
from src.agents.order_agent import run_order_fulfillment
from src.agents.after_sales_agent import run_after_sales
from src.agents.compliance_agent import run_compliance
from src.agents.human_handoff_agent import run_human_handoff
# from src.rag import RAGRetriever  # 方案A：如需使用RAG请取消注释
from src.tools.registry import get_tools_by_agent
from src.config.settings import settings

# 模型选择节点（缓存优化）
_selected_model_cache = None

def select_model_based_on_complexity(state: ConversationState) -> str:
    """根据任务复杂度和语言选择合适的模型（带缓存）"""
    global _selected_model_cache
    
    if _selected_model_cache is not None:
        return _selected_model_cache
    
    # 强制使用国内大模型（如果配置）
    if settings.qwen_api_key:
        _selected_model_cache = "qwen-plus"  # 国内大模型
        return _selected_model_cache
    
    # 如果没有配置国内模型，使用默认模型
    _selected_model_cache = settings.llm_models["default"]
    return _selected_model_cache

# 路由节点（使用快速路由）
def _route_node(state: ConversationState) -> dict:
    """路由节点：根据意图选择下一 Agent，并写入状态（使用快速路由）"""
    import time
    start_time = time.time()
    target = fast_route_intent(state["messages"])
    end_time = time.time()
    print(f"[快速路由] 耗时: {(end_time - start_time)*1000:.2f}毫秒, 路由到: {target}")
    selected_model = select_model_based_on_complexity(state)
    return {
        "current_agent": target, 
        "current_intent": target,
        "selected_model": selected_model
    }

# 路由条件边
def _route_edges(state: ConversationState) -> str:
    """条件边：根据路由结果选择下一节点"""
    return state.get("current_agent") or "consultation"

# 异常处理节点（简化版 - 移除asyncio开销）
def _execute_with_fallback(node_func, state: ConversationState) -> dict:
    """带异常处理的节点执行（简化版，无asyncio）"""
    try:
        return node_func(state)
    except Exception as e:
        print(f"Error executing node: {e}")
        # 异常处理：返回降级响应
        from langchain_core.messages import AIMessage
        fallback_msg = AIMessage(content=settings.fallback_response)
        return {"messages": [fallback_msg], "error": str(e)}

# 咨询接待节点
def _consultation_node(state: ConversationState) -> dict:
    # 方案B：若不使用RAG，快速响应
    platform = state.get("session_metadata", {}).get("platform", "amazon")
    msg = run_consultation(state["messages"], rag=None, model=state.get("selected_model"), platform=platform)
    # 方案A：若使用RAG，要取消下面注释并注释上面一行
    # rag = RAGRetriever()
    # msg = run_consultation(state["messages"], rag=rag, model=state.get("selected_model"), platform=platform)
    return {"messages": [msg]}

# 订单处理节点
def _order_node(state: ConversationState) -> dict:
    tools = get_tools_by_agent("order_fulfillment")
    msg = run_order_fulfillment(state["messages"], tools=tools, model=state.get("selected_model"))
    return {"messages": [msg]}

# 售后处理节点
def _after_sales_node(state: ConversationState) -> dict:
    # 方案B：若不使用RAG，快速响应
    msg = run_after_sales(state["messages"], rag=None, model=state.get("selected_model"))
    # 方案A：若使用RAG，要取消下面注释并注释上面一行
    # rag = RAGRetriever()
    # msg = run_after_sales(state["messages"], rag=rag, model=state.get("selected_model"))
    return {"messages": [msg]}

# 合规处理节点
def _compliance_node(state: ConversationState) -> dict:
    # 方案B：若不使用RAG，快速响应
    msg = run_compliance(state["messages"], rag=None, model=state.get("selected_model"))
    # 方案A：若使用RAG，要取消下面注释并注释上面一行
    # rag = RAGRetriever()
    # msg = run_compliance(state["messages"], rag=rag, model=state.get("selected_model"))
    return {"messages": [msg]}

# 人工转接节点
def _human_handoff_node(state: ConversationState) -> dict:
    msg = run_human_handoff(state["messages"], model=state.get("selected_model"))
    return {"messages": [msg]}

# 创建客服 LangGraph（性能优化版）
def create_customer_service_graph():
    """创建客服 LangGraph（性能优化版 - 移除asyncio开销）"""
    graph = StateGraph(ConversationState)

    # 节点（直接使用函数，移除asyncio.run()）
    graph.add_node("route", _route_node)
    graph.add_node("consultation", lambda state: _execute_with_fallback(_consultation_node, state))
    graph.add_node("order_fulfillment", lambda state: _execute_with_fallback(_order_node, state))
    graph.add_node("after_sales", lambda state: _execute_with_fallback(_after_sales_node, state))
    graph.add_node("compliance", lambda state: _execute_with_fallback(_compliance_node, state))
    graph.add_node("human_handoff", lambda state: _execute_with_fallback(_human_handoff_node, state))

    # 入口：先路由
    graph.set_entry_point("route")

    # 条件边：route -> 各 Agent
    graph.add_conditional_edges("route", _route_edges, {
        "consultation": "consultation",
        "order_fulfillment": "order_fulfillment",
        "after_sales": "after_sales",
        "compliance": "compliance",
        "human_handoff": "human_handoff",
    })

    # 各 Agent 执行后结束
    graph.add_edge("consultation", END)
    graph.add_edge("order_fulfillment", END)
    graph.add_edge("after_sales", END)
    graph.add_edge("compliance", END)
    graph.add_edge("human_handoff", END)

    return graph.compile()


