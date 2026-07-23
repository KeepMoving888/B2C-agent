# 测试用例

此目录包含 74 项单元测试用例，覆盖多语言预处理、意图识别、反幻觉校验、上下文总线、监控指标、检索引擎等模块。

测试用例不包含在开源版本中。

## 测试覆盖

| 模块 | 测试文件 | 覆盖能力 |
|------|---------|---------|
| 多语言预处理 | test_multilingual.py | 语言识别（8种）、NFKC归一化、分区路由 |
| 意图识别 | test_intent.py | 双层识别、置信度评分、10类意图覆盖 |
| 反幻觉校验 | test_anti_hallucination.py | 引用溯源、置信度分档、事实一致性 |
| 上下文总线 | test_context_bus.py | 滑动窗口、意图聚焦、上下文摘要 |
| 监控指标 | test_metrics.py | 指标采集、Prometheus exposition |
| 检索引擎 | test_retriever.py | CoT查询扩展、RRF融合、去重、分词 |
