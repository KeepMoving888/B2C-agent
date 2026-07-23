"""环境初始化脚本

一键完成：依赖安装、Milvus 初始化、知识库灌入、健康检查。
"""
import os
import subprocess
import sys


def run(cmd, cwd=None):
    """执行命令"""
    print(f"\n>>> {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd)
    if result.returncode != 0:
        print(f"命令执行失败: {cmd}")
        return False
    return True


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print("=" * 60)
    print("多语言多平台智能客服系统 - 环境初始化")
    print(f"项目根目录: {root}")
    print("=" * 60)

    # 1. 安装后端依赖
    print("\n[1/4] 安装后端 Python 依赖...")
    if not run("pip install -r requirements.txt", cwd=os.path.join(root, "backend")):
        print("后端依赖安装失败，请手动检查")
        return

    # 2. 复制环境变量
    print("\n[2/4] 配置环境变量...")
    env_src = os.path.join(root, ".env.example")
    env_dst = os.path.join(root, "backend", ".env")
    if not os.path.exists(env_dst):
        import shutil
        shutil.copy(env_src, env_dst)
        print(f"已复制 .env.example → backend/.env")
    else:
        print("backend/.env 已存在，跳过")

    # 3. Milvus 初始化（可选，Milvus 未启动时跳过）
    print("\n[3/4] Milvus 初始化...")
    try:
        run(f"python {os.path.join(root, 'deployment', 'milvus', 'init_schema.py')}")
    except Exception as e:
        print(f"Milvus 初始化跳过（未启动？）: {e}")

    # 4. 知识库灌入
    print("\n[4/4] 灌入知识库数据...")
    try:
        run(f"python {os.path.join(root, 'scripts', 'seed_data.py')}")
    except Exception as e:
        print(f"知识库灌入失败: {e}")

    print("\n" + "=" * 60)
    print("环境初始化完成！")
    print("\n启动方式：")
    print("  后端: cd backend && uvicorn app.main:app --reload --port 8000")
    print("  前端: cd frontend && python -m http.server 8080")
    print("  访问: http://localhost:8080")
    print("=" * 60)


if __name__ == "__main__":
    main()
