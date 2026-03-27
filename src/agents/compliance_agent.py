"""合规解答 Agent - 平台政策、保修、合规咨询"""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from src.agents.base import get_llm
from src.rag import RAGRetriever

# 合规解答系统提示
COMPLIANCE_SYSTEM = """你是亚马逊CarPlay官方店的政策和合规专家。

你帮助客户解决以下问题：
- 亚马逊平台规则和政策
- 亚马逊保修和保证
- 亚马逊A-to-Z保障
- 亚马逊销售的合规要求

根据用户的语言自动匹配回复语言。保持回答简洁、有帮助。"""

# 合规解答节点
def run_compliance(
    messages: list[BaseMessage],
    rag: RAGRetriever | None = None,
    model: str | None = None,
) -> AIMessage:
    llm = get_llm(model=model)

    sys = SystemMessage(content=COMPLIANCE_SYSTEM)
    response = llm.invoke([sys] + messages[-3:])
    return AIMessage(content=response.content)
