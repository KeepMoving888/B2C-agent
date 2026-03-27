"""Agent 基类与 LLM 初始化"""

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from src.agents.domestic_models import ChatQwen
from src.config import settings


_llm_instance = None


from langchain_core.messages import AIMessage, BaseMessage, SystemMessage


def get_llm(model: str | None = None):
    """获取LLM实例（使用模块级单例缓存）"""
    global _llm_instance
    
    if _llm_instance is not None:
        return _llm_instance
    
    # 强制使用国内大模型（如果配置）
    if settings.qwen_api_key:
        _llm_instance = ChatQwen(
            qwen_api_key=settings.qwen_api_key,
            model=settings.llm_models["domestic"],
            temperature=0.3,
            timeout=30
        )
        return _llm_instance
    
    # 如果没有配置国内模型，尝试使用其他模型
    # 以下代码作为可选项，暂时注释掉
    """
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        _llm_instance = ChatAnthropic(
            model=model or "claude-3-5-sonnet-20241022",
            api_key=settings.anthropic_api_key,
        )
        return _llm_instance
    
    if settings.openai_api_key:
        _llm_instance = ChatOpenAI(
            model=model or settings.llm_models["default"],
            api_key=settings.openai_api_key,
            temperature=0.3,
            timeout=30,  # 增加超时时间到30秒
            max_retries=3,  # 增加重试次数
        )
        return _llm_instance
    """
    
    # 如果没有配置任何模型，返回一个简单的模拟LLM
    class MockLLM:
        def invoke(self, messages):
            # 简单的模拟回复
            content = "您好！我是智能客服助手，很高兴为您服务。请问有什么可以帮助您的？"
            return AIMessage(content=content)
        
        def bind_tools(self, tools):
            return self
    
    _llm_instance = MockLLM()
    return _llm_instance
