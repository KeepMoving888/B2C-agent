"""售后处理 Agent - 退换货、退款、投诉"""

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from src.agents.base import get_llm
from src.rag import RAGRetriever

AFTER_SALES_SYSTEM = """你是亚马逊CarPlay官方店的售后专家。

你帮助客户解决以下问题：
- 亚马逊退换货
- 亚马逊退款和A-to-Z保障
- 亚马逊上的投诉和质量问题

你可以使用以下工具来帮助用户：
- create_return_label：创建退换货标签
- pre_approve_refund：预审批退款
- get_return_status：查询退货进度
- create_exchange_request：发起换货申请

根据用户的语言自动匹配回复语言。要有同理心和解决方案导向。"""

# 售后处理节点
def run_after_sales(
    messages: list[BaseMessage],
    rag: RAGRetriever | None = None,
    tools: list | None = None,
    model: str | None = None,
) -> AIMessage:
    llm = get_llm(model=model)
    
    sys = SystemMessage(content=AFTER_SALES_SYSTEM)
    response = llm.invoke([sys] + messages[-3:])
    return AIMessage(content=response.content or "我在这里帮您解决亚马逊订单问题。")
