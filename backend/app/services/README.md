# 业务服务模块

此模块包含 LLM 调用、翻译、情感分析、意图识别等业务服务实现。

该模块为项目业务逻辑，仅展示架构设计，具体实现不包含在开源版本中。

## 服务说明

- **LLM Service**：支持 DeepSeek / vLLM / OpenAI 多后端
- **Translation Service**：8 种语言实时互译
- **Sentiment Service**：分级关键词 + 强度修饰词情感分析
- **Intent Service**：双层意图识别 + 置信度评分
