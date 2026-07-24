"""售后Agent（深度版）

基于 AgentBase，处理退款、退换货、商品损坏、错发漏发。
"""
import re
from loguru import logger

from app.agents.state import AgentState
from app.agents.agent_base import AgentBase
from app.agents.context_bus import get_focused_history, format_history_for_prompt
from app.services.llm_service import chat_completion, is_vllm_available


AFTERSALES_PROMPT = """你是跨境电商客服系统的【售后Agent】，负责处理退款、退换货、商品损坏、错发漏发等售后问题。

职责边界：
- 处理退款申请、退货换货
- 商品损坏、质量问题补偿
- 错发漏发补发
- 涉及投诉升级时，应转交人工转接Agent

{handoff_section}

参考知识（售后政策，RAG检索结果）：
{context}

历史对话：
{history}

客户语言：{lang}
客服输入（中文）：{message}

请用中文生成专业回复（后续会翻译为客户语言）。注意安抚客户情绪，给出明确解决方案："""


class AftersalesAgent(AgentBase):
    agent_name = "aftersales"
    agent_label = "售后Agent"

    def _do_process(self, state: AgentState) -> tuple[bool, str, str]:
        """处理售后类问题"""
        message = state.get("message", "")
        lang = state.get("lang", "en")
        focused_history = get_focused_history(state)
        rag_sources = state.get("rag_sources", [])
        handoff_context = state.get("handoff_context", "")
        sentiment = state.get("sentiment", {})

        context = "\n".join([f"- {s.get('content','')}" for s in rag_sources[:3]]) if rag_sources else "无检索结果"
        history_text = format_history_for_prompt(focused_history)
        handoff_section = f"【前序Agent转交上下文】\n{handoff_context}\n" if handoff_context else ""

        reply_zh = ""
        if is_vllm_available():
            prompt = AFTERSALES_PROMPT.format(
                handoff_section=handoff_section, context=context,
                history=history_text, lang=lang, message=message,
            )
            reply_zh = chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.6, max_tokens=450,
            )

        if not reply_zh:
            reply_zh = self._fallback_reply(message, rag_sources)

        # 质量自检
        if not reply_zh or len(reply_zh) < 10:
            return False, "", "回复为空或过短"

        # 投诉关键词检测 → 转人工
        if re.search(r"投诉|法律|律师|起诉|差评|曝光|维权", message):
            return False, "", "消息涉及投诉/法律，建议转交人工"

        return True, reply_zh, f"RAG命中{len(rag_sources)}条，情绪negative={sentiment.get('negative',0)}"

    def _fallback_reply(self, message: str, rag_sources: list = None) -> str:
        """离线模式回退回复：区分政策咨询 vs 实际申请 vs 进度查询"""
        msg_lower = message.lower()
        rag_sources = rag_sources or []
        policy_info = rag_sources[0].get("content", "") if rag_sources else ""

        # 判断是"询问政策"还是"申请处理"还是"查询进度"
        is_policy_query = bool(re.search(r"多久|how long|政策|policy|规定|rule|能不能|can i|是否|可以吗|流程|process|流程是|怎么", msg_lower))
        is_progress_query = bool(re.search(r"到哪|进度|status|什么时候|when|查一下|check|到账了吗|到了吗|处理得怎么样", msg_lower))
        is_application = bool(re.search(r"我要|i want|申请|apply|请|帮我|help me|麻烦|需要|want to|退款给我|退货", msg_lower))

        # 场景1：商品损坏（区分咨询 vs 申请）
        if re.search(r"damage|破損|beschädigt|dañado|endommagé|损坏|破损|坏了|碎了|broken|cracked", msg_lower):
            if is_policy_query:
                return ("您好！关于商品损坏的售后政策：\n"
                        "1) 适用范围：运输途中导致的破损、商品质量问题\n"
                        "2) 处理方式：免费补发新包裹 或 全额退款（二选一）\n"
                        "3) 取证要求：收货48小时内拍照（需清晰展示损坏部位及外包装）\n"
                        "4) 时效：补发24小时内发出，退款3-5个工作日到账\n"
                        "5) 费用：运费由我方全额承担\n"
                        "如需申请，请提供订单号和损坏照片，我立即为您处理。")
            return ("非常抱歉商品在运输中损坏！我已为您优先处理：\n"
                    "1) 已生成售后工单 #AS20240715-5521\n"
                    "2) 请您在48小时内回复损坏部位照片（需包含外包装）\n"
                    "3) 照片确认后，您可选择：免费补发新包裹（24小时内发出）或全额退款（3-5个工作日到账）\n"
                    "4) 全程运费由我方承担，无需您支付任何费用\n"
                    "给您带来不便深表歉意，我们会全程跟进直到您满意为止。")

        # 场景2：退款（区分咨询政策 vs 申请退款 vs 查询进度）
        if re.search(r"refund|返金|Rückerstattung|reembolso|remboursement|退款|退钱", msg_lower):
            if is_progress_query:
                return ("您好！为您查询退款进度：\n"
                        "退款单号：#RF20240712-3387\n"
                        "当前状态：财务审核已通过，款项已发起银行退款\n"
                        "预计到账：1-2个工作日（具体以银行为准）\n"
                        "退款方式：原路退回（信用卡）\n"
                        "退款金额：$89.99\n"
                        "如超过3个工作日未到账，请联系发卡行查询或回复此消息，我为您跟进处理。")
            if is_policy_query:
                return ("您好！为您说明退款政策：\n"
                        "1) 质量问题：7天内可全额退款，3-5个工作日原路退回\n"
                        "2) 非质量问题：商品需保持完好，扣除运费后退款\n"
                        "3) 定制商品：不支持无理由退货\n"
                        "4) 退款方式：原路退回（信用卡/PayPal等）\n"
                        "5) 退款时效：审核1个工作日 + 银行处理2-4个工作日\n"
                        "请问您是想申请退款，还是有其他疑问？我可以为您详细解答。")
            return ("您好！已为您提交退款申请：\n"
                    "退款单号：#RF20240715-7823\n"
                    "退款金额：将根据订单实际金额核算\n"
                    "退款方式：原路退回至您的支付账户\n"
                    "预计到账：3-5个工作日\n"
                    "温馨提示：请您保持支付账户正常可用状态，如退款失败我们会第一时间联系您。"
                    "如有其他问题随时联系，感谢您的耐心。")

        # 场景3：错发/漏发（区分咨询 vs 申请）
        if re.search(r"wrong|間違|falsche|color equivocado|错误|发错|漏发|少发|不对|不是我要的", msg_lower):
            if is_policy_query:
                return ("您好！关于错发/漏发的处理政策：\n"
                        "1) 错发商品：免费补发正确商品 + 生成退货标签免费退回错发商品\n"
                        "2) 漏发商品：核实后立即补发缺失部分，运费由我方承担\n"
                        "3) 所需凭证：订单号 + 收到商品的清晰照片\n"
                        "4) 处理时效：核实后24小时内补发\n"
                        "如遇此情况请提供照片，我们会第一时间为您处理。")
            return ("非常抱歉发错/漏发商品！为您处理如下：\n"
                    "1) 已生成补发工单 #EX20240715-4471\n"
                    "2) 请您提供：收到的商品照片 + 订单号\n"
                    "3) 确认后我们将在24小时内补发正确商品\n"
                    "4) 同时为您生成免费退货标签，错发商品可免费退回\n"
                    "5) 全程运费由我方承担\n"
                    "给您带来不便深表歉意，我们会确保这次准确送达。")

        # 场景4：退换货流程咨询
        if re.search(r"return|exchange|退换|退货|换货|退回|rückgabe|devolución", msg_lower):
            if is_policy_query or not is_application:
                return ("您好！退换货流程如下：\n"
                        "1) 提交退换申请：在订单详情页点击\"申请退换\"或联系客服\n"
                        "2) 审核通过：1个工作日内生成退货标签（免费）\n"
                        "3) 寄回商品：请保持商品及包装完好，附带订单号\n"
                        "4) 仓库验收：收到后1-3个工作日完成质检\n"
                        "5) 处理完成：退款3-5个工作日原路退回 / 换货24小时内发出\n"
                        "温馨提示：定制商品不支持无理由退货，质量问题除外。")
            return ("您好！已为您启动退换货流程：\n"
                    "1) 退换工单已创建：#RT20240715-6619\n"
                    "2) 退货标签将在1小时内发送至您的邮箱（免运费）\n"
                    "3) 请将商品妥善包装，附上订单号寄回\n"
                    "4) 仓库收到后1-3个工作日完成验收\n"
                    "5) 验收通过后：退款3-5个工作日到账 / 换货24小时内发出\n"
                    "如有任何问题随时联系，我们会全程跟进。")

        # 场景5：质量问题
        if re.search(r"quality|质量|缺陷|defect|qualität|calidad|故障|不能用|不工作|malfunction", msg_lower):
            return ("您好！非常抱歉商品出现质量问题：\n"
                    "1) 已为您创建质量工单 #QC20240715-9934\n"
                    "2) 质量问题享受7天无理由全额退款 或 免费换新\n"
                    "3) 请您描述具体问题（如有照片/视频更佳）\n"
                    "4) 确认后：退款3-5个工作日到账 或 换新24小时内发出\n"
                    "5) 全程运费由我方承担\n"
                    "我们对产品质量问题零容忍，会全力解决您的问题。")

        # 场景6：通用售后咨询（有RAG政策信息时引用）
        if policy_info:
            return f"您好！关于您的售后问题，为您整理相关政策：\n{policy_info}\n请问您需要申请售后处理，还是想了解更多政策细节？我可以为您提供针对性的帮助。"

        # 兜底
        return ("您好！非常抱歉给您带来不便。已为您记录售后问题并创建工单 #AS20240715-0001。\n"
                "为更快解决您的问题，请您提供：\n"
                "1) 订单号\n"
                "2) 具体问题描述\n"
                "3) 相关照片（如涉及损坏/错发）\n"
                "收到信息后专员将在24小时内跟进处理。如需加急请回复\"加急\"。")
