"""FastAPI 应用入口

多语言多平台智能客服系统后端服务。
提供 REST + WebSocket 接口，对接 LangGraph 多智能体与 vLLM 推理。
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.models import HealthResponse
from app.api import api_router, ws_router
from app.services.llm_service import get_mode


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时构建索引"""
    logger.info("=" * 60)
    logger.info("多语言多平台智能客服系统启动中")
    logger.info(f"版本: 1.0.0")
    logger.info(f"推理模式: {get_mode()}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Milvus: {settings.milvus_host}:{settings.milvus_port}")
    logger.info(f"vLLM: {settings.vllm_base_url} model={settings.vllm_model}")
    logger.info("=" * 60)

    # 构建知识库索引
    if settings.auto_build_index:
        try:
            from app.rag.indexer import build_index
            build_index()
        except Exception as e:
            logger.warning(f"索引构建跳过: {e}")

    # 预热状态图
    try:
        from app.agents import get_graph
        get_graph()
    except Exception as e:
        logger.warning(f"状态图预热跳过: {e}")

    logger.info("系统启动完成")
    yield
    logger.info("系统关闭")


app = FastAPI(
    title="多语言多平台智能客服系统",
    description="基于多智能体 + RAG + Qwen2.5-7B 的跨境B2C多语言智能客服开源参考实现",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 安全配置：从环境变量读取允许的前端域名，生产环境严禁使用通配符
_cors_origins = [
    o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# 注册路由
app.include_router(api_router)
app.include_router(ws_router)


@app.get("/health", response_model=HealthResponse)
async def health():
    """健康检查

    mode 取值: vllm / openai / deepseek / qwen / custom / rule
    """
    return HealthResponse(
        status="ok",
        mode=get_mode(),
        version="1.0.0",
    )


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus 指标端点（app 级别，不在 /api 前缀下）"""
    from app.services.metrics import format_prometheus
    from fastapi import Response
    return Response(content=format_prometheus(), media_type="text/plain; charset=utf-8")


# 挂载前端静态文件（同端口服务，避免跨域与端口冲突）
# StaticFiles 挂载在所有 API 路由之后，仅对未匹配的路径生效（如 /、/css/、/js/）
_frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
    )
