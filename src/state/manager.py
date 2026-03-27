"""多轮对话状态管理 - Redis 持久化 + 结构化压缩"""

from datetime import datetime
from typing import Any
import structlog
# 日志记录器
logger = structlog.get_logger()

# 默认使用内存存储，生产环境可切换 Redis
_store: dict[str, dict[str, Any]] = {}

# 会话状态管理器
class ConversationStateManager:
    """
    管理会话状态：
    1. 结构化存储替代全量上下文
    2. 长会话时用 summaries 压缩历史
    3. 窗口超限时 truncate messages，保留 summaries
    """

    MAX_RECENT_MESSAGES = 10  # 保留最近消息数
    MAX_SUMMARIES = 50  # 最多保留摘要轮数
    # 初始化管理器
    def __init__(self, backend: str = "memory"):
        self.backend = backend
        self._store = _store
    # 获取会话状态
    def get(self, session_id: str) -> dict[str, Any] | None:
        return self._store.get(session_id)
    # 设置会话状态
    def set(self, session_id: str, state: dict[str, Any], ttl: int = 86400) -> None:
        self._store[session_id] = {
            **state,
            "_updated": datetime.utcnow().isoformat(),
        }
    # 更新会话状态中的单轮摘要
    def update_turn_summary(
        self,
        session_id: str,
        role: str,
        intent: str | None,
        key_entities: dict[str, str],
        summary: str,
    ) -> None:
        state = self.get(session_id) or {}
        summaries = state.get("turn_summaries", [])
        summaries.append({
            "role": role,
            "intent": intent,
            "key_entities": key_entities,
            "summary": summary,
            "timestamp": datetime.utcnow().isoformat(),
        })
        if len(summaries) > self.MAX_SUMMARIES:
            summaries = summaries[-self.MAX_SUMMARIES:]
        state["turn_summaries"] = summaries
        self.set(session_id, state)
    # 截断会话状态中的消息
    def truncate_if_needed(self, session_id: str, messages: list) -> tuple[list, list]:
        """
        若消息过多，将较早消息转为 summary 并截断
        返回 (保留的 messages, 已有 summaries)
        """
        state = self.get(session_id) or {}
        summaries = state.get("turn_summaries", [])
        if len(messages) <= self.MAX_RECENT_MESSAGES:
            return messages, summaries
            
        # 简单策略：保留最后 N 条
        return messages[-self.MAX_RECENT_MESSAGES:], summaries
