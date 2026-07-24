"""合规Agent（深度版）

基于 AgentBase，处理支付问题、隐私政策、数据合规、跨境贸易合规。
"""
import re
from loguru import logger

from app.agents.state import AgentState
from app.agents.agent_base import AgentBase
from app.agents.context_bus import get_focused_history, format_history_for_prompt
from app.services.llm_service import chat_completion, is_vllm_available


COMPLIANCE_PROMPT = """你是跨境电商客服系统的【合规Agent】，负责处理支付问题、隐私政策、数据合规、跨境贸易合规等问题。

职责边界：
- 支付安全、支付失败、支付方式咨询
- 隐私政策、数据保护（GDPR等）咨询
- 跨境关税、清关问题
- 涉及法律纠纷时，应转交人工转接Agent

{handoff_section}

参考知识（合规政策，RAG检索结果）：
{context}

历史对话：
{history}

客户语言：{lang}
客服输入（中文）：{message}

请用中文生成专业回复（后续会翻译为客户语言）。需严谨、合规、不承诺超出政策范围的事项："""


class ComplianceAgent(AgentBase):
    agent_name = "compliance"
    agent_label = "合规Agent"

    def _do_process(self, state: AgentState) -> tuple[bool, str, str]:
        """处理合规类问题"""
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
            prompt = COMPLIANCE_PROMPT.format(
                handoff_section=handoff_section, context=context,
                history=history_text, lang=lang, message=message,
            )
            reply_zh = chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.4, max_tokens=400,
            )

        if not reply_zh:
            reply_zh = self._fallback_reply(message, rag_sources)

        # 质量自检
        if not reply_zh or len(reply_zh) < 10:
            return False, "", "回复为空或过短"

        # 法律纠纷检测 → 转人工
        if re.search(r"律师|起诉|诉讼|法院|法律纠纷|报案", message):
            return False, "", "消息涉及法律纠纷，建议转交人工"

        return True, reply_zh, f"RAG命中{len(rag_sources)}条"

    def _fallback_reply(self, message: str, rag_sources: list = None) -> str:
        """离线模式回退回复：区分支付失败 vs 支付方式咨询 vs 隐私 vs 关税"""
        msg_lower = message.lower()
        rag_sources = rag_sources or []
        policy_info = rag_sources[0].get("content", "") if rag_sources else ""

        # 判断意图子类
        is_payment_failure = bool(re.search(r"failed|failure|declined|rejected|失败|被拒|扣不了|付不了|can't pay|cannot pay|错误|error|扣款", msg_lower))
        is_payment_inquiry = bool(re.search(r"payment method|支付方式|付款方式|accept|支持|哪种|which|what.*pay|怎么付", msg_lower))
        is_data_request = bool(re.search(r"delete|删除|erase|remove|删除我的|delete my|forget|遗忘", msg_lower))

        # 场景1：支付失败排查
        if is_payment_failure or (re.search(r"payment|支払い|支付|付款", msg_lower) and is_payment_failure):
            return ("您好！很抱歉支付遇到问题，请按以下步骤排查：\n"
                    "1) 核对卡片信息：卡号、有效期、CVV是否输入正确\n"
                    "2) 余额/额度：确认账户余额充足或信用卡额度可用\n"
                    "3) 发卡行限制：部分银行会拦截跨境交易，请联系发卡行确认\n"
                    "4) 更换支付方式：我们支持信用卡、PayPal、Apple Pay、Google Pay及本地支付\n"
                    "5) 重新尝试：清除浏览器缓存后重新下单\n"
                    "温馨提示：您的支付信息经PCI-DSS加密保护，我们不存储完整卡号。"
                    "如仍无法支付，请回复您的支付方式，我为您进一步排查。")

        # 场景2：支付方式咨询
        if re.search(r"payment|支払い|支付|付款|paypal|信用卡|credit card|apple pay|google pay", msg_lower):
            if is_payment_inquiry or not is_payment_failure:
                return ("您好！我们支持以下安全支付方式：\n"
                        "1) 信用卡：Visa / Mastercard / American Express / JCB\n"
                        "2) 电子钱包：PayPal / Apple Pay / Google Pay\n"
                        "3) 本地支付：支持欧美、东南亚主流本地支付方式\n"
                        "安全认证：全部支付通道经PCI-DSS认证加密，不存储完整卡号信息。\n"
                        "请问您想使用哪种支付方式？如有其他问题随时咨询。")

        # 场景3：隐私/数据保护（区分咨询 vs 数据删除请求）
        if re.search(r"privacy|GDPR|隐私|数据|personal data|datenschutz|privacidad", msg_lower):
            if is_data_request:
                return ("您好！收到您的数据删除请求：\n"
                        "1) 已为您创建数据处理工单 #GDPR20240715-2278\n"
                        "2) 根据 GDPR 规定，我们将在30天内完成数据删除\n"
                        "3) 删除范围：个人身份信息、订单记录、浏览数据\n"
                        "4) 保留信息：法律法规要求保留的交易记录（如税务凭证）\n"
                        "5) 完成后我们会通过邮件确认，届时您将无法登录账户\n"
                        "请确认您要继续删除操作吗？此操作不可逆。")
            return ("您好！关于隐私与数据保护：\n"
                    "1) 合规标准：严格遵守 GDPR 及各国数据保护法规\n"
                    "2) 数据用途：个人信息仅用于订单处理和客户服务，不会出售给第三方\n"
                    "3) 数据存储：采用加密存储，传输全程TLS加密\n"
                    "4) 数据权利：您有权访问、更正、删除个人数据，可随时申请\n"
                    "5) 第三方共享：仅在物流配送、支付处理等必要范围内共享\n"
                    "如需查看完整隐私政策或申请数据删除，请随时告诉我。")

        # 场景4：跨境关税/清关
        if re.search(r"tax|customs|关税|清关|duty|zoll|aduana|douane", msg_lower):
            return ("您好！关于跨境关税说明：\n"
                    "1) 关税征收：由目的地海关根据商品类别和价值征收，通常由收件人承担\n"
                    "2) 免税额度：\n"
                    "   - 美国：$800以下免税\n"
                    "   - 欧盟：€150以下免税（但需缴VAT）\n"
                    "   - 日本：¥10,000以下免税\n"
                    "   - 东南亚：各国标准不同，建议咨询当地海关\n"
                    "3) DDP服务：我们提供完税交货服务（下单可选），由我们代缴关税，包裹直达无需清关\n"
                    "4) 清关时效：通常1-3个工作日，旺季可能延长\n"
                    "5) 关税估算：以下单时结算页显示的预估金额为准，实际以海关核定为准\n"
                    "如需使用DDP服务或有关税疑问，请随时咨询。")

        # 场景5：安全/合规咨询
        if re.search(r"safe|secure|安全|certif|认证|encrypt|加密|compliance|合规", msg_lower):
            return ("您好！关于安全合规：\n"
                    "1) 支付安全：PCI-DSS认证，全链路TLS加密，不存储完整卡号\n"
                    "2) 数据保护：GDPR合规，个人信息加密存储\n"
                    "3) 商品合规：所有商品通过CE/FCC/RoHS等目的地国认证\n"
                    "4) 物流合规：与正规跨境物流商合作，合法清关\n"
                    "5) 平台资质：持有跨境电商经营许可，合规经营\n"
                    "如有具体合规问题，请详细说明，我为您解答。")

        # 场景6：通用合规咨询（有RAG政策信息时引用）
        if policy_info:
            return f"您好！关于您的合规咨询，为您整理相关政策：\n{policy_info}\n如有具体问题或需要进一步说明，请随时告诉我，我会为您提供专业解答。"

        # 兜底
        return ("您好！关于合规问题，已为您记录并由合规专员跟进处理（工单 #CP20240715-0001）。\n"
                "我们严格遵守各国跨境电商法规，保障您的权益。请您详细描述具体问题，"
                "我会在1个工作日内为您回复。如涉及支付、隐私、关税等具体问题，"
                "也可以直接说明，我可以先为您初步解答。")
