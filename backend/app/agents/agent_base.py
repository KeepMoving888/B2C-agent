"""Agent 基类

统一所有 Agent 的处理流程：
1. 进入时记录 trace
2. 能力边界检测，超界则转交
3. 保存回滚快照
4. 调用具体 Agent 的处理逻辑
5. 处理失败时重试/降级
6. 成功时记录 trace

这样每个 Agent 专注自己的业务逻辑，协作机制由基类统一处理。
"""
from typing import Optional

from loguru import logger

from app.agents.state import AgentState, AgentStatus, HandoffReason
from app.agents.collaboration import (
    check_capability, save_rollback_snapshot, rollback, should_retry,
    record_trace, append_agent_chain, create_handoff_context,
    force_escalate_to_human, AGENT_NAMES,
)


class AgentBase:
    """Agent 基类

    子类需实现：
    - agent_name: Agent 标识
    - _do_process(state): 具体业务处理逻辑，返回 (success: bool, reply_zh: str, detail: str)
    """

    agent_name: str = ""           # Agent 标识（如 "consultation"）
    agent_label: str = ""          # 中文名（如 "咨询Agent"）

    def process(self, state: AgentState) -> AgentState:
        """统一处理流程（模板方法模式）"""
        # 1. 进入时记录 trace
        state = append_agent_chain(state, self.agent_name)
        state = {**state, "current_agent": self.agent_name}
        state = record_trace(state, self.agent_name, self.agent_name,
                             f"进入{self.agent_label}", AgentStatus.RUNNING.value)

        # 2. 能力边界检测
        # 两种情况跳过检测，直接处理：
        #   a) 人工转接Agent 是终点，始终可处理
        #   b) 被前序Agent转交过来（有 handoff_context），信任前序决策
        skip_capability = (
            self.agent_name == "human_handoff"
            or bool(state.get("handoff_context", ""))
        )

        if skip_capability:
            skip_reason = "终点Agent" if self.agent_name == "human_handoff" else "前序Agent转交"
            state = {**state, "capability_check": {
                "capable": True, "reason": "", "suggested_handoff": "",
            }}
            logger.info(f"{self.agent_label} 跳过能力边界检测（{skip_reason}）")
        else:
            cap_check = check_capability(state, self.agent_name)
            state = {**state, "capability_check": cap_check}

            if not cap_check.get("capable", True):
                # 超界，生成转交上下文并转交
                target = cap_check.get("suggested_handoff", "human_handoff")
                reason = cap_check.get("reason", HandoffReason.CAPABILITY_EXCEEDED.value)
                handoff_ctx = create_handoff_context(state, self.agent_name, target, reason)

                state = record_trace(state, self.agent_name, self.agent_name,
                                     f"能力边界检测：{reason}", AgentStatus.HANDOFF.value,
                                     reason, f"建议转交 {target}")
                state = {**state, "handoff_reason": reason, "handoff_context": handoff_ctx}
                logger.info(f"{self.agent_label} 能力边界检测：{reason} → 转交 {target}")
                return state

            logger.info(f"{self.agent_label} 能力边界检测通过，开始处理")

        # 3. 保存回滚快照
        state = save_rollback_snapshot(state)

        # 4. 调用具体处理逻辑
        try:
            success, reply_zh, detail = self._do_process(state)

            if success:
                # --- 反幻觉三层校验（引用溯源 + 置信度阈值 + 答案一致性）---
                should_escalate, reply_zh, anti_halluc_report = \
                    self._apply_anti_hallucination(state, reply_zh)

                if should_escalate:
                    # 高幻觉风险 → 转人工兜底
                    target = "human_handoff"
                    reason = HandoffReason.ANTI_HALLUCINATION.value
                    handoff_ctx = create_handoff_context(state, self.agent_name, target, reason)
                    risk = anti_halluc_report.get("hallucination_risk", "high") if anti_halluc_report else "high"
                    state = record_trace(
                        state, self.agent_name, self.agent_name,
                        f"反幻觉校验未通过(风险={risk})",
                        AgentStatus.HANDOFF.value, reason, "转人工兜底",
                    )
                    state = {
                        **state,
                        "handoff_reason": reason,
                        "handoff_context": handoff_ctx,
                        "anti_hallucination_report": anti_halluc_report,
                    }
                    logger.warning(f"{self.agent_label} 反幻觉校验未通过(风险={risk}) → 转人工")
                    return state

                # 5a. 成功：清除前序 Agent 遗留的转交状态
                state = record_trace(state, self.agent_name, self.agent_name,
                                     f"处理成功", AgentStatus.SUCCESS.value,
                                     detail=detail)
                state = self._set_reply(state, reply_zh)
                state = {
                    **state,
                    "agent_name": self.agent_label,
                    "handoff_reason": HandoffReason.NONE.value,
                    "handoff_context": "",  # 已消费，清除
                    "retry_count": 0,       # 重置重试计数
                    "anti_hallucination_report": anti_halluc_report,
                }
                logger.info(f"{self.agent_label} 处理成功")
                return state

            # 5b. 失败
            state = record_trace(state, self.agent_name, self.agent_name,
                                 f"处理失败（第{state.get('retry_count', 0) + 1}次）",
                                 AgentStatus.FAILED.value,
                                 detail=detail)

            if should_retry(state):
                # 可重试：回滚后重试
                state = rollback(state)
                logger.warning(f"{self.agent_label} 失败，准备重试（第{state.get('retry_count', 0)}次）")
                # 递归重试（受 max_retries 限制）
                return self.process(state)
            else:
                # 重试超限：转交升级
                from app.agents.collaboration import ESCALATION_CHAIN
                target = ESCALATION_CHAIN.get(self.agent_name, "human_handoff")
                reason = HandoffReason.RETRY_EXCEEDED.value
                handoff_ctx = create_handoff_context(state, self.agent_name, target, reason)
                state = record_trace(state, self.agent_name, self.agent_name,
                                     f"重试超限，转交升级", AgentStatus.HANDOFF.value,
                                     reason, f"转交 {target}")
                state = {**state, "handoff_reason": reason, "handoff_context": handoff_ctx}
                logger.warning(f"{self.agent_label} 重试超限，转交 {target}")
                return state

        except Exception as e:
            # 异常处理
            logger.error(f"{self.agent_label} 异常：{e}")
            state = record_trace(state, self.agent_name, self.agent_name,
                                 f"异常：{type(e).__name__}", AgentStatus.FAILED.value,
                                 detail=str(e))
            # 异常直接转人工
            return force_escalate_to_human(state, HandoffReason.ERROR_FALLBACK.value)

    def _apply_anti_hallucination(
        self, state: AgentState, reply_zh: str,
    ) -> tuple[bool, str, Optional[dict]]:
        """反幻觉三层校验：引用溯源 + 置信度阈值 + 答案一致性

        在 Agent 生成回复后、提交为最终回复前执行：
        - 高风险(should_escalate=True) → 标注回复并建议转人工
        - 中风险(hallucination_risk=medium) → 标注[仅供参考]
        - 低风险 → 正常通过

        跳过条件：终点Agent / 无RAG源 / 无回复

        Returns:
            (should_escalate, reply_zh, report_dict)
        """
        # 终点 Agent 跳过
        if self.agent_name == "human_handoff":
            return False, reply_zh, None

        # 无 RAG 源跳过（如订单/售后等依赖业务系统的 Agent）
        rag_sources = state.get("rag_sources", [])
        if not rag_sources:
            return False, reply_zh, None

        # 无回复或过短跳过
        if not reply_zh or len(reply_zh) < 10:
            return False, reply_zh, None

        try:
            from app.rag.anti_hallucination import check_reply, annotate_reply
            query = state.get("message", "")
            intent = state.get("intent", "")
            report = check_reply(query, rag_sources, reply_zh, intent=intent)
            report_dict = report.dict() if hasattr(report, "dict") else dict(report)

            if report.should_escalate:
                annotated = annotate_reply(report, reply_zh)
                logger.warning(
                    f"{self.agent_label} 反幻觉校验：风险={report.hallucination_risk} "
                    f"置信度={report.confidence:.2f}({report.confidence_level}) "
                    f"一致性={report.faithfulness:.2f} → 转人工"
                )
                return True, annotated, report_dict

            # medium 风险：标注但不转人工
            if report.hallucination_risk == "medium":
                reply_zh = annotate_reply(report, reply_zh)
                logger.info(
                    f"{self.agent_label} 反幻觉校验：风险=medium "
                    f"置信度={report.confidence:.2f} → 标注[仅供参考]"
                )
            else:
                logger.info(
                    f"{self.agent_label} 反幻觉校验通过：风险={report.hallucination_risk} "
                    f"置信度={report.confidence:.2f} 一致性={report.faithfulness:.2f}"
                )

            return False, reply_zh, report_dict
        except Exception as e:
            logger.warning(f"{self.agent_label} 反幻觉校验异常(跳过)：{e}")
            return False, reply_zh, None

    def _do_process(self, state: AgentState) -> tuple[bool, str, str]:
        """子类实现：具体业务处理

        Returns:
            (success, reply_zh, detail)
            - success: 是否处理成功
            - reply_zh: 中文回复
            - detail: 调试详情
        """
        raise NotImplementedError

    def _set_reply(self, state: AgentState, reply_zh: str) -> AgentState:
        """设置 Agent 的回复字段"""
        # 翻译
        from app.services.translation import translate
        lang = state.get("lang", "en")
        reply = translate(reply_zh, "zh", lang)

        # 根据 agent_name 设置对应字段
        field_map = {
            "consultation": "consultation_reply",
            "order": "order_reply",
            "aftersales": "aftersales_reply",
            "compliance": "compliance_reply",
            "human_handoff": "human_handoff_reply",
        }
        field = field_map.get(self.agent_name, "consultation_reply")
        return {
            **state,
            field: reply,
            "final_reply": reply,
            "final_reply_zh": reply_zh,
        }
