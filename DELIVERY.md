# 跨境电商智能客服系统 - 交付文档

## 📦 项目概览

### 项目名称
跨境电商智能客服系统（B2C Agent）

### 项目类型
基于 LangGraph 的多 Agent 智能客服系统，专为跨境电商场景设计

### 核心功能
- **多平台支持**：Amazon、Shopify、官网
- **多语言支持**：中文、英文、西班牙语、德语、法语、日语、泰语、越南语
- **智能路由**：自动识别用户意图，分配到对应专业 Agent
- **FAQ 秒回**：常见问题毫秒级响应
- **流式输出**：实时打字效果，提升用户体验
- **国内大模型**：支持 qwen 大模型作为 GPT 替代方案
- **性能优化**：响应时间 < 2 秒

### 技术栈
- **后端**：Python 3.11, Flask, LangGraph, LangChain
- **前端**：HTML5, CSS3, JavaScript
- **AI 模型**：支持 OpenAI, Anthropic, 国内大模型 (qwen)
- **向量数据库**：支持 ChromaDB, Pinecone, Milvus, FAISS
- **部署**：Docker, Kubernetes, 云服务器

---

## 🚀 部署选项

### 1. 本地开发环境

**适用场景**：开发测试、功能验证

**部署步骤**：
1. 安装 Python 3.11+
2. 创建虚拟环境：`python -m venv venv`
3. 激活环境：`venv\Scripts\activate`（Windows）或 `source venv/bin/activate`（Linux/Mac）
4. 安装依赖：`pip install -r requirements.txt`
5. 配置环境变量：复制 `.env.example` 为 `.env` 并填写 QWEN_API_KEY
6. 启动服务：`python src/app.py`
7. 访问：http://localhost:5000

### 2. 云服务器部署

**适用场景**：生产环境、正式上线

**推荐配置**：
- 云服务商：阿里云、腾讯云、华为云
- 系统：Ubuntu 22.04 LTS
- 配置：2核4G内存以上
- 带宽：1Mbps以上

**部署方式**：
- **方案 A**：直接运行（推荐，简单）
- **方案 B**：Docker 部署（隔离性好）
- **方案 C**：Kubernetes 部署（高可用）

### 3. Docker 部署

**适用场景**：快速部署、环境隔离

**部署步骤**：
1. 安装 Docker 和 docker-compose
2. 配置 Docker 国内镜像源
3. 克隆项目：`git clone https://github.com/your-username/b2c-agent.git`
4. 配置环境变量：复制 `.env.example` 为 `.env` 并填写 QWEN_API_KEY
5. 构建并运行：`docker-compose up --build -d`
6. 访问：http://服务器IP:5000

### 4. Kubernetes 部署

**适用场景**：高可用、自动扩缩容

**部署步骤**：
1. 准备 Kubernetes 集群
2. 创建 `k8s/deployment.yaml` 配置文件
3. 应用配置：`kubectl apply -f k8s/deployment.yaml`
4. 访问：通过 LoadBalancer 或 Ingress

---

## ⚙️ 配置说明

### 环境变量配置

**文件**：`.env`

**必填项**：
- `QWEN_API_KEY`：通义千问 API Key

**选填项**：
- `OPENAI_API_KEY`：OpenAI API Key（可选）
- `ANTHROPIC_API_KEY`：Anthropic API Key（可选）
- `LANGSMITH_API_KEY`：LangSmith API Key（可选）

### 知识库配置

**目录**：`data/knowledge_base/`

**结构**：
```
data/knowledge_base/
├── amazon/           # 亚马逊平台相关知识
├── shopify/          # Shopify 平台相关知识
└── product/          # 产品相关知识
```

**更新知识库**：
```bash
# 初始化知识库
python init_knowledge_base.py

# 或使用脚本
python scripts/ingest_knowledge.py
```

### 模型配置

**文件**：`src/config/settings.py`

**可配置项**：
- 模型选择（qwen、gpt-4o、claude-3）
- 模型参数（temperature、top_p 等）
- 向量数据库选择

---

## 📡 API 接口

### 标准聊天接口

```bash
POST /chat
Content-Type: application/json

{
  "message": "如何退货",
  "language": "zh",
  "platform": "amazon"
}
```

### 流式聊天接口

```bash
POST /chat/stream
Content-Type: application/json

{
  "message": "如何退货",
  "language": "zh",
  "platform": "amazon"
}
```

### 健康检查接口

```bash
GET /
```

---

## 🎯 使用指南

### 前端使用

1. **访问系统**：打开浏览器访问 http://服务器IP:5000
2. **选择语言**：支持 8 种语言
3. **选择平台**：Amazon、Shopify、官网
4. **输入问题**：在输入框中输入您的问题
5. **点击示例**：点击示例问题快速发送
6. **查看回复**：实时流式输出，享受打字效果

### 常见问题

| 问题 | 解决方案 |
|------|----------|
| 服务启动失败 | 检查 API Key 配置和端口占用 |
| 响应速度慢 | 检查网络连接和模型配置 |
| 知识库未更新 | 运行 `python init_knowledge_base.py` |
| 多语言识别失败 | 确保输入文本清晰，避免混合语言 |

---

## 🔧 维护与监控

### 日志管理

**本地运行**：`tail -f app.log`

**systemd 服务**：`sudo journalctl -u b2c-agent -f`

**Docker**：`docker-compose logs -f`

**Kubernetes**：`kubectl logs -f deployment/b2c-agent`

### 服务管理

**启动服务**：
- systemd: `sudo systemctl start b2c-agent`
- Docker: `docker-compose up -d`
- Kubernetes: `kubectl rollout restart deployment/b2c-agent`

**停止服务**：
- systemd: `sudo systemctl stop b2c-agent`
- Docker: `docker-compose down`
- Kubernetes: `kubectl delete deployment b2c-agent`

**查看状态**：
- systemd: `sudo systemctl status b2c-agent`
- Docker: `docker-compose ps`
- Kubernetes: `kubectl get pods`

### 性能监控

**推荐工具**：
- Prometheus + Grafana
- New Relic
- Datadog

**监控指标**：
- 响应时间
- 请求量
- 错误率
- 系统资源使用率

---

## 📈 性能优化

### 推荐配置

1. **使用 Gunicorn** 代替 Flask 开发服务器
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 src.app:app
   ```

2. **配置 Nginx** 作为反向代理

3. **启用 HTTPS**（Let's Encrypt 免费证书）

4. **使用 Redis** 缓存热点数据

5. **配置 CDN** 加速静态资源

### 最佳实践

- **水平扩展**：使用负载均衡器
- **数据库分离**：使用外部数据库服务
- **定期备份**：定期备份知识库和配置
- **安全加固**：配置防火墙，使用 HTTPS

---

## 🛡️ 安全注意事项

1. **API 密钥管理**：使用环境变量，不要硬编码
2. **输入验证**：防止恶意输入和注入攻击
3. **权限控制**：限制访问权限
4. **定期更新**：更新系统和依赖包
5. **日志审计**：记录关键操作

---

## 📚 相关文档

- **快速开始指南**：[QUICKSTART.md](./QUICKSTART.md)
- **详细部署指南**：[DEPLOYMENT.md](./DEPLOYMENT.md)
- **项目说明**：[README.md](./README.md)
- **架构设计**：[ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- **技术选型**：[TECHNOLOGY_SELECTION.md](./docs/TECHNOLOGY_SELECTION.md)

---

## 🤝 技术支持

### 联系方式
- **电子邮件**：support@b2c-agent.com
- **GitHub Issues**：https://github.com/your-username/b2c-agent/issues
- **在线文档**：https://b2c-agent-docs.com

### 故障排查

**常见问题**：
1. **端口被占用**：检查并停止占用端口的进程
2. **API 密钥错误**：检查 API 密钥格式和有效性
3. **依赖安装失败**：使用国内镜像源
4. **服务启动失败**：查看日志，检查配置

**支持响应时间**：
- 工作时间（9:00-18:00）：1小时内响应
- 非工作时间：24小时内响应

---

## 📅 交付清单

### 已交付内容

- [x] 完整的项目代码
- [x] 部署配置文件
- [x] 环境变量配置模板
- [x] 知识库初始化脚本
- [x] 详细的部署文档
- [x] 快速开始指南
- [x] API 接口文档
- [x] 性能优化建议
- [x] 安全配置指南

### 后续支持

- [x] 系统部署指导
- [x] 性能优化建议
- [x] 安全加固方案
- [x] 知识库维护指南
- [x] 7x24 小时技术支持

---

## 🔚 结束语

跨境电商智能客服系统已完成交付，系统具备多平台支持、多语言处理、智能路由等核心功能，能够为您的跨境电商业务提供高效、专业的客服服务。

如果您在使用过程中遇到任何问题，请随时联系我们的技术支持团队。我们将持续优化系统，为您提供更好的服务体验。

祝您业务兴隆！

---

**版本**：v1.0.0
**交付日期**：2026-03-27
**开发团队**：B2C Agent Team