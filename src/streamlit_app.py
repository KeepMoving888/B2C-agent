"""Streamlit 应用入口（适配 Streamlit Cloud / Python 3.11）。"""

from __future__ import annotations

import sys
from pathlib import Path

# 兼容本地/Streamlit Cloud 启动路径，确保可导入 src 包
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.messages import HumanMessage
import streamlit as st

from src.agents import create_customer_service_graph
from src.agents.fast_routing import check_faq_response
from src.state.schema import ConversationState
from src.config.settings import settings


@st.cache_resource
def get_graph():
    return create_customer_service_graph()


def run_chat(user_message: str, language: str = "zh", platform: str = "website") -> dict:
    faq_response = check_faq_response(user_message, user_message, platform, language)
    if faq_response:
        return {
            "response": faq_response,
            "agent": "faq_fast",
            "model": "faq_cache",
        }

    state: ConversationState = {
        "messages": [HumanMessage(content=user_message)],
        "session_metadata": {
            "platform": platform,
            "language": language,
        },
    }

    result = get_graph().invoke(state)
    last_msg = result["messages"][-1]

    model_name = result.get("selected_model", "unknown")
    if settings.qwen_api_key:
        model_name = "qwen-plus"

    return {
        "response": last_msg.content,
        "agent": result.get("current_agent", "unknown"),
        "model": model_name,
    }


def main() -> None:
    st.set_page_config(page_title="B2C 多 Agent 智能客服", layout="centered")
    st.title("B2C 多 Agent 智能客服")
    st.caption("Qwen API 优先，适配 Streamlit Cloud")

    with st.sidebar:
        st.subheader("会话设置")
        language = st.selectbox("语言", ["zh", "en", "es", "de", "fr", "ja", "th", "vi"], index=0)
        platform = st.selectbox("平台", ["website", "amazon", "shopify", "ebay"], index=0)
        st.markdown("---")
        st.write("本地模型路径：")
        st.code(str(settings.local_model_dir))

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("请输入您的问题...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                result = run_chat(user_input, language=language, platform=platform)
            reply = result["response"]
            st.markdown(reply)
            st.caption(f"Agent: {result['agent']} | Model: {result['model']}")

        st.session_state.messages.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
