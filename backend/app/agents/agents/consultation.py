"""咨询Agent（深度版）

基于 AgentBase，专注业务逻辑：
- 商品咨询、库存查询、技术支持
- 依托 RAG 检索商品知识
- 处理失败时由基类统一重试/降级
"""
import re
from loguru import logger

from app.agents.state import AgentState
from app.agents.agent_base import AgentBase
from app.agents.context_bus import get_focused_history, format_history_for_prompt
from app.services.llm_service import chat_completion, is_vllm_available


CONSULTATION_PROMPT = """你是跨境电商客服系统的【咨询Agent】，负责处理商品咨询、库存查询、技术支持等通用咨询问题。

职责边界：
- 仅处理商品信息、规格、库存、使用方法、兼容性等咨询
- 涉及订单/物流/退款等问题时，应建议转交对应Agent
- 回复需专业、准确、有温度

{handoff_section}

参考知识（RAG检索结果）：
{context}

历史对话：
{history}

客户语言：{lang}
客服输入（中文）：{message}

请用中文生成专业回复（后续会翻译为客户语言）："""


class ConsultationAgent(AgentBase):
    agent_name = "consultation"
    agent_label = "咨询Agent"

    def _do_process(self, state: AgentState) -> tuple[bool, str, str]:
        """处理咨询类问题"""
        message = state.get("message", "")
        lang = state.get("lang", "en")
        focused_history = get_focused_history(state)
        rag_sources = state.get("rag_sources", [])
        handoff_context = state.get("handoff_context", "")

        # 构建 RAG 上下文
        context = "\n".join([f"- {s.get('content','')}" for s in rag_sources[:3]]) if rag_sources else "无检索结果"
        history_text = format_history_for_prompt(focused_history)
        handoff_section = f"【前序Agent转交上下文】\n{handoff_context}\n" if handoff_context else ""

        reply_zh = ""
        if is_vllm_available():
            prompt = CONSULTATION_PROMPT.format(
                handoff_section=handoff_section, context=context,
                history=history_text, lang=lang, message=message,
            )
            reply_zh = chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.7, max_tokens=400,
            )

        if not reply_zh:
            reply_zh = self._fallback_reply(message, rag_sources)

        # 质量自检：回复不能为空、不能包含"无法处理"
        if not reply_zh or len(reply_zh) < 10:
            return False, "", "回复为空或过短"

        if "无法处理" in reply_zh or "超出能力" in reply_zh:
            return False, "", "Agent 自检判定超出能力边界"

        return True, reply_zh, f"RAG命中{len(rag_sources)}条，回复{len(reply_zh)}字"

    def _fallback_reply(self, message: str, rag_sources: list) -> str:
        """离线模式回退回复：基于客户消息关键词 + RAG知识库内容生成针对性回复"""
        msg_lower = message.lower()

        # 提取RAG检索到的产品信息（搜索所有来源，不仅第一个）
        all_rag_content = ""
        if rag_sources:
            all_rag_content = " ".join([s.get("content", "") for s in rag_sources])

        # 内置产品知识库（当RAG检索不准确时兜底，确保回复始终具体）
        product_kb = {
            "耳机": "无线蓝牙耳机 Pro：蓝牙5.3，续航32小时，支持主动降噪，IPX5防水。兼容iOS/Android。保修期12个月。",
            "earphone": "无线蓝牙耳机 Pro：蓝牙5.3，续航32小时，支持主动降噪，IPX5防水。兼容iOS/Android。保修期12个月。",
            "bluetooth": "无线蓝牙耳机 Pro：蓝牙5.3，续航32小时，支持主动降噪，IPX5防水。兼容iOS/Android。保修期12个月。",
            "手表": "智能手表 Series 7：1.8英寸AMOLED屏，支持心率/血氧/睡眠监测，IP68防水，续航7天。兼容iOS 12+/Android 6+。",
            "watch": "智能手表 Series 7：1.8英寸AMOLED屏，支持心率/血氧/睡眠监测，IP68防水，续航7天。兼容iOS 12+/Android 6+。",
        }

        # 综合产品信息（RAG + 内置知识库）
        def has_info(keyword):
            return keyword in all_rag_content or any(keyword in v for v in product_kb.values())

        # 场景1：产品规格咨询（蓝牙版本/续航/防水/屏幕等）
        if re.search(r"蓝牙|bluetooth|蓝牙版本|bt", msg_lower):
            if has_info("蓝牙5.3"):
                return "您好！这款无线蓝牙耳机 Pro 搭载蓝牙5.3芯片，连接更稳定、延迟更低，兼容主流蓝牙设备。同时支持主动降噪和IPX5防水，续航可达32小时。请问还有其他想了解的吗？"
            return "您好！该产品支持最新蓝牙协议，连接稳定低延迟。具体蓝牙版本请参考商品详情页规格参数表，如有其他问题随时为您解答。"

        if re.search(r"续航|电池|battery|续航多久|能用多久", msg_lower):
            if has_info("续航32小时"):
                return "您好！蓝牙耳机 Pro 满电续航约32小时（配合充电仓），单次使用约8小时。充电仓支持快充，充电15分钟即可使用2小时。"
            if has_info("续航7天"):
                return "您好！智能手表 Series 7 在常规使用下续航约7天，开启全天心率监测约5天。支持磁吸快充，2小时可充满。"
            return "您好！该产品的续航信息请参考商品详情页的规格参数。如有其他问题，欢迎随时咨询。"

        if re.search(r"防水|waterproof|ipx|ip\d", msg_lower):
            if has_info("IPX5"):
                return "您好！蓝牙耳机 Pro 支持IPX5级防水，可防雨水和汗渍，适合运动场景使用。但不建议浸泡在水中或淋浴时佩戴。"
            if has_info("IP68"):
                return "您好！智能手表 Series 7 支持IP68级防水，可游泳佩戴（水深1.5米内30分钟）。但不建议在热水浴或桑拿时佩戴。"
            return "您好！该产品的防水等级请参考商品规格参数。如有其他疑问随时为您解答。"

        # 场景2：兼容性咨询
        if re.search(r"兼容|compat|iphone|android|ios|安卓|苹果", msg_lower):
            if has_info("兼容iOS/Android"):
                return "您好！蓝牙耳机 Pro 兼容iOS和Android系统，支持蓝牙5.0及以上设备。配对方式：长按电源键3秒进入配对模式，在手机蓝牙设置中选择设备即可。"
            if has_info("兼容iOS 12+/Android 6+"):
                return "您好！智能手表 Series 7 兼容iOS 12及以上、Android 6及以上系统。需下载配套App使用全部功能。"
            return "您好！该产品兼容主流操作系统，具体版本要求请参考商品详情页。如有其他问题随时咨询。"

        # 场景3：库存/现货咨询
        if re.search(r"stock|库存|现货|有货|availability", msg_lower):
            return "您好！该商品目前有现货，下单后48小时内发货。如遇旺季可能延迟至72小时，建议尽早下单。您可以在商品页面查看实时库存状态。"

        # 场景4：保修咨询
        if re.search(r"warranty|保修|质保|guarantee", msg_lower):
            if has_info("保修期12个月"):
                return "您好！蓝牙耳机 Pro 提供为期12个月的官方质保，涵盖非人为损坏的硬件故障。质保期内可免费维修或更换，请联系客服提供订单号申请售后服务。"
            return "您好！该产品享有官方质保服务，具体保修期限请参考商品详情页或联系客服查询。"

        # 场景5：通用商品咨询（有RAG结果时引用）
        if all_rag_content and len(all_rag_content) > 20:
            return f"您好！关于您咨询的问题，为您整理以下信息：\n{all_rag_content[:200]}\n如果您还有其他疑问，或需要更详细的说明，请随时告诉我，很乐意为您解答。"

        # 兜底
        return "您好！感谢您的咨询。您的问题我已记录，稍后会为您查询详细信息。请问您具体想了解产品的哪方面信息呢？例如规格参数、兼容性、库存状态等，我可以为您提供更精准的解答。"
