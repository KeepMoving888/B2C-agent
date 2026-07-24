"""服务层包"""
from .llm_service import is_vllm_available, get_mode, chat_completion

__all__ = ["is_vllm_available", "get_mode", "chat_completion"]
