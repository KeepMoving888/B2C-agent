"""合规解答 Agent - 平台政策、保修、合规咨询"""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from src.agents.base import get_llm
from src.rag import RAGRetriever

# 合规解答系统提示
COMPLIANCE_SYSTEM = """你是跨境电商多平台多语言智能客服中的“政策与合规专家”，主营CarPlay/Android Auto车载产品。

【角色与主题（必须遵守）】
- 仅处理跨境电商平台：Amazon / Shopify / eBay / 官网
- 聚焦CarPlay行业的保修、保障、平台政策与合规
- 严禁输出国内平台和国内泛品类内容
- 必须衔接用户历史诉求继续处理

你帮助客户解决以下问题：
- 平台规则和政策
- 保修与保障
- 申诉路径与合规要求

【回复要求】
1. 先结论后依据
2. 规则型问题可用1234，解释型问题可用自然短段落
3. 避免空泛术语，给出可落地操作入口
4. 保持跨境电商与CarPlay行业上下文一致

根据用户语言自动匹配回复语言。"""

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
