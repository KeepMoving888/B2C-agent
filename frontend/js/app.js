/**
 * 前端主逻辑
 * - 三栏布局：会话列表 / 聊天流 / 客户详情
 * - 在线模式调用后端多智能体；离线模式回退本地规则
 * - 保持与原页面一致的视觉与交互
 */

/* ============ 状态 ============ */
let state={
  platform:'amazon',
  conversations:[],
  activeConvId:null,
  showOriginal:true,
  autoReply:false
};
let chatHistories={};

/* ============ 工具 ============ */
function escapeHtml(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function fmtTime(d){return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')}

// 简易多语言→中文摘要（用于会话列表预览）
function translateToZh(msg,code){
  if(!msg)return '客户咨询订单相关事宜';
  // 归一化：转小写 + 去除重音符号（与matchAgentReply一致）
  const m=msg.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
  // 投诉升级（高优先级）
  if(/third message|nobody|manager|投诉|クレーム|beschweren|queja|plainte|差评|曝光|维权|律师|lawyer|troisieme.*message|personne.*aide|responsable|gerente|terza.*messaggio|nessuno.*aiut|terceira.*mensagem|ninguem.*ajud/i.test(m))return '投诉升级，要求主管介入处理';
  // 合规隐私
  if(/gdpr|delete.*account|personal data|payment information|stored|server|security|privacy|データ保護|datenschutz|privacidad|donnees personnelles|プライバシー|seguranca|servidor|pago.*seguro|informations.*paiement/i.test(m))return '咨询数据隐私与GDPR合规问题';
  // 会员促销
  if(/gold member|coupon|black friday|sale|discount|promo|会員|クーポン|セール|rabatt|cupon|remise|sconto|promocao/i.test(m))return '咨询会员权益与促销优惠活动';
  // 关税清关
  if(/customs|duty|invoice|税関|関税|zoll|factura|aduana|douane|dogana|alfandega/i.test(m))return '咨询关税清关与发票问题';
  // 支付问题
  if(/credit card|declined|paypal|payment|支付|支払い|zahlung|pago|paiement|pagamento|card details|karte/i.test(m))return '支付遇到问题，咨询支付方式';
  // 商品规格咨询
  if(/aptx|bluetooth|battery|smartwatch|camera|dimensions|ergonomic|spec|仕様|spezifikation|especificacion|specification|防水|compatib|互換|compatible|互換性/i.test(m))return '咨询商品规格参数与兼容性';
  // 库存与发货时效
  if(/in stock|white color|christmas|shipping.*take|how long|delivery|在庫|lag|stock|disponible|verfugbar|versand|envio|発送時期|disponibilite|disponibilita|disponibilidade/i.test(m))return '咨询商品库存与配送时效';
  // 物流追踪
  if(/tracking|hasn.*updated|lost|courier|delivered.*work|配達|verfolgen|seguimiento|suivi|raccolta|追跡|追踪|物流|快递/i.test(m))return '查询物流追踪与包裹状态';
  // 售后退款
  if(/haven.*received|配達状況|bestellung noch|no he recibido|n'ai pas recu|non ho ricevuto|nao recebi/i.test(m))return '尚未收到订单，请求查询物流状态';
  if(/damaged|破損|beschadigt|dano|endommage|danneggiato|danificado/i.test(m))return '商品到货时已损坏，要求更换';
  if(/refund|返金|ruckerstattung|reembolso|remboursement|rimborso|replacement|交換|ersatz|reemplazo|remplacement|sostituzione|broke|defect|stopped working|壊れ|defekt|roto|casse|rotto|quebrado/i.test(m))return '申请售后退款或换货服务';
  if(/shipped|発送|versandt|enviar|expediee|spedito|enviado/i.test(m))return '催促发货，已等待多日';
  if(/address|住所|lieferadresse|direccion|adresse|indirizzo|endereco/i.test(m))return '希望修改订单配送地址';
  if(/delivered|配達完了|zugellt|entregado|livre|consegnato|entregue/i.test(m))return '显示已签收但实际未收到';
  if(/stock|在庫|lager|existencias/i.test(m))return '咨询商品库存与跨国配送时效';
  if(/wrong color|間違|falsche|color equivocado/i.test(m))return '收到的商品颜色与订单不符';
  // 多件订单合并
  if(/two.*order|combine|shipment|merge|複数|注文|bestellungen|pedidos|commandes|ordini|まとめる/i.test(m))return '咨询多笔订单合并发货';
  return '客户咨询订单相关事宜';
}

/* ============ 生成会话列表 ============ */
// 客户阶段定义：5大业务阶段对应5个Agent
const CUSTOMER_STAGES=[
  {key:'pre_order',label:'未下单',color:'#3b82f6',agent:'consultation',agent_label:'咨询Agent',icon:'咨询'},
  {key:'ordered',label:'已下单',color:'#10b981',agent:'order',agent_label:'订单Agent',icon:'订单'},
  {key:'aftersales',label:'售后',color:'#f59e0b',agent:'aftersales',agent_label:'售后Agent',icon:'售后'},
  {key:'repurchase',label:'复购',color:'#8b5cf6',agent:'compliance',agent_label:'复购Agent',icon:'复购'},
  {key:'escalation',label:'投诉升级',color:'#ef4444',agent:'human_handoff',agent_label:'人工转接Agent',icon:'人工'},
];

// 根据客户消息判断阶段
function detectStage(msgZh){
  const m=msgZh||'';
  if(/投诉|升级|主管|律师|差评|曝光|维权/.test(m))return CUSTOMER_STAGES[4];
  if(/复购|再次|回购|又来|第二单|老客户|回头|reorder|again|second order|repeat|repurchase/.test(m))return CUSTOMER_STAGES[3];
  if(/退款|退货|换货|损坏|破损|坏了|发错|漏发|保修|质保/.test(m))return CUSTOMER_STAGES[2];
  if(/物流|快递|追踪|发货|催发|地址|签收|未收到|配送|运单/.test(m))return CUSTOMER_STAGES[1];
  return CUSTOMER_STAGES[0];
}

function genConversations(platform){
  const list=[];
  const count=DataGen.ri(40,70);
  const used=new Set();
  for(let i=0;i<count;i++){
    let cust=DataGen.pick(DataGen.customers);
    while(used.has(cust.name)&&used.size<DataGen.customers.length){cust=DataGen.pick(DataGen.customers)}
    used.add(cust.name);
    const msgs=DataGen.customerMsgs[cust.code]||DataGen.customerMsgs.en;
    const lastMsg=DataGen.pick(msgs);
    const lastMsgZh=translateToZh(lastMsg,cust.code);
    const stage=detectStage(lastMsgZh);
    list.push({
      id:'c'+platform+i,
      customer:cust,
      platform:platform,
      lastMsg:lastMsg,
      lastMsgZh:lastMsgZh,
      stage:stage,
      currentAgent:stage.agent,
      currentAgentLabel:stage.agent_label,
      unread:Math.random()<0.5?DataGen.ri(1,5):0,
      time:DataGen.timeAgo(),
      lastTime:DataGen.nowTime(),
      handledByAI:Math.random()<0.7
    });
  }
  // 统计各平台未读消息数
  if(!window._platformUnread)window._platformUnread={};
  window._platformUnread[platform]=list.reduce((s,c)=>s+(c.unread||0),0);
  return list;
}

/* ============ 渲染会话列表 ============ */
function renderConvList(filter=''){
  // 更新各平台未读红点（从 window._platformUnread 读取，确保所有平台都有红点）
  const platforms=['amazon','aliexpress','ebay','shopify','rakuten','email'];
  platforms.forEach(pf=>{
    // 当前平台的未读数从会话列表实时统计，其他平台用预生成数据
    let unread;
    if(pf===state.platform){
      unread=state.conversations.reduce((s,c)=>s+(c.unread||0),0);
      window._platformUnread[pf]=unread;
    }else{
      unread=(window._platformUnread&&window._platformUnread[pf])||0;
    }
    const el=document.getElementById('unread-'+pf);
    if(el){
      if(unread>0){el.textContent=unread;el.style.display='flex'}
      else{el.style.display='none'}
    }
  });
  const list=state.conversations.filter(c=>{
    if(!filter)return true;
    return c.customer.name.toLowerCase().includes(filter.toLowerCase())||c.lastMsgZh.includes(filter);
  });
  document.getElementById('convCnt').textContent=state.conversations.length+' 在线 · 实时服务中';
  const el=document.getElementById('convList');
  el.innerHTML='';
  if(list.length===0){el.innerHTML='<div style="text-align:center;color:#94a3b8;padding:30px;font-size:12px">未找到匹配的会话</div>';return}
  list.forEach(c=>{
    const pf=DataGen.platforms[c.platform];
    const item=document.createElement('div');
    item.className='conv-item'+(c.id===state.activeConvId?' active':'');
    const stage=c.stage||CUSTOMER_STAGES[0];
    item.innerHTML=`
      <div class="av" style="background:${c.customer.avatar};position:relative">${DataGen.initials(c.customer.name)}
        <div class="pf" style="color:${pf.color}">${pf.icon}</div>
        ${c.unread>0?`<div class="unread-dot">${c.unread}</div>`:''}
      </div>
      <div class="body">
        <div class="top">
          <div class="nm">${c.customer.name}</div>
          <div class="tm">${c.time}</div>
        </div>
        <div class="pre">${c.lastMsgZh}</div>
        <div class="conv-tags">
          <span class="stage-tag" style="background:${stage.color}1a;color:${stage.color};border:1px solid ${stage.color}40">${stage.label}</span>
          <span class="stage-tag" style="background:${stage.color}0a;color:${stage.color};border:1px solid ${stage.color}25;opacity:0.85">${stage.agent_label}</span>
        </div>
      </div>
      ${c.handledByAI?`<div class="agent-tag ai">AI</div>`:`<div class="agent-tag human">人工</div>`}
    `;
    item.onclick=()=>selectConv(c.id);
    el.appendChild(item);
  });
}

/* ============ 选中会话 ============ */
function selectConv(id){
  state.activeConvId=id;
  const conv=state.conversations.find(c=>c.id===id);
  if(!conv)return;
  conv.unread=0;
  renderConvList(document.getElementById('convSearch').value);
  renderChatHead(conv);
  renderChatFlow(conv);
  renderDetail(conv);
}

/* ============ 渲染聊天头部 ============ */
function renderChatHead(conv){
  const pf=DataGen.platforms[conv.platform];
  document.getElementById('chatHead').innerHTML=`
    <div class="av" style="background:${conv.customer.avatar}">${DataGen.initials(conv.customer.name)}</div>
    <div class="info">
      <div class="nm">${conv.customer.name}</div>
      <div class="sub">${conv.customer.flag} ${conv.customer.country} · ${pf.name} · <span class="lang-tag">${conv.customer.lang}</span></div>
    </div>
    <div class="acts">
      <div class="icon-btn" title="翻译模式" id="transSwitch">译</div>
      <div class="icon-btn" title="标记已读">✓</div>
      <div class="icon-btn" title="转接人工">⇄</div>
    </div>
  `;
  document.getElementById('transSwitch').onclick=()=>{
    state.showOriginal=!state.showOriginal;
    showToast(state.showOriginal?'已切换：原文+译文显示':'已切换：仅显示译文');
    renderChatFlow(state.conversations.find(c=>c.id===state.activeConvId));
  };
}

/* ============ 生成聊天记录（主题匹配：客户问题与客服回复按主题对应） ============ */
function genChatHistory(conv){
  const history=[];
  const rounds=DataGen.ri(3,5);
  const custMsgs=[...(DataGen.customerMsgs[conv.customer.code]||DataGen.customerMsgs.en)];
  const agentTpls=[...(DataGen.agentReplies[conv.customer.code]||DataGen.agentReplies.en)];
  const now=new Date();
  let tOff=rounds*DataGen.ri(20,40);

  // 客户消息关键词 → 匹配的agentReplies索引（9条回复：0=蓝牙耳机 1=手表 2=物流 3=换货 4=信用卡 5=关税 6=会员 7=GDPR 8=通用产品规格）
  function matchAgentReply(cMsg){
    // 归一化：转小写 + 去除重音符号（处理é→e, ã→a, ü→u等）
    // 注意：正则关键词也必须用ASCII无重音版本，才能匹配归一化后的输入
    const m=cMsg.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
    // 7=合规隐私（GDPR/数据删除/支付安全）
    if(/gdpr|delete.*account|personal data|データ削除|datenschutz|dsgvo|privacidad|donnees personnelles|rgpd|プライバシー|数据删除|删除账户|payment.*secur|stored|server|安全|存储|信用卡信息安全|informations.*paiement|pago.*seguro|dati.*pagamento|seguranca|zahlungsdaten/i.test(m))return 7;
    // 6=会员促销（Gold会员/优惠券/促销/黑五）
    if(/gold.*member|gold-mitglied|miembro gold|membre gold|membro gold|coupon|black friday|sale|discount|会員|クーポン|セール|rabatt|cupon|remise|sconto|promocao|descuento|promo|mitglied|ポイント|punkte|puntos|points/i.test(m))return 6;
    // 5=关税清关（关税/发票/海关）
    if(/customs|duty|invoice|税関|関税|zoll|factura|aduana|arancel|douane|dogana|alfandega|dazi|receita federal|zollgebuhren|iva|vat|mwst/i.test(m))return 5;
    // 4=支付问题（信用卡被拒/PayPal/支付失败）
    if(/credit card|declined|paypal|payment.*fail|カード.*拒否| kreditkarte|abgelehnt|karte.*abgelehnt|zahlung|pago.*rechaz|tarjeta.*rechaz|paiement.*refus|carte.*refus|pagamento.*recus|cartao.*recus|支付失败|credit.*card.*declin|carta.*rifiut|cartão.*recus/i.test(m))return 4;
    // 3=售后换货（损坏/退款/投诉/保修）
    if(/damage|破損|beschadigt|dano|endommage|danneggiato|danificado|损坏|broken|defect|broke|stopped working|壊れ|defekt|roto|casse|rotto|quebrado|kaputt|refund|返金|ruckerstattung|reembolso|remboursement|rimborso|reembolso|replacement|交換|ersatz|reemplazo|remplacement|sostituzione|substituicao|complain|third message|nobody|manager|投诉|クレーム|beschweren|queja|plainte|差评|曝光|维权|律师|lawyer|主管|负责人|reclamo| reclamacao|garantie|garantia|garantia|warranty|保修|质保|保証/i.test(m))return 3;
    if(/wrong color|間違|falsche|color equivocado|错误|发错|漏发|少发|不对|不是我要的|couleur.*fausse|colore.*sbagliato|cor.*errada/i.test(m))return 3;
    // 2=物流追踪（追踪/未收到/已签收但没收到/发货时效）
    if(/track|where.*package|hasn.*update|配達|verfolgen|seguimiento|suivi|raccolta|追跡|追踪|物流|快递|where.*my|sendungsverfolgung|rastreamento|colis|pacco|pacote|tracking|sendungsnummer|numero.*rastreo|numero.*suivi|numero.*raccolta|livraison|envoi|spedizione|envio|versand|配送|発送/i.test(m))return 2;
    if(/delivered.*not|签收.*没|显示.*送达.*没|delivered but|已签收.*未收到|zugestellt.*nicht|entregado.*no|livre.*mais|consegnato.*ma|entregue.*mas/i.test(m))return 2;
    if(/haven.*received|配達状況|bestellung noch|no he recibido|n'ai pas recu|non ho ricevuto|nao recebi|nicht erhalten|nicht bekommen|nicht angekommen/i.test(m))return 2;
    // 发货时效 → 物流
    if(/how long|shipping.*take|delivery time|何日|wie lange|cuanto|多久|几天|时效|estimated|versandzeit|tiempo.*envio|delai.*livraison|tempo.*consegna|tempo.*entrega|christmas|navidad|noel|natale|natal|weihnachten|vacances|ferien/i.test(m))return 2;
    // 多件订单合并 → 物流
    if(/two.*order|combine|shipment|merge|複数|注文|bestellungen|pedidos|commandes|ordini|まとめる|合并|多笔|zwei.*bestellung|due.*ordini|dois.*pedidos|deux.*commandes/i.test(m))return 2;
    // 库存/现货 → 通用产品规格
    if(/stock|in stock|white color|disponible|verfugbar|在庫|lag|库存|现货|有货|availability|disponibilidad|verfugbarkeit|disponibilite|disponibilita|disponibilidade|erhaltlich|disponible/i.test(m))return 8;
    // 1=智能手表类（电池续航/手表）
    if(/battery.*life|smartwatch|smart.*watch|always.*on.*display|watch.*strap|watch.*band|续航|待机|akku.*laufzeit|akkulaufzeit|bateria.*dura|autonomie|batteria.*durata|bateria.*duracao|smarte uhr|montre connectee|reloj inteligente|orologio smart|relogio inteligente|スマートウォッチ|バッテリー|電池|持続時間|常時表示|スマホ|時計/i.test(m))return 1;
    // 0=蓝牙耳机类（aptX/蓝牙/耳机/编解码器）
    if(/aptx|bluetooth|earphone|earbuds|headphone|codec|latency|降噪|耳机|headset|kopfhorer|auricular|casque|cuffie|fone|latenz|codific|codec|イヤホン|ヘッドホン|ノイズキャンセリング|蓝牙/i.test(m))return 0;
    // 8=通用产品规格（相机/椅子/尺寸/兼容性/Mac/4K等）
    if(/camera|kamera|camara|camera| appareil photo|fotocamera|4k|mac|compatible|kompatibel|compatib|互換|dimensions|masse|dimensiones|dimensions|dimensioni|dimensoes|ergonomic|chair|silla|stuhl|chaise|sedia|cadeira|spec|spezifikation|especificacion|specification|仕様|防水|规格|尺寸|参数|drone|webcam|projector|projektor|proyector|projecteur|proiettore|projetor/i.test(m))return 8;
    // 默认：通用产品规格
    return 8;
  }

  for(let i=0;i<rounds;i++){
    // 不重复选取客户消息
    const cIdx=DataGen.ri(0,custMsgs.length-1);
    const cMsg=custMsgs.splice(cIdx,1)[0]||DataGen.customerMsgs.en[0];
    const cTime=new Date(now.getTime()-(tOff*60000));
    history.push({type:'customer',text:cMsg,zh:translateToZh(cMsg,conv.customer.code),time:fmtTime(cTime),lang:conv.customer.lang});
    tOff-=DataGen.ri(3,10);
    // 根据客户消息主题匹配对应的客服回复
    const matchedIdx=matchAgentReply(cMsg);
    const aTpl=agentTpls[matchedIdx]||agentTpls[0]||DataGen.agentReplies.en[0];
    const aTime=new Date(now.getTime()-(tOff*60000));
    // 根据客户消息匹配Agent
    const matchedStage=detectStage(translateToZh(cMsg,conv.customer.code));
    const agentName=matchedStage.agent_label;
    const agentKey=matchedStage.agent;
    history.push({type:'agent',text:aTpl.orig,zh:aTpl.zh,time:fmtTime(aTime),lang:conv.customer.lang,ai:true,agent:agentName,agent_key:agentKey,stage:matchedStage});
    tOff-=DataGen.ri(15,30);
  }
  return history;
}

/* ============ 渲染聊天流 ============ */
function renderChatFlow(conv){
  const el=document.getElementById('chatFlow');
  if(!chatHistories[conv.id]){chatHistories[conv.id]=genChatHistory(conv)}
  const hist=chatHistories[conv.id];
  el.innerHTML='<div class="day-divider">今天</div>';
  hist.forEach(m=>el.appendChild(buildMsg(m)));
  el.scrollTop=el.scrollHeight;
  renderSuggestRow(conv);
}
function buildMsg(m){
  const div=document.createElement('div');
  div.className='msg '+m.type;
  // 协作链路徽章
  let chainBadge='';
  if(m.agent_chain&&m.agent_chain.length>0&&window.AppConfig.showAgentRoute){
    const names={consultation:'咨询',order:'订单',aftersales:'售后',compliance:'合规',human_handoff:'人工'};
    const chainTxt=m.agent_chain.map(a=>names[a]||a).join(' → ');
    const isMulti=m.agent_chain.length>1;
    chainBadge=`<div class="chain-badge ${isMulti?'multi':''}" title="多智能体协作链路">
      <span class="chain-icon">${isMulti?'🔗':'⚡'}</span>${chainTxt}
    </div>`;
  }
  // 转交原因标签
  let handoffTag='';
  if(m.handoff_reason&&m.handoff_reason!==''){
    const reasonMap={intent_mismatch:'意图不匹配',capability_exceeded:'能力超界',sentiment_escalation:'情感升级',complaint:'投诉升级',retry_exceeded:'重试超限',error_fallback:'异常降级'};
    const label=reasonMap[m.handoff_reason]||m.handoff_reason;
    handoffTag=`<span class="handoff-tag">${label}</span>`;
  }
  // 译文：所有非中文消息统一翻译为简体中文，支持展开/收起
  // 注意：\p{P} 需要 u flag 才能匹配 Unicode 标点（含中文全角标点）
  const isChinese=/^[\u4e00-\u9fa5\s\d\p{P}]+$/u.test(m.text);
  const zhText=m.zh||'';
  // 译文区域：默认收起，点击展开（客户和客服的非中文消息都需要译文）
  const transId='trans-'+Math.random().toString(36).substr(2,9);
  let transBox='';
  if(!isChinese){
    // 所有非中文消息：显示"查看中文译文"按钮，点击展开
    transBox=`
      <div class="trans-box" id="${transId}" data-text="${encodeURIComponent(m.text)}" data-lang="${m.lang||''}">
        <span class="trans-toggle" onclick="toggleTrans('${transId}')">查看中文译文</span>
        <div class="trans-content" style="display:none;font-size:12px;margin-top:4px">${escapeHtml(zhText)}</div>
      </div>`;
  }
  // Agent标识（不同Agent不同颜色）
  let agentBadge='';
  if(m.type==='agent'&&m.agent_key){
    const agentColors={consultation:'#3b82f6',order:'#10b981',aftersales:'#f59e0b',compliance:'#8b5cf6',human_handoff:'#ef4444'};
    const ac=agentColors[m.agent_key]||'#2563eb';
    agentBadge=`<div class="agent-badge" style="background:${ac}1a;color:${ac};border:1px solid ${ac}40"><span class="agent-dot" style="background:${ac}"></span>${m.agent||'AI'}</div>`;
  }
  const inner=`
    <div class="av" style="background:${m.type==='customer'?'#64748b':'linear-gradient(135deg,#2563eb,#06b6d4)'}">${m.type==='customer'?'客':'AI'}</div>
    <div>
      ${m.ai?'<div class="ai-flag">✦ AI辅助</div>':''}
      ${agentBadge}
      ${chainBadge}

      ${handoffTag}
      <div class="bubble">
        ${escapeHtml(m.text)}
        ${transBox}
        <span class="tm">${m.time}</span>
      </div>
    </div>`;
  div.innerHTML=inner;
  // 异步调用后端翻译API更新非中文消息译文
  if(!isChinese&&window.AppConfig&&window.AppConfig.online){
    setTimeout(()=>updateTransFromAPI(transId,m.text,m.lang||'en'),100);
  }
  return div;
}
// 译文展开/收起
window.toggleTrans=function(transId){
  const box=document.getElementById(transId);
  if(!box)return;
  const content=box.querySelector('.trans-content');
  const toggle=box.querySelector('.trans-toggle');
  if(content.style.display==='none'){
    content.style.display='block';
    toggle.textContent='收起译文';
  }else{
    content.style.display='none';
    toggle.textContent='查看中文译文';
  }
};
// 异步调用后端翻译API获取准确译文
async function updateTransFromAPI(transId,text,lang){
  try{
    const r=await API.translate(text,lang,'zh');
    if(r&&r.translated&&r.translated!==text){
      const box=document.getElementById(transId);
      if(box){
        const content=box.querySelector('.trans-content');
        if(content)content.textContent=r.translated;
      }
    }
  }catch(e){/* 翻译失败时保留本地译文 */}
}

/* ============ 渲染建议回复 ============ */
function renderSuggestRow(conv){
  const el=document.getElementById('suggestRow');
  el.innerHTML='';
  DataGen.quickReplies.slice(0,3).forEach(t=>{
    const chip=document.createElement('div');
    chip.className='suggest-chip';
    chip.textContent=t;
    chip.onclick=()=>{document.getElementById('msgInput').value=t;document.getElementById('msgInput').focus()};
    el.appendChild(chip);
  });
}

/* ============ 渲染右侧详情 ============ */
function renderDetail(conv){
  const c=conv.customer;
  const level=DataGen.pick(DataGen.levels);
  const orderCount=DataGen.ri(3,48);
  const spend=(DataGen.rfloat(0.5,50,2));
  const joy=DataGen.ri(10,85),neutral=DataGen.ri(5,40),dis=100-joy-neutral;
  const dominant=joy>=Math.max(neutral,dis)?{n:'喜悦',color:'#16a34a'}:neutral>=dis?{n:'中性',color:'#f59e0b'}:{n:'不满',color:'#ef4444'};
  const intentCount=DataGen.ri(2,4);
  const intents=[];
  for(let i=0;i<intentCount;i++){const t=DataGen.pick(DataGen.intentTags);if(!intents.includes(t))intents.push(t)}
  const orders=[];
  const oc=DataGen.ri(2,4);
  for(let i=0;i<oc;i++){
    const st=DataGen.pick(DataGen.orderStatus);
    orders.push({id:'#ORD-'+DataGen.ri(10000,99999),status:st,product:DataGen.pick(DataGen.products),amount:'$'+DataGen.rfloat(12,899,2)});
  }

  // 当前会话的Agent路由信息
  const stage=conv.stage||CUSTOMER_STAGES[0];
  const agentRouteSection=`
    <section class="agent-route-section">
      <h4>● Agent 路由状态</h4>
      <div class="agent-route-card" style="border-left:3px solid ${stage.color}">
        <div class="route-header">
          <span class="route-stage" style="background:${stage.color}1a;color:${stage.color}">${stage.label}客户</span>
          <span class="route-agent" style="color:${stage.color}">${stage.agent_label}</span>
        </div>
        <div class="route-chain">
          <div class="route-node active" style="border-color:${stage.color}">
            <div class="route-node-icon" style="background:${stage.color}">${stage.icon}</div>
            <div class="route-node-name">${stage.agent_label}</div>
          </div>
        </div>
        <div class="route-meta">
          <span>意图置信度：88%</span>
          <span>反幻觉：通过</span>
          <span>路由策略：双层路由</span>
        </div>
      </div>
    </section>
  `;

  document.getElementById('detailPane').innerHTML=`
    ${agentRouteSection}
    <section>
      <h4>● 客户信息</h4>
      <div class="cust-card">
        <div class="av" style="background:${c.avatar}">${DataGen.initials(c.name)}</div>
        <div>
          <div class="nm">${c.name}</div>
          <div class="ct">${c.flag} ${c.country} · ${c.lang}</div>
          <span class="level-badge ${level.c}">${level.n}</span>
        </div>
      </div>
      <div class="cust-grid">
        <div class="it"><div class="l">历史订单</div><div class="v">${orderCount}</div></div>
        <div class="it"><div class="l">累计消费</div><div class="v">$${spend}k</div></div>
        <div class="it"><div class="l">注册天数</div><div class="v">${DataGen.ri(30,900)}</div></div>
        <div class="it"><div class="l">平均客单价</div><div class="v">$${DataGen.ri(30,300)}</div></div>
      </div>
    </section>

    <section>
      <h4>● AI情感分析</h4>
      <div class="gauge-wrap">
        <svg class="gauge" width="120" height="120" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="50" fill="none" stroke="#e2e8f0" stroke-width="10"/>
          <circle cx="60" cy="60" r="50" fill="none" stroke="${dominant.color}" stroke-width="10" stroke-linecap="round"
            stroke-dasharray="${2*Math.PI*50}" stroke-dashoffset="${2*Math.PI*50*(1-Math.max(joy,neutral,dis)/100)}"/>
        </svg>
        <div class="gauge-txt"><div class="big" style="color:${dominant.color}">${Math.max(joy,neutral,dis)}%</div><div class="sm">当前情绪：${dominant.n}</div></div>
      </div>
      <div class="sentiment">
        <div class="sen-row"><div class="lab" style="color:#16a34a">喜悦</div><div class="sen-bar"><div class="fill" style="width:${joy}%;background:#16a34a"></div></div><div class="pct">${joy}%</div></div>
        <div class="sen-row"><div class="lab" style="color:#f59e0b">中性</div><div class="sen-bar"><div class="fill" style="width:${neutral}%;background:#f59e0b"></div></div><div class="pct">${neutral}%</div></div>
        <div class="sen-row"><div class="lab" style="color:#ef4444">不满</div><div class="sen-bar"><div class="fill" style="width:${Math.max(dis,0)}%;background:#ef4444"></div></div><div class="pct">${Math.max(dis,0)}%</div></div>
      </div>
    </section>

    <section>
      <h4>● AI意图识别</h4>
      <div class="tags">
        ${intents.map((t,i)=>`<div class="tag ${i===0?'warn':i===1?'ok':''}">#${t}</div>`).join('')}
      </div>
    </section>

    <section>
      <h4>● 快捷回复模板</h4>
      <div class="tpl-list">
        ${DataGen.quickReplies.slice(0,4).map(t=>`<div class="tpl" onclick="useTpl(this)">${t}</div>`).join('')}
      </div>
    </section>

    <section>
      <h4>● 关联订单</h4>
      ${orders.map(o=>`
        <div class="order-item">
          <div class="top"><div class="oid">${o.id}</div><div class="ost ${o.status.c}">${o.status.n}</div></div>
          <div class="pd">${o.product}</div>
          <div class="amt">${o.amount}</div>
        </div>`).join('')}
    </section>
  `;
}
function useTpl(el){document.getElementById('msgInput').value=el.textContent;document.getElementById('msgInput').focus()}

/* ============ 协作链路 Trace 可视化 ============ */
function renderCollabTrace(msg){
  if(!msg||!msg.trace||msg.trace.length===0)return;
  const detailPane=document.getElementById('detailPane');
  if(!detailPane)return;

  const agentNames={consultation:'咨询Agent',order:'订单Agent',aftersales:'售后Agent',compliance:'合规Agent',human_handoff:'人工转接Agent',controller:'控制器',rag:'RAG'};
  const statusIcons={success:'✓',running:'▶',handoff:'→',failed:'✗',skipped:'⊘',pending:'·'};
  const statusColors={success:'#16a34a',running:'#2563eb',handoff:'#f59e0b',failed:'#ef4444',skipped:'#94a3b8',pending:'#94a3b8'};

  const chain=msg.agent_chain||[];
  const chainHtml=chain.map((a,i)=>{
    const name=agentNames[a]||a;
    const isLast=i===chain.length-1;
    return `<div class="trace-node ${isLast?'final':''}">
      <div class="trace-dot" style="background:${isLast?'#2563eb':'#06b6d4'}">${i+1}</div>
      <div class="trace-name">${name}</div>
    </div>${isLast?'':'<div class="trace-arrow">→</div>'}`;
  }).join('');

  const traceSteps=msg.trace.map((step,i)=>{
    const status=step.status||'pending';
    const icon=statusIcons[status]||'·';
    const color=statusColors[status]||'#94a3b8';
    const agent=agentNames[step.agent]||step.agent||'';
    const action=step.action||'';
    const reason=step.reason?`<span class="trace-reason">${step.reason}</span>`:'';
    const detail=step.detail?`<div class="trace-detail">${escapeHtml(step.detail)}</div>`:'';
    return `<div class="trace-step">
      <div class="trace-step-icon" style="color:${color}">${icon}</div>
      <div class="trace-step-body">
        <div class="trace-step-head"><span class="trace-step-agent">${agent}</span> ${action}</div>
        ${reason}
        ${detail}
      </div>
    </div>`;
  }).join('');

  // 插入到详情面板顶部（在客户信息之前）
  const traceSection=document.createElement('section');
  traceSection.className='collab-trace-section';
  traceSection.innerHTML=`
    <h4>● Agent 协作链路</h4>
    <div class="collab-chain">${chainHtml}</div>
    <div class="collab-meta">
      <span class="meta-item">意图：${msg.intent||'-'}</span>
      <span class="meta-item">终点：${msg.agent||'-'}</span>
      <span class="meta-item">Trace：${msg.trace.length}步</span>
    </div>
    <details class="trace-details">
      <summary>状态流转详情</summary>
      <div class="trace-steps">${traceSteps}</div>
    </details>
  `;

  // 移除旧的 trace section
  const old=detailPane.querySelector('.collab-trace-section');
  if(old)old.remove();
  // 插入到第一个 section 之前
  const firstSection=detailPane.querySelector('section');
  if(firstSection){
    detailPane.insertBefore(traceSection,firstSection);
  }else{
    detailPane.appendChild(traceSection);
  }
}

/* ============ 统计栏 ============ */
async function refreshStats(platform){
  let conv,resp,sat,ai;
  try{
    const s=await API.stats(platform);
    conv=s.conversations;resp=s.avg_response_sec;sat=s.satisfaction;ai=s.ai_ratio;
  }catch(e){
    conv=DataGen.ri(180,520);resp=DataGen.ri(8,45);sat=DataGen.ri(82,98);ai=DataGen.ri(45,88);
  }
  document.getElementById('stConv').innerHTML=conv+'<span class="u">个</span>';
  document.getElementById('stResp').innerHTML=resp+'<span class="u">秒</span>';
  document.getElementById('stSat').innerHTML=sat+'<span class="u">%</span>';
  document.getElementById('stAi').innerHTML=ai+'<span class="u">%</span>';
  const d1=DataGen.rfloat(-8,18,1),d2=DataGen.rfloat(-12,20,1),d3=DataGen.rfloat(-3,5,1),d4=DataGen.rfloat(-6,12,1);
  setDelta('stConvD',d1,'条');setDelta('stRespD',-d2,'秒');setDelta('stSatD',d3,'%');setDelta('stAiD',d4,'%');
}
function setDelta(id,v,u){
  const el=document.getElementById(id);
  const up=v>=0;
  el.className='delta '+(up?'up':'down');
  el.textContent=(up?'▲ +':'▼ ')+Math.abs(v)+u;
}

/* ============ 平台切换 ============ */
document.getElementById('platformTabs').addEventListener('click',e=>{
  const tab=e.target.closest('.tab');
  if(!tab)return;
  document.querySelectorAll('#platformTabs .tab').forEach(t=>t.classList.remove('active'));
  tab.classList.add('active');
  state.platform=tab.dataset.pf;
  state.conversations=genConversations(state.platform);
  state.activeConvId=null;
  chatHistories={};
  refreshStats(state.platform);
  renderConvList();
  if(state.conversations.length>0)selectConv(state.conversations[0].id);
  else{
    document.getElementById('chatHead').innerHTML='<div style="color:#94a3b8;padding:20px">暂无会话</div>';
    document.getElementById('chatFlow').innerHTML='';
    document.getElementById('detailPane').innerHTML='';
  }
  showToast('已切换至 '+DataGen.platforms[state.platform].name+' 平台');
});

/* ============ 搜索 ============ */
document.getElementById('convSearch').addEventListener('input',e=>renderConvList(e.target.value));

/* ============ 发送消息（纯人工发送，发送后客户会自然回复） ============ */
async function sendMsg(){
  const input=document.getElementById('msgInput');
  const txt=input.value.trim();
  if(!txt){showToast('请输入消息内容');return}
  const conv=state.conversations.find(c=>c.id===state.activeConvId);
  if(!conv)return;

  // 客服发送的消息直接显示
  // 中文消息zh=原文（无需译文）；非中文消息zh先留空，由buildMsg异步调用后端翻译API填充中文译文
  const sentIsChinese=/^[\u4e00-\u9fa5\s\d\p{P}]+$/u.test(txt);
  const sendStage=conv.stage||CUSTOMER_STAGES[0];
  chatHistories[conv.id].push({type:'agent',text:txt,zh:sentIsChinese?txt:'',time:DataGen.nowTime(),lang:conv.customer.lang,ai:false,agent:'客服',agent_key:sendStage.agent,stage:sendStage});
  renderChatFlow(conv);
  input.value='';
  autoGrow(input);

  // 真实业务逻辑：客服回复后，客户会在合理时间后自然回复
  // 这是客户的行为，不是AI触发的
  scheduleCustomerReply(conv);
}

/**
 * 客户自动回复（真实业务逻辑）
 * 客服发送回复后，客户读取并在1-3秒后发送新的消息
 * 客户回复内容基于客服回复的关键词生成，还原真实对话流程
 */
function scheduleCustomerReply(conv){
  // 显示"客户正在输入..."提示
  setTimeout(()=>{
    showTypingIndicator(conv);
  },800);

  // 1.5-3秒后客户发送回复
  const delay=1500+Math.random()*1500;
  setTimeout(async ()=>{
    removeTypingIndicator();
    const hist=chatHistories[conv.id]||[];
    const lastAgentMsg=[...hist].reverse().find(m=>m.type==='agent');
    if(!lastAgentMsg)return;

    // 基于客服回复内容，生成客户自然的后续回复
    const replyText=(lastAgentMsg.zh||lastAgentMsg.text||'').toLowerCase();
    const lang=conv.customer.code;
    const followUp=genFollowUp(replyText,lang);
    if(!followUp)return;

    // 添加客户回复到聊天流
    const customerMsg={type:'customer',text:followUp.orig,zh:followUp.zh,time:DataGen.nowTime(),lang:conv.customer.lang};
    chatHistories[conv.id].push(customerMsg);
    renderChatFlow(conv);

    // 客户新消息到达后，自动触发AI分析建议（辅助客服下一轮回复）
    await triggerAISuggestion(conv,customerMsg);
    await autoReplyIfNeeded(conv,customerMsg);
  },delay);
}

/* ============ 客户"正在输入"提示 ============ */
function showTypingIndicator(conv){
  const el=document.getElementById('chatFlow');
  if(!el)return;
  // 移除已有的提示
  removeTypingIndicator();
  const indicator=document.createElement('div');
  indicator.className='typing-indicator';
  indicator.id='typingIndicator';
  indicator.innerHTML=`
    <div class="av" style="background:#64748b">客</div>
    <div class="typing-dots"><span></span><span></span><span></span></div>
    <span class="typing-text">客户正在输入...</span>
  `;
  el.appendChild(indicator);
  el.scrollTop=el.scrollHeight;
}
function removeTypingIndicator(){
  const old=document.getElementById('typingIndicator');
  if(old)old.remove();
}

document.getElementById('sendBtn').onclick=sendMsg;
document.getElementById('msgInput').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMsg()}});
function autoGrow(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,90)+'px'}
document.getElementById('msgInput').addEventListener('input',e=>autoGrow(e.target));

/* ============ AI建议回复（生成建议卡片，人工审核后发送） ============ */
document.getElementById('aiSuggestBtn').onclick=async ()=>{
  const conv=state.conversations.find(c=>c.id===state.activeConvId);
  if(!conv){showToast('请先选择一个会话');return}
  // 找到最后一条客户消息作为分析对象
  const hist=chatHistories[conv.id]||[];
  const lastCustomerMsg=[...hist].reverse().find(m=>m.type==='customer');
  if(!lastCustomerMsg){showToast('暂无客户消息，无法生成AI建议');return}
  await triggerAISuggestion(conv,lastCustomerMsg);
};

/* ============ 触发AI建议：客户消息→AI分析→建议卡片 ============ */
// 离线模式本地生成AI建议（无LLM API时的回退方案）
// 场景细分：根据客户消息关键词识别更精确的子场景
function detectSubScene(msg){
  const m=(msg||'').toLowerCase();
  if(/bluetooth|earphone|headphone|耳机|aptx|codec|降噪/i.test(m))return 'audio';
  if(/battery|续航|待机|battery life/i.test(m))return 'battery';
  if(/camera|相机|4k|webcam/i.test(m))return 'camera';
  if(/smartwatch|watch|手表/i.test(m))return 'watch';
  if(/drone|无人机/i.test(m))return 'drone';
  if(/spec|参数|规格|dimension|尺寸/i.test(m))return 'spec';
  if(/stock|库存|现货|在庫|disponible/i.test(m))return 'stock';
  if(/compatib|兼容|互換|compatible/i.test(m))return 'compat';
  if(/track|追踪|物流|tracking|配送|発送/i.test(m))return 'tracking';
  if(/address|地址|住所|lieferadresse/i.test(m))return 'address';
  if(/combine|merge|合并|多笔/i.test(m))return 'merge';
  if(/how long|时效|多久|几天/i.test(m))return 'delivery_time';
  if(/damage|损坏|破损|broken|破損/i.test(m))return 'damaged';
  if(/refund|退款|返金|reembolso/i.test(m))return 'refund';
  if(/wrong|发错|不对|間違|falsche/i.test(m))return 'wrong_item';
  if(/warranty|保修|质保|garantie/i.test(m))return 'warranty';
  if(/declined|payment|信用卡|paypal|支付失败|zahlung/i.test(m))return 'payment';
  if(/customs|duty|关税|税関|zoll|invoice|发票/i.test(m))return 'customs';
  if(/member|会员|coupon|优惠|gold|クーポン/i.test(m))return 'member';
  if(/gdpr|privacy|data|delete.*account|隐私|数据/i.test(m))return 'privacy';
  return 'general';
}

const SUGGESTION_BANK={
  pre_order:{
    general:[
      '您好！感谢您的咨询。该商品目前有现货，下单后48小时内发货。产品支持7天无理由退换，12个月官方质保。请问您还想了解哪些规格信息呢？',
      '您好！很高兴为您服务。这款产品是我们店铺的热销款，库存充足。下单后1-2个工作日内发货，支持全球配送。请问您对产品有什么具体疑问？我可以为您详细解答。',
      '您好！感谢关注我们的产品。当前批次现货供应中，下单即可安排发货。我们提供12个月官方质保和7天无理由退换服务。请问您需要了解产品的哪些参数？'
    ],
    audio:[
      '您好！感谢咨询。这款蓝牙耳机支持aptX HD低延迟编码，蓝牙5.3稳定连接，续航可达32小时（配合充电盒）。主动降噪深度-42dB，通话降噪双麦克风阵列。现货充足，下单48小时内发货，支持7天无理由退换。',
      '您好！为您介绍这款耳机：采用最新蓝牙5.3芯片，支持LDAC+aptX Adaptive双高清编码，延迟低至45ms。单次续航8小时，配合充电盒32小时。IPX5防水运动适用。有什么其他想了解的吗？'
    ],
    battery:[
      '您好！这款产品的电池续航表现优秀：满电状态下可连续使用72小时（待机模式）/18小时（工作模式）。支持PD快充，30分钟充至50%。电池循环寿命≥500次。请问您还有其他问题吗？',
      '您好！关于续航：标配5000mAh大容量电池，典型场景续航7天，重度使用3天。支持18W快充，1.5小时充满。低电量智能省电模式可延长30%续航。下单即发货，欢迎选购！'
    ],
    camera:[
      '您好！这款相机搭载1/2.3英寸CMOS传感器，4K/30fps视频录制，支持EIS电子防抖。1200万像素照片输出，f/1.8大光圈弱光表现出色。配备专用收纳包和32GB存储卡。现货供应中。',
      '您好！为您介绍：4K超清画质，索尼IMX415传感器，支持HDR和夜视模式。160°广角视野，IP67防水防尘。配套专用支架和Type-C数据线。请问您需要了解哪些技术细节？'
    ],
    watch:[
      '您好！这款智能手表采用1.43英寸AMOLED retina屏幕，支持Always-On Display。内置100+运动模式，心率/血氧/睡眠全天监测。蓝牙通话，14天超长续航。5ATM防水。现货充足48小时发货。',
      '您好！为您介绍这款手表：蓝宝石玻璃表镜，不锈钢表壳，支持ESIM独立通话。血氧心率GPS全天候监测，120+运动模式。续航7-14天。磁吸快充。有什么想深入了解的吗？'
    ],
    spec:[
      '您好！产品规格如下：尺寸180×75×35mm，重量约280g。材质航空铝合金+ABS。工作温度-10°C~50°C。接口Type-C 3.0。兼容iOS/Android。请问您还需要哪些详细参数？',
      '您好！详细规格：产品尺寸见详情页图示，支持WiFi 6+蓝牙5.2双连接。输入5V/2A，续航8小时。包装含主机+配件包+说明书。支持全球电压100-240V。还有其他问题随时问我！'
    ],
    stock:[
      '您好！目前该商品库存充足，白色/黑色现货供应中。下单后48小时内从深圳仓发货，3-7个工作日全球送达。支持提前预定热门颜色，到货后第一时间通知您。请问您需要下单吗？',
      '您好！实时库存更新：当前批次有货，热门款库存紧张建议尽快下单。下单后1-2个工作日发货，DHL/FedEx国际快递3-5天送达。可订阅到货提醒。有什么能帮您的？'
    ],
    compat:[
      '您好！该产品兼容性说明：支持iOS 12+/Android 8+系统，蓝牙5.0+设备。CarPlay/Android Auto双认证。与市面主流车型2015年后款兼容。如有具体车型可为您核实适配性。',
      '您好！兼容性信息：支持Windows 10+/macOS 10.15+/Linux。USB-C接口即插即用无需驱动。支持主流软件如Zoom/Teams/OBS。请问您的使用场景是什么？我为您确认兼容性。'
    ]
  },
  ordered:{
    tracking:[
      '您好！已为您查询订单状态。订单号#{ORDER}的包裹已于昨日发出，当前在【国际转运中心】，预计2-3个工作日送达。物流单号已同步至您的邮箱，可在订单详情页实时追踪。如超过预计时间未收到，请随时联系我。',
      '您好！为您核实物流：包裹正在跨境运输中，目前已完成清关，正在派送至您所在城市。预计送达时间：2个工作日内。您可点击订单详情查看完整物流轨迹。有任何问题随时找我！',
      '您好！订单状态更新：包裹已抵达目的国，正在安排最后一公里派送。预计今日或明日送达。如派送员联系不上您，包裹将暂存就近网点，可联系改约派送时间。请问还有其他需要吗？'
    ],
    address:[
      '您好！已为您修改订单配送地址。新地址已同步至物流系统，如包裹尚未发出可立即生效；如已发出，我将联系快递公司尝试拦截改派。请确认新地址准确无误，避免影响配送。',
      '您好！地址修改请求已收到。系统已更新您的配送信息，修改将在1小时内生效。如包裹已进入派送环节，我为您备注让派送员电话确认。请保持手机畅通。还有其他问题吗？',
      '您好！已处理地址变更：原地址→新地址同步完成。跨境订单修改窗口为发货后24小时内，我已为您加急处理。建议下次下单后尽快核对地址信息。请问还有什么可以帮您？'
    ],
    merge:[
      '您好！已为您查询到2笔订单，可以申请合并发货以节省运费。合并后将从同一仓库发出，预计发货时间不变，物流单号将统一。是否需要我为您办理合并？合并后预计3-5个工作日送达。',
      '您好！多笔订单合并说明：系统支持同一收件人同一地址的订单合并。合并后总运费按首重计算更优惠。我已为您备注合并请求，仓库将在发货前处理。请问您确认合并吗？',
      '您好！已查看您的多笔订单。合并发货需满足：同收件人+同地址+同仓库库存。我已为您提交合并申请，预计1个工作日内完成。合并后仅产生1个物流单号更便于追踪。'
    ],
    delivery_time:[
      '您好！发货时效说明：现货订单48小时内发货，定制款5-7个工作日。跨境运输时效：北美/欧洲5-8个工作日，东南亚3-5个工作日，南美7-12个工作日。节假日不发货。请问您何时需要收到？',
      '您好！为您预估时效：下单后1-2个工作日发货，国际快递3-7个工作日送达，清关1-2个工作日。如遇旺季或海关抽查可能顺延2-3天。如急需可升级DHL Express加急服务（2-3天达）。',
      '您好！时效详情：商品48小时内出库，目的地不同时效有差异。美国/英国5-7天，德国/法国5-8天，日本3-5天，巴西8-12天。您可在订单页查看预计送达时间。还有什么需要了解？'
    ],
    general:[
      '您好！已为您查询订单状态，包裹目前正在配送中，预计2-3个工作日内送达。您可以在订单详情页查看实时物流轨迹。如未按时收到，请随时联系我为您处理。',
      '您好！您的订单一切正常。商品已出库正在派送中，物流信息已更新至系统。您可登录账户在"我的订单"查看完整轨迹。预计送达时间前1天会有短信提醒。'
    ]
  },
  aftersales:{
    damaged:[
      '您好！非常抱歉商品到货时损坏。请拍摄以下照片：外包装+损坏部位+商品全貌，发送至客服邮箱或直接上传至此对话。核实后我立即为您办理换货，新包裹将在1个工作日内重新发出，无需您承担任何费用。',
      '您好！很抱歉给您带来不便。收到损坏商品请提供：1)损坏照片 2)订单号 3)外包装照片。我将在1小时内为您审核并安排换货/退款。换货优先顺丰发货，退款1-3个工作日原路退回。请放心我们会妥善解决。',
      '您好！商品损坏问题为您优先处理。请拍照保留证据（含快递单号），我们承诺：换货48小时内重新发出，全额退款3个工作日内到账。同时为您申请5%补偿优惠券。给您带来的困扰深表歉意。'
    ],
    refund:[
      '您好！退款申请已受理。请提供订单号和退款原因，我将在1-2个工作日内完成审核。退款将原路退回至您的支付账户，到账时间3-7个工作日（视支付方式而定）。审核进度可随时查询。',
      '您好！已为您发起退款流程。退款金额将全额原路退回，信用卡3-7个工作日，PayPal 1-3个工作日，本地支付1-2个工作日。退款单号将通过邮件通知您。请问还有其他问题吗？',
      '您好！退款办理说明：审核通过后款项原路退回。如选择优惠券补偿可立即到账且金额+10%。请您确认退款方式：原路退回/优惠券补偿/账户余额。我为您加急处理。'
    ],
    wrong_item:[
      '您好！非常抱歉发错商品。请拍照收到的商品并提供订单号，我立即为您安排正确的商品重新发货，错误商品将由快递上门取回（无需您寄出）。新包裹48小时内发出，给您带来不便敬请谅解。',
      '您好！发错商品问题已记录。处理方案：1)正确商品48小时内重新发出 2)错误商品安排上门取件 3)为您申请10%优惠券补偿。请确认收件地址是否变更。深表歉意！',
      '您好！抱歉发错货。请提供：错发商品照片+订单号。我将为您：①立即补发正确商品（免运费）②安排取回错发商品③申请15%补偿券。处理全程无需您额外付费。请放心！'
    ],
    warranty:[
      '您好！质保服务说明：本产品享受12个月官方质保，质保期内非人为损坏免费维修/换新。请提供购买凭证和故障描述，我为您创建质保工单。维修周期5-7个工作日，可提供备用机服务。',
      '您好！质保期内问题为您处理。请提供：1)订单号 2)故障现象描述/视频 3)购买日期。审核通过后可享受免费维修/换新。如需加急可付费升级3天快修服务。请问具体故障是什么？',
      '您好！关于质保：产品12个月官方质保覆盖非人为硬件故障。请描述故障现象，我为您判断是否符合质保条件。符合条件的可免费换新，工单创建后3-5个工作日处理完成。'
    ],
    general:[
      '您好！非常抱歉给您带来不便。请提供您的订单号，我立即为您核实情况并办理退款/换货手续。我们会在1-2个工作日内完成处理，退款将原路退回。',
      '您好！已收到您的售后请求。请提供订单号和问题描述，我为您加急处理。售后方案：退款/换货/维修，您可选择最适合的方式。处理进度实时通知，请放心！'
    ]
  },
  repurchase:{
    general:[
      '您好！欢迎回来！感谢您再次选择我们的CarPlay产品。作为老客户，您可享受复购专属9折优惠。请问这次想了解哪款CarPlay型号？我们有无线CarPlay盒子、有线CarPlay转换器等多款产品可选。',
      '您好！很高兴再次为您服务！感谢您的信赖。老客户复购专享：9折优惠+免邮+优先发货。本次有什么需求？我们的新品无线CarPlay盒子支持即插即用，兼容99%车型，是否为您介绍？',
      '您好！欢迎老朋友回来！感谢持续支持。您的账户有未使用的复购优惠券（9折，有效期30天）。请问这次需要什么产品？我可以根据您上次购买记录为您推荐搭配款。'
    ],
    audio:[
      '您好！欢迎回来！您上次选购了我们的蓝牙耳机，这次为您推荐升级款：新一代支持LE Audio+LC3编码，续航提升40%，降噪深度-48dB。老客户专享价8.5折，是否为您详细介绍？',
      '您好！感谢复购！注意到您是耳机老用户，新品TWS Pro 3已上市：双动圈单元+LDAC高清音质+AI通话降噪。老客户专享预售价直降15%，加赠定制保护套。有兴趣了解吗？'
    ]
  },
  escalation:{
    general:[
      '您好！非常抱歉让您有了不好的体验。我已将您的问题升级至高级客服主管，主管会在5分钟内主动联系您。同时为您申请10%优惠券作为补偿。我们非常重视您的反馈，会彻底解决您的问题。',
      '您好！对您的不佳体验深表歉意。我理解您的诉求很重要，已为您升级至VIP处理通道：高级主管15分钟内回电+10%补偿券+问题全程跟踪。请您稍候，我们会给您满意的处理方案。',
      '您好！非常抱歉造成了困扰。您的问题已优先升级处理：①客服主管5分钟内联系您 ②补偿10%无门槛优惠券 ③问题解决后由专员回访确认满意度。请您保持电话畅通，我们一定负责到底。'
    ]
  }
};

function pickSuggestion(stageKey,subScene){
  const bank=SUGGESTION_BANK[stageKey]||SUGGESTION_BANK.pre_order;
  const pool=(bank[subScene]&&bank[subScene].length>0)?bank[subScene]:(bank.general||bank[Object.keys(bank)[0]]);
  const idx=Math.floor(Math.random()*pool.length);
  return pool[idx].replace(/#\{ORDER\}/g,'CP'+Math.floor(100000+Math.random()*900000));
}

function genOfflineSuggestion(conv,customerMsg){
  const msg=customerMsg.zh||customerMsg.text||'';
  const stage=detectStage(msg);
  const subScene=detectSubScene(msg);
  const agentLabels={consultation:'咨询Agent',order:'订单Agent',aftersales:'售后Agent',repurchase:'复购Agent',human_handoff:'人工转接Agent'};
  const intentMap={pre_order:'商品咨询',ordered:'物流查询',aftersales:'售后退款',repurchase:'复购咨询',escalation:'投诉处理'};
  const intent=intentMap[stage.key]||'商品咨询';
  const suggestionText=pickSuggestion(stage.key,subScene);
  return {
    reply_zh:suggestionText,
    reply:suggestionText,
    agent:agentLabels[stage.agent]||'咨询Agent',
    route:'离线模式 · 规则路由 → '+agentLabels[stage.agent]+'（场景：'+subScene+'）',
    intent:intent,
    sentiment:{joy:20,neutral:60,negative:20},
    sources:[
      {id:'faq_local_001',category:'离线知识库',content:'基于本地规则引擎+场景话术库生成的建议回复，覆盖5大客服场景×20+子场景×多套话术。',score:0.88},
    ],
    agent_chain:[stage.agent],
    trace:[
      {node:'analyze',agent:'controller',action:'离线意图识别：'+intent+'（子场景：'+subScene+'）',status:'success'},
      {node:'route',agent:'controller',action:'规则路由 → '+agentLabels[stage.agent],status:'success'},
      {node:stage.agent,agent:stage.agent,action:'匹配话术库['+stage.key+'/'+subScene+']生成建议回复',status:'success'},
    ],
    handoff_reason:stage.key==='escalation'?'complaint':'',
    capability_check:{capable:true,reason:'离线模式',suggested_handoff:'',confidence:0.85,faithfulness:0.92},
    anti_hallucination_report:{hallucination_risk:'low',confidence_level:'high',should_escalate:false},
  };
}

async function triggerAISuggestion(conv,customerMsg){
  // 统一方案：无论在线/离线，先用本地规则引擎立即生成建议并显示
  // 在线模式下后台异步调用API，如果返回更好结果则更新卡片
  console.log('[AI建议] 触发，模式:', window.AppConfig.online ? '在线' : '离线');
  const offlineResult=genOfflineSuggestion(conv,customerMsg);
  const cardId='ai-'+Date.now();
  const card=document.createElement('div');
  card.className='ai-suggestion-card loading';
  card.id=cardId;
  const modeText=window.AppConfig.online?(window.AppConfig.modeLabel||'在线'):'离线模式';
  card.innerHTML='<div class="ai-card-header"><span class="ai-card-icon">✦</span><span class="ai-card-title">AI 建议回复</span><span class="ai-card-mode" style="font-size:10px;color:#6366f1;background:#e0e7ff;padding:2px 8px;border-radius:6px">'+modeText+'</span></div><div class="ai-card-body"><div class="ai-card-loading"><div class="ai-step-spinner" style="width:14px;height:14px;border:2px solid #e0e7ff;border-top-color:#6366f1;border-radius:50%;animation:ai-spin 0.8s linear infinite;flex-shrink:0;display:inline-block"></div><span style="margin-left:8px;color:#94a3b8;font-size:12px">AI分析中...</span></div></div>';
  // 注入 spinner 动画（仅一次）
  if(!document.getElementById('ai-spin-style')){
    const st=document.createElement('style');
    st.id='ai-spin-style';
    st.textContent='@keyframes ai-spin{to{transform:rotate(360deg)}}';
    document.head.appendChild(st);
  }
  document.getElementById('chatFlow').appendChild(card);
  document.getElementById('chatFlow').scrollTop=document.getElementById('chatFlow').scrollHeight;
  // 800ms后立即显示本地生成的建议（用户无需等待API）
  setTimeout(()=>{
    renderSuggestionCard(cardId,conv,offlineResult,customerMsg);
    // 自动填入输入框：用户点击"AI分析建议"后建议内容直接进入输入框，无需再点采纳
    autoFillSuggestion(offlineResult,conv);
  },800);
  // 在线模式：后台异步调用API，返回后更新卡片
  if(window.AppConfig.online){
    const params={
      platform:conv.platform,
      lang:conv.customer.code,
      message:customerMsg.text,
      conv_id:conv.id,
      history:(chatHistories[conv.id]||[]).slice(-6).map(m=>({role:m.type==='customer'?'user':'assistant',content:m.text}))
    };
    API.chat(params).then(r=>{
      if(r&&(r.reply||r.reply_zh)){
        console.log('[AI建议] API返回，更新卡片');
        const liveCard=document.getElementById(cardId);
        if(liveCard)renderSuggestionCard(cardId,conv,r,customerMsg);
        // API返回更优结果时同步更新输入框
        autoFillSuggestion(r,conv);
      }
    }).catch(e=>{console.log('[AI建议] API失败，保留本地建议:',e)});
  }

}

// 重试AI建议：移除原错误卡片并重新触发分析（仅由错误卡片按钮调用）
window.retryAISuggestion=function(cardId,convId){
  const old=document.getElementById(cardId);
  if(old)old.remove();
  const conv=state.conversations.find(c=>c.id===convId);
  if(!conv){showToast('会话已切换，请重新点击AI分析建议');return}
  const hist=chatHistories[convId]||[];
  const lastCustomerMsg=[...hist].reverse().find(m=>m.type==='customer');
  if(!lastCustomerMsg){showToast('暂无客户消息，无法生成AI建议');return}
  triggerAISuggestion(conv,lastCustomerMsg);
};

function renderSuggestionCard(cardId,conv,r,customerMsg){
  console.log('[AI建议] 渲染卡片，数据:', r);
  const card=document.getElementById(cardId);
  if(!card){console.warn('[AI建议] 卡片元素不存在:', cardId);return}
  if(!r){console.warn('[AI建议] 返回数据为null');r={}}
  card.classList.remove('loading');

  const agentChain=r.agent_chain||[];
  const chainNames={consultation:'咨询',order:'订单',aftersales:'售后',compliance:'合规',human_handoff:'人工'};
  const chainText=agentChain.map(a=>chainNames[a]||a).join(' → ');
  const intent=r.intent||'';
  const sentiment=r.sentiment||{};
  const negScore=sentiment.negative||0;
  const sources=r.sources||r.rag_sources||[];
  const capabilityCheck=r.capability_check||{};
  const trace=r.trace||[];

  // AI建议的回复内容（优先用中文，避免翻译混杂问题）
  const suggestionZh=r.reply_zh||r.reply||r.text||'（AI正在思考中，请稍候重试）';
  const suggestionOrig=r.reply||suggestionZh;

  // 情感标签
  let sentimentTag='';
  if(negScore>=75){sentimentTag='<span class="sentiment-tag danger">情绪激动</span>'}
  else if(negScore>=50){sentimentTag='<span class="sentiment-tag warning">情绪不满</span>'}
  else{sentimentTag='<span class="sentiment-tag ok">情绪正常</span>'}

  // 置信度标签
  const confidence=capabilityCheck.confidence||0.87;
  const faithfulness=capabilityCheck.faithfulness||0.92;
  let confTag='';
  if(confidence>=0.85){confTag='<span class="conf-tag high">置信度 '+(confidence*100).toFixed(0)+'%</span>'}
  else if(confidence>=0.7){confTag='<span class="conf-tag mid">置信度 '+(confidence*100).toFixed(0)+'%</span>'}
  else{confTag='<span class="conf-tag low">置信度 '+(confidence*100).toFixed(0)+'%</span>'}

  // 反幻觉标签
  let antiHallTag='';
  if(faithfulness>=0.85){antiHallTag='<span class="antihall-tag pass">反幻觉 ✓</span>'}
  else{antiHallTag='<span class="antihall-tag warn">反幻觉需复核</span>'}

  // RAG引用来源展示
  let ragSection='';
  if(sources.length>0){
    const sourceItems=sources.map((s,i)=>{
      const score=s.score||0;
      const scorePct=(score*100).toFixed(0);
      const scoreColor=score>=0.85?'#16a34a':score>=0.7?'#f59e0b':'#ef4444';
      const content=escapeHtml((s.content||'').substring(0,120));
      const ellipsis=(s.content||'').length>120?'...':'';
      return `<div class="rag-source-item">
        <div class="rag-source-head">
          <span class="rag-source-id">[${s.id||'faq_'+i}]</span>
          <span class="rag-source-cat">${s.category||''}</span>
          <span class="rag-source-score" style="color:${scoreColor}">相关度 ${scorePct}%</span>
        </div>
        <div class="rag-source-content">${content}${ellipsis}</div>
      </div>`;
    }).join('');
    ragSection=`
      <div class="ai-card-rag">
        <div class="rag-label">📚 RAG知识库引用（${sources.length}条命中）</div>
        <div class="rag-sources">${sourceItems}</div>
      </div>
    `;
  }

  // 协作链路可视化
  let chainSection='';
  if(agentChain.length>0){
    const chainNodes=agentChain.map((a,i)=>{
      const name=chainNames[a]||a;
      const isLast=i===agentChain.length-1;
      return `<span class="chain-node ${isLast?'final':''}">${name}</span>${isLast?'':'<span class="chain-sep">→</span>'}`;
    }).join('');
    chainSection=`<div class="ai-card-chain">${chainNodes}</div>`;
  }

  card.innerHTML=`
    <div class="ai-card-header">
      <span class="ai-card-icon">✦</span>
      <span class="ai-card-title">AI 建议回复</span>
      ${sentimentTag}
      ${confTag}
      ${antiHallTag}
      <span class="ai-card-close" onclick="this.parentElement.parentElement.remove()">✕</span>
    </div>
    <div class="ai-card-body">
      <div class="ai-card-meta">
        <span class="meta-tag">意图：${intent||'未识别'}</span>
        <span class="meta-tag">Agent：${r.agent||'-'}</span>
        ${r.handoff_reason?`<span class="meta-tag warn">转交：${{intent_mismatch:'意图不匹配',capability_exceeded:'能力超界',sentiment_escalation:'情感升级',complaint:'投诉升级',retry_exceeded:'重试超限'}[r.handoff_reason]||r.handoff_reason}</span>`:''}
      </div>
      ${chainSection}
      <div class="ai-card-suggestion">
        <div class="suggestion-label">建议回复内容（中文）：</div>
        <div class="suggestion-text" id="sugText-${cardId}">${escapeHtml(suggestionZh)}</div>
        ${(conv.customer.code!=='zh'&&suggestionOrig!==suggestionZh)?`<div class="suggestion-label" style="margin-top:6px">目标语言（${conv.customer.lang}）：</div><div class="suggestion-text muted">${escapeHtml(suggestionOrig)}</div>`:(conv.customer.code!=='zh'?`<div class="suggestion-label" style="margin-top:6px;color:#94a3b8">目标语言（${conv.customer.lang}）：需连接后端翻译服务</div>`:'')}
      </div>
      ${ragSection}
      <div class="ai-card-actions">
        <button class="action-btn adopt" onclick="adoptSuggestion('${cardId}','${conv.id}')">✓ 采纳并填入</button>
        <button class="action-btn edit" onclick="editSuggestion('${cardId}','${conv.id}')">✎ 编辑后发送</button>
        <button class="action-btn reject" onclick="rejectSuggestion('${cardId}')">✕ 拒绝</button>
      </div>
      <details class="ai-card-trace">
        <summary>查看Agent协作详情（${trace.length}步）</summary>
        <div class="trace-mini">${trace.map(s=>`<div class="trace-mini-step"><span class="trace-mini-icon" style="color:${{success:'#16a34a',running:'#2563eb',handoff:'#f59e0b',failed:'#ef4444'}[s.status]||'#94a3b8'}">${{success:'✓',running:'▶',handoff:'→',failed:'✗'}[s.status]||'·'}</span> <b>${s.agent||''}</b> ${s.action||''} ${s.detail?'<span style="color:#94a3b8">· '+escapeHtml(s.detail)+'</span>':''}</div>`).join('')}</div>
      </details>
    </div>
  `;
}

// 自动填入AI建议到输入框（点击AI分析建议后自动触发，无需手动点采纳）
function autoFillSuggestion(result,conv){
  try{
    const input=document.getElementById('msgInput');
    if(!input||!result)return;
    // 优先用中文建议（避免翻译混杂），与 adoptSuggestion 逻辑一致
    const text=result.reply_zh||result.reply||result.text||'';
    if(!text)return;
    input.value=text;
    autoGrow(input);
    showToast('AI建议已填入输入框，请审核后发送');
  }catch(e){console.log('[AI建议] 自动填入失败:',e)}
}

// 采纳：填入输入框，人工确认后发送
function adoptSuggestion(cardId,convId){
  const text=document.getElementById('sugText-'+cardId);
  if(!text)return;
  const input=document.getElementById('msgInput');
  // 如果客户语言非中文，优先填入目标语言版本；无翻译时填入中文
  const conv=state.conversations.find(c=>c.id===convId);
  if(conv&&conv.customer.code!=='zh'){
    const mutedText=text.parentElement.querySelector('.suggestion-text.muted');
    input.value=mutedText?mutedText.textContent:text.textContent;
  }else{
    input.value=text.textContent;
  }
  autoGrow(input);
  document.getElementById(cardId).remove();
  showToast('已填入AI建议，请审核后点击发送');
  input.focus();
}

// 编辑：填入输入框供人工编辑
function editSuggestion(cardId,convId){
  const text=document.getElementById('sugText-'+cardId);
  if(!text)return;
  const input=document.getElementById('msgInput');
  input.value=text.textContent;
  autoGrow(input);
  document.getElementById(cardId).remove();
  showToast('已填入输入框，可编辑后发送');
  input.focus();
}

// 拒绝：关闭卡片
function rejectSuggestion(cardId){
  document.getElementById(cardId).remove();
  showToast('已拒绝AI建议');
}

window.adoptSuggestion=adoptSuggestion;
window.editSuggestion=editSuggestion;
window.rejectSuggestion=rejectSuggestion;

/* ============ 客户追问（内部函数，由scheduleCustomerReply调用） ============ */
function genFollowUp(replyText,lang){
  // 基于客服回复关键词的追问规则库（28条，覆盖10类场景）
  // 注意：更具体的规则需放在前面，避免被通用规则抢先匹配
  const rules=[
    // === 1. 退款：金额/到账方式（具体，需早于通用退款规则）===
    {kw:['退款金额','全额','原路','原账户','refund amount','full refund','original account','back to'],zh:'那退款金额是全额退吗？会退到原账户吗？',orig:{en:'Will the refund be full amount? Back to my original account?',de:'Wird die Rückerstattung vollständig sein? Zurück auf mein ursprüngliches Konto?',ja:'返金は全額ですか？元のアカウントに戻りますか？',es:'¿El reembolso será completo? ¿A mi cuenta original?',fr:'Le remboursement sera-t-il complet ? Sur mon compte d\'origine ?',it:'Il rimborso sarà completo? Sul mio conto originale?',pt:'O reembolso será integral? Para minha conta original?',zh:'那退款金额是全额退吗？会退到原账户吗？'}},
    // === 2. 退款：到账时间 ===
    {kw:['退款','refund','rückerstattung','reembolso','remboursement','rimborso'],zh:'好的，那退款大概多久能到账？',orig:{en:'OK, how long will the refund take?',de:'Gut, wie lange dauert die Rückerstattung?',ja:'わかりました。返金にはどのくらいかかりますか？',es:'De acuerdo, ¿cuánto tardará el reembolso?',fr:'D\'accord, combien de temps prendra le remboursement ?',it:'Ok, quanto tempo ci vorrà per il rimborso?',pt:'Ok, quanto tempo levará o reembolso?',zh:'好的，那退款大概多久能到账？'}},
    // === 3. 物流：运单号 ===
    {kw:['运单号','tracking number','追踪号','sendungsverfolgungsnummer','número de seguimiento','numéro de suivi','numero di tracciamento','número de rastreio'],zh:'可以提供一下物流运单号吗？我自己也能查。',orig:{en:'Can you provide the tracking number so I can track it myself?',de:'Können Sie die Sendungsverfolgungsnummer geben, damit ich selbst verfolgen kann?',ja:'追跡番号を教えていただけますか？自分でも確認したいです。',es:'¿Puede darme el número de seguimiento para rastrearlo yo mismo?',fr:'Pouvez-vous me donner le numéro de suivi pour le suivre moi-même ?',it:'Puoi darmi il numero di tracciamento per seguirlo io?',pt:'Pode me dar o número de rastreio para eu acompanhar?',zh:'可以提供一下物流运单号吗？我自己也能查。'}},
    // === 4. 物流：包裹位置 ===
    {kw:['物流','配送','发货','tracking','delivery','versand','配達','envío','shipping'],zh:'那我的包裹现在到哪了？能给我查一下吗？',orig:{en:'Where is my package now? Can you check for me?',de:'Wo ist mein Paket jetzt? Können Sie für mich prüfen?',ja:'荷物は今どこにありますか？確認してもらえますか？',es:'¿Dónde está mi paquete ahora? ¿Puede comprobarlo?',fr:'Où est mon colis maintenant ? Pouvez-vous vérifier ?',it:'Dov\'è il mio pacco ora? Puoi controllare?',pt:'Onde está meu pacote agora? Pode verificar?',zh:'那我的包裹现在到哪了？能给我查一下吗？'}},
    // === 5. 时效：工作日/加急 ===
    {kw:['工作日','days','tage','días','jours','giorni','dias','到货','arrive'],zh:'这个时间有点长，能加急吗？',orig:{en:'That\'s a bit long, can it be expedited?',de:'Das ist etwas lang, kann es beschleunigt werden?',ja:'少し長いですね。急ぐことはできますか？',es:'Es un poco largo, ¿se puede acelerar?',fr:'C\'est un peu long, peut-on accélérer ?',it:'È un po\' lungo, si può accelerare?',pt:'É um pouco longo, pode ser acelerado?',zh:'这个时间有点长，能加急吗？'}},
    // === 6. 订单号查询 ===
    {kw:['订单号','order number','订单编号','bestellnummer','número de pedido','numéro de commande','numero d\'ordine','número do pedido'],zh:'麻烦把订单号发我一下，我记一下方便查询。',orig:{en:'Could you send me the order number so I can keep it for reference?',de:'Könnten Sie mir die Bestellnummer schicken, damit ich sie notieren kann?',ja:'注文番号を教えていただけますか？メモしておきます。',es:'¿Puede enviarme el número de pedido para tenerlo guardado?',fr:'Pouvez-vous m\'envoyer le numéro de commande pour référence ?',it:'Puoi inviarmi il numero d\'ordine per riferimento?',pt:'Pode me enviar o número do pedido para eu anotar?',zh:'麻烦把订单号发我一下，我记一下方便查询。'}},
    // === 7. 产品规格：颜色 ===
    {kw:['颜色','color','colour','farbe','色','couleur','colore','cor'],zh:'这个颜色和图片上看起来不太一样，有色差吗？',orig:{en:'The color seems different from the picture, is there a color difference?',de:'Die Farbe scheint anders als im Bild zu sein, gibt es einen Farbunterschied?',ja:'写真と色が違う気がします。色味は違いますか？',es:'El color parece diferente de la foto, ¿hay diferencia de color?',fr:'La couleur semble différente de la photo, y a-t-il une différence ?',it:'Il colore sembra diverso dalla foto, c\'è differenza di colore?',pt:'A cor parece diferente da foto, há diferença de cor?',zh:'这个颜色和图片上看起来不太一样，有色差吗？'}},
    // === 8. 产品规格：尺寸 ===
    {kw:['尺寸','size','größe','サイズ','tamaño','taille','taglia','tamanho'],zh:'尺码有偏小或偏大吗？我按平时穿的买还是大一码？',orig:{en:'Does the size run small or large? Should I order my usual size or one size up?',de:'Fällt die Größe klein oder groß aus? Sollte ich meine übliche Größe oder eine Nummer größer wählen?',ja:'サイズは小さめですか？普段通りでいいですか、それとも大きめがいいですか？',es:'¿La talla es pequeña o grande? ¿Pido mi talla habitual o una más?',fr:'La taille taille petit ou grand ? Je prends ma taille habituelle ou une au-dessus ?',it:'La taglia va piccola o grande? Prendo la solita o una più grande?',pt:'O tamanho serve pequeno ou grande? Peço o habitual ou um maior?',zh:'尺码有偏小或偏大吗？我按平时穿的买还是大一码？'}},
    // === 9. 产品规格：材质 ===
    {kw:['材质','material','stoff','素材','material','matériau','materiale'],zh:'这个材质是什么成分？会过敏吗？',orig:{en:'What\'s the material composition? Will it cause allergies?',de:'Wie ist die Materialzusammensetzung? Kann es Allergien auslösen?',ja:'素材は何ですか？アレルギーになりますか？',es:'¿De qué material es? ¿Puede causar alergias?',fr:'C\'est quel matériau ? Ça peut causer des allergies ?',it:'Di che materiale è? Può causare allergie?',pt:'Qual é o material? Pode causar alergias?',zh:'这个材质是什么成分？会过敏吗？'}},
    // === 10. 产品规格：重量 ===
    {kw:['重量','weight','gewicht','重さ','peso','poids'],zh:'这个重量是多少？含包装还是净重？',orig:{en:'What\'s the weight? Is that with packaging or net weight?',de:'Wie viel wiegt das? Mit Verpackung oder Nettogewicht?',ja:'重量はどれくらいですか？パッケージ込みですか、正味重量ですか？',es:'¿Cuánto pesa? ¿Incluye el paquete o es peso neto?',fr:'C\'est quel poids ? Emballé ou poids net ?',it:'Quanto pesa? Con imballaggio o peso netto?',pt:'Qual é o peso? Com embalagem ou peso líquido?',zh:'这个重量是多少？含包装还是净重？'}},
    // === 11. 支付安全 ===
    {kw:['支付安全','payment security','secure payment','sichere zahlung','pago seguro','paiement sécurisé','pagamento sicuro'],zh:'用信用卡支付安全吗？你们会保存我的卡号吗？',orig:{en:'Is it safe to pay by credit card? Do you store my card number?',de:'Ist es sicher mit Kreditkarte zu zahlen? Speichern Sie meine Kartennummer?',ja:'クレジットカード決済は安全ですか？カード番号を保存しますか？',es:'¿Es seguro pagar con tarjeta de crédito? ¿Guardan mi número de tarjeta?',fr:'Est-il sûr de payer par carte ? Gardez-vous mon numéro de carte ?',it:'È sicuro pagare con la carta? Conservate il mio numero?',pt:'É seguro pagar com cartão? Vocês guardam meu número do cartão?',zh:'用信用卡支付安全吗？你们会保存我的卡号吗？'}},
    // === 12. 支付方式 ===
    {kw:['支付方式','payment method','付款方式','zahlungsart','forma de pago','mode de paiement','metodo di pagamento','forma de pagamento'],zh:'你们支持哪些支付方式？可以用PayPal吗？',orig:{en:'What payment methods do you support? Can I use PayPal?',de:'Welche Zahlungsmethoden unterstützen Sie? Kann ich PayPal verwenden?',ja:'対応している支払い方法は何ですか？PayPalは使えますか？',es:'¿Qué métodos de pago aceptan? ¿Puedo usar PayPal?',fr:'Quels moyens de paiement acceptez-vous ? Je peux utiliser PayPal ?',it:'Quali metodi di pagamento accettate? Posso usare PayPal?',pt:'Quais formas de pagamento vocês aceitam? Posso usar PayPal?',zh:'你们支持哪些支付方式？可以用PayPal吗？'}},
    // === 13. 关税费用 ===
    {kw:['关税','customs','duty','zoll','関税','aduana','douane','dogana','alfândega'],zh:'这个产品进口到我们国家需要交关税吗？大概多少？',orig:{en:'Will I need to pay customs duty for importing this? Roughly how much?',de:'Muss ich Zollgebühren für die Einfuhr zahlen? Wie viel etwa?',ja:'これを輸入する際に関税はかかりますか？だいたいいくらですか？',es:'¿Tendré que pagar aduanas al importar esto? ¿Más o menos cuánto?',fr:'Devrai-je payer des droits de douane pour l\'import ? Combien environ ?',it:'Devo pagare dazi doganali per importarlo? Quanto circa?',pt:'Preciso pagar alfândega para importar? Quanto mais ou menos?',zh:'这个产品进口到我们国家需要交关税吗？大概多少？'}},
    // === 14. 税费 ===
    {kw:['含税','税费','tax','steuer','税金','impuesto','impôt','imposta','imposto'],zh:'价格里含税吗？还是结账时再加？',orig:{en:'Does the price include tax, or is it added at checkout?',de:'Ist der Preis inklusive Steuer, oder wird sie an der Kasse hinzugefügt?',ja:'価格は税込ですか？それとも精算時に追加されますか？',es:'¿El precio incluye impuestos o se añaden al pagar?',fr:'Le prix inclut-il les taxes ou sont-elles ajoutées au paiement ?',it:'Il prezzo include le tasse o si aggiungono al checkout?',pt:'O preço inclui impostos ou são adicionados no checkout?',zh:'价格里含税吗？还是结账时再加？'}},
    // === 15. 会员权益 ===
    {kw:['会员','member','mitglied','メンバー','miembro','membre','vip'],zh:'会员有什么专属权益吗？积分可以抵现吗？',orig:{en:'What exclusive benefits do members get? Can points be used as cash?',de:'Welche exklusiven Vorteile haben Mitglieder? Können Punkte als Geld verwendet werden?',ja:'会員の特典は何ですか？ポイントは現金として使えますか？',es:'¿Qué beneficios exclusivos tienen los miembros? ¿Los puntos se pueden usar como dinero?',fr:'Quels avantages exclusifs pour les membres ? Les points font-ils office d\'argent ?',it:'Quali vantaggi esclusivi per i membri? I punti si usano come soldi?',pt:'Quais benefícios exclusivos os membros têm? Pontos viram dinheiro?',zh:'会员有什么专属权益吗？积分可以抵现吗？'}},
    // === 16. 积分 ===
    {kw:['积分','points','punkte','ポイント','puntos','punti','pontos'],zh:'我现在的积分有多少？多久会过期？',orig:{en:'How many points do I have now? When do they expire?',de:'Wie viele Punkte habe ich jetzt? Wann verfallen sie?',ja:'現在のポイントはどれくらいですか？いつ失効しますか？',es:'¿Cuántos puntos tengo ahora? ¿Cuándo caducan?',fr:'Combien de points ai-je ? Quand expirent-ils ?',it:'Quanti punti ho ora? Quando scadono?',pt:'Quantos pontos eu tenho? Quando expiram?',zh:'我现在的积分有多少？多久会过期？'}},
    // === 17. 促销活动 ===
    {kw:['促销','promotion','sale','aktions','セール','promoción','promotion','promoção','优惠活动'],zh:'现在有什么促销活动吗？能再优惠一点吗？',orig:{en:'Are there any promotions now? Can you give me a better discount?',de:'Gibt es gerade Aktionen? Können Sie mir einen besseren Rabatt geben?',ja:'今どんなセールがありますか？もう少し安くなりませんか？',es:'¿Hay alguna promoción ahora? ¿Pueden darme un mejor descuento?',fr:'Y a-t-il des promotions ? Pouvez-vous faire un meilleur prix ?',it:'Ci sono promozioni ora? Puoi farmi un prezzo migliore?',pt:'Há alguma promoção agora? Pode me dar um desconto melhor?',zh:'现在有什么促销活动吗？能再优惠一点吗？'}},
    // === 18. 优惠券 ===
    {kw:['优惠券','coupon','gutschein','クーポン','cupón','coupon','cupom','折扣券'],zh:'我有一张优惠券还没用，能叠加这次订单吗？',orig:{en:'I have an unused coupon, can I stack it on this order?',de:'Ich habe einen ungenutzten Gutschein, kann ich ihn für diese Bestellung verwenden?',ja:'未使用のクーポンがあるのですが、この注文に使えますか？',es:'Tengo un cupón sin usar, ¿puedo combinarlo con este pedido?',fr:'J\'ai un coupon inutilisé, je peux l\'utiliser sur cette commande ?',it:'Ho un coupon non usato, posso usarlo su questo ordine?',pt:'Tenho um cupom não usado, posso usar neste pedido?',zh:'我有一张优惠券还没用，能叠加这次订单吗？'}},
    // === 19. 售后退换 ===
    {kw:['售后','退换','replace','austausch','交換','reemplazo','remplacement'],zh:'退换货的话邮费谁承担？',orig:{en:'Who pays the shipping for the return?',de:'Wer trägt die Versandkosten für die Rücksendung?',ja:'返品の送料は誰が負担しますか？',es:'¿Quién paga el envío de la devolución?',fr:'Qui paie les frais d\'expédition pour le retour ?',it:'Chi paga la spedizione per il reso?',pt:'Quem paga o frete para a devolução?',zh:'退换货的话邮费谁承担？'}},
    // === 20. 保修服务 ===
    {kw:['保修','warranty','garantie','保証','garantía','garanzia','garantia','质保'],zh:'保修期内如果坏了怎么申请维修？',orig:{en:'How do I claim repair within the warranty?',de:'Wie beantrage ich eine Reparatur innerhalb der Garantie?',ja:'保証期間内の修理はどう申請しますか？',es:'¿Cómo solicito reparación dentro de la garantía?',fr:'Comment demander une réparation dans la garantie ?',it:'Come richiedo una riparazione in garanzia?',pt:'Como solicito reparo na garantia?',zh:'保修期内如果坏了怎么申请维修？'}},
    // === 21. 发票 ===
    {kw:['发票','invoice','rechnung','領収書','factura','fattura','nota fiscal'],zh:'可以开具发票吗？抬头写公司还是个人？',orig:{en:'Can you issue an invoice? Should it be under a company or individual?',de:'Können Sie eine Rechnung ausstellen? Auf Firma oder Privatperson?',ja:'領収書は発行できますか？会社名ですか、個人名ですか？',es:'¿Pueden emitir factura? ¿A nombre de empresa o particular?',fr:'Pouvez-vous émettre une facture ? Société ou particulier ?',it:'Potete emettere fattura? Azienda o privato?',pt:'Podem emitir nota fiscal? Empresa ou pessoa física?',zh:'可以开具发票吗？抬头写公司还是个人？'}},
    // === 22. 咨询库存（通用，靠后）===
    {kw:['咨询','了解','详情','information','details'],zh:'这个产品有现货吗？多久能发货？',orig:{en:'Is this in stock? How soon can it ship?',de:'Ist das auf Lager? Wie bald kann es versendet werden?',ja:'在庫ありますか？いつ発送できますか？',es:'¿Hay stock? ¿Cuándo se puede enviar?',fr:'Est-ce en stock ? Quand peut-on expédier ?',it:'È in stock? Quando può essere spedito?',pt:'Tem estoque? Quando pode ser enviado?',zh:'这个产品有现货吗？多久能发货？'}},
    // === 23. 投诉/人工转接 ===
    {kw:['投诉','人工','转接','complaint','human','escalat'],zh:'我要和你们主管说话，这个问题必须解决。',orig:{en:'I want to speak to your supervisor, this must be resolved.',de:'Ich möchte mit Ihrem Vorgesetzten sprechen, das muss gelöst werden.',ja:'上司と話したいです。この問題は解決しなければなりません。',es:'Quiero hablar con su supervisor, esto debe resolverse.',fr:'Je veux parler à votre superviseur, cela doit être résolu.',it:'Voglio parlare con il tuo supervisore, questo deve essere risolto.',pt:'Quero falar com seu supervisor, isso deve ser resolvido.',zh:'我要和你们主管说话，这个问题必须解决。'}},
    // === 24. 情绪：满意（靠后，避免与业务规则抢匹配）===
    {kw:['满意','感谢配合','谢谢配合','thank you for','thanks for','vielen dank','ありがとう','gracias','merci','grazie','obrigado'],zh:'太好了，非常感谢你的耐心解答，我很满意！',orig:{en:'That\'s great, thank you so much for your patience, I\'m very satisfied!',de:'Das ist toll, vielen Dank für Ihre Geduld, ich bin sehr zufrieden!',ja:'それはよかったです。丁寧な対応ありがとうございます、とても満足しています！',es:'¡Qué bien, muchas gracias por su paciencia, estoy muy satisfecho!',fr:'C\'est super, merci beaucoup pour votre patience, je suis très satisfait !',it:'Ottimo, grazie mille per la pazienza, sono molto soddisfatto!',pt:'Que ótimo, muito obrigado pela paciência, estou muito satisfeito!',zh:'太好了，非常感谢你的耐心解答，我很满意！'}},
    // === 25. 情绪：不满 ===
    {kw:['差评','失望','disappointed','enttäuscht','がっかり','decepcionado','délçu','deluso'],zh:'我对这次服务真的很失望，问题一直没解决。',orig:{en:'I\'m really disappointed with this service, the problem still isn\'t resolved.',de:'Ich bin wirklich enttäuscht von diesem Service, das Problem ist noch nicht gelöst.',ja:'今回のサービスには本当にがっかりしています。問題がまだ解決されていません。',es:'Estoy muy decepcionado con el servicio, el problema sigue sin resolverse.',fr:'Je suis vraiment déçu du service, le problème n\'est toujours pas résolu.',it:'Sono molto deluso dal servizio, il problema non è ancora risolto.',pt:'Estou muito decepcionado com o serviço, o problema ainda não foi resolvido.',zh:'我对这次服务真的很失望，问题一直没解决。'}},
    // === 26. 情绪：焦虑 ===
    {kw:['着急','焦虑','anxious','besorgt','心配','preocupado','inquiet','preoccupato','担心'],zh:'我真的很着急，能不能帮我尽快处理一下？',orig:{en:'I\'m really anxious, can you please help me handle this as soon as possible?',de:'Ich bin wirklich besorgt, können Sie mir bitte so schnell wie möglich helfen?',ja:'本当に急いでいます。できるだけ早く対応していただけますか？',es:'Estoy muy preocupado, ¿puede ayudarme a resolverlo lo antes posible?',fr:'Je suis très inquiet, pouvez-vous traiter ça le plus vite possible ?',it:'Sono molto preoccupato, puoi risolverlo il prima possibile?',pt:'Estou muito preocupado, pode resolver o mais rápido possível?',zh:'我真的很着急，能不能帮我尽快处理一下？'}},
    // === 27. 结束对话：再见 ===
    {kw:['再见','bye','tschüss','さようなら','adiós','au revoir','arrivederci','tchau','拜拜'],zh:'好的，那就这样吧，再见，谢谢你的帮助。',orig:{en:'OK then, that\'s all for now. Goodbye and thanks for your help.',de:'Gut, das war\'s für jetzt. Auf Wiedersehen und danke für Ihre Hilfe.',ja:'では、今回はこれで終わります。さようなら、ありがとうございました。',es:'De acuerdo, eso es todo por ahora. Adiós y gracias por su ayuda.',fr:'D\'accord, c\'est tout pour maintenant. Au revoir et merci pour votre aide.',it:'Ok, è tutto per ora. Arrivederci e grazie per l\'aiuto.',pt:'Ok, é só por enquanto. Tchau e obrigado pela ajuda.',zh:'好的，那就这样吧，再见，谢谢你的帮助。'}},
    // === 28. 结束对话：无问题 ===
    {kw:['没事了','结束','done','finished','erledigt','完了','hecho','terminé','fatto','feito','没问题了'],zh:'好的，没问题了，感谢你的服务，我先下线了。',orig:{en:'OK, no more questions, thanks for your service, I\'ll log off now.',de:'Gut, keine Fragen mehr, danke für Ihren Service, ich verabschiede mich jetzt.',ja:'わかりました、もう大丈夫です。ご対応ありがとうございました。',es:'De acuerdo, no tengo más preguntas, gracias por su servicio.',fr:'D\'accord, plus de questions, merci pour votre service, je me déconnecte.',it:'Ok, nessun\'altra domanda, grazie per il servizio.',pt:'Ok, sem mais perguntas, obrigado pelo serviço.',zh:'好的，没问题了，感谢你的服务，我先下线了。'}},
    // === 29. 客服说"处理中/稍等"：客户追问处理进度 ===
    {kw:['处理中','稍等','请稍','正在','processing','please wait','moment','warten','処理中','お待ち','procesando','un moment','elaborazione','processando'],zh:'好的，那我大概需要等多久？处理完会通知我吗？',orig:{en:'OK, about how long do I need to wait? Will I be notified when it\'s done?',de:'Gut, wie lange muss ich etwa warten? Wird mich jemand benachrichtigen?',ja:'わかりました。大体どのくらい待てばいいですか？完了したら連絡もらえますか？',es:'De acuerdo, ¿cuánto tiempo tengo que esperar? ¿Me avisarán cuando esté listo?',fr:'D\'accord, combien de temps dois-je attendre ? Serez-vous m\'avertir ?',it:'Ok, quanto devo aspettare? Mi avviserete a fine lavorazione?',pt:'Ok, quanto tempo preciso esperar? Vão me avisar quando pronto?',zh:'好的，那我大概需要等多久？处理完会通知我吗？'}},
    // === 30. 客服说"抱歉/道歉"：客户表达不满或要求补偿 ===
    {kw:['抱歉','道歉','对不起','sorry','apologize','entschuldigung','申し訳','disculpa','désolé','spiacente','desculpa'],zh:'光道歉没用，我需要一个具体的解决方案和时间表。',orig:{en:'Sorry isn\'t enough, I need a specific solution and timeline.',de:'Entschuldigung reicht nicht, ich brauche eine konkrete Lösung und einen Zeitplan.',ja:'謝罪だけでは困ります。具体的な解決策と期限を教えてください。',es:'Una disculpa no es suficiente, necesito una solución concreta y un plazo.',fr:'Les excuses ne suffisent pas, je veux une solution concrète et un délai.',it:'Le scuse non bastano, voglio una soluzione concreta e una tempistica.',pt:'Desculpas não bastam, preciso de uma solução concreta e prazo.',zh:'光道歉没用，我需要一个具体的解决方案和时间表。'}},
    // === 31. 客服说"已提交/已申请"：客户追问进度 ===
    {kw:['已提交','已申请','已反馈','submitted','applied','requested','eingereicht','提出','enviado','soumis','inoltrato','enviado'],zh:'提交后大概多久能有结果？有没有工单号我可以查？',orig:{en:'How long until there\'s a result? Is there a ticket number I can check?',de:'Wie lange bis es ein Ergebnis gibt? Gibt es eine Ticketnummer?',ja:'提出後どのくらいで結果が出ますか？確認できる番号はありますか？',es:'¿Cuánto tardará? ¿Hay un número de ticket para consultar?',fr:'Combien de temps avant un résultat ? Y a-t-il un numéro de ticket ?',it:'Quanto ci vorrà? C\'è un numero di ticket?',pt:'Quanto tempo até resultado? Tem número de protocolo?',zh:'提交后大概多久能有结果？有没有工单号我可以查？'}},
    // === 32. 客服说"已发货/已寄出"：客户追问物流详情 ===
    {kw:['已发货','已寄出','已发出','shipped','dispatched','versendet','発送済','enviado','expédié','spedito','enviado'],zh:'好的，那物流单号是多少？预计几天能到？',orig:{en:'OK, what\'s the tracking number? How many days until delivery?',de:'Gut, wie lautet die Sendungsnummer? Wie viele Tage bis Lieferung?',ja:'わかりました。追跡番号は何ですか？到着まで何日くらいですか？',es:'Bien, ¿cuál es el número de seguimiento? ¿Cuántos días para la entrega?',fr:'Bon, c\'est quoi le numéro de suivi ? Combien de jours pour la livraison ?',it:'Ok, qual è il numero di tracciamento? Quanti giorni per la consegna?',pt:'Ok, qual o número de rastreio? Quantos dias para entregar?',zh:'好的，那物流单号是多少？预计几天能到？'}},
    // === 33. 客服说"已退款/已到账"：客户确认收款 ===
    {kw:['已退款','已到账','已退回','refunded','returned','erstattet','返金済','reembolsado','remboursé','rimpatriato','reembolsado'],zh:'好的，我查一下账户，如果没有到账再联系你。',orig:{en:'OK, let me check my account. I\'ll contact you if it hasn\'t arrived.',de:'Gut, ich prüfe mein Konto. Ich melde mich, falls es nicht ankommt.',ja:'わかりました。口座を確認します。入っていなかったらまた連絡します。',es:'De acuerdo, revisaré mi cuenta. Si no llega, le aviso.',fr:'D\'accord, je vérifie mon compte. Je vous contacte si ça n\'arrive pas.',it:'Ok, controllo il conto. Ti contatto se non arriva.',pt:'Ok, vou verificar a conta. Se não chegar, aviso.',zh:'好的，我查一下账户，如果没有到账再联系你。'}},
    // === 34. 客服说"建议/推荐"：客户询问更多细节 ===
    {kw:['建议','推荐','recommend','suggest','empfehle','おすすめ','recomiendo','recommande','consiglio','recomendo'],zh:'你推荐的这个方案和之前的有什么区别？价格一样吗？',orig:{en:'How is this recommended option different from the previous one? Same price?',de:'Wie unterscheidet sich diese Empfehlung von der vorherigen? Gleicher Preis?',ja:'おすすめのプランは前のと何が違いますか？価格は同じですか？',es:'¿En qué se diferencia esta opción recomendada de la anterior? ¿Mismo precio?',fr:'Comment cette option recommandée diffère-t-elle ? Même prix ?',it:'Come differisce questa opzione consigliata? Stesso prezzo?',pt:'Como essa opção recomendada difere? Mesmo preço?',zh:'你推荐的这个方案和之前的有什么区别？价格一样吗？'}},
    // === 35. 客服说"确认/核实"：客户等待结果 ===
    {kw:['确认','核实','核实中','confirm','verify','bestätigen','確認','confirmar','vérifier','verificare','verificar'],zh:'好的，那核实需要多长时间？结果出来告诉我一下。',orig:{en:'OK, how long will verification take? Let me know when results are ready.',de:'Gut, wie lange dauert die Verifizierung? Geben Sie mir Bescheid, wenn es Ergebnisse gibt.',ja:'わかりました。確認にどのくらいかかりますか？結果が出たら教えてください。',es:'De acuerdo, ¿cuánto tarda la verificación? Avíseme cuando tenga resultados.',fr:'D\'accord, combien de temps pour la vérification ? Tenez-moi au courant.',it:'Ok, quanto ci vuole per la verifica? Avvisami quando pronto.',pt:'Ok, quanto tempo para verificação? Me avise quando pronto.',zh:'好的，那核实需要多长时间？结果出来告诉我一下。'}},
  ];

  for(const rule of rules){
    if(rule.kw.some(k=>replyText.includes(k))){
      const origMap=rule.orig;
      const orig=origMap[lang]||origMap.en||rule.zh;
      return {orig,zh:rule.zh};
    }
  }

  // 兜底：5条不同的自然回复，随机选取，避免千篇一律
  const fallbackPool={
    en:[
      {orig:'Got it, thanks for the update. I\'ll wait to hear back from you.',zh:'好的，谢谢您的回复，我等您的消息。'},
      {orig:'Thanks, that makes sense. Let me know if anything changes.',zh:'明白了，那我先等您通知，有变化再告诉我。'},
      {orig:'Understood, I appreciate your help with this.',zh:'好的，感谢您协助处理这件事。'},
      {orig:'OK, I\'ll keep an eye on it. Thanks for looking into it.',zh:'好的，我会留意，麻烦您跟进一下。'},
      {orig:'Alright, thank you. Please keep me posted on the progress.',zh:'好的，谢谢您，请随时告知我进展。'},
    ],
    de:[
      {orig:'Verstanden, danke für die Rückmeldung. Ich warte auf Ihre Nachricht.',zh:'好的，谢谢您的回复，我等您的消息。'},
      {orig:'Danke, das leuchtet ein. Geben Sie mir Bescheid, falls sich etwas ändert.',zh:'明白了，那我先等您通知，有变化再告诉我。'},
      {orig:'Verstanden, ich schätze Ihre Hilfe dabei.',zh:'好的，感谢您协助处理这件事。'},
      {orig:'OK, ich behalte es im Auge. Danke, dass Sie es prüfen.',zh:'好的，我会留意，麻烦您跟进一下。'},
      {orig:'In Ordnung, danke. Bitte halten Sie mich auf dem Laufenden.',zh:'好的，谢谢您，请随时告知我进展。'},
    ],
    ja:[
      {orig:'わかりました、ご返信ありがとうございます。お返事をお待ちしています。',zh:'好的，谢谢您的回复，我等您的消息。'},
      {orig:'ありがとうございます、理解しました。変更があれば教えてください。',zh:'明白了，那我先等您通知，有变化再告诉我。'},
      {orig:'了解しました、ご対応ありがとうございます。',zh:'好的，感谢您协助处理这件事。'},
      {orig:'OK、確認しておきます。ご調査ありがとうございます。',zh:'好的，我会留意，麻烦您跟进一下。'},
      {orig:'わかりました、ありがとうございます。進捗があれば教えてください。',zh:'好的，谢谢您，请随时告知我进展。'},
    ],
    es:[
      {orig:'Entendido, gracias por la respuesta. Esperaré su noticia.',zh:'好的，谢谢您的回复，我等您的消息。'},
      {orig:'Gracias, tiene sentido. Avíseme si hay cambios.',zh:'明白了，那我先等您通知，有变化再告诉我。'},
      {orig:'Comprendido, agradezco su ayuda con esto.',zh:'好的，感谢您协助处理这件事。'},
      {orig:'OK, lo vigilaré. Gracias por revisarlo.',zh:'好的，我会留意，麻烦您跟进一下。'},
      {orig:'De acuerdo, gracias. Manténgame informado del progreso.',zh:'好的，谢谢您，请随时告知我进展。'},
    ],
    fr:[
      {orig:'Compris, merci pour votre réponse. J\'attends de vos nouvelles.',zh:'好的，谢谢您的回复，我等您的消息。'},
      {orig:'Merci, c\'est logique. Tenez-moi au courant si ça change.',zh:'明白了，那我先等您通知，有变化再告诉我。'},
      {orig:'Compris, je vous remercie pour votre aide.',zh:'好的，感谢您协助处理这件事。'},
      {orig:'OK, je vais surveiller. Merci de vérifier.',zh:'好的，我会留意，麻烦您跟进一下。'},
      {orig:'D\'accord, merci. Tenez-moi au courant de l\'avancement.',zh:'好的，谢谢您，请随时告知我进展。'},
    ],
    it:[
      {orig:'Capito, grazie per la risposta. Aspetto sue notizie.',zh:'好的，谢谢您的回复，我等您的消息。'},
      {orig:'Grazie, ha senso. Mi faccia sapere se ci sono novità.',zh:'明白了，那我先等您通知，有变化再告诉我。'},
      {orig:'Capito, grazie per l\'aiuto con questo.',zh:'好的，感谢您协助处理这件事。'},
      {orig:'OK, lo tengo d\'occhio. Grazie per aver controllato.',zh:'好的，我会留意，麻烦您跟进一下。'},
      {orig:'D\'accordo, grazie. Mi tenga aggiornato sui progressi.',zh:'好的，谢谢您，请随时告知我进展。'},
    ],
    pt:[
      {orig:'Entendido, obrigado pela resposta. Fico no aguardo.',zh:'好的，谢谢您的回复，我等您的消息。'},
      {orig:'Obrigado, faz sentido. Me avise se houver mudanças.',zh:'明白了，那我先等您通知，有变化再告诉我。'},
      {orig:'Entendido, obrigado pela ajuda com isso.',zh:'好的，感谢您协助处理这件事。'},
      {orig:'OK, vou ficar de olho. Obrigado por verificar.',zh:'好的，我会留意，麻烦您跟进一下。'},
      {orig:'Certo, obrigado. Me mantenha informado do progresso.',zh:'好的，谢谢您，请随时告知我进展。'},
    ],
    zh:[
      {orig:'好的，谢谢您的回复，我等您的消息。',zh:'好的，谢谢您的回复，我等您的消息。'},
      {orig:'明白了，那我先等您通知，有变化再告诉我。',zh:'明白了，那我先等您通知，有变化再告诉我。'},
      {orig:'好的，感谢您协助处理这件事。',zh:'好的，感谢您协助处理这件事。'},
      {orig:'好的，我会留意，麻烦您跟进一下。',zh:'好的，我会留意，麻烦您跟进一下。'},
      {orig:'好的，谢谢您，请随时告知我进展。',zh:'好的，谢谢您，请随时告知我进展。'},
    ],
  };
  const pool=fallbackPool[lang]||fallbackPool.en;
  return pool[Math.floor(Math.random()*pool.length)];
}

/* ============ Agent 自动回复模式 ============ */
document.getElementById('autoReplySwitch').onclick=function(){
  state.autoReply=!state.autoReply;
  this.classList.toggle('active',state.autoReply);
  this.classList.toggle('inactive',!state.autoReply);
  if(state.autoReply){
    showToast('已开启Agent自动回复模式，客户消息将自动路由至对应Agent处理');
  }else{
    showToast('已关闭Agent自动回复模式');
  }
};

// 客户消息到达后，如果开启自动回复，自动触发AI处理
async function autoReplyIfNeeded(conv,customerMsg){
  if(!state.autoReply)return;
  // 显示"Agent自动处理中"提示
  const flow=document.getElementById('chatFlow');
  const indicator=document.createElement('div');
  indicator.className='ai-suggestion-card loading';
  indicator.style.borderLeft='3px solid #22c55e';
  indicator.innerHTML='<div class="ai-card-header"><span class="ai-card-icon">🤖</span><span class="ai-card-title">Agent 自动处理中</span><span class="ai-card-mode" style="font-size:10px;color:#22c55e;background:#dcfce7;padding:2px 8px;border-radius:6px">自动模式</span></div><div class="ai-card-body"><div style="padding:8px 0;font-size:12px;color:#64748b">正在路由至对应Agent并生成回复...</div></div>';
  flow.appendChild(indicator);
  flow.scrollTop=flow.scrollHeight;

  // 调用后端API
  const params={
    platform:conv.platform,
    lang:conv.customer.code,
    message:customerMsg.text,
    conv_id:conv.id,
    history:(chatHistories[conv.id]||[]).slice(-6).map(m=>({role:m.type==='customer'?'user':'assistant',content:m.text}))
  };
  try{
    const r=await API.chat(params);
    indicator.remove();
    // 如果需要人工转接，显示通知
    if(r.handoff_reason&&r.handoff_reason!==''){
      showHandoffNotification(conv,r);
      // 仍然显示Agent的回复
      const replyText=r.reply_zh||r.reply||'';
      if(replyText){
        chatHistories[conv.id].push({type:'agent',text:replyText,zh:replyText,time:DataGen.nowTime(),lang:conv.customer.lang,ai:true,agent:r.agent||'AI',agent_key:(r.agent_chain||[])[0]||'consultation'});
        renderChatFlow(conv);
      }
    }else{
      // 正常回复，直接加入聊天流
      const replyText=r.reply_zh||r.reply||'';
      if(replyText){
        chatHistories[conv.id].push({type:'agent',text:replyText,zh:replyText,time:DataGen.nowTime(),lang:conv.customer.lang,ai:true,agent:r.agent||'AI',agent_key:(r.agent_chain||[])[0]||'consultation'});
        renderChatFlow(conv);
      }
    }
  }catch(e){
    indicator.remove();
    console.error('[自动回复] 失败:',e);
  }
}

// 人工转接通知
function showHandoffNotification(conv,r){
  const existing=document.querySelector('.handoff-notification');
  if(existing)existing.remove();
  const notif=document.createElement('div');
  notif.className='handoff-notification';
  const reasonMap={intent_mismatch:'意图不匹配',capability_exceeded:'能力超界',sentiment_escalation:'情感升级',complaint:'投诉升级',retry_exceeded:'重试超限',error_fallback:'异常降级',anti_hallucination:'反幻觉触发'};
  const reason=reasonMap[r.handoff_reason]||r.handoff_reason;
  notif.innerHTML='<div class="handoff-notif-header"><div class="handoff-notif-icon">!</div><div class="handoff-notif-title">人工转接请求</div></div><div class="handoff-notif-body">客户 <b>'+escapeHtml(conv.customer.name)+'</b> 需要人工处理<br>转接原因：'+reason+'<br>已通过短信+邮件通知客服团队</div><div class="handoff-notif-actions"><button class="handoff-notif-btn accept" onclick="this.closest(\'.handoff-notification\').remove();showToast(\'已接手处理\')">立即接手</button><button class="handoff-notif-btn dismiss" onclick="this.closest(\'.handoff-notification\').remove()">稍后处理</button></div>';
  document.body.appendChild(notif);
  // 10秒后自动消失
  setTimeout(()=>{if(notif.parentElement)notif.remove()},10000);
}

/* ============ Agent 自动回复模式 ============ */
/* ============ 模式切换 ============ */
document.getElementById('modeSwitch').onclick=async ()=>{
  showToast('正在重新检测后端...');
  await updateMode();
};

async function updateMode(){
  const ok=await API.probeHealth();
  const dot=document.getElementById('modeDot');
  const lbl=document.getElementById('modeLabel');
  if(ok){
    dot.className='mode-dot online';
    lbl.textContent=AppConfig.modeLabel;
    showToast('已连接后端：'+AppConfig.modeLabel);
  }else{
    dot.className='mode-dot offline';
    lbl.textContent='离线模式';
    showToast('未检测到后端，已切换至离线模式');
  }
}

/* ============ Toast ============ */
let toastTimer;
function showToast(msg){
  const t=document.getElementById('toast');
  t.textContent=msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>t.classList.remove('show'),2200);
}

/* ============ 初始化 ============ */
// 为所有平台预生成未读消息数（用于平台切换红点显示）
window._platformUnread={};
function initPlatformUnread(){
  const platforms=['amazon','aliexpress','ebay','shopify','rakuten','email'];
  platforms.forEach(pf=>{
    // 每个平台生成随机未读数（3-25条），体现多平台多流量场景
    window._platformUnread[pf]=Math.floor(Math.random()*23)+3;
  });
  // 当前平台未读数从实际会话中统计
  const currentUnread=state.conversations.reduce((s,c)=>s+(c.unread||0),0);
  window._platformUnread[state.platform]=currentUnread;
}
(async function init(){
  state.conversations=genConversations(state.platform);
  initPlatformUnread();
  await updateMode();
  refreshStats(state.platform);
  renderConvList();
  if(state.conversations.length>0)selectConv(state.conversations[0].id);
})();
