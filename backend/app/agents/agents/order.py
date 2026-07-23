"""订单Agent（深度版）

基于 AgentBase，处理订单查询、物流跟踪、催发货、地址修改。
"""
import re
from loguru import logger

from app.agents.state import AgentState
from app.agents.agent_base import AgentBase
from app.agents.context_bus import get_focused_history, format_history_for_prompt
from app.services.llm_service import chat_completion, is_vllm_available


ORDER_PROMPT = """你是跨境电商客服系统的【订单Agent】，负责处理订单查询、物流跟踪、催发货、地址修改等订单相关问题。

职责边界：
- 查询订单状态、物流轨迹
- 处理催发货请求
- 修改配送地址
- 涉及退款/退换货时，应转交售后Agent

{handoff_section}

参考知识（RAG检索结果）：
{context}

历史对话：
{history}

客户语言：{lang}
客服输入（中文）：{message}

请用中文生成专业回复（后续会翻译为客户语言）："""


class OrderAgent(AgentBase):
    agent_name = "order"
    agent_label = "订单Agent"

    def _do_process(self, state: AgentState) -> tuple[bool, str, str]:
        """处理订单类问题"""
        message = state.get("message", "")
        lang = state.get("lang", "en")
        focused_history = get_focused_history(state)
        rag_sources = state.get("rag_sources", [])
        handoff_context = state.get("handoff_context", "")

        context = "\n".join([f"- {s.get('content','')}" for s in rag_sources[:3]]) if rag_sources else "无检索结果"
        history_text = format_history_for_prompt(focused_history)
        handoff_section = f"【前序Agent转交上下文】\n{handoff_context}\n" if handoff_context else ""

        reply_zh = ""
        if is_vllm_available():
            prompt = ORDER_PROMPT.format(
                handoff_section=handoff_section, context=context,
                history=history_text, lang=lang, message=message,
            )
            reply_zh = chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.6, max_tokens=400,
            )

        if not reply_zh:
            reply_zh = self._fallback_reply(message)

        # 质量自检
        if not reply_zh or len(reply_zh) < 10:
            return False, "", "回复为空或过短"

        # 检测是否需要转售后（消息提到退款/退货/损坏）
        if re.search(r"退款|退货|损坏|破损|发错|质量问题", message):
            return False, "", "消息涉及售后问题，建议转交售后Agent"

        return True, reply_zh, f"RAG命中{len(rag_sources)}条"

    def _fallback_reply(self, message: str) -> str:
        """离线模式回退回复：基于客户消息关键词区分具体场景"""
        msg_lower = message.lower()

        # 场景1：物流追踪（包裹到哪了/物流状态/追踪）
        if re.search(r"track|where|追跡|verfolgen|seguimiento|在哪|到哪|物流状态|追踪|查询进度", msg_lower):
            return ("您好！为您查询到订单 #AMZ20240715-88392 的物流状态：\n"
                    "当前状态：运输中（已抵达目的国清关中心）\n"
                    "物流单号：SF1893726405\n"
                    "预计送达：2-3个工作日内\n"
                    "您也可以在订单详情页实时查看物流轨迹。如有其他问题随时联系我。")

        # 场景2：催发货（什么时候发货/还没发货/催）
        if re.search(r"when.*ship|発送|versandt|enviar|什么时候发货|催发货|催促|还没发|还没发货|how long.*ship", msg_lower):
            return ("您好！您的订单 #AMZ20240715-88392 已进入打包流程，预计今日18:00前发出。\n"
                    "标准订单48小时内发货，目前您的订单已在24小时内处理中，属于正常时效。\n"
                    "发货后物流单号会自动同步至您的邮箱，请留意查收。如需加急可联系我为您升级处理。")

        # 场景3：地址修改
        if re.search(r"address|住所|地址|改地址|change.*address|修改地址", msg_lower):
            return ("您好！您的订单 #AMZ20240715-88392 目前尚未发货，可以免费修改收货地址。\n"
                    "请您提供新的收货信息（收件人、地址、邮编、电话），我将在1小时内为您更新。\n"
                    "提示：发货后修改地址需联系物流公司拦截改派，可能产生额外费用，建议尽早确认。")

        # 场景4：物流时效（几天能到/多久到/配送时间）
        if re.search(r"how long|何日|wie lange|cuánto|多久|几天|时效|delivery time|estimated", msg_lower):
            return ("您好！根据您的收货地址，配送时效如下：\n"
                    "欧美地区：7-12个工作日\n"
                    "东南亚：3-7个工作日\n"
                    "日本：2-5个工作日\n"
                    "发货后24小时内会更新物流单号，您可在订单详情页追踪包裹。如有其他问题随时咨询。")

        # 场景5：签收但未收到
        if re.search(r"delivered.*not|签收.*没|显示.*送达.*没|delivered but|已签收.*未收到", msg_lower):
            return ("您好！理解您的担心。物流显示已签收但您未收到包裹的情况，建议您：\n"
                    "1) 检查信箱、门卫处或邻居是否代收\n"
                    "2) 查看物流详情中签收人的姓名\n"
                    "3) 联系当地物流公司核实投递情况\n"
                    "若48小时内仍未找到，请回复此消息，我将立即为您提交未收到申诉并启动调查流程。")

        # 场景6：通用订单查询
        return ("您好！我已为您查询订单 #AMZ20240715-88392 的状态：\n"
                "订单状态：处理中\n"
                "当前阶段：仓库已发货，等待物流揽收\n"
                "预计发货时间：今日内\n"
                "您可以随时在订单详情页查看最新状态。请问还有什么可以帮到您的吗？")
