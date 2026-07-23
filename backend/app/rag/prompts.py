"""思维链（Chain-of-Thought）Prompt 模板

用于引导大模型进行结构化推理，提升回复质量与准确率。
"""

# 通用思维链模板
COT_SYSTEM_PROMPT = """你是一个专业的跨境电商客服助手。请按照以下思维链步骤处理客户问题：

1. 【意图理解】分析客户的核心诉求
2. 【知识检索】结合提供的参考知识
3. 【情感判断】识别客户情绪状态
4. 【方案制定】给出明确的解决方案
5. 【回复生成】用专业、有温度的语言回复

参考知识：
{context}

请严格基于参考知识回复，避免编造信息。若参考知识不足，请如实告知并建议转人工。"""


COT_USER_TEMPLATE = """客户消息：{message}
客户语言：{lang}
历史对话：{history}

请按思维链步骤处理，最终输出给客户的回复（中文）："""


# 建议回复模板
SUGGEST_PROMPT = """你是跨境电商客服助手。根据以下上下文，生成一条专业的客服回复建议。

客户语言：{lang}
平台：{platform}
历史对话：
{history}

要求：
- 用客户语言（{lang}）生成回复
- 专业、有温度、解决导向
- 不超过100字

建议回复："""


def build_cot_prompt(message: str, lang: str, history: list[dict], context: str = "") -> list[dict]:
    """构建思维链 Prompt

    Returns:
        OpenAI 消息格式
    """
    history_text = "\n".join([f"{m.get('role','user')}: {m.get('content','')}" for m in history[-4:]]) or "无"
    return [
        {"role": "system", "content": COT_SYSTEM_PROMPT.format(context=context or "无")},
        {"role": "user", "content": COT_USER_TEMPLATE.format(message=message, lang=lang, history=history_text)},
    ]


def build_suggest_prompt(lang: str, platform: str, history: list[dict]) -> list[dict]:
    """构建建议回复 Prompt"""
    history_text = "\n".join([f"{m.get('role','user')}: {m.get('content','')}" for m in history[-4:]]) or "无"
    return [
        {"role": "user", "content": SUGGEST_PROMPT.format(lang=lang, platform=platform, history=history_text)},
    ]
