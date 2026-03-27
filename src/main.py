"""
B2C 多 Agent 智能客服 - 主入口
启动示例对话，演示 5 Agent 路由与响应。
"""

from langchain_core.messages import HumanMessage

from src.agents import create_customer_service_graph
from src.state.schema import ConversationState

# 主函数
def main() -> None:
    graph = create_customer_service_graph()

    # 示例对话
    state: ConversationState = {
        "messages": [HumanMessage(content="我的订单 #123456 物流到哪里了？")],
        "session_metadata": {"platform": "amazon", "language": "zh"},
    }
    # 调用客服图
    result = graph.invoke(state)
    last_msg = result["messages"][-1]
    print("用户:", state["messages"][0].content)
    print("Agent:", last_msg.content)
    print("路由到:", result.get("current_agent", "?"))



if __name__ == "__main__":
    main()
