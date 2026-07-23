"""WebSocket 实时会话推送"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 实时会话通道

    支持双向通信：
    - 客户端发送消息 → 服务端调用多智能体处理 → 返回回复
    - 支持流式输出（后续扩展）
    """
    await websocket.accept()
    logger.info("WebSocket 连接已建立")
    try:
        while True:
            data = await websocket.receive_json()
            # 复用 REST 逻辑
            from app.agents import run_graph
            state = {
                "platform": data.get("platform", "amazon"),
                "lang": data.get("lang", "en"),
                "message": data.get("message", ""),
                "history": data.get("history", []),
                "conv_id": data.get("conv_id"),
            }
            result = run_graph(state)
            await websocket.send_json({
                "type": "reply",
                "reply": result.get("final_reply", ""),
                "reply_zh": result.get("final_reply_zh", ""),
                "agent": result.get("agent_name", ""),
                "route": result.get("route_desc", ""),
                "intent": result.get("intent", ""),
            })
    except WebSocketDisconnect:
        logger.info("WebSocket 连接已断开")
    except Exception as e:
        logger.error(f"WebSocket 异常: {e}")
