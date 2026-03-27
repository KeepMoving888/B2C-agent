#!/usr/bin/env python3
"""
测试配置加载和模型选择
"""

import os
import sys

# 添加项目根目录到sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 测试配置加载
print("=== 配置加载测试 ===")
print(f"当前目录: {os.getcwd()}")
print(f".env文件存在: {os.path.exists('.env')}")
print()

# 读取.env文件内容
if os.path.exists('.env'):
    print("=== .env文件内容 ===")
    with open('.env', 'r', encoding='utf-8') as f:
        content = f.read()
        print(content)
    print()

# 测试导入配置
print("=== 配置导入测试 ===")
try:
    from src.config import settings
    print("✓ 成功导入settings")
    print(f"USE_DOMESTIC_MODEL: {settings.use_domestic_model}")
    print(f"QWEN_API_KEY: {'已配置' if settings.qwen_api_key else '未配置'}")
    print(f"OpenAI API Key: {'已配置' if settings.openai_api_key else '未配置'}")
    print(f"默认模型: {settings.llm_models['default']}")
    print(f"国内模型: {settings.llm_models['domestic']}")
except Exception as e:
    print(f"✗ 导入失败: {e}")
    import traceback
    traceback.print_exc()

print("\n测试完成！")
