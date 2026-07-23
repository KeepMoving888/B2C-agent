"""REST API 路由"""
import time
from fastapi import APIRouter, Response
from loguru import logger

from app.services.metrics import record_chat, get_stats, format_prometheus

from app.models import (
    ChatRequest, ChatResponse,
    SuggestRequest, SuggestResponse,
    TranslateRequest, TranslateResponse,
    StatsResponse,
)
from app.agents import run_graph
from app.services.translation import translate
from app.services.llm_service import chat_completion, is_vllm_available
from app.rag.prompts import build_suggest_prompt

router = APIRouter(prefix="/api", tags=["customer-service"])


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """多智能体会话处理

    入口：客服输入消息（中文）
    流程：意图识别 → 情感分析 → RAG检索 → 条件路由 → 对应Agent处理 → 翻译输出
    """
    logger.info(f"收到会话请求 platform={req.platform} lang={req.lang} message={req.message[:50]}...")

    _start_ts = time.time()
    state = {
        "platform": req.platform,
        "lang": req.lang,
        "message": req.message,
        "history": [m.model_dump() for m in req.history],
        "conv_id": req.conv_id,
    }

    result = run_graph(state)
    _latency_ms = (time.time() - _start_ts) * 1000

    # 记录监控指标
    record_chat(
        intent=result.get("intent", ""),
        agent_name=result.get("agent_name", ""),
        latency_ms=_latency_ms,
        rag_sources=result.get("rag_sources", []),
        anti_hallucination_report=result.get("anti_hallucination_report"),
        handoff_reason=result.get("handoff_reason", ""),
        sentiment=result.get("sentiment", {}),
        agent_chain=result.get("agent_chain", []),
        lang=req.lang,
    )

    return ChatResponse(
        reply=result.get("final_reply", req.message),
        reply_zh=result.get("final_reply_zh", req.message),
        agent=result.get("agent_name", "咨询Agent"),
        route=result.get("route_desc", ""),
        intent=result.get("intent", ""),
        sentiment=result.get("sentiment", {}),
        sources=result.get("rag_sources", []),
        agent_chain=result.get("agent_chain", []),
        trace=result.get("trace", []),
        handoff_reason=result.get("handoff_reason", ""),
        capability_check=result.get("capability_check", {}),
        anti_hallucination_report=result.get("anti_hallucination_report") or {},
    )


@router.post("/suggest", response_model=SuggestResponse)
async def suggest(req: SuggestRequest):
    """AI 建议回复"""
    history = [m.model_dump() for m in req.history]

    if is_vllm_available():
        messages = build_suggest_prompt(req.lang, req.platform, history)
        text = chat_completion(messages, temperature=0.7, max_tokens=200)
        if text:
            return SuggestResponse(text=text)

    # 离线回退
    text = _fallback_suggest(req.lang)
    return SuggestResponse(text=text)


@router.post("/translate", response_model=TranslateResponse)
async def translate_text(req: TranslateRequest):
    """多语言翻译"""
    result = translate(req.text, req.from_lang, req.to_lang)
    return TranslateResponse(text=req.text, translated=result)


@router.get("/stats", response_model=StatsResponse)
async def stats(platform: str = "amazon"):
    """统计数据（基于真实运行指标，非随机值）"""
    return StatsResponse(**get_stats())


@router.get("/metrics")
async def metrics():
    """Prometheus 指标端点（供 Grafana / Prometheus 拉取）

    返回 text/plain 格式的 exposition 文本，包含：
    - cs_total_requests / cs_avg_response_ms
    - cs_anti_hallucination_pass_rate / cs_handoff_rate
    - cs_intent_count{intent=...} / cs_agent_count{agent=...}
    - cs_handoff_reason_count{reason=...}
    """
    return Response(content=format_prometheus(), media_type="text/plain; charset=utf-8")


def _fallback_suggest(lang: str) -> str:
    """离线建议回复回退"""
    pool = {
        "en": "Hello! I've checked your order and it's currently in transit. The package will arrive within 2-3 business days. Is there anything else I can help you with?",
        "ja": "こんにちは！ご注文を確認しました。現在配送中で、2-3営業日以内に到着予定です。他にご不明点はございますか？",
        "de": "Hallo! Ich habe Ihre Bestellung geprüft. Sie befindet sich auf dem Transportweg und wird in 2-3 Werktagen eintreffen. Kann ich noch weiter helfen?",
        "es": "¡Hola! He verificado su pedido. Está en tránsito y llegará en 2-3 días laborables. ¿Puedo ayudarle con algo más?",
        "fr": "Bonjour ! J'ai vérifié votre commande. Elle est en cours de transport et arrivera dans 2-3 jours ouvrés. Puis-je vous aider autrement ?",
        "it": "Salve! Ho verificato il suo ordine. È in transito e arriverà in 2-3 giorni lavorativi. Posso aiutarla con altro?",
        "pt": "Olá! Verifiquei seu pedido. Está em trânsito e chegará em 2-3 dias úteis. Posso ajudar com algo mais?",
        "zh": "您好！我已为您查询订单状态，包裹目前正在配送中，预计2-3个工作日内送达。请问还有什么可以帮您的吗？",
    }
    return pool.get(lang, pool["en"])
