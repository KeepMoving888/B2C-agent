"""订单履约 Agent - 订单状态、物流追踪"""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from src.agents.base import get_llm


ORDER_SYSTEM = """你是亚马逊CarPlay官方店的订单和物流专家。

你帮助客户解决以下问题：
- 亚马逊订单状态查询
- 亚马逊物流追踪
- 亚马逊配送预估和送达时间

你可以使用以下工具来帮助用户：
- get_order_status：查询订单状态
- get_order_details：获取订单详情
- list_user_orders：列出用户最近订单
- get_tracking_info：查询物流轨迹
- get_shipping_estimate：预估物流时效与费用
- get_warehouse_inventory：查询仓库库存

根据用户的语言自动匹配回复语言。保持回答简洁、有帮助。"""

# 订单履约节点
def run_order_fulfillment(
    messages: list[BaseMessage],
    tools=None,
    model: str | None = None,
) -> AIMessage:
    llm = get_llm(model=model)
    
    sys = SystemMessage(content=ORDER_SYSTEM)
    response = llm.invoke([sys] + messages[-3:])
    return AIMessage(content=response.content or "我来帮您查询亚马逊订单状态。")
