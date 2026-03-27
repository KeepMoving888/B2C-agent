"""
基于Flask的简单web界面，用于测试多Agent智能客服系统
"""

import sys
import os
# 添加项目根目录到sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify, Response
import json
import time
from langchain_core.messages import HumanMessage
from src.agents import create_customer_service_graph
from src.state.schema import ConversationState
from src.agents.fast_routing import check_faq_response  # 导入FAQ快速回复

app = Flask(__name__)

# 创建客服图实例
customer_service_graph = create_customer_service_graph()
# 首页路由
@app.route('/')
def index():
    """首页"""
    return render_template('index.html')
# 聊天路由
@app.route('/chat', methods=['POST'])
def chat():
    """处理聊天请求（秒回版）"""
    import time
    total_start_time = time.time()
    
    data = request.json
    user_message = data.get('message')
    language = data.get('language', 'zh')
    platform = data.get('platform', 'website')
    
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    
    print(f"\n{'='*60}")
    print(f"[请求] 用户消息: {user_message[:50]}...")
    print(f"[请求] 平台: {platform}, 语言: {language}")
    
    # 阶段1: 检查FAQ快速回复（毫秒级）
    faq_start_time = time.time()
    faq_response = check_faq_response(user_message)
    faq_time = time.time() - faq_start_time
    
    if faq_response:
        total_time = time.time() - total_start_time
        print(f"[FAQ快速回复] 匹配成功! 耗时: {faq_time*1000:.2f}毫秒")
        print(f"[性能监控] 总响应时间: {total_time:.3f}秒 (FAQ秒回)")
        print(f"{'='*60}\n")
        return jsonify({
            'response': faq_response,
            'agent': 'faq_fast',
            'model': 'faq_cache'
        })
    
    print(f"[FAQ检查] 未匹配，耗时: {faq_time*1000:.2f}毫秒")
    
    # 阶段2: 构建对话状态
    state: ConversationState = {
        "messages": [HumanMessage(content=user_message)],
        "session_metadata": {
            "platform": platform,
            "language": language
        },
    }
    
    # 阶段3: 调用客服图
    try:
        graph_start_time = time.time()
        print(f"[图执行] 开始...")
        
        result = customer_service_graph.invoke(state)
        
        graph_time = time.time() - graph_start_time
        print(f"[图执行] 完成，耗时: {graph_time:.2f}秒")
        
        # 获取最后一条回复
        last_msg = result["messages"][-1]
        response = last_msg.content
        
        # 获取路由信息
        current_agent = result.get("current_agent", "unknown")
        
        # 强制使用国内模型名称
        from src.config import settings
        if settings.qwen_api_key:
            selected_model = "qwen-plus"
        else:
            selected_model = result.get("selected_model", "unknown")
        
        total_time = time.time() - total_start_time
        print(f"[性能监控] 总响应时间: {total_time:.3f}秒")
        print(f"{'='*60}\n")
        
        return jsonify({
            'response': response,
            'agent': current_agent,
            'model': selected_model
        })
    except Exception as e:
        total_time = time.time() - total_start_time
        print(f"[错误] {str(e)}")
        print(f"[性能监控] 总响应时间: {total_time:.3f}秒 (出错)")
        print(f"{'='*60}\n")
        return jsonify({
            'response': '抱歉，系统出现技术问题，请稍后重试。',
            'error': str(e)
        }), 500

# 流式聊天接口
@app.route('/chat/stream', methods=['POST'])
def chat_stream():
    """流式处理聊天请求"""
    data = request.json
    user_message = data.get('message')
    language = data.get('language', 'zh')
    platform = data.get('platform', 'website')
    
    if not user_message:
        def generate_error():
            yield f"data: {json.dumps({'error': 'Message is required'})}\n\n"
        return Response(generate_error(), mimetype='text/event-stream')
    
    print(f"\n{'='*60}")
    print(f"[流式请求] 用户消息: {user_message[:50]}...")
    print(f"[流式请求] 平台: {platform}, 语言: {language}")
    
    # 1. 检查FAQ快速回复
    faq_response = check_faq_response(user_message)
    
    if faq_response:
        print("[流式FAQ] 匹配成功!")
        print(f"{'='*60}\n")
        
        def generate_faq():
            # 流式输出FAQ回复
            for i in range(0, len(faq_response), 10):
                chunk = faq_response[i:i+10]
                done = i+10 >= len(faq_response)
                yield f"data: {json.dumps({'chunk': chunk, 'done': done, 'agent': 'faq_fast', 'model': 'faq_cache'})}\n\n"
                time.sleep(0.05)  # 控制输出速度
        
        return Response(generate_faq(), mimetype='text/event-stream')
    
    # 2. 构建对话状态
    state: ConversationState = {
        "messages": [HumanMessage(content=user_message)],
        "session_metadata": {
            "platform": platform,
            "language": language
        },
    }
    
    # 3. 调用客服图获取完整响应
    try:
        print(f"[图执行] 开始...")
        result = customer_service_graph.invoke(state)
        
        # 获取最后一条回复
        last_msg = result["messages"][-1]
        response = last_msg.content
        
        # 获取路由信息
        current_agent = result.get("current_agent", "unknown")
        
        # 强制使用国内模型名称
        from src.config import settings
        if settings.qwen_api_key:
            selected_model = "qwen-plus"
        else:
            selected_model = result.get("selected_model", "unknown")
        
        print("[流式输出] 开始...")
        print(f"{'='*60}\n")
        
        # 4. 流式输出响应
        def generate():
            for i in range(0, len(response), 15):
                chunk = response[i:i+15]
                done = i+15 >= len(response)
                yield f"data: {json.dumps({'chunk': chunk, 'done': done, 'agent': current_agent, 'model': selected_model})}\n\n"
                time.sleep(0.08)  # 控制输出速度
        
        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        print(f"[错误] {str(e)}")
        print(f"{'='*60}\n")
        
        def generate_error():
            error_msg = '抱歉，系统出现技术问题，请稍后重试。'
            yield f"data: {json.dumps({'chunk': error_msg, 'done': True, 'error': str(e)})}\n\n"
        
        return Response(generate_error(), mimetype='text/event-stream')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
