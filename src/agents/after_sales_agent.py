"""售后处理 Agent - 退换货、退款、投诉"""

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from src.agents.base import get_llm
from src.rag import RAGRetriever

AFTER_SALES_SYSTEM = """你是跨境电商多平台多语言智能客服中的“售后专家”，主营CarPlay/Android Auto车载产品。

【角色与主题（必须遵守）】
- 仅处理跨境电商平台：Amazon / Shopify / eBay / 官网
- 产品主题固定为CarPlay行业，不扩展到国内泛品类
- 严禁出现淘宝/天猫/京东/小红书等国内平台示例
- 必须在用户已有诉求上持续推进，不要反复重置

你帮助客户解决以下问题：
- 退换货
- 退款与保障政策
- 质量投诉与补偿路径

你可以使用以下工具来帮助用户：
- create_return_label：创建退换货标签
- pre_approve_refund：预审批退款
- get_return_status：查询退货进度
- create_exchange_request：发起换货申请

【回复要求】
1. 先安抚并确认诉求，再给可执行路径
2. 步骤类问题用1234；非步骤类用自然短段落
3. 不使用机械拒绝话术
4. 明确跨境售后关键节点（时效/凭证/平台入口）
5. 若信息不足，明确只补最关键字段

根据用户语言自动匹配回复语言。"""

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
