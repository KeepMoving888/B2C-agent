"""国内大模型实现（性能优化版）"""

import requests
import json
from typing import Optional, Dict, Any, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ChatMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.load.serializable import Serializable
from pydantic import Field


_request_session = None

# 获取HTTP会话（模块级别单例）
def get_request_session():
    """获取HTTP会话（模块级别单例 - 连接复用）"""
    global _request_session
    if _request_session is None:
        _request_session = requests.Session()
        _request_session.headers.update({"Content-Type": "application/json"})
        # 连接池配置优化
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=1,
        )
        _request_session.mount("https://", adapter)
    return _request_session

# Qwen大模型实现
class ChatQwen(BaseChatModel, Serializable):
    """Qwen大模型实现（性能优化版）"""
    
    qwen_api_key: str = Field(..., description="Qwen API密钥")
    model: str = Field(default="qwen-plus", description="模型名称")
    temperature: float = Field(default=0.3, description="温度参数")
    timeout: int = Field(default=15, description="超时时间（优化为15秒）")
    
    @property
    def _llm_type(self) -> str:
        """LLM类型"""
        return "qwen"
    
    def _generate(self, messages: List[BaseMessage], **kwargs) -> ChatResult:
        """生成回复（性能优化版）"""
        
        # 构建请求消息（优化：只取最近2轮对话）
        chat_messages = []
        recent_messages = messages[-4:] if len(messages) > 4 else messages
        for msg in recent_messages:
            if isinstance(msg, HumanMessage):
                chat_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                chat_messages.append({"role": "assistant", "content": msg.content})
        
        # 调用API
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.qwen_api_key}"
        }
        payload = {
            "model": self.model,
            "input": {
                "messages": chat_messages
            },
            "parameters": {
                "temperature": self.temperature,
                "max_tokens": 512  # 优化：减少Token数量
            }
        }
        
        try:
            session = get_request_session()
            response = session.post(url, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            
            # 解析响应
            if "output" in result and "text" in result["output"]:
                content = result["output"]["text"]
                chat_message = ChatMessage(role="assistant", content=content)
                generation = ChatGeneration(message=chat_message)
                return ChatResult(generations=[generation])
            else:
                raise ValueError(f"Invalid response format: {result}")
        except Exception as e:
            raise RuntimeError(f"Qwen API call failed: {str(e)}")
