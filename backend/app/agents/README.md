# 多智能体模块

此模块包含基于 LangGraph 构建的 5 大核心智能体（咨询/订单/售后/复购/人工转接）的完整实现，
含能力边界检测、转交上下文、retry/rollback 协作链。

该模块为项目核心业务逻辑，仅展示架构设计，具体实现不包含在开源版本中。

## 架构说明

- **Controller Agent**：意图识别 + 路由决策 + 能力边界检测
- **Consultation Agent**：商品咨询、规格解答
- **Order Agent**：物流查询、订单状态
- **Aftersales Agent**：退款退货、售后处理
- **Repurchase Agent**：复购引导、会员权益
- **Human Handoff Agent**：投诉升级、人工转接

智能体间通过 ContextBus 共享上下文，支持滑动窗口 + 意图聚焦。
