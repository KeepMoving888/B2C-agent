"""Celery 异步任务队列

用途：
1. 知识库索引构建（首次启动或 FAQ 更新后批量索引）
2. 批量翻译（多语言 FAQ 同步翻译）
3. 报表生成（每日/每周客服绩效报表）
4. 邮件/短信通知（转人工后通知客服）

设计要点：
- broker 用 Redis（与缓存共用，DB 隔离）
- 连接失败不阻塞主流程，任务降级为同步执行
- 所有任务幂等设计，支持重试
"""
from typing import Optional
from loguru import logger

from app.config import settings

_app = None
_available = False


def _init():
    """懒加载 Celery 应用"""
    global _app, _available
    if _app is not None:
        return
    try:
        from celery import Celery
        _app = Celery(
            "cs_agent",
            broker=settings.celery_broker_url,
            backend=settings.celery_result_backend,
        )
        _app.conf.update(
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            timezone="Asia/Shanghai",
            enable_utc=True,
            task_time_limit=settings.celery_task_time_limit,
            task_soft_time_limit=settings.celery_task_time_limit - 30,
            task_acks_late=True,
            worker_prefetch_multiplier=1,
        )
        _available = True
        logger.info(f"Celery 已初始化: broker={settings.celery_broker_url}")
    except Exception as e:
        _available = False
        _app = None
        logger.debug(f"Celery 不可用，任务将同步执行: {e}")


def is_available() -> bool:
    _init()
    return _available


def get_app():
    """获取 Celery 应用实例（供 worker 进程使用）"""
    _init()
    return _app


def task_build_knowledge_index():
    """异步构建知识库索引（装饰器方式定义）"""
    def decorator(func):
        if is_available():
            return _app.task(bind=True, max_retries=3, default_retry_delay=60)(func)
        return func
    return decorator


def task_batch_translate():
    """异步批量翻译任务"""
    def decorator(func):
        if is_available():
            return _app.task(bind=True, max_retries=2, default_retry_delay=30)(func)
        return func
    return decorator


def task_generate_report():
    """异步生成报表"""
    def decorator(func):
        if is_available():
            return _app.task(bind=True, max_retries=2, default_retry_delay=120)(func)
        return func
    return decorator


def run_async(func, *args, **kwargs):
    """执行任务：Celery 可用时异步派发，不可用时同步执行

    Args:
        func: 任务函数
        *args, **kwargs: 任务参数

    Returns:
        Celery 可用：AsyncResult（异步结果）
        Celery 不可用：函数同步执行结果
    """
    if is_available():
        try:
            return func.delay(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Celery 派发失败，降级同步执行: {e}")
    return func(*args, **kwargs)


def health_check() -> dict:
    return {
        "available": is_available(),
        "broker": settings.celery_broker_url,
        "backend": settings.celery_result_backend,
    }
