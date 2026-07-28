# 微服务部署方案设计

## 1. 架构概览

本系统采用模块化单体（Modular Monolith）作为默认部署形态，同时提供微服务拆分方案，支持按业务规模平滑演进。

```
                    ┌─────────────────────────────────────────┐
                    │              API 网关 (Nginx)            │
                    │   路由分发 / 限流 / TLS 终止 / CORS      │
                    └──────┬──────────┬──────────┬─────────────┘
                           │          │          │
              ┌────────────▼──┐ ┌─────▼──────┐ ┌─▼──────────────┐
              │  会话服务      │ │ RAG 检索   │ │  Agent 编排    │
              │  (cs-chat)     │ │ (cs-rag)   │ │  (cs-agent)    │
              │  FastAPI:8001  │ │ :8002      │ │  :8003         │
              └───────┬────────┘ └─────┬──────┘ └───────┬────────┘
                      │                │                 │
              ┌───────▼────────────────▼─────────────────▼──────┐
              │              消息总线 (Kafka)                     │
              │  customer-messages / agent-replies / handoff     │
              └───────┬────────────────┬─────────────────────────┘
                      │                │
              ┌───────▼──────┐ ┌───────▼────────┐
              │ 翻译服务      │ │ 异步任务服务    │
              │ (cs-translate)│ │ (cs-worker)    │
              │ :8004         │ │ Celery         │
              └───────────────┘ └────────────────┘
```

## 2. 服务拆分

| 服务名 | 职责 | 端口 | 技术栈 | 可独立部署 |
|--------|------|------|--------|-----------|
| cs-gateway | API 网关，路由分发、限流、TLS | 80 | Nginx | ✅ |
| cs-chat | 会话管理、WebSocket 推送、消息收发 | 8001 | FastAPI | ✅ |
| cs-agent | 多智能体编排（LangGraph 状态图） | 8002 | FastAPI + LangGraph | ✅ |
| cs-rag | 知识库检索（向量+BM25+ES 三路融合） | 8003 | FastAPI + Milvus | ✅ |
| cs-translate | 多语言翻译（DeepSeek/LLM） | 8004 | FastAPI | ✅ |
| cs-worker | 异步任务（索引构建、报表、通知） | - | Celery + Redis | ✅ |

## 3. 服务间通信

### 3.1 同步调用（gRPC / HTTP）

```
cs-chat ──HTTP──> cs-agent ──HTTP──> cs-rag
                                  └──HTTP──> cs-translate
```

- 会话服务收到客户消息后，同步调用 Agent 编排服务
- Agent 编排服务内部调用 RAG 检索和翻译服务
- 超时设置：Agent 编排 30s，RAG 检索 5s，翻译 10s

### 3.2 异步消息（Kafka）

| Topic | 生产者 | 消费者 | 用途 |
|-------|--------|--------|------|
| customer-messages | cs-gateway | cs-chat | 多平台消息接入削峰 |
| agent-replies | cs-chat | cs-gateway | Agent 回复推送 |
| human-handoff | cs-agent | cs-chat | 人工转交事件 |
| rag-eval-events | cs-rag | cs-worker | RAG 质量评估异步处理 |

### 3.3 服务发现

- **开发环境**：环境变量配置（`.env`）
- **生产环境**：Consul / Nacos 服务注册中心
- **K8s 环境**：CoreDNS + Service 资源

## 4. 数据存储分配

| 存储组件 | 使用服务 | 用途 |
|---------|---------|------|
| Milvus | cs-rag | 向量索引（知识库语义检索） |
| Elasticsearch | cs-rag | BM25 稀疏检索（跨语言关键词匹配） |
| PostgreSQL | cs-chat, cs-agent | 会话记录、订单数据、转交事件 |
| Redis | cs-chat, cs-worker | 会话状态缓存、Celery broker |
| Kafka | 全部 | 异步消息总线 |

## 5. 部署形态对比

### 5.1 单体部署（默认，适合开发与小规模）

```bash
# 单进程启动全部功能
python main.py

# 或 Docker Compose 一键启动
docker-compose up -d
```

- 优点：部署简单、调试方便、无网络开销
- 适用：日请求量 < 10万、单机资源充足

### 5.2 微服务部署（适合生产与大规模）

```bash
# 每个服务独立构建镜像
docker build -t cs-chat:latest -f deploy/docker/chat.Dockerfile .
docker build -t cs-agent:latest -f deploy/docker/agent.Dockerfile .
docker build -t cs-rag:latest -f deploy/docker/rag.Dockerfile .

# 按需启动
docker-compose -f deploy/docker-compose.microservices.yml up -d
```

- 优点：独立扩缩容、故障隔离、技术栈灵活
- 适用：日请求量 > 10万、多团队协作

### 5.3 Kubernetes 部署（大规模生产）

```yaml
# deploy/k8s/chat-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cs-chat
spec:
  replicas: 3
  selector:
    matchLabels:
      app: cs-chat
  template:
    spec:
      containers:
        - name: cs-chat
          image: cs-chat:latest
          resources:
            requests: { cpu: "500m", memory: "512Mi" }
            limits: { cpu: "1000m", memory: "1Gi" }
          livenessProbe:
            httpGet: { path: /health, port: 8001 }
          readinessProbe:
            httpGet: { path: /health, port: 8001 }
```

- 优点：自动扩缩容、滚动更新、自愈能力
- 适用：多集群、跨可用区高可用

## 6. 弹性设计

### 6.1 全链路降级策略

| 组件故障 | 降级策略 | 影响 |
|---------|---------|------|
| Milvus 不可用 | 回退内存向量检索（关键词相似度） | 召回率下降，功能正常 |
| Elasticsearch 不可用 | 跳过 BM25 路，仅向量+内存检索 | 召回率下降 15% |
| PostgreSQL 不可用 | 跳过持久化，仅内存处理 | 无审计记录 |
| Redis 不可用 | 跳过缓存，每次全量检索 | 响应延迟增加 |
| Kafka 不可用 | 同步处理，跳过削峰 | 高并发时可能阻塞 |
| LLM API 不可用 | 回退规则引擎 + 关键词翻译 | 回复质量下降 |
| Jaeger 不可用 | 跳过链路追踪 | 无 trace 可视化 |

### 6.2 熔断与限流

- **熔断**：连续 5 次调用失败 → 熔断 30 秒 → 半开探测
- **限流**：Redis 分布式限流（QPS 机制），单 IP 5 QPS，全局 50 QPS
- **超时**：Agent 编排 30s，RAG 5s，翻译 10s，LLM 15s

### 6.3 健康检查

```
GET /health
{
  "status": "ok",
  "mode": "deepseek",
  "infrastructure": {
    "redis": {"available": true, "latency_ms": 2},
    "postgres": {"available": true, "latency_ms": 5},
    "elasticsearch": {"available": false, "reason": "connection refused"},
    "kafka": {"available": false, "reason": "no module"},
    "jaeger": {"available": false, "reason": "no module"}
  }
}
```

## 7. 可观测性

| 维度 | 工具 | 指标 |
|------|------|------|
| Metrics | Prometheus + Grafana | QPS、延迟、错误率、RAG 召回率 |
| Logging | Loguru → ELK | 结构化日志，按 trace_id 串联 |
| Tracing | Jaeger | 全链路 trace（消息接入→Agent→RAG→翻译） |
| Alerting | Alertmanager | 错误率 > 5%、延迟 P99 > 5s |

## 8. 演进路径

```
阶段1: 单体部署（当前）
  ↓ 日请求量 > 5万
阶段2: RAG 服务独立部署（检索压力分离）
  ↓ 日请求量 > 10万
阶段3: Agent 编排独立部署（计算压力分离）
  ↓ 日请求量 > 50万
阶段4: 全微服务 + K8s（按服务独立扩缩容）
```
