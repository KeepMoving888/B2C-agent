"""咨询接待 Agent - 产品、价格、FAQ - 多平台支持"""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from src.agents.base import get_llm
from src.rag import RAGRetriever
from src.config import settings


def get_platform_system_prompt(platform: str = "amazon") -> str:
    """根据平台获取对应的系统提示词"""
    platform_config = settings.platform_configs.get(platform, settings.platform_configs["amazon"])
    platform_name = platform_config.get("name", "Amazon")
    
    if platform == "amazon":
        return f"""你是{platform_name}CarPlay配件的专业客服代表。

你帮助客户解决以下问题：
- {platform_name}商品的产品功能和兼容性
- {platform_name}上的定价、促销、折扣
- 关于{platform_name}购物、配送和退货的常见问题
- {platform_name} Prime会员权益和配送时效
- {platform_name} A-to-Z保障政策

使用提供的知识库上下文准确回答。如果不确定，请告知并提供联系人工客服的选项。
根据用户的语言自动匹配回复语言。保持回答简洁有帮助。"""
    elif platform == "shopify":
        return f"""你是{platform_name}独立站CarPlay配件的专业客服代表。

你帮助客户解决以下问题：
- {platform_name}独立站商品的产品功能和兼容性
- {platform_name}上的定价、促销、折扣代码
- 关于{platform_name}购物、配送和退货的常见问题
- {platform_name}订单追踪和物流信息

使用提供的知识库上下文准确回答。如果不确定，请告知并提供联系人工客服的选项。
根据用户的语言自动匹配回复语言。保持回答简洁有帮助。"""
    elif platform == "ebay":
        return f"""你是{platform_name}CarPlay配件的专业客服代表。

你帮助客户解决以下问题：
- {platform_name}商品的产品功能和兼容性
- {platform_name}拍卖和一口价模式说明
- 关于{platform_name}购物、配送和退货的常见问题
- {platform_name}买家保障和退款政策

使用提供的知识库上下文准确回答。如果不确定，请告知并提供联系人工客服的选项。
根据用户的语言自动匹配回复语言。保持回答简洁有帮助。"""
    else:
        return f"""你是官方网站CarPlay配件的专业客服代表。

你帮助客户解决以下问题：
- 官方网站商品的产品功能和兼容性
- 官方网站上的定价、促销、折扣
- 关于购物、配送和退货的常见问题

使用提供的知识库上下文准确回答。如果不确定，请告知并提供联系人工客服的选项。
根据用户的语言自动匹配回复语言。保持回答简洁有帮助。"""


def get_consultation_system_prompt(platform: str = "amazon") -> str:
    """获取咨询Agent的系统提示词"""
    return get_platform_system_prompt(platform)

# 咨询接待节点
def run_consultation(
    messages: list[BaseMessage],
    rag: RAGRetriever | None = None,
    model: str | None = None,
    platform: str = "amazon",
) -> AIMessage:
    llm = get_llm(model=model)
    last_user = _get_last_user_message(messages)
    if not last_user:
        platform_config = settings.platform_configs.get(platform, settings.platform_configs["amazon"])
        platform_name = platform_config.get("name", "Amazon")
        return AIMessage(content=f"您好！我是您的{platform_name}CarPlay官方店客服专员。请问有什么可以帮助您的？")
    
    # 获取平台特定的系统提示词
    sys_prompt = get_consultation_system_prompt(platform)
    sys = SystemMessage(content=sys_prompt)
    response = llm.invoke([sys] + messages[-3:])  # 减少到最近3轮  
    return AIMessage(content=response.content)

# 获取最后一条用户消息
def _get_last_user_message(messages: list[BaseMessage]) -> str | None:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return str(m.content)
    return None
