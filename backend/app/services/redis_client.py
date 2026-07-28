"""Redis 缓存服务

用途：
1. 多轮对话状态管理（按 conv_id 缓存最近 N 轮上下文）
2. 热点知识缓存（高频 FAQ 命中后缓存，降低 Milvus 查询压力）
3. 分布式限流（按 user_id 限制 QPS，防止恶意刷量）

设计要点：
- 连接失败不阻塞主流程，自动降级（返回 None / 空列表）
- 所有操作带 try/except，确保 Redis 不可用时业务正常
- key 命名规范：cs:{domain}:{id}
"""
import json
from typing import Optional
from loguru import logger

from app.config import settings

_client = None
_available = False


def _init():
    global _client, _available
    if _client is not None:
        return
    try:
        import redis
        _client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            db=settings.redis_db,
            socket_timeout=2,
            socket_connect_timeout=2,
            decode_responses=True,
        )
        _client.ping()
        _available = True
        logger.info(f"Redis 已连接: {settings.redis_host}:{settings.redis_port}")
    except Exception as e:
        _available = False
        _client = None
        logger.debug(f"Redis 不可用，降级至无缓存模式: {e}")


def is_available() -> bool:
    _init()
    return _available


def _key(domain: str, uid: str) -> str:
    return f"cs:{domain}:{uid}"


def save_session_state(conv_id: str, state: dict, ttl: int = None) -> bool:
    """缓存会话状态（多轮对话上下文）"""
    if not is_available():
        return False
    try:
        key = _key("session", conv_id)
        _client.setex(key, ttl or settings.redis_session_ttl, json.dumps(state, ensure_ascii=False))
        return True
    except Exception as e:
        logger.debug(f"Redis 会话缓存失败: {e}")
        return False


def load_session_state(conv_id: str) -> Optional[dict]:
    """读取会话状态"""
    if not is_available():
        return None
    try:
        data = _client.get(_key("session", conv_id))
        return json.loads(data) if data else None
    except Exception:
        return None


def delete_session_state(conv_id: str) -> bool:
    """删除会话状态（会话结束时清理）"""
    if not is_available():
        return False
    try:
        _client.delete(_key("session", conv_id))
        return True
    except Exception:
        return False


def cache_knowledge(query_hash: str, docs: list, ttl: int = 300) -> bool:
    """缓存 RAG 检索结果（高频查询加速）"""
    if not is_available():
        return False
    try:
        _client.setex(_key("kb", query_hash), ttl, json.dumps(docs, ensure_ascii=False))
        return True
    except Exception:
        return False


def get_cached_knowledge(query_hash: str) -> Optional[list]:
    """读取缓存的知识检索结果"""
    if not is_available():
        return None
    try:
        data = _client.get(_key("kb", query_hash))
        return json.loads(data) if data else None
    except Exception:
        return None


def check_rate_limit(user_id: str, max_qps: int = 10, window: int = 1) -> bool:
    """滑动窗口限流

    Returns:
        True 允许通过，False 被限流
    """
    if not is_available():
        return True
    try:
        key = _key("rate", user_id)
        pipe = _client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        count, _ = pipe.execute()
        return count <= max_qps
    except Exception:
        return True


def health_check() -> dict:
    return {
        "available": is_available(),
        "host": f"{settings.redis_host}:{settings.redis_port}",
        "db": settings.redis_db,
    }
