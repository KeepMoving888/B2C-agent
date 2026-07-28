# -*- coding: utf-8 -*-
"""多语言多平台智能客服系统 - 统一启动入口

用法：
    python main.py                  # 启动后端（8000）+ 前端（8080）
    python main.py --backend        # 仅启动后端
    python main.py --frontend       # 仅启动前端
    python main.py --port 9000      # 指定后端端口

后端启动后，浏览器访问 http://localhost:8000 即可使用（后端同端口提供前端静态文件）。
前端独立启动时访问 http://localhost:8080。
"""
import os
import sys
import argparse
import subprocess
import threading
import time
import http.server
import socketserver


def get_project_root():
    return os.path.dirname(os.path.abspath(__file__))


def start_backend(port=8000):
    """启动后端服务（FastAPI + LangGraph 多智能体）"""
    root = get_project_root()
    backend_dir = os.path.join(root, "backend")
    sys.path.insert(0, backend_dir)
    os.chdir(backend_dir)

    print(f"[*] 启动后端服务 http://localhost:{port}")
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )


class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """禁用缓存的前端静态文件服务器"""

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()


def start_frontend(port=8080):
    """启动前端独立服务器（开发模式，禁用缓存）"""
    root = get_project_root()
    frontend_dir = os.path.join(root, "frontend")
    os.chdir(frontend_dir)

    print(f"[*] 启动前端服务 http://localhost:{port}")
    with socketserver.TCPServer(("", port), NoCacheHTTPRequestHandler) as httpd:
        httpd.serve_forever()


def wait_for_backend(port, timeout=60):
    """等待后端就绪"""
    import urllib.request
    for i in range(timeout):
        try:
            urllib.request.urlopen(f"http://localhost:{port}/health", timeout=2)
            return True
        except Exception:
            time.sleep(1)
            if i % 5 == 0:
                print(f"    等待后端启动... ({i}s)")
    return False


def main():
    parser = argparse.ArgumentParser(description="多语言多平台智能客服系统启动入口")
    parser.add_argument("--backend", action="store_true", help="仅启动后端")
    parser.add_argument("--frontend", action="store_true", help="仅启动前端")
    parser.add_argument("--port", type=int, default=8000, help="后端端口（默认 8000）")
    parser.add_argument("--frontend-port", type=int, default=8080, help="前端端口（默认 8080）")
    args = parser.parse_args()

    print("=" * 60)
    print("  多语言多平台智能客服系统")
    print("=" * 60)

    if args.backend and not args.frontend:
        start_backend(args.port)
        return

    if args.frontend and not args.backend:
        start_frontend(args.frontend_port)
        return

    # 同时启动前后端
    backend_thread = threading.Thread(target=start_backend, args=(args.port,), daemon=True)
    backend_thread.start()

    # 等待后端就绪
    if wait_for_backend(args.port):
        print(f"[OK] 后端就绪: http://localhost:{args.port}")
    else:
        print(f"[!] 后端启动超时，继续启动前端")

    # 启动前端
    frontend_thread = threading.Thread(target=start_frontend, args=(args.frontend_port,), daemon=True)
    frontend_thread.start()
    time.sleep(1)

    print(f"
[OK] 系统启动完成")
    print(f"    后端 API:  http://localhost:{args.port}/docs")
    print(f"    前端页面:  http://localhost:{args.frontend_port}/")
    print(f"    健康检查:  http://localhost:{args.port}/health")
    print(f"    按 Ctrl+C 停止所有服务
")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("
[*] 正在停止所有服务...")


if __name__ == "__main__":
    main()
