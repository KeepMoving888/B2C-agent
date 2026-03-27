"""人工转接 Agent - 复杂场景升级"""

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage

from src.agents.base import get_llm
from src.tools.registry import get_tools_by_agent

# 人工转接系统提示
HUMAN_HANDOFF_SYSTEM = """你正在处理需要人工帮助的亚马逊客户。

你的任务：
1. 有同理心地确认他们的担忧
2. 确认亚马逊专家将很快协助他们
3. 总结转接的问题
4. 如有可能提供预期等待时间

使用escalate_to_human工具完成转接。
根据用户的语言自动匹配回复语言。"""

# 人工转接节点
def run_human_handoff(messages: list[BaseMessage], model: str | None = None) -> AIMessage:
    llm = get_llm(model=model)
    tools = get_tools_by_agent("human_handoff")
    bound = llm.bind_tools(tools) if tools else llm

    sys = SystemMessage(content=HUMAN_HANDOFF_SYSTEM)
    response = bound.invoke([sys] + messages[-2:])
    
    # 默认回复，实际应执行 escalate_to_human
    return AIMessage(
        content=response.content
        or "亚马逊专家将很快协助您。感谢您的耐心等待！"
    )
