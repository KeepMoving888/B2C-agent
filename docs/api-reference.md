# API 接口文档

## 基础信息

- **Base URL**: `http://localhost:8000`
- **交互式文档**: `http://localhost:8000/docs` (Swagger UI)
- **ReDoc 文档**: `http://localhost:8000/redoc`

## 接口列表

### 1. 健康检查

`GET /health`

**响应**：
```json
{
  "status": "ok",
  "mode": "vllm",  // vllm / rule
  "version": "1.0.0"
}
```

---

### 2. 多智能体会话

`POST /api/chat`

调用 LangGraph 多智能体编排处理客服消息。

**请求**：
```json
{
  "platform": "amazon",
  "lang": "en",
  "message": "您好，请帮我查一下订单物流状态",
  "conv_id": "c-amazon-001",
  "history": [
    {"role": "user", "content": "Hi, I haven't received my order"},
    {"role": "assistant", "content": "Hello, let me check for you..."}
  ]
}
```

**响应**：
```json
{
  "reply": "Hello! I've checked your order status...",
  "reply_zh": "您好！我已为您查询订单状态...",
  "agent": "订单Agent",
  "route": "条件路由：意图=物流查询 → 订单Agent",
  "intent": "物流查询",
  "sentiment": {"joy": 40, "neutral": 50, "negative": 10},
  "sources": [
    {"id": "faq_001", "content": "标准配送时效...", "category": "物流查询", "score": 0.85}
  ]
}
```

---

### 3. AI 建议回复

`POST /api/suggest`

根据上下文生成 AI 建议回复。

**请求**：
```json
{
  "platform": "amazon",
  "lang": "en",
  "conv_id": "c-amazon-001",
  "history": [...]
}
```

**响应**：
```json
{
  "text": "Hello! I've checked your order. It's currently in transit..."
}
```

---

### 4. 多语言翻译

`POST /api/translate`

**请求**：
```json
{
  "text": "您好，请问有什么可以帮您？",
  "from_lang": "zh",
  "to_lang": "en"
}
```

**响应**：
```json
{
  "text": "您好，请问有什么可以帮您？",
  "translated": "Hello, how may I help you?"
}
```

**支持语言**：zh, en, ja, de, es, fr, it, pt

---

### 5. 统计数据

`GET /api/stats?platform=amazon`

**响应**：
```json
{
  "conversations": 326,
  "avg_response_sec": 3,
  "satisfaction": 96,
  "ai_ratio": 78
}
```

---

### 6. WebSocket 实时会话

`WS /ws`

双向实时通信，支持流式输出。

**客户端发送**：
```json
{
  "platform": "amazon",
  "lang": "en",
  "message": "When will my order arrive?",
  "history": [...],
  "conv_id": "c-amazon-001"
}
```

**服务端返回**：
```json
{
  "type": "reply",
  "reply": "Your order is in transit...",
  "reply_zh": "您的订单正在配送中...",
  "agent": "订单Agent",
  "route": "条件路由：意图=物流查询 → 订单Agent",
  "intent": "物流查询"
}
```

## 错误处理

所有接口遵循统一错误格式：

```json
{
  "detail": "错误描述"
}
```

| HTTP 状态码 | 说明 |
|------------|------|
| 200 | 成功 |
| 422 | 请求参数校验失败 |
| 500 | 服务内部错误 |

## 降级行为

- vLLM 不可用时：自动回退至规则引擎模式，`mode=rule`
- Milvus 不可用时：自动回退至内存检索
- 所有接口保证可用，不会因依赖缺失而报错
