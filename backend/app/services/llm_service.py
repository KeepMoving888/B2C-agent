"""模型服务对接层

对接 OpenAI 兼容接口，提供统一的大模型调用能力。
支持 vLLM / OpenAI / DeepSeek / Qwen / 自定义 五种 provider，
所有 provider 均不可用时自动回退至规则引擎模式，保证服务可用性。

向后兼容：
- is_vllm_available() 接口保留，等价于 is_llm_available()（任意 provider 可用即为 True）
- chat_completion() 签名不变
"""
from typing import Optional
from loguru import logger

from app.config import settings

# 客户端懒加载
_client = None
_client_inited = False
_llm_available = False  # 统一可用性标志（任意 provider 可用即为 True）
_llm_mode: str = "rule"  # 当前实际生效的推理模式


def _resolve_provider_config() -> tuple[str, str, str]:
    """根据 llm_provider 配置返回 (base_url, api_key, model)

    支持: vllm / openai / deepseek / qwen / custom
    custom 复用 openai_* 配置项作为通用 OpenAI 兼容端点。
    """
    provider = (settings.llm_provider or "vllm").strip().lower()
    if provider == "openai":
        return settings.openai_base_url, settings.openai_api_key, settings.openai_model
    if provider == "deepseek":
        return settings.deepseek_base_url, settings.deepseek_api_key, settings.deepseek_model
    if provider == "qwen":
        return settings.qwen_base_url, settings.qwen_api_key, settings.qwen_model
    if provider == "custom":
        # custom: 通用 OpenAI 兼容端点，复用 openai_* 配置
        return settings.openai_base_url, settings.openai_api_key, settings.openai_model
    # 默认 vllm
    return settings.vllm_base_url, settings.vllm_api_key, settings.vllm_model


def _init_client():
    """初始化 LLM 客户端（按 llm_provider 选择对应后端，不阻塞启动）

    探测失败时记录明确的 warning 日志，并回退至规则引擎模式。
    探测超时由 llm_request_timeout 控制（默认 15 秒）。
    """
    global _client, _client_inited, _llm_available, _llm_mode
    if _client_inited:
        return
    _client_inited = True

    provider = (settings.llm_provider or "vllm").strip().lower()
    base_url, api_key, model = _resolve_provider_config()
    timeout = settings.llm_request_timeout

    # 云服务商必须有 API Key（vllm 默认 EMPTY 可放行）
    if provider in ("openai", "deepseek", "qwen", "custom") and not api_key:
        logger.warning(
            f"LLM provider={provider} 未配置 API Key（{provider}_api_key 为空），"
            f"回退至规则引擎模式"
        )
        _llm_available = False
        _llm_mode = "rule"
        return

    try:
        from openai import OpenAI
        _client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=0,
        )
        # 探测可用性
        _client.models.list()
        _llm_available = True
        _llm_mode = provider
        logger.info(
            f"LLM 推理服务已连接: provider={provider} base_url={base_url} model={model}"
        )
    except Exception as e:
        _llm_available = False
        _llm_mode = "rule"
        logger.warning(
            f"LLM 推理服务不可用（provider={provider}, base_url={base_url}），"
            f"回退至规则引擎模式: {type(e).__name__}: {e}"
        )
        _client = None


def is_vllm_available() -> bool:
    """LLM 是否可用（向后兼容接口）

    历史命名保留：等价于 is_llm_available()，即任意 provider 可用即返回 True。
    新代码建议直接使用 is_llm_available()。
    """
    _init_client()
    return _llm_available


def is_llm_available() -> bool:
    """统一判断当前 LLM 是否可用（任意 provider: vllm/openai/deepseek/qwen/custom）"""
    _init_client()
    return _llm_available


def get_mode() -> str:
    """获取当前推理模式

    返回值: "vllm" / "openai" / "deepseek" / "qwen" / "custom" / "rule"
    """
    _init_client()
    return _llm_mode


def chat_completion(
    messages: list[dict],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """调用大模型生成回复

    Args:
        messages: OpenAI 消息格式 [{"role":"system","content":"..."},...]
        temperature: 采样温度
        max_tokens: 最大生成 token 数

    Returns:
        模型生成的文本；不可用或调用失败时返回空字符串（由上层回退规则引擎）
    """
    _init_client()
    if not _llm_available or _client is None:
        return ""

    _, _, model = _resolve_provider_config()
    try:
        resp = _client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature or settings.llm_temperature,
            max_tokens=max_tokens or settings.llm_max_tokens,
            top_p=settings.llm_top_p,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM 调用失败 (provider={settings.llm_provider}): {e}")
        return ""
