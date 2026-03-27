"""物流相关 API 封装 - 多物流商轨迹查询"""

from langchain_core.tools import tool

# 查询物流轨迹
@tool
def get_tracking_info(tracking_number: str, carrier: str = "auto") -> str:
    """
    查询物流轨迹。支持多物流商：DHL、FedEx、USPS、顺丰国际等。
    Args:
        tracking_number: 物流单号
        carrier: 物流商，auto 可自动识别
    """
    return f"[物流系统] 物流单 {tracking_number}：已到达目的地国家清关"

# 预估物流时效与费用
@tool
def get_shipping_estimate(
    country_code: str,
    weight_kg: float = 0.2,
    product_type: str = "carplay",
) -> str:
    """
    预估物流时效与费用
    """
    return f"[物流系统] 发往 {country_code} 预估 7-14 工作日，约 $5.99"

# 查询仓库库存
@tool
def get_warehouse_inventory(sku: str, region: str = "US") -> str:
    """
    查询仓库库存（多站点）
    """
    return f"[模拟] SKU {sku} 在 {region} 仓库存 500 件"


logistics_tools = [get_tracking_info, get_shipping_estimate, get_warehouse_inventory]
