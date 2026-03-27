"""Supervisor 路由节点 - 意图识别与任务分配（性能优化版）"""

import json
import time
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from src.agents.base import get_llm
from src.config.constants import INTENT_TO_AGENT

# 意图识别缓存（性能优化）
_intent_cache = {}
_cache_ttl = 300  # 5分钟缓存

# 路由节点提示词
ROUTING_PROMPT = """You are a customer service intent router for a cross-border CarPlay e-commerce company.

Based on the user's message, identify the PRIMARY intent. Reply with a JSON object only:
{
  "intent": "<one of: product_inquiry, price_discount, faq, order_status, logistics_tracking, shipping_info, return_exchange, refund, complaint, policy_compliance, platform_rules, warranty, complex_escalation>",
  "confidence": 0.0-1.0,
  "key_entities": {"order_id": "", "tracking_number": "", "product_sku": "", "user_id": ""}
}

If the request is unclear, ambiguous, or involves multiple conflicting issues, use "complex_escalation".
Extract any order_id, tracking_number, product_sku, user_id from the message into key_entities."""

# 意图复杂度映射
INTENT_COMPLEXITY = {
    "product_inquiry": 0.3,      # 简单     # 产品咨询
    "price_discount": 0.3,       # 简单     # 价格咨询
    "faq": 0.2,                  # 简单     # 常见问题
    "order_status": 0.4,         # 中等     # 订单状态
    "logistics_tracking": 0.4,   # 中等     # 物流跟踪
    "shipping_info": 0.4,        # 中等     # 配送信息
    "return_exchange": 0.7,      # 复杂     # 退货换货
    "refund": 0.8,               # 复杂     # 退款
    "complaint": 0.9,            # 复杂     # 投诉
    "policy_compliance": 0.6,     # 中等     # 政策合规
    "platform_rules": 0.6,        # 中等     # 平台规则
    "warranty": 0.5,             # 中等     # 售后保修
    "complex_escalation": 1.0     # 最复杂     # 复杂问题升级处理   
}


def calculate_task_complexity(messages: list[BaseMessage]) -> float:
    """计算任务复杂度，返回 0.0-1.0 的分数"""
    # 获取最后一条用户消息
    last_user_message = None
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            last_user_message = m.content
            break
    
    if not last_user_message:
        return 0.3  # 默认中等复杂度
    
    # 1. 基于消息长度的复杂度
    message_length = len(last_user_message)
    length_complexity = min(message_length / 500, 1.0)  # 超过500字符视为复杂
    
    # 2. 基于意图的复杂度
    intent = route_intent(messages)
    intent_complexity = INTENT_COMPLEXITY.get(intent, 0.5)
    
    # 3. 基于关键词的复杂度
    complex_keywords = [
        "refund", "return", "exchange", "complaint", "dispute",
        "warranty", "policy", "legal", "problem", "issue",
        "delay", "missing", "damaged", "broken", "error"
    ]
    # 关键词复杂度
    keyword_complexity = 0.0
    message_lower = last_user_message.lower()
    for keyword in complex_keywords:
        if keyword in message_lower:
            keyword_complexity += 0.1
    keyword_complexity = min(keyword_complexity, 1.0)
    
    # 4. 综合计算复杂度
    total_complexity = (
        length_complexity * 0.2 +
        intent_complexity * 0.5 +
        keyword_complexity * 0.3
    )
    
    return min(total_complexity, 1.0)

# 意图识别节点（带缓存）
def route_intent(messages: list[BaseMessage]) -> str:
    """根据用户消息识别意图，返回目标 Agent 名称（带缓存）"""
    # 获取最后一条用户消息作为缓存键
    last_user = None
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            last_user = m.content
            break
    
    if not last_user:
        return "consultation"
    
    # 检查缓存
    cache_key = last_user[:100]  # 用前100字符作为缓存键
    current_time = time.time()
    
    if cache_key in _intent_cache:
        cached_intent, cached_time = _intent_cache[cache_key]
        if current_time - cached_time < _cache_ttl:
            return cached_intent
    
    llm = get_llm()
    sys = SystemMessage(content=ROUTING_PROMPT)
    
    start_time = time.time()
    
    # 减少重试次数，缩短退避时间
    max_retries = 1  # 进一步减少重试次数
    for attempt in range(max_retries):
        try:
            response = llm.invoke([sys, HumanMessage(content=str(last_user))])
            text = response.content if hasattr(response, "content") else str(response)
            try:
                raw = text.strip().strip("`")
                if "json" in raw[:10].lower():
                    raw = raw.split("\n", 1)[-1]
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(raw[start:end])
                    intent = data.get("intent", "faq")
                    result = INTENT_TO_AGENT.get(intent, "consultation")
                    # 缓存结果
                    _intent_cache[cache_key] = (result, current_time)
                    end_time = time.time()
                    print(f"意图识别耗时: {end_time - start_time:.2f}秒")
                    return result
            except Exception as e:
                print(f"解析响应失败: {e}")
                
                # 解析失败时继续重试
        except Exception as e:
            print(f"API调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(0.5)  # 进一步缩短退避时间
            else:
                # 最后一次尝试失败，返回默认值并缓存
                result = "consultation"
                _intent_cache[cache_key] = (result, current_time)
                end_time = time.time()
                print(f"意图识别耗时: {end_time - start_time:.2f}秒 (使用默认)")
                return result
    
    # 默认返回
    result = "consultation"
    _intent_cache[cache_key] = (result, current_time)
    return result
