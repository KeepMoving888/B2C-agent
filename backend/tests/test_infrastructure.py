"""企业级基础设施集成测试

覆盖 6 个服务客户端的降级行为：
- Redis: 不可用时返回 False，不抛异常
- PostgreSQL: 不可用时返回 False，不抛异常
- Elasticsearch: 不可用时返回空列表
- Kafka: 不可用时返回 False，不抛异常
- Jaeger: span 上下文不抛异常
- Celery: 应用对象可创建

确保所有外部依赖故障时系统优雅降级，核心功能可用。
"""
import pytest
from unittest.mock import patch, MagicMock


class TestRedisClient:
    """Redis 客户端降级测试"""

    def test_unavailable_returns_false_on_save(self):
        """Redis 不可用时 save_session_state 返回 False"""
        from app.services import redis_client
        with patch.object(redis_client, '_client', None):
            with patch.object(redis_client, 'is_available', return_value=False):
                assert redis_client.save_session_state("conv-1", {"k": "v"}) is False

    def test_unavailable_returns_none_on_load(self):
        """Redis 不可用时 load_session_state 返回 None"""
        from app.services import redis_client
        with patch.object(redis_client, '_client', None):
            with patch.object(redis_client, 'is_available', return_value=False):
                assert redis_client.load_session_state("conv-1") is None

    def test_health_check_unavailable(self):
        """Redis 不可用时 health_check 返回 available=False"""
        from app.services import redis_client
        with patch.object(redis_client, '_client', None):
            with patch.object(redis_client, 'is_available', return_value=False):
                result = redis_client.health_check()
                assert result["available"] is False


class TestPostgresClient:
    """PostgreSQL 客户端降级测试"""

    def test_unavailable_returns_false_on_save_message(self):
        """PG 不可用时 save_message 返回 False"""
        from app.services import postgres
        with patch.object(postgres, '_pool', None):
            with patch.object(postgres, 'is_available', return_value=False):
                assert postgres.save_message("conv-1", "user", "hello") is False

    def test_unavailable_returns_false_on_save_conversation(self):
        """PG 不可用时 save_conversation 返回 False"""
        from app.services import postgres
        with patch.object(postgres, '_pool', None):
            with patch.object(postgres, 'is_available', return_value=False):
                assert postgres.save_conversation("conv-1", "amazon") is False

    def test_health_check_unavailable(self):
        """PG 不可用时 health_check 返回 available=False"""
        from app.services import postgres
        with patch.object(postgres, '_pool', None):
            with patch.object(postgres, 'is_available', return_value=False):
                result = postgres.health_check()
                assert result["available"] is False


class TestElasticsearchClient:
    """Elasticsearch 客户端降级测试"""

    def test_unavailable_returns_empty_list(self):
        """ES 不可用时 search 返回空列表"""
        from app.services import es_client
        with patch.object(es_client, '_client', None):
            with patch.object(es_client, 'is_available', return_value=False):
                result = es_client.search("query text", lang="en", top_k=5)
                assert result == []

    def test_health_check_unavailable(self):
        """ES 不可用时 health_check 返回 available=False"""
        from app.services import es_client
        with patch.object(es_client, '_client', None):
            with patch.object(es_client, 'is_available', return_value=False):
                result = es_client.health_check()
                assert result["available"] is False


class TestKafkaClient:
    """Kafka 客户端降级测试"""

    def test_unavailable_publish_returns_false(self):
        """Kafka 不可用时 publish_customer_message 返回 False"""
        from app.services import kafka_client
        with patch.object(kafka_client, '_producer', None):
            with patch.object(kafka_client, 'is_available', return_value=False):
                assert kafka_client.publish_customer_message(
                    platform="amazon", conv_id="c1", message="hi", lang="en"
                ) is False

    def test_health_check_unavailable(self):
        """Kafka 不可用时 health_check 返回 available=False"""
        from app.services import kafka_client
        with patch.object(kafka_client, '_producer', None):
            with patch.object(kafka_client, 'is_available', return_value=False):
                result = kafka_client.health_check()
                assert result["available"] is False


class TestTracerClient:
    """Jaeger 链路追踪降级测试"""

    def test_span_context_no_exception(self):
        """Jaeger 不可用时 span 上下文不抛异常"""
        from app.services import tracer
        with tracer.span("test.operation", {"key": "value"}):
            pass  # 不应抛异常

    def test_health_check(self):
        """health_check 返回字典结构"""
        from app.services import tracer
        result = tracer.health_check()
        assert isinstance(result, dict)
        assert "available" in result


class TestCeleryApp:
    """Celery 异步任务应用测试"""

    def test_module_importable(self):
        """Celery 模块可正常导入"""
        from app.services import celery_app
        assert hasattr(celery_app, 'get_app')
        assert hasattr(celery_app, 'is_available')
        assert hasattr(celery_app, 'run_async')

    def test_health_check_structure(self):
        """health_check 返回字典结构且包含必要字段"""
        from app.services.celery_app import health_check
        result = health_check()
        assert isinstance(result, dict)
        assert "available" in result
        assert "broker" in result
        assert "backend" in result

    def test_run_async_fallback_sync(self):
        """Celery 不可用时 run_async 同步执行函数"""
        from app.services import celery_app
        with patch.object(celery_app, 'is_available', return_value=False):
            result = celery_app.run_async(lambda x: x * 2, 5)
            assert result == 10
