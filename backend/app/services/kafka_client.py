"""Kafka 多平台消息接入层

用途：
- 异步接收 Amazon/WhatsApp/Shopify/AliExpress/Shopee 等5大平台消息
- 削峰填谷，支撑旺季高并发（Kafka 消费者按组消费）
- 统一消息格式，屏蔽各平台 webhook 差异

设计要点：
- 生产者：webhook 接收后立即写入 Kafka（快速响应）
- 消费者：后台 worker 消费消息，调用多智能体处理
- 连接失败自动降级至同步处理模式

Topic 设计：
- customer-messages: 客户消息（入站）
- agent-replies: Agent 回复（出站）
- human-handoff: 转人工事件
"""
import json
import threading
import time
from typing import Optional, Callable
from loguru import logger

from app.config import settings

_producer = None
_available = False
_consumers = []
_lock = threading.Lock()


def _init():
    global _producer, _available
    if _producer is not None:
        return
    try:
        from kafka import KafkaProducer
        _producer = KafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks=1,
            retries=0,
            request_timeout_ms=5000,
            api_version_auto_timeout_ms=3000,
        )
        _available = True
        logger.info(f"Kafka 已连接: {settings.kafka_bootstrap_servers}")
    except Exception as e:
        _available = False
        _producer = None
        logger.debug(f"Kafka 不可用，降级至同步处理模式: {e}")


def is_available() -> bool:
    _init()
    return _available


def publish_message(topic: str, key: str, value: dict) -> bool:
    """发布消息到 Kafka"""
    if not is_available():
        return False
    try:
        _producer.send(topic, key=key, value=value)
        _producer.flush(timeout=2)
        return True
    except Exception as e:
        logger.debug(f"Kafka 发布失败: {e}")
        return False


def publish_customer_message(platform: str, conv_id: str, message: str,
                              lang: str = "zh", user_id: str = None) -> bool:
    """发布客户消息到 customer-messages topic"""
    return publish_message(
        settings.kafka_topic_customer_msg,
        conv_id,
        {"platform": platform, "conv_id": conv_id, "message": message,
         "lang": lang, "user_id": user_id, "timestamp": time.time()},
    )


def publish_agent_reply(conv_id: str, reply: str, agent: str,
                         intent: str = None, lang: str = "zh") -> bool:
    """发布 Agent 回复到 agent-replies topic"""
    return publish_message(
        settings.kafka_topic_agent_reply,
        conv_id,
        {"conv_id": conv_id, "reply": reply, "agent": agent,
         "intent": intent, "lang": lang, "timestamp": time.time()},
    )


def publish_handoff(conv_id: str, from_agent: str, to_agent: str, reason: str) -> bool:
    """发布转人工事件到 human-handoff topic"""
    return publish_message(
        settings.kafka_topic_handoff,
        conv_id,
        {"conv_id": conv_id, "from_agent": from_agent, "to_agent": to_agent,
         "reason": reason, "timestamp": time.time()},
    )


def start_consumer(topic: str, group_id: str, handler: Callable[[dict], None],
                   poll_timeout_ms: int = 1000) -> Optional[threading.Thread]:
    """启动 Kafka 消费者线程

    Args:
        topic: 消费的主题
        group_id: 消费者组 ID
        handler: 消息处理回调函数（接收 dict 参数）
        poll_timeout_ms: 轮询超时（毫秒）

    Returns:
        消费者线程对象（None 表示启动失败）
    """
    if not is_available():
        return None

    def _consume():
        try:
            from kafka import KafkaConsumer
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id=group_id,
                auto_offset_reset=settings.kafka_auto_offset_reset,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                consumer_timeout_ms=poll_timeout_ms * 10,
                enable_auto_commit=True,
            )
            logger.info(f"Kafka 消费者启动: topic={topic} group={group_id}")
            for msg in consumer:
                try:
                    handler(msg.value)
                except Exception as e:
                    logger.error(f"Kafka 消息处理失败: {e}")
        except Exception as e:
            logger.error(f"Kafka 消费者异常: {e}")

    thread = threading.Thread(target=_consume, daemon=True, name=f"kafka-{topic}")
    thread.start()
    with _lock:
        _consumers.append(thread)
    return thread


def health_check() -> dict:
    return {
        "available": is_available(),
        "bootstrap_servers": settings.kafka_bootstrap_servers,
        "topics": [
            settings.kafka_topic_customer_msg,
            settings.kafka_topic_agent_reply,
            settings.kafka_topic_handoff,
        ],
    }
