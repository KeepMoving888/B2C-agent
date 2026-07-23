/**
 * 前端配置
 * - 支持在线模式（对接 FastAPI 后端 + vLLM 推理）与离线模式（本地规则引擎）
 * - 自动探测后端可用性，失败则回退至离线模式
 */
window.AppConfig = {
  // 后端 API 地址
  API_BASE: '',  // 同源访问（前端由后端 8000 端口提供）
  // WebSocket 地址（实时会话推送）
  WS_BASE: 'ws://localhost:8000/ws',
  // 后端健康检测超时（毫秒）- 后端启动时需探测DeepSeek API，需较长超时
  HEALTH_TIMEOUT: 10000,
  // 是否已连接后端（运行时动态设置）
  online: false,
  // 当前模式标签
  modeLabel: '离线模式',
  // 客户回复延迟（毫秒）
  CUSTOMER_REPLY_DELAY: [1200, 2000],
  // Agent 路由展示开关
  showAgentRoute: true
};
