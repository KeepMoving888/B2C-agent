/**
 * 数据池
 * 多语言客户、消息模板、客服回复、AI建议回复
 * 离线模式下作为规则引擎的数据源；在线模式下仅用于生成示例会话列表
 * 场景覆盖跨境电商10大业务类目，每语言15+条，确保企业级数据密度
 */
window.DataGen = {
  platforms:{
    amazon:{name:'Amazon',color:'#ff9900',icon:'A'},
    aliexpress:{name:'速卖通',color:'#e62e04',icon:'速'},
    ebay:{name:'eBay',color:'#e53238',icon:'E'},
    shopify:{name:'独立站',color:'#95bf47',icon:'独'},
    rakuten:{name:'乐天',color:'#bf0000',icon:'乐'},
    email:{name:'邮件',color:'#4285f4',icon:'@'}
  },
  customers:[
    {name:'Marcus Brennan',country:'美国',lang:'English',code:'en',flag:'🇺🇸',avatar:'#2563eb'},
    {name:'Yuki Tanaka',country:'日本',lang:'日本語',code:'ja',flag:'🇯🇵',avatar:'#ef4444'},
    {name:'Lukas Hoffmann',country:'德国',lang:'Deutsch',code:'de',flag:'🇩🇪',avatar:'#f59e0b'},
    {name:'Mateo Fernández',country:'西班牙',lang:'Español',code:'es',flag:'🇪🇸',avatar:'#8b5cf6'},
    {name:'Camille Laurent',country:'法国',lang:'Français',code:'fr',flag:'🇫🇷',avatar:'#ec4899'},
    {name:'Darren Tan',country:'新加坡',lang:'English',code:'en',flag:'🇸🇬',avatar:'#06b6d4'},
    {name:'Haruka Mori',country:'日本',lang:'日本語',code:'ja',flag:'🇯🇵',avatar:'#10b981'},
    {name:'Felix Wagner',country:'德国',lang:'Deutsch',code:'de',flag:'🇩🇪',avatar:'#6366f1'},
    {name:'Diego Torres',country:'西班牙',lang:'Español',code:'es',flag:'🇪🇸',avatar:'#f97316'},
    {name:'Olivia Pemberton',country:'英国',lang:'English',code:'en',flag:'🇬🇧',avatar:'#0ea5e9'},
    {name:'Alessandro Romano',country:'意大利',lang:'Italiano',code:'it',flag:'🇮🇹',avatar:'#84cc16'},
    {name:'Nikolaj Pedersen',country:'丹麦',lang:'English',code:'en',flag:'🇩🇰',avatar:'#a855f7'},
    {name:'Kaito Sugiyama',country:'日本',lang:'日本語',code:'ja',flag:'🇯🇵',avatar:'#14b8a6'},
    {name:'Beatriz Almeida',country:'巴西',lang:'Português',code:'pt',flag:'🇧🇷',avatar:'#dc2626'},
    {name:'Min-jun Park',country:'韩国',lang:'English',code:'en',flag:'🇰🇷',avatar:'#3b82f6'},
    {name:'Annika Brandt',country:'德国',lang:'Deutsch',code:'de',flag:'🇩🇪',avatar:'#d946ef'},
    {name:'Liam O\'Connor',country:'澳大利亚',lang:'English',code:'en',flag:'🇦🇺',avatar:'#0891b2'},
    {name:'Chloé Moreau',country:'加拿大',lang:'English',code:'en',flag:'🇨🇦',avatar:'#7c3aed'},
    {name:'Rafael Costa',country:'葡萄牙',lang:'Português',code:'pt',flag:'🇵🇹',avatar:'#059669'},
    {name:'Stefan Novák',country:'捷克',lang:'English',code:'en',flag:'🇨🇿',avatar:'#db2777'},
    {name:'Mei Ling Chen',country:'马来西亚',lang:'English',code:'en',flag:'🇲🇾',avatar:'#9333ea'},
    {name:'Tobias Lindqvist',country:'瑞典',lang:'English',code:'en',flag:'🇸🇪',avatar:'#0d9488'},
    {name:'Sofia Ricci',country:'意大利',lang:'Italiano',code:'it',flag:'🇮🇹',avatar:'#e11d48'},
    {name:'Henrik Olsen',country:'挪威',lang:'English',code:'en',flag:'🇳🇴',avatar:'#7c2d12'},
    {name:'Priya Sharma',country:'印度',lang:'English',code:'en',flag:'🇮🇳',avatar:'#be123c'},
    {name:'Jasper de Vries',country:'荷兰',lang:'English',code:'en',flag:'🇳🇱',avatar:'#1d4ed8'},
    {name:'Emil Schmidt',country:'瑞士',lang:'Deutsch',code:'de',flag:'🇨🇭',avatar:'#15803d'},
    {name:'Naomi Reyes',country:'菲律宾',lang:'English',code:'en',flag:'🇵🇭',avatar:'#a16207'},
    {name:'Daniel Whitmore',country:'新西兰',lang:'English',code:'en',flag:'🇳🇿',avatar:'#4338ca'},
    {name:'Ingrid Berg',country:'芬兰',lang:'English',code:'en',flag:'🇫🇮',avatar:'#b45309'}
  ],
  products:[
    '无线蓝牙耳机 Pro','智能手表 Series 7','便携充电宝 20000mAh','4K高清摄像头','人体工学办公椅',
    '陶瓷保温杯 500ml','LED护眼台灯','降噪头戴耳机','机械键盘 RGB','超薄笔记本电脑支架',
    '空气净化器','扫地机器人','电动牙刷套装','智能门锁','投影仪 4K','降噪睡眠耳塞'
  ],
  /* 会话消息池：10大场景×7语言，每语言15+条，覆盖跨境电商真实业务全貌 */
  customerMsgs:{
    en:[
      // CarPlay商品规格咨询
      'Hi, does this wireless CarPlay adapter support iPhone 15 Pro Max?',
      'What\'s the difference between the CarPlay AI Box Pro and the standard version?',
      'Does this CarPlay dashboard camera support 4K recording and night vision?',
      'Can this CarPlay head unit fit my 2019 Toyota Corolla? I need the exact dimensions.',
      // 库存与发货时效
      'Is the black CarPlay AI Box still in stock? I need it before Christmas.',
      'How long does shipping take to Australia for the CarPlay adapter?',
      // 物流追踪
      'My CarPlay order tracking hasn\'t updated for 5 days, is my package lost?',
      'The courier says delivered but I was at work, where did they leave my CarPlay box?',
      // 售后退款
      'The CarPlay adapter keeps disconnecting after 2 weeks, I want a replacement.',
      'The CarPlay screen has dead pixels, this is clearly a manufacturing defect. Refund please.',
      // 支付问题
      'My credit card was declined for the CarPlay order but I\'m sure I have enough balance.',
      'Do you accept PayPal for the CarPlay AI Box Pro purchase?',
      // 关税清关
      'Will I be charged customs duty for a $199 CarPlay order to Germany?',
      'My CarPlay package is stuck at customs, they\'re asking for a product invoice.',
      // 会员促销
      'I\'m a Gold member, do I get free express shipping on this CarPlay order?',
      'I have a 15% off coupon but it\'s not working for the CarPlay AI Box.',
      // 合规隐私
      'I want to delete my account and all personal data. How do I do that under GDPR?',
      'Is my payment information stored on your servers? I\'m concerned about security.',
      // 投诉升级
      'This is my third message about the defective CarPlay unit and nobody helped me!',
      // 复购咨询
      'I bought a CarPlay adapter last year and loved it. Can I get a discount for a second one?',
      'I\'m a returning customer, do you have any loyalty discount for repeat CarPlay purchases?'
    ],
    ja:[
      'こんにちは、このワイヤレスCarPlayアダプターはiPhone 15 Pro Maxに対応していますか？',
      'CarPlay AI Box Proと標準版の違いは何ですか？',
      'このCarPlayダッシュカメラは4K録画とナイトビジョンに対応していますか？',
      'このCarPlayヘッドユニットは2019年トヨタカローラに適合しますか？',
      'ブラックのCarPlay AI Boxはまだ在庫ありますか？クリスマスまでに届きますか？',
      'CarPlayアダプターのオーストラリアへの配送は何日かかりますか？',
      'CarPlayの注文追跡が5日間更新されていません、紛失しましたか？',
      '配達完了になっていますが仕事中でした、CarPlayボックスはどこに？',
      'CarPlayアダプターが2週間で頻繁に切断されます、交換をお願いします。',
      'CarPlay画面にドット抜けがあります、明らかに製造不良です。返金してください。',
      'CarPlay注文でクレジットカードが拒否されましたが残高は十分あります。',
      'CarPlay AI Box Proの購入にPayPalは使えますか？',
      'ドイツへ199ドルのCarPlay注文で関税がかかりますか？',
      'CarPlayの荷物が税関で止まっています、製品の請求書を求められています。',
      'ゴールド会員ですが、このCarPlay注文で無料速達配送はありますか？',
      '15%オフのクーポンがありますがCarPlay AI Boxに使えません。',
      'アカウントとすべての個人データを削除したいです。GDPRに基づきどうすればいいですか？',
      '私の決済情報はサーバーに保存されていますか？セキュリティが心配です。',
      '不良品のCarPlayについて3回目のメッセージですが誰も助けてくれません！',
      '去年CarPlayアダプターを買って気に入りました。2台目に割引はありますか？',
      'リピーターですが、CarPlayの再購入にロイヤリティ割引はありますか？'
    ],
    de:[
      'Hallo, unterstuetzt dieser kabellose CarPlay-Adapter das iPhone 15 Pro Max?',
      'Was ist der Unterschied zwischen dem CarPlay AI Box Pro und der Standardversion?',
      'Unterstuetzt diese CarPlay-Dashcam 4K-Aufnahme und Nachtsicht?',
      'Passt dieses CarPlay-Head-Unit in meinen Toyota Corolla 2019? Ich brauche die genauen Masse.',
      'Ist die schwarze CarPlay AI Box noch auf Lager? Ich brauche sie vor Weihnachten.',
      'Wie lange dauert der Versand nach Australien fuer den CarPlay-Adapter?',
      'Meine CarPlay-Bestellverfolgung hat sich seit 5 Tagen nicht aktualisiert, ist mein Paket verloren?',
      'Der Kurier sagt zugestellt, aber ich war bei der Arbeit, wo haben sie meine CarPlay-Box gelassen?',
      'Der CarPlay-Adapter trennt die Verbindung nach 2 Wochen staendig, ich moechte einen Ersatz.',
      'Der CarPlay-Bildschirm hat tote Pixel, das ist eindeutig ein Herstellungsfehler. Rueckerstattung bitte.',
      'Meine Kreditkarte wurde fuer die CarPlay-Bestellung abgelehnt, aber ich habe sicher genug Guthaben.',
      'Akzeptieren Sie PayPal fuer den Kauf des CarPlay AI Box Pro?',
      'Werden fuer eine 199$ CarPlay-Bestellung nach Deutschland Zollgebuehren faellig?',
      'Mein CarPlay-Paket steckt beim Zoll fest, sie fordern eine Produktrechnung.',
      'Ich bin Gold-Mitglied, bekomme ich kostenlosen Express-Versand fuer diese CarPlay-Bestellung?',
      'Ich habe einen 15% Rabatt-Code, aber er funktioniert nicht fuer die CarPlay AI Box.',
      'Ich moechte mein Konto und alle personenbezogenen Daten loeschen. Wie geht das nach DSGVO/GDPR?',
      'Werden meine Zahlungsdaten auf Ihren Servern gespeichert? Ich mache mir Sorgen um Sicherheit.',
      'Das ist meine dritte Nachricht ueber das defekte CarPlay-Geraet und niemand hat geholfen!',
      'Ich habe letztes Jahr einen CarPlay-Adapter gekauft und war begeistert. Gibt es einen Rabatt fuer ein zweites?',
      'Ich bin Stammkunde, haben Sie einen Treuerabatt fuer wiederholte CarPlay-Kaeufe?'
    ],
    es:[
      'Hola, ¿este auricular Bluetooth soporta el códec aptX? Necesito baja latencia para gaming.',
      '¿Cuánto dura la batería de este reloj inteligente con pantalla siempre encendida?',
      '¿Es la cámara 4K compatible con Mac? Uso Final Cut Pro.',
      '¿Puede decirme las dimensiones exactas de la silla ergonómica? Tengo espacio limitado.',
      '¿El color blanco sigue en stock? Lo necesito antes de Navidad.',
      '¿Cuánto tarda el envío a Australia? Estoy en Sídney.',
      'Mi número de seguimiento no se ha actualizado en 5 días, ¿está perdido mi paquete?',
      'El mensajero dice entregado pero estaba en el trabajo, ¿dónde lo dejaron?',
      'El lado izquierdo del auricular dejó de funcionar después de 2 semanas, quiero un reemplazo.',
      'La correa del reloj se rompió, es claramente un defecto de fabricación. Reembolso por favor.',
      'Mi tarjeta fue rechazada pero seguro que tengo saldo suficiente. ¿Qué pasa?',
      '¿Aceptan PayPal? No quiero ingresar los datos de mi tarjeta otra vez.',
      '¿Se cobrarán aranceles por un pedido de $150 a Alemania?',
      'Mi paquete está atrapado en aduanas, piden una factura del producto. ¿Pueden ayudar?',
      'Soy miembro Gold, ¿tengo envío exprés gratis en este pedido?',
      'Tengo un código de 15% de descuento pero no funciona en el checkout.',
      '¿Cuándo es su próxima rebaja de Black Friday? Quiero comprar 3 artículos.',
      'Quiero eliminar mi cuenta y todos mis datos personales bajo GDPR. ¿Cómo lo hago?',
      '¿Se guarda mi información de pago en sus servidores? Me preocupa la seguridad.',
      '¡Este es mi tercer mensaje y nadie me ha ayudado! ¡Quiero hablar con un gerente!',
      'Hice dos pedidos separados hoy, ¿pueden combinarlos en un solo envío?'
    ],
    fr:[
      'Bonjour, ce casque Bluetooth supporte-t-il le codec aptX ? J\'ai besoin d\'une faible latence pour le gaming.',
      'Quelle est l\'autonomie de cette montre connectée avec affichage permanent ?',
      'Cette caméra 4K est-elle compatible Mac ? J\'utilise Final Cut Pro.',
      'Pouvez-vous me donner les dimensions exactes du siège ergonomique ? J\'ai un espace limité.',
      'La couleur blanche est-elle toujours en stock ? J\'en ai besoin avant Noël.',
      'Combien de temps prend la livraison vers l\'Australie ? Je suis à Sydney.',
      'Mon numéro de suivi n\'a pas été mis à jour depuis 5 jours, mon colis est-il perdu ?',
      'Le livreur indique livré mais j\'étais au travail, où l\'ont-ils laissé ?',
      'Le côté gauche du casque a cessé de fonctionner après 2 semaines, je veux un remplacement.',
      'Le bracelet de la montre est cassé, c\'est clairement un défaut de fabrication. Remboursement svp.',
      'Ma carte a été refusée mais j\'ai assez de solde. Que se passe-t-il ?',
      'Acceptez-vous PayPal ? Je ne veux pas saisir à nouveau mes informations de carte.',
      'Des droits de douane seront-ils facturés pour une commande de 150€ vers l\'Allemagne ?',
      'Mon colis est bloqué à la douane, ils demandent une facture produit. Pouvez-vous aider ?',
      'Je suis membre Gold, ai-je la livraison express gratuite ?',
      'J\'ai un code de 15% de réduction mais il ne fonctionne pas au paiement.',
      'Quand est votre prochain Black Friday ? Je veux acheter 3 articles.',
      'Je veux supprimer mon compte et toutes mes données personnelles (RGPD). Comment faire ?',
      'Mes informations de paiement sont-elles stockées sur vos serveurs ?',
      'C\'est mon troisième message et personne ne m\'a aidé ! Je veux parler à un responsable !',
      'J\'ai passé deux commandes séparées aujourd\'hui, pouvez-vous les combiner ?'
    ],
    it:[
      'Salve, queste cuffie Bluetooth supportano il codec aptX? Ho bisogno di bassa latenza per il gaming.',
      'Quanto dura la batteria di questo smartwatch con display sempre acceso?',
      'Questa fotocamera 4K è compatibile con Mac? Uso Final Cut Pro.',
      'Può dirmi le dimensioni esatte della sedia ergonomica? Ho spazio limitato.',
      'Il colore bianco è ancora disponibile? Mi serve prima di Natale.',
      'Quanto tempo richiede la spedizione in Australia? Sono a Sydney.',
      'Il mio numero di tracciamento non si aggiorna da 5 giorni, il pacco è perso?',
      'Il corriere dice consegnato ma ero al lavoro, dove l\'hanno lasciato?',
      'Il lato sinistro delle cuffie ha smesso di funzionare dopo 2 settimane, voglio una sostituzione.',
      'Il cinturino dell\'orologio si è rotto, è chiaramente un difetto di fabbrica. Rimborso.',
      'La mia carta è stata rifiutata ma ho saldo sufficiente. Cosa succede?',
      'Accettate PayPal? Non voglio inserire di nuovo i dati della carta.',
      'Verranno addebitati dazi doganali per un ordine di 150€ verso la Germania?',
      'Il mio pacco è bloccato alla dogana, richiedono una fattura. Potete aiutare?',
      'Sono membro Gold, ho la spedizione express gratuita?',
      'Ho un codice sconto del 15% ma non funziona al checkout.',
      'Quando sarà il vostro prossimo Black Friday? Voglio comprare 3 articoli.',
      'Voglio eliminare il mio account e tutti i dati personali (GDPR). Come fare?',
      'I miei dati di pagamento sono salvati sui vostri server? Sono preoccupato.',
      'È il mio terzo messaggio e nessuno mi ha aiutato! Voglio parlare con un responsabile!',
      'Ho fatto due ordini separati oggi, potete combinarli in una spedizione?'
    ],
    pt:[
      'Olá, este fone Bluetooth suporta o codec aptX? Preciso de baixa latência para jogos.',
      'Qual a duração da bateria deste smartwatch com display sempre ligado?',
      'Esta câmera 4K é compatível com Mac? Uso Final Cut Pro.',
      'Pode me dizer as dimensões exatas da cadeira ergonômica? Tenho espaço limitado.',
      'A cor branca ainda está em estoque? Preciso antes do Natal.',
      'Quanto tempo leva o envio para a Austrália? Estou em Sydney.',
      'Meu número de rastreamento não atualiza há 5 dias, meu pacote está perdido?',
      'O entregador diz entregue mas eu estava no trabalho, onde deixaram?',
      'O lado esquerdo do fone parou de funcionar após 2 semanas, quero substituição.',
      'A pulseira do relógio quebrou, é claramente defeito de fabricação. Reembolso.',
      'Meu cartão foi recusado mas tenho saldo suficiente. O que acontece?',
      'Aceitam PayPal? Não quero inserir os dados do cartão novamente.',
      'Haverá taxas alfandegárias para um pedido de US$ 150 para a Alemanha?',
      'Meu pacote está preso na alfândega, pedem uma fatura do produto. Podem ajudar?',
      'Sou membro Gold, tenho envio express gratuito?',
      'Tenho um cupom de 15% de desconto mas não funciona no checkout.',
      'Quando será sua próxima Black Friday? Quero comprar 3 itens.',
      'Quero excluir minha conta e todos os dados pessoais (LGPD/GDPR). Como fazer?',
      'Meus dados de pagamento são armazenados nos servidores? Estou preocupado.',
      'Este é meu terceiro pedido e ninguém ajudou! Quero falar com o gerente!',
      'Fiz dois pedidos separados hoje, podem combiná-los em uma remessa?'
    ]
  },
  /* 客服回复模板池：每语言8+条，覆盖10大场景 */
  agentReplies:{
    en:[
      {zh:'您好！这款蓝牙耳机Pro支持aptX Adaptive codec，延迟低至38ms，非常适合游戏使用。同时还支持AAC和SBC codec。',orig:'Hello! This Bluetooth Earphone Pro supports aptX Adaptive codec with latency as low as 38ms, perfect for gaming. It also supports AAC and SBC codecs.'},
      {zh:'您好！智能手表Series 7在始终显示模式下续航约3天，关闭始终显示可达7天。支持磁吸快充，2小时充满。',orig:'Hi! The Smart Watch Series 7 lasts about 3 days with always-on display, and up to 7 days with it disabled. Magnetic fast charging takes 2 hours for a full charge.'},
      {zh:'您好！您的包裹目前在国际运输中，物流更新可能有3-5天延迟。包裹未丢失，预计2-3个工作日内抵达。',orig:'Hello! Your package is currently in international transit, tracking updates may be delayed 3-5 days. It\'s not lost, expected to arrive in 2-3 business days.'},
      {zh:'非常抱歉耳机出现故障。已为您生成换新工单#EX20240715-4471，请提供购买凭证，我们24小时内免费补发。',orig:'We\'re sorry about the earphone issue. Replacement order #EX20240715-4471 has been created. Please provide your proof of purchase, we\'ll ship a replacement within 24 hours at no cost.'},
      {zh:'您好！信用卡被拒通常是发卡行的跨境交易安全拦截。建议：1)联系发卡行确认 2)尝试PayPal 3)使用其他卡片。我们支持多种支付方式。',orig:'Hi! Credit card decline is usually a cross-border fraud prevention block by your bank. Try: 1) Contact your bank 2) Use PayPal 3) Try another card. We support multiple payment methods.'},
      {zh:'您好！德国订单€150以下免税，但需缴纳19%增值税(VAT)。我们提供DDP完税服务，下单时可选，包裹直达无需清关。',orig:'Hello! Orders under €150 to Germany are duty-free, but 19% VAT applies. We offer DDP (Delivered Duty Paid) service at checkout for direct delivery without customs hassle.'},
      {zh:'尊敬的Gold会员，您享受免费Express配送（3-5天达）、专属客服、生日双倍积分等权益。已为您自动应用。',orig:'Dear Gold member, you enjoy free Express shipping (3-5 days), dedicated support, and birthday double points. Already applied to your order.'},
      {zh:'您好！根据GDPR规定，我已为您创建数据删除工单#GDPR20240715-2278，30天内完成删除。删除后您将无法登录账户，此操作不可逆。',orig:'Hello! Per GDPR, we\'ve created data deletion ticket #GDPR20240715-2278. Deletion completes within 30 days. You won\'t be able to log in afterward, this is irreversible.'},
      {zh:'您好！感谢您的咨询。这款产品完全兼容Mac系统，支持4K/60fps输出，附带USB-C数据线。如需了解详细规格参数，请告诉我您具体想了解哪些方面。',orig:'Hello! Thank you for your inquiry. This product is fully compatible with Mac, supporting 4K/60fps output with a USB-C cable included. For detailed specs, please let me know which specific parameters you\'d like to know about.'}
    ],
    ja:[
      {zh:'こんにちは！このBluetoothイヤホンProはaptX Adaptiveコーデック対応、遅延38msでゲームに最適です。',orig:'こんにちは！このBluetoothイヤホンProはaptX Adaptiveコーデックに対応、遅延はわずか38msでゲームに最適です。AAC/SBCも対応。'},
      {zh:'こんにちは！スマートウォッチSeries 7は常時表示オンで約3日、オフで7日持続します。',orig:'こんにちは！スマートウォッチSeries 7は常時表示オンで約3日、オフで7日持続します。マグネット急速充電で2時間充满。'},
      {zh:'お客様の荷物は現在国際輸送中です。追跡更新に3-5日遅延があります。紛失ではありません。',orig:'お客様の荷物は現在国際輸送中です。追跡更新に3-5日遅延が生じる場合があります。紛失ではございません。2-3営業日でお届け予定です。'},
      {zh:'イヤホンの故障につきまして、交換工单#EX20240715-4471を作成しました。24時間以内に無料再送します。',orig:'イヤホンの不具合につき、交換手続き#EX20240715-4471を作成しました。購入証明をご提供ください。24時間以内に無料で再発送いたします。'},
      {zh:'クレジットカード拒否は通常、発行銀行の越境取引セキュリティブロックです。銀行にご確認ください。',orig:'クレジットカードの拒否は通常、発行元銀行の海外取引セキュリティブロックです。銀行にご確認いただくか、PayPalをご利用ください。'},
      {zh:'ドイツへ150ユーロ以下の注文は関税免税ですが、19%のVATがかかります。DDPサービスも選択可能です。',orig:'ドイツ宛150ユーロ以下の注文は関税免除ですが、19%の付加価値税がかかります。DDPサービスもご利用いただけます。'},
      {zh:'ゴールド会員様、無料Express配送、専属カスタマーサポート、誕生日ポイント2倍の特典があります。',orig:'ゴールド会員様には、無料Express配送、専属サポート、誕生日ポイント2倍の特典があります。既に適用済みです。'},
      {zh:'GDPRに基づきデータ削除手配#GDPR20240715-2278を作成しました。30日以内に削除完了します。',orig:'GDPRに基づき、データ削除依頼#GDPR20240715-2278を作成しました。30日以内に削除が完了します。この操作は取り消せません。'},
      {zh:'こんにちは！お問い合わせありがとうございます。この製品はMacと完全に互換性があり、4K/60fps出力に対応、USB-Cケーブル付属です。詳細な仕様は製品ページをご参照ください。',orig:'こんにちは！お問い合わせありがとうございます。この製品はMacと完全な互換性があり、4K/60fps出力に対応、USB-Cケーブル付属です。詳細な仕様は製品ページをご参照ください。'}
    ],
    de:[
      {zh:'Hallo! Dieses Bluetooth-Headset Pro unterstützt aptX Adaptive Codec, Latenz 38ms, ideal für Gaming.',orig:'Hallo! Dieses Bluetooth-Headset Pro unterstützt aptX Adaptive Codec mit 38ms Latenz, ideal für Gaming. AAC/SBC ebenfalls unterstützt.'},
      {zh:'Hallo! Die Smart Watch Series 7 hält mit Always-On 3 Tage, ohne 7 Tage. Magnet-Schnellladung in 2h.',orig:'Hallo! Die Smart Watch Series 7 hält mit Always-On-Display ca. 3 Tage, ohne ca. 7 Tage. Magnet-Schnellladung in 2 Stunden.'},
      {zh:'Ihr Paket ist im internationalen Versand. Tracking-Updates können 3-5 Tage verzögert sein. Nicht verloren.',orig:'Ihr Paket befindet sich im internationalen Versand. Tracking-Updates können 3-5 Tage verzögert sein. Es ist nicht verloren. Ankunft in 2-3 Werktagen.'},
      {zh:'Kopfhörerfehler: Ersatzticket #EX20240715-4471 erstellt. Bitte Kaufbeleg senden, 24h kostenloser Ersatz.',orig:'Kopfhörer-Defekt: Ersatzticket #EX20240715-4471 erstellt. Bitte Kaufbeleg senden, 24h kostenloser Ersatz.'},
      {zh:'Kreditkartenablehnung meist Bank-Sicherheitssperre für Auslandstransaktionen. Bank kontaktieren oder PayPal.',orig:'Kreditkartenablehnung ist meist eine Banksperre für Auslandstransaktionen. Bitte Bank kontaktieren oder PayPal verwenden.'},
      {zh:'Deutschland: Bestellungen unter 150€ sind zollfrei, aber 19% MwSt fällig. DDP-Service verfügbar.',orig:'Deutschland: Bestellungen unter 150€ sind zollfrei, aber 19% MwSt fällig. DDP-Service beim Checkout verfügbar.'},
      {zh:'Gold-Mitglied: Kostenloser Express-Versand, dedizierter Support, Geburtstags-Doppelpunkte. Angewendet.',orig:'Gold-Mitglied: Kostenloser Express-Versand, dedizierter Support, Geburtstags-Doppelpunkte. Bereits angewendet.'},
      {zh:'DSGVO: Datenlöschung-Ticket #GDPR20240715-2278 erstellt. Löschung in 30 Tagen. Unumkehrbar.',orig:'DSGVO: Datenlöschung-Ticket #GDPR20240715-2278 erstellt. Löschung in 30 Tagen abgeschlossen. Unumkehrbar.'},
      {zh:'Hallo! Vielen Dank für Ihre Anfrage. Dieses Produkt ist vollständig mit Mac kompatibel, unterstützt 4K/60fps und wird mit USB-C-Kabel geliefert. Details auf der Produktseite.',orig:'Hallo! Vielen Dank für Ihre Anfrage. Dieses Produkt ist vollständig mit Mac kompatibel, unterstützt 4K/60fps-Ausgabe und wird mit einem USB-C-Kabel geliefert. Details finden Sie auf der Produktseite.'}
    ],
    es:[
      {zh:'Hola! Este auricular Pro soporta aptX Adaptive, latencia 38ms, ideal para gaming.',orig:'Hola! Este auricular Pro soporta códec aptX Adaptive con latencia de 38ms, ideal para gaming. También AAC/SBC.'},
      {zh:'Hola! El Smart Watch Series 7 dura 3 días con always-on, 7 días sin. Carga rápida 2h.',orig:'Hola! El Smart Watch Series 7 dura 3 días con pantalla siempre activa, 7 días sin. Carga magnética en 2h.'},
      {zh:'Su paquete está en tránsito internacional. Actualizaciones pueden tardar 3-5 días. No está perdido.',orig:'Su paquete está en tránsito internacional. Las actualizaciones pueden tardar 3-5 días. No está perdido. Llegará en 2-3 días hábiles.'},
      {zh:'Fallo del auricular: ticket de reemplazo #EX20240715-4471. Envíe comprobante, reposición 24h gratis.',orig:'Fallo del auricular: ticket de reemplazo #EX20240715-4471. Envíe comprobante de compra, reposición gratuita en 24h.'},
      {zh:'Rechazo de tarjeta suele ser bloque de seguridad del banco. Contacte al banco o use PayPal.',orig:'El rechazo de tarjeta suele ser bloque de seguridad del banco para transacciones internacionales. Contacte al banco o use PayPal.'},
      {zh:'Alemania: pedidos bajo 150€ libres de arancel, pero 19% IVA. Servicio DDP disponible.',orig:'Alemania: pedidos bajo 150€ exentos de arancel, pero 19% IVA. Servicio DDP disponible al finalizar compra.'},
      {zh:'Miembro Gold: envío Express gratis, soporte dedicado, puntos dobles en cumpleaños. Aplicado.',orig:'Miembro Gold: envío Express gratis, soporte dedicado, puntos dobles en cumpleaños. Ya aplicado.'},
      {zh:'GDPR: ticket de eliminación #GDPR20240715-2278. Eliminación en 30 días. Irreversible.',orig:'GDPR: ticket de eliminación de datos #GDPR20240715-2278. Eliminación en 30 días. Operación irreversible.'},
      {zh:'Hola! Gracias por su consulta. Este producto es compatible con Mac, soporta 4K/60fps e incluye cable USB-C. Detalles en la página del producto.',orig:'Hola! Gracias por su consulta. Este producto es totalmente compatible con Mac, soporta salida 4K/60fps e incluye cable USB-C. Para detalles, consulte la página del producto.'}
    ]
  },
  /* AI建议回复池：每语言8+条，含RAG引用标记 */
  aiSuggestions:{
    en:[
      'Hello! I\'ve checked your order #AMZ20240715-88392. The Bluetooth Earphone Pro supports aptX Adaptive codec (38ms latency), perfect for gaming. It also supports AAC/SBC. Any other questions?',
      'Hi! The Smart Watch Series 7 lasts 3 days with always-on display, 7 days without. It supports magnetic fast charging (2h full). Compatible with iOS 12+/Android 6+.',
      'I\'ve tracked your package (SF1893726405). It\'s in international transit; tracking updates may delay 3-5 days. Expected delivery in 2-3 business days. Not lost.',
      'I\'m sorry about the earphone issue. I\'ve created replacement ticket #EX20240715-4471. Please provide proof of purchase, we\'ll ship a free replacement within 24 hours.',
      'Credit card declines are usually cross-border fraud prevention by your bank. Try: 1) Contact your bank 2) Use PayPal 3) Try another card. All payments are PCI-DSS encrypted.',
      'For Germany, orders under €150 are duty-free but 19% VAT applies. We offer DDP service at checkout for hassle-free delivery. Customs invoice can be provided if needed.',
      'As a Gold member, you enjoy free Express shipping (3-5 days), dedicated support, and birthday double points. Already applied to your order automatically.',
      'Per GDPR, I\'ve created data deletion ticket #GDPR20240715-2278. All personal data will be deleted within 30 days. This is irreversible. Please confirm to proceed.'
    ],
    ja:[
      'こんにちは！ご注文#AMZ20240715-88392を確認しました。BluetoothイヤホンProはaptX Adaptive対応（遅延38ms）、ゲームに最適です。',
      'スマートウォッチSeries 7は常時表示オンで3日、オフで7日持続します。磁気急速充電2時間で充满。iOS 12+/Android 6+対応。',
      '荷物（SF1893726405）は国際輸送中です。追跡更新に3-5日遅延があります。2-3営業日でお届け予定です。紛失ではありません。',
      'イヤホン不具合につき交換手配#EX20240715-4471を作成しました。購入証明をご提供ください。24時間以内に無料交換します。',
      'クレジットカード拒否は通常、銀行の海外取引セキュリティです。銀行確認、PayPal、別カードをお試しください。PCI-DSS暗号化済みです。',
      'ドイツは150ユーロ以下関税免税ですが19%VATがかかります。DDPサービスも選択可能。税関請求書も発行可能です。',
      'ゴールド会員様は無料Express配送、専属サポート、誕生日ポイント2倍の特典があります。自動適用済みです。',
      'GDPRに基づきデータ削除#GDPR20240715-2278を作成しました。30日以内に全個人データを削除します。取り消せません。'
    ],
    de:[
      'Hallo! Bestellung #AMZ20240715-88392 geprüft. Das Headset Pro unterstützt aptX Adaptive (38ms), ideal für Gaming.',
      'Smart Watch Series 7: 3 Tage mit Always-On, 7 Tage ohne. Magnetladung 2h. iOS 12+/Android 6+ kompatibel.',
      'Paket (SF1893726405) im internationalen Versand. Tracking verzögert 3-5 Tage. Ankunft in 2-3 Werktagen. Nicht verloren.',
      'Kopfhörer-Defekt: Ersatzticket #EX20240715-4471. Kaufbeleg senden, 24h kostenloser Ersatz.',
      'Kartenablehnung meist Banksicherheit. Bank kontaktieren, PayPal oder andere Karte. PCI-DSS verschlüsselt.',
      'Deutschland: unter 150€ zollfrei, 19% MwSt. DDP verfügbar. Zollrechnung verfügbar.',
      'Gold-Mitglied: kostenlos Express, dedizierter Support, Geburtstags-Doppelpunkte. Automatisch angewendet.',
      'DSGVO: Datenlöschung #GDPR20240715-2278. Alle Daten in 30 Tagen gelöscht. Unumkehrbar.'
    ],
    es:[
      'Hola! Pedido #AMZ20240715-88392 verificado. Auricular Pro soporta aptX Adaptive (38ms), ideal para gaming.',
      'Smart Watch Series 7: 3 días con always-on, 7 sin. Carga magnética 2h. iOS 12+/Android 6+.',
      'Paquete (SF1893726405) en tránsito internacional. Seguimiento retrasa 3-5 días. Llegada 2-3 días hábiles.',
      'Fallo auricular: ticket #EX20240715-4471. Envíe comprobante, reemplazo gratis 24h.',
      'Rechazo tarjeta suele ser seguridad del banco. Contacte banco, PayPal u otra tarjeta. PCI-DSS.',
      'Alemania: bajo 150€ sin arancel, 19% IVA. DDP disponible. Factura aduanera disponible.',
      'Miembro Gold: Express gratis, soporte dedicado, puntos dobles cumpleaños. Aplicado.',
      'GDPR: eliminación #GDPR20240715-2278. Todos los datos en 30 días. Irreversible.'
    ]
  },
  quickReplies:[
    '感谢您的联系，请问有什么可以帮您？',
    '请您提供一下订单号，我为您查询。',
    '非常抱歉给您带来不便，我们马上为您处理。',
    '您的反馈我们已记录，将在24小时内给您答复。',
    '已为您加急处理，请留意后续通知。',
    '请问您方便提供一下收货地址吗？',
    '我们已通知物流部门跟进，预计今日内给您更新。'
  ],
  intentTags:['物流查询','售后退款','商品咨询','投诉处理','地址修改','退换货','支付问题','技术支持','催发货','缺货询问','会员服务','关税清关','合规隐私','促销活动'],
  levels:[{n:'钻石会员',c:'lvl-diamond'},{n:'白金会员',c:'lvl-plat'},{n:'黄金会员',c:'lvl-gold'},{n:'银牌会员',c:'lvl-silver'}],
  orderStatus:[{n:'已发货',c:'shipped'},{n:'已付款',c:'paid'},{n:'待发货',c:'pending'},{n:'退款中',c:'refund'}],

  pick(arr){return arr[Math.floor(Math.random()*arr.length)]},
  ri(a,b){return Math.floor(Math.random()*(b-a+1))+a},
  rfloat(a,b,d=1){return (Math.random()*(b-a)+a).toFixed(d)},
  initials(name){return name.split(' ').map(s=>s[0]).slice(0,2).join('').toUpperCase()},
  timeAgo(){const mins=this.ri(1,180);if(mins<60)return mins+'分钟前';return Math.floor(mins/60)+'小时前'},
  nowTime(){const d=new Date();return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')}
};
