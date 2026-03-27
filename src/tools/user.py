"""用户相关 API 封装 - 用户信息、会话转接"""

from langchain_core.tools import tool

# 获取用户画像
@tool
def get_user_profile(user_id: str) -> str:
    """获取用户画像：订单数、偏好、历史问题类型"""
    return f"[用户系统] 用户 {user_id}：3 笔订单，偏好英语，曾咨询过物流"

# 会话转接人工客服
@tool
def escalate_to_human(
    session_id: str,
    reason: str,
    priority: str = "normal",
) -> str:
    """
    将会话转接人工客服
    Args:
        session_id: 会话 ID
        reason: 转接原因
        priority: 优先级 urgent/normal/low
    """
    return f"[模拟] 会话 {session_id} 已排队转人工，原因：{reason}"

# 用户工具列表
user_tools = [get_user_profile, escalate_to_human]
