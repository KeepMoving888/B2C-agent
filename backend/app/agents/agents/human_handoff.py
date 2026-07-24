"""人工转接Agent（深度版）

基于 AgentBase，作为协作链路的终点：
- 接收前序 Agent 的转交上下文
- 生成对话摘要便于人工接手
- 创建工单
"""
import re
import time
import random
from loguru import logger

from app.agents.state import AgentState
from app.agents.agent_base import AgentBase
from app.agents.context_bus import get_focused_history, format_history_for_prompt
from app.services.llm_service import chat_completion, is_vllm_available


HUMAN_HANDOFF_PROMPT = """你是跨境电商客服系统的【人工转接Agent】，负责将复杂问题、投诉升级、不满情绪客户转接至人工客服。

触发条件：
- 客户不满情绪超过阈值
- 涉及投诉、法律纠纷
- 复杂售后问题超出AI处理范围
- 客户明确要求人工服务
- 前序Agent处理失败或重试超限

{handoff_section}

历史对话：
{history}

客户语言：{lang}
客服输入（中文）：{message}
情感分析：{sentiment}
前序Agent处理链：{agent_chain}

请用中文生成：
1. 对客户的安抚回复（后续会翻译为客户语言）
2. 人工客服接手摘要（内部使用）

回复："""


class HumanHandoffAgent(AgentBase):
    agent_name = "human_handoff"
    agent_label = "人工转接Agent"

    def _do_process(self, state: AgentState) -> tuple[bool, str, str]:
        """处理人工转接"""
        message = state.get("message", "")
        lang = state.get("lang", "en")
        focused_history = get_focused_history(state)
        sentiment = state.get("sentiment", {})
        handoff_context = state.get("handoff_context", "")
        agent_chain = state.get("agent_chain", [])

        history_text = format_history_for_prompt(focused_history)
        handoff_section = f"【前序Agent转交上下文】\n{handoff_context}\n" if handoff_context else ""

        reply_zh = ""
        if is_vllm_available():
            prompt = HUMAN_HANDOFF_PROMPT.format(
                handoff_section=handoff_section, history=history_text,
                lang=lang, message=message, sentiment=sentiment,
                agent_chain=" → ".join(agent_chain),
            )
            reply_zh = chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.5, max_tokens=400,
            )

        if not reply_zh:
            reply_zh = self._fallback_reply(message, sentiment)

        # 创建工单
        ticket_id = self._create_ticket(state)
        logger.info(f"人工转接Agent 创建工单 {ticket_id}，处理链：{' → '.join(agent_chain)}")

        return True, reply_zh, f"工单号={ticket_id}，处理链长度={len(agent_chain)}"

    def _fallback_reply(self, message: str, sentiment: dict, state: AgentState = None) -> str:
        """离线模式回退回复：根据情绪强度和转接原因生成针对性安抚"""
        msg_lower = message.lower()
        negative = sentiment.get("negative", 0)

        # 判断转接原因
        is_complaint = bool(re.search(r"投诉|complain|律师|lawyer|起诉|sue|法院|court|曝光|媒体|差评|bad review|维权|rights", msg_lower))
        is_request_human = bool(re.search(r"人工|human|agent|真人|real person|manager|supervisor|主管|经理|manager", msg_lower))
        is_urgent = bool(re.search(r"紧急|urgent|马上|immediately|asap|立刻|马上|现在|now|加急", msg_lower))

        # 场景1：投诉/法律威胁 - 最高优先级安抚
        if is_complaint or negative >= 75:
            return ("尊敬的客户，非常抱歉给您带来如此不好的体验。\n"
                    "我完全理解您的心情，您的问题我已经记录并标记为最高优先级。\n"
                    "已为您加急转接至高级客服主管，工单 #TKT-URGENT，主管将在5分钟内主动联系您。\n"
                    "同时我会将您的完整对话记录和问题摘要转交给主管，避免您重复说明。\n"
                    "我们一定会给您一个满意的解决方案，请您稍候。")

        # 场景2：客户主动要求人工服务
        if is_request_human:
            return ("您好！已为您转接人工客服。\n"
                    "您的对话记录已同步给客服专员，无需您重复说明问题。\n"
                    "当前排队人数较少，预计等待1-3分钟。\n"
                    "为加快处理速度，建议您提前准备好：订单号、问题描述、相关截图。\n"
                    "客服专员将通过此会话与您沟通，请保持在线。感谢您的耐心。")

        # 场景3：紧急问题
        if is_urgent:
            return ("您好！理解您的紧急情况，已为您加急处理：\n"
                    "1) 已标记为紧急工单 #TKT-PRIORITY\n"
                    "2) 优先分配至资深客服专员\n"
                    "3) 预计5分钟内响应\n"
                    "4) 您的问题摘要已同步给专员\n"
                    "我们会以最快速度为您解决，请稍候。")

        # 场景4：一般情绪不满
        if negative >= 50:
            return ("非常抱歉给您带来不便，我理解您的感受。\n"
                    "该问题需要人工客服进一步处理，已为您转接至对应技能组。\n"
                    "工单已创建 #TKT-STD，客服专员将尽快与您联系。\n"
                    "您的对话记录已同步，无需重复说明。我们会全力解决您的问题，请您放心。")

        # 场景5：一般转接
        return ("感谢您的耐心。该问题需要人工客服进一步核实处理，已为您转接至对应技能组。\n"
                "工单已创建 #TKT-STD，您的对话记录已同步给客服专员。\n"
                "预计等待3-5分钟，客服专员将通过此会话与您联系。"
                "如需加急处理请回复\"加急\"，如有其他问题也可随时告诉我。")

    def _create_ticket(self, state: AgentState) -> str:
        """创建转接工单"""
        ticket_id = f"TKT-{int(time.time())}-{random.randint(1000, 9999)}"
        # 生产环境中此处应调用工单系统 API
        return ticket_id
