"""售后相关 API 封装 - 退换货标签、退款预审批"""

from langchain_core.tools import tool

# 自动生成退换货标签
@tool
def create_return_label(
    order_id: str,
    reason: str = "customer_return",
    product_sku: str = "",
) -> str:
    """
    自动生成退换货标签
    Args:
        order_id: 订单号
        reason: 退货原因
        product_sku: 商品 SKU（可选）
    """
    return f"[售后系统] 已为订单 {order_id} 生成退换货标签，打印链接已发送邮箱"

# 预审批退款申请
@tool
def pre_approve_refund(
    order_id: str,
    amount: float,
    reason: str = "defective",
) -> str:
    """
    预审批退款申请
    Args:
        order_id: 订单号
        amount: 退款金额
        reason: 退款原因 defective/damaged/not_as_described
    """
    return f"[售后系统] 订单 {order_id} 退款 ${amount} 已预审批，1-3 工作日到账"

# 查询退货进度
@tool
def get_return_status(return_id: str) -> str:
    """查询退货进度"""
    return f"[售后系统] 退货单 {return_id} 状态：仓库已收货，退款处理中"

# 发起换货申请
@tool
def create_exchange_request(
    order_id: str,
    original_sku: str,
    new_sku: str,
    reason: str = "wrong_item",
) -> str:
    """发起换货申请"""
    return f"[售后系统] 订单 {order_id} 换货申请已提交：{original_sku} -> {new_sku}"

# 售后相关工具列表
after_sales_tools = [
    create_return_label,
    pre_approve_refund,
    get_return_status,
    create_exchange_request,
]
