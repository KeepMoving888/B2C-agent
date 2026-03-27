"""订单相关 API 封装 - 订单信息、状态查询"""

from typing import Optional
from langchain_core.tools import tool

# 查询订单状态
@tool
def get_order_status(order_id: str, platform: str = "amazon") -> str:
    """
    查询订单状态。支持独立站与亚马逊多站点。
    Args:
        order_id: 订单号
        platform: 平台标识 amazon / shopify / 独立站
    """
    # 实际接入：调用订单系统 API
    return f"[订单系统] 订单 {order_id} 在 {platform} 上状态：已发货"

# 获取订单详情
@tool
def get_order_details(order_id: str, platform: str = "amazon") -> str:
    """
    获取订单详情：商品、金额、收货地址等
    """
    return f"[订单系统] 订单 {order_id} 详情：CarPlay 适配器 x1, 金额 $29.99"

# 列出用户最近订单
@tool
def list_user_orders(
    user_id: str,
    limit: int = 10,
    status: Optional[str] = None,
) -> str:
    """
    列出用户最近订单
    Args:
        user_id: 用户 ID 或邮箱
        limit: 返回条数
        status: 筛选状态 pending/shipped/delivered
    """
    return f"[模拟] 用户 {user_id} 最近 {limit} 笔订单"

# 订单相关工具列表
order_tools = [get_order_status, get_order_details, list_user_orders]
