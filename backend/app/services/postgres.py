"""PostgreSQL 业务数据持久化

用途：
1. 会话记录持久化（审计 + 历史回溯）
2. 订单信息存储（供订单 Agent 查询）
3. 客户档案管理（VIP 识别、历史投诉）
4. 客服绩效统计（AI 解决率、转人工率、满意度）

设计要点：
- 连接池管理（psycopg2.pool.ThreadedConnectionPool）
- 连接失败不阻塞主流程，自动降级
- 所有写操作带 try/except，确保 PG 不可用时业务正常
"""
import threading
from typing import Optional
from loguru import logger

from app.config import settings

_pool = None
_available = False
_lock = threading.Lock()


def _init():
    global _pool, _available
    if _pool is not None:
        return
    with _lock:
        if _pool is not None:
            return
        try:
            import psycopg2
            from psycopg2 import pool
            _pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=settings.postgres_pool_size,
                host=settings.postgres_host,
                port=settings.postgres_port,
                dbname=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.postgres_password or None,
                connect_timeout=3,
            )
            _available = True
            logger.info(f"PostgreSQL 已连接: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
        except Exception as e:
            _available = False
            _pool = None
            logger.debug(f"PostgreSQL 不可用，降级至无持久化模式: {e}")


def is_available() -> bool:
    _init()
    return _available


def _get_conn():
    _init()
    if not _available:
        return None
    try:
        return _pool.getconn()
    except Exception:
        return None


def _put_conn(conn):
    if conn and _pool:
        try:
            _pool.putconn(conn)
        except Exception:
            pass


def _execute(sql: str, params: tuple = None, fetch: bool = False):
    """执行 SQL（内部工具函数）"""
    conn = _get_conn()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            result = cur.fetchall() if fetch else cur.rowcount
            conn.commit()
            return result
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.debug(f"SQL 执行失败: {e}")
        return None
    finally:
        _put_conn(conn)


# DDL：表结构
DDL_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS conversations (
        id SERIAL PRIMARY KEY,
        conv_id VARCHAR(64) UNIQUE NOT NULL,
        platform VARCHAR(32) NOT NULL,
        user_id VARCHAR(64),
        lang VARCHAR(8) DEFAULT \'zh\',
        status VARCHAR(16) DEFAULT \'active\',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        conv_id VARCHAR(64) NOT NULL,
        role VARCHAR(16) NOT NULL,
        content TEXT NOT NULL,
        intent VARCHAR(32),
        agent VARCHAR(32),
        lang VARCHAR(8),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        order_id VARCHAR(64) UNIQUE NOT NULL,
        platform VARCHAR(32) NOT NULL,
        customer_email VARCHAR(128),
        shipping_address TEXT,
        status VARCHAR(32) DEFAULT \'pending\',
        total_amount DECIMAL(10, 2),
        currency VARCHAR(8) DEFAULT \'USD\',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS customers (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(64) UNIQUE NOT NULL,
        email VARCHAR(128),
        name VARCHAR(64),
        vip_level INT DEFAULT 0,
        total_orders INT DEFAULT 0,
        total_spent DECIMAL(10, 2) DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS agent_handoffs (
        id SERIAL PRIMARY KEY,
        conv_id VARCHAR(64) NOT NULL,
        from_agent VARCHAR(32),
        to_agent VARCHAR(32),
        reason VARCHAR(64),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
]


def init_schema():
    """初始化数据库表结构"""
    if not is_available():
        return False
    for ddl in DDL_STATEMENTS:
        _execute(ddl)
    logger.info("PostgreSQL 表结构初始化完成")
    return True


def save_conversation(conv_id: str, platform: str, user_id: str = None, lang: str = "zh") -> bool:
    """创建/更新会话记录"""
    if not is_available():
        return False
    _execute(
        "INSERT INTO conversations (conv_id, platform, user_id, lang) VALUES (%s, %s, %s, %s) ON CONFLICT (conv_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP",
        (conv_id, platform, user_id, lang),
    )
    return True


def save_message(conv_id: str, role: str, content: str, intent: str = None,
                 agent: str = None, lang: str = "zh") -> bool:
    """持久化消息记录（审计用）"""
    if not is_available():
        return False
    _execute(
        "INSERT INTO messages (conv_id, role, content, intent, agent, lang) VALUES (%s, %s, %s, %s, %s, %s)",
        (conv_id, role, content, intent, agent, lang),
    )
    return True


def get_conversation_history(conv_id: str, limit: int = 20) -> list:
    """查询会话历史消息"""
    if not is_available():
        return []
    rows = _execute(
        "SELECT role, content, intent, agent, lang, created_at FROM messages WHERE conv_id = %s ORDER BY created_at DESC LIMIT %s",
        (conv_id, limit),
        fetch=True,
    )
    if not rows:
        return []
    return [{"role": r[0], "content": r[1], "intent": r[2], "agent": r[3],
             "lang": r[4], "created_at": r[5].isoformat() if r[5] else None} for r in rows]


def get_order(order_id: str) -> Optional[dict]:
    """查询订单信息（供订单 Agent 使用）"""
    if not is_available():
        return None
    rows = _execute(
        "SELECT order_id, platform, customer_email, shipping_address, status, total_amount, currency, created_at FROM orders WHERE order_id = %s",
        (order_id,),
        fetch=True,
    )
    if not rows:
        return None
    r = rows[0]
    return {"order_id": r[0], "platform": r[1], "customer_email": r[2],
            "shipping_address": r[3], "status": r[4], "total_amount": float(r[5]) if r[5] else None,
            "currency": r[6], "created_at": r[7].isoformat() if r[7] else None}


def update_order_status(order_id: str, status: str) -> bool:
    """更新订单状态"""
    if not is_available():
        return False
    _execute(
        "UPDATE orders SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE order_id = %s",
        (status, order_id),
    )
    return True


def record_handoff(conv_id: str, from_agent: str, to_agent: str, reason: str) -> bool:
    """记录 Agent 转交（审计 + 绩效统计）"""
    if not is_available():
        return False
    _execute(
        "INSERT INTO agent_handoffs (conv_id, from_agent, to_agent, reason) VALUES (%s, %s, %s, %s)",
        (conv_id, from_agent, to_agent, reason),
    )
    return True


def health_check() -> dict:
    return {
        "available": is_available(),
        "host": f"{settings.postgres_host}:{settings.postgres_port}",
        "db": settings.postgres_db,
    }
