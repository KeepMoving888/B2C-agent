"""工具注册中心 - 第三方业务 API 集成框架

支持的第三方应用：
- 飞书 (Feishu)
- 钉钉 (DingTalk)
- 企微 (WeCom)
- WhatsApp
- ERP 系统...
"""

from typing import Callable, Dict, Any, Optional
from langchain_core.tools import BaseTool
from abc import ABC, abstractmethod

from src.config import settings

# 各模块工具列表
from .order import order_tools
from .logistics import logistics_tools
from .after_sales import after_sales_tools
from .user import user_tools


class BaseIntegrationService(ABC):
    """第三方应用集成基类"""
    
    def __init__(self, platform: str):
        self.platform = platform
        self.config = settings.integration_configs.get(platform, {})
        self.enabled = self.config.get("enabled", False)
    
    @abstractmethod
    def send_message(self, to: str, content: str) -> bool:
        """发送消息"""
        pass
    
    @abstractmethod
    def sync_order(self, order_id: str) -> Dict[str, Any]:
        """同步订单"""
        pass
    
    @abstractmethod
    def get_customer_info(self, customer_id: str) -> Dict[str, Any]:
        """获取客户信息"""
        pass
    
    def is_available(self) -> bool:
        """检查服务是否可用"""
        return self.enabled


class FeishuIntegration(BaseIntegrationService):
    """飞书集成"""
    # 初始化飞书集成服务
    def __init__(self):
        super().__init__("feishu")
        self.app_id = self.config.get("app_id", "")
        self.app_secret = self.config.get("app_secret", "")
    # 发送飞书消息
    def send_message(self, to: str, content: str) -> bool:
        """发送飞书消息"""
        if not self.is_available():
            return False
        # TODO: 实现飞书API调用
        print(f"[Feishu] Sending message to {to}: {content}")
        return True
    # 同步飞书工单
    def sync_order(self, order_id: str) -> Dict[str, Any]:
        """同步飞书工单"""
        if not self.is_available():
            return {}
        # TODO: 实现飞书工单同步
        return {"order_id": order_id, "status": "synced"}
    
    def get_customer_info(self, customer_id: str) -> Dict[str, Any]:
        """获取飞书用户信息"""
        if not self.is_available():
            return {}
        # TODO: 实现飞书用户信息获取
        return {"customer_id": customer_id}

# 钉钉集成
class DingTalkIntegration(BaseIntegrationService):
    """钉钉集成"""
    
    def __init__(self):
        super().__init__("dingtalk")
        self.app_key = self.config.get("app_key", "")
        self.app_secret = self.config.get("app_secret", "")
    
    def send_message(self, to: str, content: str) -> bool:
        """发送钉钉消息"""
        if not self.is_available():
            return False
        # TODO: 实现钉钉API调用
        print(f"[DingTalk] Sending message to {to}: {content}")
        return True
    
    def sync_order(self, order_id: str) -> Dict[str, Any]:
        """同步钉钉工单"""
        if not self.is_available():
            return {}
        # TODO: 实现钉钉工单同步
        return {"order_id": order_id, "status": "synced"}
    
    def get_customer_info(self, customer_id: str) -> Dict[str, Any]:
        """获取钉钉用户信息"""
        if not self.is_available():
            return {}
        # TODO: 实现钉钉用户信息获取
        return {"customer_id": customer_id}

# 企微集成
class WeComIntegration(BaseIntegrationService):
    """企微集成"""
    
    def __init__(self):
        super().__init__("wecom")
        self.corpid = self.config.get("corpid", "")
        self.corpsecret = self.config.get("corpsecret", "")
    
    def send_message(self, to: str, content: str) -> bool:
        """发送企微消息"""
        if not self.is_available():
            return False
        # TODO: 实现企微API调用
        print(f"[WeCom] Sending message to {to}: {content}")
        return True
    
    def sync_order(self, order_id: str) -> Dict[str, Any]:
        """同步企微工单"""
        if not self.is_available():
            return {}
        # TODO: 实现企微工单同步
        return {"order_id": order_id, "status": "synced"}
    
    def get_customer_info(self, customer_id: str) -> Dict[str, Any]:
        """获取企微用户信息"""
        if not self.is_available():
            return {}
        # TODO: 实现企微用户信息获取
        return {"customer_id": customer_id}

# WhatsApp集成
class WhatsAppIntegration(BaseIntegrationService):
    """WhatsApp集成"""
    
    def __init__(self):
        super().__init__("whatsapp")
        self.phone_number_id = self.config.get("phone_number_id", "")
        self.access_token = self.config.get("access_token", "")
    
    def send_message(self, to: str, content: str) -> bool:
        """发送WhatsApp消息"""
        if not self.is_available():
            return False
        # TODO: 实现WhatsApp Business API调用
        print(f"[WhatsApp] Sending message to {to}: {content}")
        return True
    
    def sync_order(self, order_id: str) -> Dict[str, Any]:
        """同步WhatsApp订单"""
        if not self.is_available():
            return {}
        # TODO: 实现WhatsApp订单同步
        return {"order_id": order_id, "status": "synced"}
    
    def get_customer_info(self, customer_id: str) -> Dict[str, Any]:
        """获取WhatsApp用户信息"""
        if not self.is_available():
            return {}
        # TODO: 实现WhatsApp用户信息获取
        return {"customer_id": customer_id}

# ERP集成
class ERPIntegration(BaseIntegrationService):
    """ERP集成"""
    
    def __init__(self):
        super().__init__("erp")
        self.api_url = self.config.get("api_url", "")
        self.api_key = self.config.get("api_key", "")
    
    def send_message(self, to: str, content: str) -> bool:
        """发送ERP通知"""
        if not self.is_available():
            return False
        # TODO: 实现ERP API调用
        print(f"[ERP] Sending notification: {content}")
        return True
    
    def sync_order(self, order_id: str) -> Dict[str, Any]:
        """同步ERP订单"""
        if not self.is_available():
            return {}
        # TODO: 实现ERP订单同步
        return {"order_id": order_id, "status": "synced"}
    
    def get_customer_info(self, customer_id: str) -> Dict[str, Any]:
        """获取ERP客户信息"""
        if not self.is_available():
            return {}
        # TODO: 实现ERP客户信息获取
        return {"customer_id": customer_id}


# 集成服务注册表
INTEGRATION_SERVICES: Dict[str, BaseIntegrationService] = {
    "feishu": FeishuIntegration(),
    "dingtalk": DingTalkIntegration(),
    "wecom": WeComIntegration(),
    "whatsapp": WhatsAppIntegration(),
    "erp": ERPIntegration(),
}


def get_integration_service(platform: str) -> Optional[BaseIntegrationService]:
    """获取指定平台的集成服务"""
    return INTEGRATION_SERVICES.get(platform)


def get_enabled_integrations() -> list[BaseIntegrationService]:
    """获取所有已启用的集成服务"""
    return [service for service in INTEGRATION_SERVICES.values() if service.is_available()]


# 返回所有已注册工具
def get_all_tools() -> list[BaseTool]:
    """返回所有已注册工具"""
    return (
        order_tools
        + logistics_tools
        + after_sales_tools
        + user_tools
    )


# 按 Agent 返回其可用工具
def get_tools_by_agent(agent_name: str) -> list[BaseTool]:
    """按 Agent 返回其可用工具"""
    mapping = {
        "consultation": [],  # 咨询主要用 RAG
        "order_fulfillment": order_tools + logistics_tools,  # 订单处理和物流相关工具
        "after_sales": after_sales_tools + order_tools,  # 售后处理和订单相关工具    
        "compliance": [],  # 合规主要用 RAG
        "human_handoff": user_tools,  # 人工交接相关工具
    }
    return mapping.get(agent_name, [])

