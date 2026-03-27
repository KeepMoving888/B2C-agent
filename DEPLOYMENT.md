# 部署指南

## 目录
- [本地开发](#本地开发)
- [云服务器部署](#云服务器部署)
- [Docker 部署](#docker-部署)
- [Kubernetes 部署](#kubernetes-部署)
- [CI/CD 配置](#cicd-配置)
- [GitHub 同步](#github-同步)
- [生产环境最佳实践](#生产环境最佳实践)

---

## 本地开发

### 快速启动

```bash
# 1. 创建虚拟环境
python -m venv venv

# 2. 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填写 QWEN_API_KEY

# 5. 启动服务
python src/app.py

# 6. 访问系统
# 打开浏览器：http://localhost:5000
```

### 开发模式

```bash
# 启用开发模式（自动重启）
FLASK_ENV=development python src/app.py
```

---

## 云服务器部署

### 方案 1：直接本地运行（推荐，简单）

#### 步骤 1：准备云服务器
- 购买国内云服务器（阿里云、腾讯云、华为云）
- 选择 Linux 系统（Ubuntu 22.04 推荐）
- 开放端口 5000（在安全组中配置）
- 建议配置：2核4G内存以上

#### 步骤 2：登录服务器
```bash
ssh root@your-server-ip
```

#### 步骤 3：安装依赖
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip git curl wget

# 安装系统依赖
sudo apt install -y build-essential libssl-dev libffi-dev python3-dev
```

#### 步骤 4：部署项目
```bash
# 克隆项目（先推送到 GitHub）
git clone https://github.com/your-username/b2c-agent.git
cd b2c-agent

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
nano .env  # 编辑配置
```

#### 步骤 5：使用 systemd 后台运行
```bash
# 创建 systemd 服务
sudo tee /etc/systemd/system/b2c-agent.service << 'EOF'
[Unit]
Description=B2C Agent Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/b2c-agent
Environment="PATH=/root/b2c-agent/venv/bin"
Environment="FLASK_ENV=production"
ExecStart=/root/b2c-agent/venv/bin/python src/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable b2c-agent
sudo systemctl start b2c-agent

# 查看状态
sudo systemctl status b2c-agent

# 查看日志
sudo journalctl -u b2c-agent -f
```

---

### 方案 2：Docker 部署（推荐，隔离性好）

#### 步骤 1：在服务器上配置 Docker
```bash
# 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 配置国内镜像源
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<-'EOF'
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://registry.docker-cn.com"
  ]
}
EOF

sudo systemctl daemon-reload
sudo systemctl restart docker

# 安装 docker-compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### 步骤 2：部署
```bash
# 克隆项目
git clone https://github.com/your-username/b2c-agent.git
cd b2c-agent

# 配置环境变量
cp .env.example .env
nano .env

# 构建并运行
docker-compose up --build -d

# 查看状态
docker-compose ps
docker-compose logs -f
```

---

## Kubernetes 部署

### 步骤 1：准备 Kubernetes 集群
- 可以使用 Minikube（本地测试）
- 或使用云服务商的托管 Kubernetes 服务

### 步骤 2：创建 Kubernetes 配置文件

创建 `k8s/deployment.yaml`：

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: b2c-agent
  labels:
    app: b2c-agent
spec:
  replicas: 2
  selector:
    matchLabels:
      app: b2c-agent
  template:
    metadata:
      labels:
        app: b2c-agent
    spec:
      containers:
      - name: b2c-agent
        image: your-dockerhub-username/b2c-agent:latest
        ports:
        - containerPort: 5000
        env:
        - name: QWEN_API_KEY
          valueFrom:
            secretKeyRef:
              name: b2c-agent-secrets
              key: qwen_api_key
        resources:
          limits:
            cpu: "1"
            memory: "2Gi"
          requests:
            cpu: "500m"
            memory: "1Gi"
---
apiVersion: v1
kind: Service
metadata:
  name: b2c-agent-service
spec:
  selector:
    app: b2c-agent
  ports:
  - port: 80
    targetPort: 5000
  type: LoadBalancer
---
apiVersion: v1
kind: Secret
metadata:
  name: b2c-agent-secrets
type: Opaque
data:
  qwen_api_key: <base64-encoded-api-key>
```

### 步骤 3：部署到 Kubernetes

```bash
# 应用配置
kubectl apply -f k8s/deployment.yaml

# 查看状态
kubectl get pods
kubectl get services

# 查看日志
kubectl logs -f deployment/b2c-agent
```

---

## CI/CD 配置

### GitHub Actions 配置

已自动创建 `.github/workflows/ci-cd.yml`，包含：
- 自动测试和语法检查
- 自动构建 Docker 镜像
- 自动推送到 Docker Hub

### GitHub Secrets 配置

在 GitHub 仓库 → Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 说明 | 示例 |
|------------|------|------|
| `DOCKERHUB_USERNAME` | Docker Hub 用户名 | `yourname` |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token | `dckr_pat_xxx` |
| `QWEN_API_KEY` | 通义千问 API Key | `sk-xxx` |
| `OPENAI_API_KEY` | OpenAI API Key（可选） | `sk-xxx` |
| `ANTHROPIC_API_KEY` | Anthropic API Key（可选） | `sk-xxx` |

### 获取 Docker Hub Token

1. 访问 https://hub.docker.com/settings/security
2. 点击 "New Access Token"
3. 输入描述，选择权限：Read, Write, Delete
4. 复制生成的 token

---

## GitHub 同步

### 步骤 1：初始化 Git 仓库

```bash
cd "your-project-directory"

# 初始化 Git
git init

# 添加所有文件
git add .

# 首次提交
git commit -m "Initial commit: B2C Agent System"
```

### 步骤 2：创建 GitHub 仓库

1. 访问 https://github.com/new
2. 仓库名称：`b2c-agent`
3. 选择 Public 或 Private
4. 不要初始化 README（已有）
5. 点击 Create repository

### 步骤 3：推送到 GitHub

```bash
# 添加远程仓库
git remote add origin https://github.com/your-username/b2c-agent.git

# 推送到 GitHub
git branch -M main
git push -u origin main
```

### 步骤 4：后续更新

```bash
# 查看状态
git status

# 添加修改
git add .

# 提交
git commit -m "描述你的修改"

# 推送
git push
```

---

## 安全注意事项

1. **永远不要提交 `.env` 文件到 Git**（已在 `.gitignore` 中）
2. **使用 GitHub Secrets 存储敏感信息**
3. **定期更新依赖**：`pip list --outdated`
4. **配置防火墙**：只开放必要端口
5. **使用 HTTPS**：生产环境必须配置 SSL 证书
6. **限制访问**：配置 IP 白名单或使用 API 密钥
7. **定期备份**：定期备份数据和配置

---

## 故障排查

### 查看日志
```bash
# 本地运行
tail -f app.log

# systemd 服务
sudo journalctl -u b2c-agent -f

# Docker
docker-compose logs -f

# Kubernetes
kubectl logs -f deployment/b2c-agent
```

### 重启服务
```bash
# systemd
sudo systemctl restart b2c-agent

# Docker
docker-compose restart

# Kubernetes
kubectl rollout restart deployment/b2c-agent
```

### 查看端口占用
```bash
# 查看端口 5000
netstat -tlnp | grep 5000
# 或
ss -tlnp | grep 5000

# Docker 端口映射
docker port b2c-agent_b2c-agent_1
```

### 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|---------|----------|
| 端口被占用 | 其他服务占用了端口 5000 | 查看并停止占用端口的进程 |
| API 密钥错误 | .env 文件配置错误 | 检查 API 密钥格式和有效性 |
| 依赖安装失败 | 网络问题或版本不兼容 | 检查网络连接，使用国内镜像源 |
| 服务启动失败 | 权限问题或配置错误 | 查看日志，检查权限和配置 |

---

## 生产环境最佳实践

### 性能优化

1. **使用 Gunicorn** 代替 Flask 开发服务器
   ```bash
   # 安装 Gunicorn
   pip install gunicorn
   
   # 启动服务
   gunicorn -w 4 -b 0.0.0.0:5000 src.app:app
   ```

2. **配置 Nginx** 作为反向代理
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

3. **启用 HTTPS**（Let's Encrypt 免费证书）
   ```bash
   # 安装 Certbot
   sudo apt install certbot python3-certbot-nginx
   
   # 申请证书
   sudo certbot --nginx -d your-domain.com
   ```

4. **配置日志轮转**
   ```bash
   # 创建日志轮转配置
   sudo tee /etc/logrotate.d/b2c-agent << 'EOF'
   /var/log/b2c-agent.log {
       daily
       rotate 7
       compress
       delaycompress
       missingok
       postrotate
           sudo systemctl restart b2c-agent
       endscript
   }
   EOF
   ```

5. **设置监控告警**
   - 使用 Prometheus + Grafana 监控服务状态
   - 配置邮件或短信告警

### 扩展性建议

1. **水平扩展**：使用 Kubernetes 或负载均衡器
2. **数据库分离**：使用外部数据库服务
3. **缓存优化**：使用 Redis 缓存热点数据
4. **CDN 加速**：使用 CDN 加速静态资源

### 安全加固

1. **使用非 root 用户运行**
2. **配置防火墙**：只开放必要端口
3. **定期安全扫描**：使用安全扫描工具检查漏洞
4. **更新系统和依赖**：定期更新系统和依赖包

---

## 部署清单

### 本地开发
- [ ] 安装 Python 3.11+
- [ ] 创建虚拟环境
- [ ] 安装依赖
- [ ] 配置环境变量
- [ ] 启动服务

### 云服务器部署
- [ ] 购买云服务器
- [ ] 配置安全组
- [ ] 安装依赖
- [ ] 部署项目
- [ ] 配置后台运行
- [ ] 测试访问

### Docker 部署
- [ ] 安装 Docker
- [ ] 配置 Docker 镜像源
- [ ] 构建和运行容器
- [ ] 测试访问

### 生产环境配置
- [ ] 配置 HTTPS
- [ ] 配置 Nginx
- [ ] 设置监控
- [ ] 配置备份策略
- [ ] 安全加固

---

## 相关文档

- [快速开始指南](./QUICKSTART.md)
- [项目说明](./README.md)
- [架构设计](./docs/ARCHITECTURE.md)
- [技术选型](./docs/TECHNOLOGY_SELECTION.md)
