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

    # Kafka 异步接入：发布客户消息（削峰填谷）
    from app.services import kafka_client
    kafka_client.publish_customer_message(
        platform=req.platform, conv_id=req.conv_id or "",
        message=req.message, lang=req.lang,
    )

    # Jaeger 追踪：会话处理全链路
    from app.services import tracer, postgres, redis_client

    _start_ts = time.time()
    state = {
        "platform": req.platform,
        "lang": req.lang,
        "message": req.message,
        "history": [m.model_dump() for m in req.history],
        "conv_id": req.conv_id,
    }

    # Redis 会话状态恢复（多轮对话上下文）
    if req.conv_id:
        cached_state = redis_client.load_session_state(req.conv_id)
        if cached_state and cached_state.get("history"):
            state["history"] = cached_state["history"] + state["history"]

    with tracer.span("chat.process", {"platform": req.platform, "lang": req.lang}):
        result = run_graph(state)
    _latency_ms = (time.time() - _start_ts) * 1000

    # PostgreSQL 持久化（审计 + 历史回溯）
    postgres.save_conversation(req.conv_id or "", req.platform, lang=req.lang)
    postgres.save_message(
        req.conv_id or "", "user", req.message,
        intent=result.get("intent", ""), lang=req.lang,
    )
    postgres.save_message(
        req.conv_id or "", "assistant", result.get("final_reply", ""),
        intent=result.get("intent", ""), agent=result.get("agent_name", ""),
        lang=req.lang,
    )

    # 记录转交事件
    handoff_reason = result.get("handoff_reason", "")
    if handoff_reason:
        postgres.record_handoff(
            req.conv_id or "", result.get("agent_name", ""),
            "human_handoff", handoff_reason,
        )
        kafka_client.publish_handoff(
            req.conv_id or "", result.get("agent_name", ""),
            "human_handoff", handoff_reason,
        )

    # Redis 更新会话状态
    redis_client.save_session_state(req.conv_id or "", {
        "history": state["history"],
        "intent": result.get("intent", ""),
        "agent_chain": result.get("agent_chain", []),
    })

    # Kafka 发布 Agent 回复
    kafka_client.publish_agent_reply(
        req.conv_id or "", result.get("final_reply", ""),
        result.get("agent_name", ""), result.get("intent", ""), req.lang,
    )

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

    # 翻译回复：Agent 生成中文回复，按目标语言翻译
    reply_zh = result.get("final_reply_zh", result.get("final_reply", req.message))
    target_lang = req.lang or "zh"
    if target_lang == "zh":
        reply = reply_zh
    else:
        try:
            reply = translate(reply_zh, "zh", target_lang)
            if not reply or reply == reply_zh:
                # 翻译失败（LLM 不可用且回退返回原文），尝试英文兜底
                if target_lang == "en":
                    reply = translate(reply_zh, "zh", "en")
                else:
                    # 非 zh→en 方向，LLM 不可用时保留中文并标注
                    reply = reply_zh
        except Exception as e:
            logger.warning(f"翻译失败 zh→{target_lang}: {e}")
            reply = reply_zh

    return ChatResponse(
        reply=reply,
        reply_zh=reply_zh,
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
    """AI 建议回复（始终生成中文，由前端按目标语言翻译）"""
    history = [m.model_dump() for m in req.history]

    if is_vllm_available():
        # 始终用中文生成建议，确保前端可按目标语言翻译
        messages = build_suggest_prompt("zh", req.platform, history)
        text = chat_completion(messages, temperature=0.7, max_tokens=200)
        if text:
            return SuggestResponse(text=text, reply_zh=text)

    # 离线回退：返回中文建议
    text = _fallback_suggest("zh")
    return SuggestResponse(text=text, reply_zh=text)


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
