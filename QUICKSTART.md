# 快速开始指南

## 5 分钟快速上手

---

## 🚀 第一步：立即运行本地版本

### Windows PowerShell
```powershell
cd "your-project-directory"

# 创建并激活虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填写 QWEN_API_KEY

# 启动服务
python src/app.py
```

然后访问：**http://localhost:5000**

### Linux/Mac
```bash
cd "your-project-directory"

# 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填写 QWEN_API_KEY

# 启动服务
python src/app.py
```

---

## 📦 第二步：同步到 GitHub

### 1. 初始化 Git
```bash
cd "your-project-directory"

git init
git add .
git commit -m "Initial commit: B2C Agent System"
```

### 2. 创建 GitHub 仓库
1. 访问：https://github.com/new
2. 仓库名称：`b2c-agent`
3. 选择 Public 或 Private
4. **不要**勾选 "Initialize this repository"
5. 点击 "Create repository"

### 3. 推送到 GitHub
```bash
git remote add origin https://github.com/你的用户名/b2c-agent.git
git branch -M main
git push -u origin main
```

---

## ☁️ 第三步：部署到云服务器

### 方案 1：直接运行（推荐，简单）

#### 在云服务器上执行：
```bash
# 1. 登录云服务器
ssh root@你的服务器IP

# 2. 安装依赖
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git

# 3. 克隆项目
git clone https://github.com/你的用户名/b2c-agent.git
cd b2c-agent

# 4. 配置环境
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # 填写 QWEN_API_KEY

# 5. 配置后台运行
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

# 6. 启动服务
sudo systemctl daemon-reload
sudo systemctl enable b2c-agent
sudo systemctl start b2c-agent

# 7. 查看状态
sudo systemctl status b2c-agent
```

然后访问：**http://你的服务器IP:5000**

### 方案 2：Docker 部署（隔离性好）

```bash
# 1. 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 2. 配置 Docker 镜像源
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<-'EOF'
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ]
}
EOF
sudo systemctl restart docker

# 3. 部署项目
git clone https://github.com/你的用户名/b2c-agent.git
cd b2c-agent
cp .env.example .env
nano .env  # 填写 QWEN_API_KEY

docker-compose up --build -d
```

---

## 🔧 配置 CI/CD

### GitHub Actions 已自动配置

文件位置：`.github/workflows/ci-cd.yml`

### 配置 GitHub Secrets：

1. 进入 GitHub 仓库 → **Settings**
2. 左侧菜单 → **Secrets and variables** → **Actions**
3. 点击 **New repository secret**，添加：

| Secret 名称 | 说明 |
|------------|------|
| `DOCKERHUB_USERNAME` | Docker Hub 用户名 |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token |
| `QWEN_API_KEY` | 通义千问 API Key |

### 获取 Docker Hub Token：
1. 访问：https://hub.docker.com/settings/security
2. 点击 "New Access Token"
3. 输入描述，选择权限：Read, Write, Delete
4. 复制生成的 token

---

## 📋 常用命令

### 本地开发
```bash
# 启动服务
python src/app.py

# 开发模式（自动重启）
FLASK_ENV=development python src/app.py

# 查看日志
tail -f app.log
```

### Git 操作
```bash
# 查看状态
git status

# 提交修改
git add .
git commit -m "你的描述"
git push
```

### 云服务器管理
```bash
# 查看服务状态
sudo systemctl status b2c-agent

# 重启服务
sudo systemctl restart b2c-agent

# 查看日志
sudo journalctl -u b2c-agent -f

# 停止服务
sudo systemctl stop b2c-agent
```

### Docker 管理
```bash
# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 重启容器
docker-compose restart

# 停止容器
docker-compose down
```

---

## 🎯 快速检查清单

- [ ] 本地可以正常运行（http://localhost:5000）
- [ ] 代码已推送到 GitHub
- [ ] 云服务器已购买
- [ ] 云服务器安全组已开放端口 5000
- [ ] 项目已部署到云服务器
- [ ] 服务正在后台运行
- [ ] 可以通过公网 IP 访问

---

## ❓ 遇到问题？

### 本地运行问题
- 检查 Python 版本：`python --version`（需要 3.11+）
- 检查依赖安装：`pip install -r requirements.txt`
- 检查端口占用：`netstat -tlnp | grep 5000`
- 检查环境变量：确保 `.env` 文件配置正确

### 云服务器问题
- 检查防火墙/安全组：确保端口 5000 已开放
- 查看服务日志：`sudo journalctl -u b2c-agent -f`
- 检查服务状态：`sudo systemctl status b2c-agent`
- 检查网络连接：`ping baidu.com`

### Docker 问题
- 检查 Docker 状态：`sudo systemctl status docker`
- 查看容器日志：`docker-compose logs -f`
- 检查镜像构建：`docker-compose build --no-cache`

### Git/GitHub 问题
- 检查 Git 是否已安装：`git --version`
- 检查远程仓库配置：`git remote -v`
- 检查网络连接：`ping github.com`

---

## 📚 更多文档

- 详细部署指南：[DEPLOYMENT.md](./DEPLOYMENT.md)
- 项目说明：[README.md](./README.md)
- 架构设计：[ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- 技术选型：[TECHNOLOGY_SELECTION.md](./docs/TECHNOLOGY_SELECTION.md)
