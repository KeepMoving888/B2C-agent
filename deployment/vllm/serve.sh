#!/bin/bash
# vLLM 高并发推理服务启动脚本
#
# 依赖：
#   - NVIDIA GPU（建议 24GB+ 显存）
#   - Docker + nvidia-container-toolkit
#   - 已下载的 AWQ 量化模型权重（放置于 ./models/ 目录）
#
# 使用方式：
#   bash serve.sh                          # 使用默认配置
#   MODEL_PATH=/models/Qwen2.5-7B-AWQ bash serve.sh  # 指定模型路径

set -e

# 配置
MODEL_PATH=${MODEL_PATH:-/models/Qwen2.5-7B-Instruct-AWQ}
PORT=${PORT:-8001}
GPU_MEMORY_UTILIZATION=${GPU_MEMORY_UTILIZATION:-0.9}
MAX_MODEL_LEN=${MAX_MODEL_LEN:-4096}
QUANTIZATION=${QUANTIZATION:-awq}

echo "================================================"
echo "vLLM 高并发推理服务"
echo "模型路径: $MODEL_PATH"
echo "监听端口: $PORT"
echo "量化方式: $QUANTIZATION"
echo "GPU 显存利用率: $GPU_MEMORY_UTILIZATION"
echo "最大上下文长度: $MAX_MODEL_LEN"
echo "================================================"

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "错误：未安装 Docker，请先安装 Docker + nvidia-container-toolkit"
    exit 1
fi

# 检查模型路径
if [ ! -d "./models" ]; then
    echo "警告：未找到 ./models 目录，请将 AWQ 量化模型放置于此"
    echo "      可通过 training/quantization/awq_quantize.py 生成"
fi

# 启动 vLLM
docker run -d \
    --name vllm-server \
    --runtime nvidia \
    --gpus all \
    --shm-size 1g \
    -p $PORT:8000 \
    -v $(pwd)/models:/models:ro \
    -e HUGGING_FACE_HUB_TOKEN=${HF_TOKEN:-} \
    vllm/vllm-openai:latest \
    --model $MODEL_PATH \
    --quantization $QUANTIZATION \
    --max-model-len $MAX_MODEL_LEN \
    --gpu-memory-utilization $GPU_MEMORY_UTILIZATION \
    --host 0.0.0.0 \
    --port 8000 \
    --trust-remote-code

echo ""
echo "vLLM 服务已启动"
echo "  OpenAI 兼容接口: http://localhost:$PORT/v1"
echo "  健康检查: curl http://localhost:$PORT/health"
echo ""
echo "查看日志: docker logs -f vllm-server"
echo "停止服务: docker stop vllm-server"
