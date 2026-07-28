"""Jaeger 全链路追踪

用途：
- 每个 Agent 调用节点可可视化定位路由瓶颈
- trace 覆盖：消息接入 → 意图识别 → RAG检索 → Agent路由 → 回复生成 → 翻译输出
- 采样率可配置（生产环境建议 0.1）

设计要点：
- 基于 opentelemetry-sdk，通过 OTLP 上报至 Jaeger
- 连接失败自动降级（trace 丢弃，不影响业务）
- span 命名规范：{service}.{operation}
"""
from contextlib import contextmanager
from typing import Generator
from loguru import logger

from app.config import settings

_tracer = None
_available = False


def _init():
    """初始化 OpenTelemetry tracer"""
    global _tracer, _available
    if _tracer is not None:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": settings.jaeger_service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(
            endpoint=f"{settings.jaeger_agent_host}:{settings.jaeger_agent_port}",
            insecure=True,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(__name__)
        _available = True
        logger.info(f"Jaeger 追踪已启用: {settings.jaeger_service_name}")
    except Exception as e:
        _available = False
        _tracer = None
        logger.debug(f"Jaeger 不可用，降级至无追踪模式: {e}")


def is_available() -> bool:
    _init()
    return _available


@contextmanager
def span(operation: str, attributes: dict = None) -> Generator:
    """创建追踪 span（上下文管理器）

    用法：
        with tracer.span("rag.retrieve", {"query": q}):
            docs = retrieve(q)
    """
    if not is_available() or _tracer is None:
        yield
        return

    with _tracer.start_as_current_span(operation) as s:
        if attributes:
            for k, v in attributes.items():
                try:
                    s.set_attribute(k, str(v)[:1024])
                except Exception:
                    pass
        try:
            yield
        except Exception as e:
            s.set_attribute("error", True)
            s.set_attribute("error.message", str(e)[:512])
            raise


def trace_call(operation: str, attributes: dict = None):
    """函数装饰器：自动追踪函数调用"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with span(operation, attributes):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def health_check() -> dict:
    return {
        "available": is_available(),
        "service_name": settings.jaeger_service_name,
        "agent_host": f"{settings.jaeger_agent_host}:{settings.jaeger_agent_port}",
        "sampling_rate": settings.jafer_sampling_rate,
    }
