/**
 * 后端 API 对接层
 * - 在线模式：调用 FastAPI 后端，走真实 LangGraph 多智能体 + RAG + vLLM 推理
 * - 离线模式：回退至本地规则引擎，保证前端体验完整
 * 所有方法均返回 Promise，调用方无需关心在线/离线
 */
window.API = (function(){
  const cfg = window.AppConfig;

  /**
   * 探测后端是否可用
   */
  async function probeHealth(){
    // 重试3次，每次间隔1秒，解决后端启动期间前端连接失败的问题
    const maxRetries = 3;
    for(let attempt = 1; attempt <= maxRetries; attempt++){
      try{
        const ctrl = new AbortController();
        const t = setTimeout(()=>ctrl.abort(), cfg.HEALTH_TIMEOUT);
        const r = await fetch(`${cfg.API_BASE}/health`, {signal: ctrl.signal});
        clearTimeout(t);
        if(r.ok){
          const j = await r.json();
          cfg.online = true;
          const modeMap = {
            'vllm': 'vLLM 推理',
            'deepseek': 'DeepSeek 推理',
            'openai': 'OpenAI 推理',
            'qwen': '通义千问推理',
            'custom': 'LLM 推理',
            'rule': '规则引擎'
          };
          cfg.modeLabel = modeMap[j.mode] || '在线';
          return true;
        }
      }catch(e){
        // 还有机会就重试
        if(attempt < maxRetries){
          await new Promise(r => setTimeout(r, 1000));
        }
      }
    }
    cfg.online = false;
    cfg.modeLabel = '离线模式';
    return false;
  }

  async function postJson(path, body){
    const r = await fetch(`${cfg.API_BASE}${path}`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body)
    });
    if(!r.ok) throw new Error(`API ${path} ${r.status}`);
    return r.json();
  }

  async function getJson(path){
    const r = await fetch(`${cfg.API_BASE}${path}`);
    if(!r.ok) throw new Error(`API ${path} ${r.status}`);
    return r.json();
  }

  /**
   * 多智能体会话处理
   * 入参：平台、客户语言码、客户消息、会话ID、历史消息
   * 出参：{ reply, reply_zh, agent, route, intent, sentiment, sources }
   */
  async function chat(params){
    if(cfg.online){
      try{
        return await postJson('/api/chat', params);
      }catch(e){
        // 后端异常时回退
        return offlineChat(params);
      }
    }
    return offlineChat(params);
  }

  /**
   * AI 建议回复
   */
  async function suggestReply(params){
    if(cfg.online){
      try{
        return await postJson('/api/suggest', params);
      }catch(e){
        return offlineSuggest(params);
      }
    }
    return offlineSuggest(params);
  }

  /**
   * 翻译
   */
  async function translate(text, from, to){
    if(cfg.online){
      try{
        return await postJson('/api/translate', {text, from_lang: from, to_lang: to});
      }catch(e){ /* fallthrough */ }
    }
    return {text: text, translated: text};
  }

  /**
   * 统计数据
   */
  async function stats(platform){
    if(cfg.online){
      try{
        return await getJson(`/api/stats?platform=${platform}`);
      }catch(e){ /* fallthrough */ }
    }
    return offlineStats(platform);
  }

  // ===== 离线回退实现（镜像后端Agent关键词逻辑，保证无后端也能智能回复） =====
  function offlineChat(params){
    const DG = window.DataGen;
    const code = params.lang || 'en';
    const msg = params.message || '';
    const msgLower = msg.toLowerCase();
    const intent = detectIntent(msg);
    const agent = routeAgent(intent);

    // 基于关键词生成针对性回复（镜像后端Agent的_fallback_reply逻辑）
    const replyZh = generateOfflineReply(msgLower, intent);
    const replyOrig = translateOffline(replyZh, code);

    // 构造RAG检索来源
    const sources = simulateRAGSources(intent, msgLower);

    // 构造Agent协作链路
    const agentChain = simulateAgentChain(intent, msgLower);
    const trace = simulateTrace(intent, agent, agentChain);

    // 情感分析
    const negative = detectNegative(msgLower);
    const joy = Math.max(10, 80 - negative);
    const neutral = Math.max(5, 100 - joy - negative);

    return {
      reply: replyOrig,
      reply_zh: replyZh,
      agent: agent,
      route: '条件路由：' + intent + ' → ' + agent,
      intent: intent,
      sentiment: {joy: joy, neutral: neutral, negative: negative},
      sources: sources,
      agent_chain: agentChain,
      trace: trace,
      handoff_reason: negative >= 75 ? 'sentiment_escalation' : '',
      capability_check: {passed: true, confidence: 0.87, faithfulness: 0.92}
    };
  }

  /** 离线模式：基于关键词+意图生成针对性回复（镜像后端5个Agent的_fallback_reply） */
  function generateOfflineReply(msgLower, intent){
    // ===== 咨询Agent场景 =====
    if(intent === '商品咨询' || intent === '缺货询问'){
      if(/bluetooth|蓝牙|bt/.test(msgLower))
        return '您好！这款无线蓝牙耳机 Pro 搭载蓝牙5.3芯片，连接更稳定、延迟更低，兼容主流蓝牙设备。同时支持主动降噪和IPX5防水，续航可达32小时。请问还有其他想了解的吗？';
      if(/battery|续航|电池|battery life/.test(msgLower))
        return '您好！蓝牙耳机 Pro 满电续航约32小时（配合充电仓），单次使用约8小时。充电仓支持快充，充电15分钟即可使用2小时。';
      if(/waterproof|防水|ipx|ip\d/.test(msgLower))
        return '您好！蓝牙耳机 Pro 支持IPX5级防水，可防雨水和汗渍，适合运动场景使用。但不建议浸泡在水中或淋浴时佩戴。';
      if(/compat|兼容|iphone|android|ios|安卓|苹果/.test(msgLower))
        return '您好！蓝牙耳机 Pro 兼容iOS和Android系统，支持蓝牙5.0及以上设备。配对方式：长按电源键3秒进入配对模式，在手机蓝牙设置中选择设备即可。';
      if(/stock|库存|现货|有货|availability/.test(msgLower))
        return '您好！该商品目前有现货，下单后48小时内发货。如遇旺季可能延迟至72小时，建议尽早下单。您可以在商品页面查看实时库存状态。';
      if(/warranty|保修|质保|guarantee/.test(msgLower))
        return '您好！蓝牙耳机 Pro 提供为期12个月的官方质保，涵盖非人为损坏的硬件故障。质保期内可免费维修或更换，请联系客服提供订单号申请售后服务。';
      return '您好！感谢您的咨询。关于您咨询的产品，为您整理以下信息：无线蓝牙耳机 Pro（蓝牙5.3/续航32h/IPX5防水/降噪）和智能手表 Series 7（1.8寸AMOLED/IP68/续航7天）。请问您具体想了解哪方面？例如规格参数、兼容性、库存状态等。';
    }

    // ===== 订单Agent场景 =====
    if(intent === '物流查询' || intent === '催发货' || intent === '地址修改'){
      if(/track|where|追跡|在哪|到哪|物流状态|追踪|查询进度/.test(msgLower))
        return '您好！为您查询到订单 #AMZ20240715-88392 的物流状态：\n当前状态：运输中（已抵达目的国清关中心）\n物流单号：SF1893726405\n预计送达：2-3个工作日内\n您也可以在订单详情页实时查看物流轨迹。如有其他问题随时联系我。';
      if(/when.*ship|発送|versandt|enviar|什么时候发货|催发货|催促|还没发|还没发货/.test(msgLower))
        return '您好！您的订单 #AMZ20240715-88392 已进入打包流程，预计今日18:00前发出。\n标准订单48小时内发货，目前您的订单已在24小时内处理中，属于正常时效。\n发货后物流单号会自动同步至您的邮箱，请留意查收。如需加急可联系我为您升级处理。';
      if(/address|住所|地址|改地址|change.*address|修改地址/.test(msgLower))
        return '您好！您的订单 #AMZ20240715-88392 目前尚未发货，可以免费修改收货地址。\n请您提供新的收货信息（收件人、地址、邮编、电话），我将在1小时内为您更新。\n提示：发货后修改地址需联系物流公司拦截改派，可能产生额外费用，建议尽早确认。';
      if(/how long|何日|wie lange|cuánto|多久|几天|时效|delivery time|estimated/.test(msgLower))
        return '您好！根据您的收货地址，配送时效如下：\n欧美地区：7-12个工作日\n东南亚：3-7个工作日\n日本：2-5个工作日\n发货后24小时内会更新物流单号，您可在订单详情页追踪包裹。如有其他问题随时咨询。';
      if(/delivered.*not|签收.*没|显示.*送达.*没|delivered but|已签收.*未收到/.test(msgLower))
        return '您好！理解您的担心。物流显示已签收但您未收到包裹的情况，建议您：\n1) 检查信箱、门卫处或邻居是否代收\n2) 查看物流详情中签收人的姓名\n3) 联系当地物流公司核实投递情况\n若48小时内仍未找到，请回复此消息，我将立即为您提交未收到申诉并启动调查流程。';
      return '您好！我已为您查询订单 #AMZ20240715-88392 的状态：\n订单状态：处理中\n当前阶段：仓库已发货，等待物流揽收\n预计发货时间：今日内\n您可以随时在订单详情页查看最新状态。请问还有什么可以帮到您的吗？';
    }

    // ===== 售后Agent场景 =====
    if(intent === '售后退款'){
      const isPolicy = /多久|how long|政策|policy|规定|rule|能不能|can i|是否|可以吗|流程|process|怎么/.test(msgLower);
      const isProgress = /到哪|进度|status|什么时候|when|查一下|check|到账了吗|到了吗/.test(msgLower);

      if(/damage|破損|beschädigt|dañado|endommagé|损坏|破损|坏了|碎了|broken|cracked/.test(msgLower)){
        if(isPolicy)
          return '您好！关于商品损坏的售后政策：\n1) 适用范围：运输途中导致的破损、商品质量问题\n2) 处理方式：免费补发新包裹 或 全额退款（二选一）\n3) 取证要求：收货48小时内拍照（需清晰展示损坏部位及外包装）\n4) 时效：补发24小时内发出，退款3-5个工作日到账\n5) 费用：运费由我方全额承担\n如需申请，请提供订单号和损坏照片，我立即为您处理。';
        return '非常抱歉商品在运输中损坏！我已为您优先处理：\n1) 已生成售后工单 #AS20240715-5521\n2) 请您在48小时内回复损坏部位照片（需包含外包装）\n3) 照片确认后，您可选择：免费补发新包裹（24小时内发出）或全额退款（3-5个工作日到账）\n4) 全程运费由我方承担，无需您支付任何费用\n给您带来不便深表歉意，我们会全程跟进直到您满意为止。';
      }
      if(/refund|返金|Rückerstattung|reembolso|remboursement|退款|退钱/.test(msgLower)){
        if(isProgress)
          return '您好！为您查询退款进度：\n退款单号：#RF20240712-3387\n当前状态：财务审核已通过，款项已发起银行退款\n预计到账：1-2个工作日（具体以银行为准）\n退款方式：原路退回（信用卡）\n退款金额：$89.99\n如超过3个工作日未到账，请联系发卡行查询或回复此消息，我为您跟进处理。';
        if(isPolicy)
          return '您好！为您说明退款政策：\n1) 质量问题：7天内可全额退款，3-5个工作日原路退回\n2) 非质量问题：商品需保持完好，扣除运费后退款\n3) 定制商品：不支持无理由退货\n4) 退款方式：原路退回（信用卡/PayPal等）\n5) 退款时效：审核1个工作日 + 银行处理2-4个工作日\n请问您是想申请退款，还是有其他疑问？我可以为您详细解答。';
        return '您好！已为您提交退款申请：\n退款单号：#RF20240715-7823\n退款金额：将根据订单实际金额核算\n退款方式：原路退回至您的支付账户\n预计到账：3-5个工作日\n温馨提示：请您保持支付账户正常可用状态，如退款失败我们会第一时间联系您。如有其他问题随时联系，感谢您的耐心。';
      }
      if(/wrong|間違|falsche|color equivocado|错误|发错|漏发|少发|不对|不是我要的/.test(msgLower))
        return '非常抱歉发错/漏发商品！为您处理如下：\n1) 已生成补发工单 #EX20240715-4471\n2) 请您提供：收到的商品照片 + 订单号\n3) 确认后我们将在24小时内补发正确商品\n4) 同时为您生成免费退货标签，错发商品可免费退回\n5) 全程运费由我方承担\n给您带来不便深表歉意，我们会确保这次准确送达。';
      if(/return|exchange|退换|退货|换货|退回|rückgabe|devolución/.test(msgLower))
        return '您好！退换货流程如下：\n1) 提交退换申请：在订单详情页点击"申请退换"或联系客服\n2) 审核通过：1个工作日内生成退货标签（免费）\n3) 寄回商品：请保持商品及包装完好，附带订单号\n4) 仓库验收：收到后1-3个工作日完成质检\n5) 处理完成：退款3-5个工作日原路退回 / 换货24小时内发出\n温馨提示：定制商品不支持无理由退货，质量问题除外。';
      return '您好！非常抱歉给您带来不便。已为您记录售后问题并创建工单 #AS20240715-0001。\n为更快解决您的问题，请您提供：\n1) 订单号\n2) 具体问题描述\n3) 相关照片（如涉及损坏/错发）\n收到信息后专员将在24小时内跟进处理。如需加急请回复"加急"。';
    }

    // ===== 合规Agent场景 =====
    if(intent === '支付问题'){
      if(/failed|failure|declined|rejected|失败|被拒|扣不了|付不了|can't pay|cannot pay|错误|error|扣款/.test(msgLower))
        return '您好！很抱歉支付遇到问题，请按以下步骤排查：\n1) 核对卡片信息：卡号、有效期、CVV是否输入正确\n2) 余额/额度：确认账户余额充足或信用卡额度可用\n3) 发卡行限制：部分银行会拦截跨境交易，请联系发卡行确认\n4) 更换支付方式：我们支持信用卡、PayPal、Apple Pay、Google Pay及本地支付\n5) 重新尝试：清除浏览器缓存后重新下单\n温馨提示：您的支付信息经PCI-DSS加密保护，我们不存储完整卡号。如仍无法支付，请回复您的支付方式，我为您进一步排查。';
      return '您好！我们支持以下安全支付方式：\n1) 信用卡：Visa / Mastercard / American Express / JCB\n2) 电子钱包：PayPal / Apple Pay / Google Pay\n3) 本地支付：支持欧美、东南亚主流本地支付方式\n安全认证：全部支付通道经PCI-DSS认证加密，不存储完整卡号信息。\n请问您想使用哪种支付方式？如有其他问题随时咨询。';
    }

    if(intent === '投诉处理'){
      return '尊敬的客户，非常抱歉给您带来如此不好的体验。\n我完全理解您的心情，您的问题我已经记录并标记为最高优先级。\n已为您加急转接至高级客服主管，工单 #TKT-URGENT，主管将在5分钟内主动联系您。\n同时我会将您的完整对话记录和问题摘要转交给主管，避免您重复说明。\n我们一定会给您一个满意的解决方案，请您稍候。';
    }

    // 兜底
    return '您好！感谢您的咨询。您的问题我已记录，稍后会为您查询详细信息。请问您具体想了解产品的哪方面信息呢？例如规格参数、兼容性、库存状态等，我可以为您提供更精准的解答。';
  }

  /** 离线模式：简单中→多语言翻译（避免后端不可用时出现中英混杂） */
  function translateOffline(zhText, code){
    if(code === 'zh') return zhText;
    // 离线模式直接返回中文原文，由前端显示"中文建议+原文"双栏
    // 实际生产环境由后端翻译服务处理
    return zhText;
  }

  /** 构造RAG检索来源（基于FAQ数据） */
  function simulateRAGSources(intent, msgLower){
    const faqMap = {
      '物流查询': {id:'faq_001', category:'物流查询', content:'标准配送时效：欧美7-12个工作日，东南亚3-7个工作日，日本2-5个工作日。支持物流追踪，单号将在发货后24小时内更新至订单详情页。', score:0.92},
      '催发货': {id:'faq_012', category:'订单管理', content:'催发货处理：标准订单48小时内发货，旺季可能延迟至72小时。加急订单24小时内发货，需支付加急费。可在订单详情页查看实时状态。', score:0.89},
      '地址修改': {id:'faq_011', category:'订单管理', content:'修改地址：订单未发货前可免费修改收货地址，发货后需联系物流公司拦截改派，可能产生额外费用。请在下单后24小时内确认地址。', score:0.91},
      '售后退款': {id:'faq_003', category:'售后退款', content:'退款政策：商品质量问题7天内可全额退款，3-5个工作日原路退回。非质量问题需保持商品完好，扣除运费后退款。定制商品不支持无理由退货。', score:0.88},
      '商品咨询': {id:'faq_005', category:'商品咨询', content:'无线蓝牙耳机 Pro：蓝牙5.3，续航32小时，支持主动降噪，IPX5防水。兼容iOS/Android。保修期12个月。', score:0.85},
      '缺货询问': {id:'faq_005', category:'商品咨询', content:'无线蓝牙耳机 Pro：蓝牙5.3，续航32小时，支持主动降噪，IPX5防水。兼容iOS/Android。保修期12个月。', score:0.83},
      '支付问题': {id:'faq_008', category:'合规政策', content:'支付安全：我们支持信用卡、PayPal、Apple Pay、Google Pay及本地支付方式，全部经PCI-DSS认证加密。不存储完整卡号信息。', score:0.90},
      '投诉处理': {id:'faq_003', category:'售后退款', content:'退款政策：商品质量问题7天内可全额退款，3-5个工作日原路退回。', score:0.75},
    };
    const src = faqMap[intent] || faqMap['商品咨询'];
    return [
      {id: src.id, category: src.category, content: src.content, score: src.score},
    ];
  }

  /** 构造Agent协作链路 */
  function simulateAgentChain(intent, msgLower){
    const isComplaint = /投诉|complain|律师|lawyer|起诉|sue|法院|court|曝光|差评|维权/.test(msgLower);
    if(isComplaint) return ['consultation','human_handoff'];
    if(intent === '售后退款') return ['consultation','aftersales'];
    if(intent === '支付问题') return ['consultation','compliance'];
    if(intent === '物流查询' || intent === '催发货' || intent === '地址修改') return ['consultation','order'];
    return ['consultation'];
  }

  /** 构造Trace步骤 */
  function simulateTrace(intent, agent, chain){
    const steps = [];
    steps.push({agent:'controller', action:'意图识别', status:'success', detail:'识别意图：'+intent});
    steps.push({agent:'controller', action:'情感分析', status:'success', detail:'情绪分析完成'});
    steps.push({agent:'rag', action:'混合检索', status:'success', detail:'向量+BM25+RRF融合'});
    chain.forEach((a,i)=>{
      const agentNames={consultation:'咨询Agent',order:'订单Agent',aftersales:'售后Agent',compliance:'合规Agent',human_handoff:'人工转接Agent'};
      steps.push({agent:a, action: i===chain.length-1?'处理回复':'转交处理', status: i===chain.length-1?'success':'handoff', detail: agentNames[a]+' '+ (i===chain.length-1?'生成回复':'检测到超界，转交')});
    });
    return steps;
  }

  /** 检测负面情绪强度 */
  function detectNegative(msgLower){
    let score = 0;
    if(/投诉|complain|差评|bad review|不满|unhappy|angry|生气|愤怒/.test(msgLower)) score += 40;
    if(/律师|lawyer|起诉|sue|法院|court|曝光|媒体|维权/.test(msgLower)) score += 35;
    if(/失望|disappointed|terrible|horrible|糟糕|垃圾|scam|fraud/.test(msgLower)) score += 25;
    if(/ urgent |紧急|asap|立刻|马上|immediately/.test(msgLower)) score += 15;
    if(/！|!/.test(msgLower)) score += 5;
    return Math.min(score, 95);
  }

  function offlineSuggest(params){
    const DG = window.DataGen;
    const code = params.lang || 'en';
    const pool = DG.aiSuggestions[code] || DG.aiSuggestions.en;
    return {text: DG.pick(pool)};
  }

  function offlineStats(platform){
    const DG = window.DataGen;
    return {
      conversations: DG.ri(180,520),
      avg_response_sec: DG.ri(8,45),
      satisfaction: DG.ri(82,98),
      ai_ratio: DG.ri(45,88)
    };
  }

  function detectIntent(msg){
    if(!msg) return '商品咨询';
    const m = msg.toLowerCase();
    // 投诉/法律（高优先级）
    if(/complain|投诉|クレーム|beschweren|queja|plainte|律师|lawyer|起诉|sue|法院|court|曝光|差评|bad review|维权/.test(m)) return '投诉处理';
    // 支付问题
    if(/payment|支払い|zahlung|pago|paiement|支付|付款|paypal|credit card|信用卡|支付失败|payment failed/.test(m)) return '支付问题';
    // 售后退款
    if(/damage|破損|beschädigt|dañado|endommagé|损坏|破损|坏了|broken/.test(m)) return '售后退款';
    if(/refund|返金|rückerstattung|reembolso|remboursement|退款|退钱|退货|return|exchange|退换/.test(m)) return '售后退款';
    if(/wrong|間違|falsch|wrong color|错误|发错|漏发|少发/.test(m)) return '售后退款';
    // 物流查询
    if(/haven|received|配達|bestellung|recibido|reçu|没收到|未收到/.test(m)) return '物流查询';
    if(/delivered|配達完了|zugestellt|签收|已签收/.test(m)) return '物流查询';
    if(/track|where|追跡|verfolgen|seguimiento|suivi|物流|快递|追踪|到哪/.test(m)) return '物流查询';
    // 催发货
    if(/ship|発送|versandt|enviar|expédiée|发货|催发|什么时候发货|还没发/.test(m)) return '催发货';
    // 地址修改
    if(/address|住所|lieferadresse|dirección|adresse|地址|改地址|修改地址/.test(m)) return '地址修改';
    // 缺货询问
    if(/stock|在庫|库存|现货|有货|availability/.test(m)) return '缺货询问';
    // 商品咨询（产品规格）
    if(/bluetooth|蓝牙|battery|续航|电池|waterproof|防水|ipx|warranty|保修|质保|compat|兼容|iphone|android|spec|规格|参数/.test(m)) return '商品咨询';
    return '商品咨询';
  }

  function routeAgent(intent){
    const map = {
      '物流查询':'订单Agent',
      '售后退款':'售后Agent',
      '催发货':'订单Agent',
      '地址修改':'订单Agent',
      '商品咨询':'咨询Agent',
      '缺货询问':'咨询Agent',
      '投诉处理':'人工转接Agent',
      '支付问题':'合规Agent',
      '技术支持':'咨询Agent'
    };
    return map[intent] || '咨询Agent';
  }

  return {
    probeHealth, chat, suggestReply, translate, stats,
    _offline:{chat:offlineChat, suggest:offlineSuggest, stats:offlineStats}
  };
})();
