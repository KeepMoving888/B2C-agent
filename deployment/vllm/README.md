# vLLM 部署目录说明

## 目录结构

```
deployment/vllm/
├── models/               # 模型权重存放目录（需自行准备，不纳入版本管理）
├── serve.sh              # vLLM 启动脚本（Docker 方式）
├── serving_config.json   # vLLM 服务配置
└── README.md             # 本文档
```

## 前置条件

1. **GPU 环境**：NVIDIA GPU，建议显存 ≥ 24GB（如 RTX 4090 / A10 / A100）
2. **Docker**：已安装 Docker + nvidia-container-toolkit
3. **模型权重**：AWQ 量化后的 Qwen2.5-7B 模型

## 准备模型权重

### 方式一：使用项目内置的量化脚本

```bash
# 1. 完成 QLoRA 微调（见 training/qlora/）
cd training/qlora
python train.py --config configs/qwen2.5_7b_qlora.yaml

# 2. 执行 AWQ 量化
cd ../quantization
python awq_quantize.py --model-path ../qlora/outputs/final --config configs/awq_config.yaml

# 3. 将量化模型拷贝至 vLLM 部署目录
cp -r outputs/awq ../../deployment/vllm/models/Qwen2.5-7B-Instruct-AWQ
```

### 方式二：直接下载官方 AWQ 量化模型

```bash
cd deployment/vllm/models
# 从 HuggingFace 下载官方 AWQ 量化版本
huggingface-cli download Qwen/Qwen2.5-7B-Instruct-AWQ --local-dir Qwen2.5-7B-Instruct-AWQ
```

## 启动 vLLM 服务

```bash
cd deployment/vllm

# 使用默认配置
bash serve.sh

# 自定义模型路径
MODEL_PATH=/models/Qwen2.5-7B-Instruct-AWQ bash serve.sh
```

## 服务验证

```bash
# 健康检查
curl http://localhost:8001/health

# 测试推理
curl http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2.5-7B-Instruct-AWQ",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

## 性能调优

### 关键参数

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `gpu_memory_utilization` | GPU 显存利用率 | 0.9（单卡） / 0.85（多卡） |
| `max_model_len` | 最大上下文长度 | 4096 / 8192 |
| `max_num_seqs` | 最大并发序列数 | 256（高并发场景） |
| `tensor_parallel_size` | 张量并行数 | 1（单卡） / GPU 数（多卡） |

### 高并发优化

- 启用连续批处理（continuous batching，vLLM 默认开启）
- 适当增大 `max_num_seqs` 提升吞吐
- 多卡部署时设置 `tensor_parallel_size`
- 生产环境建议前置负载均衡（Nginx / HAProxy）

## 常见问题

**Q: 显存不足？**
- 降低 `gpu_memory_utilization` 至 0.8
- 降低 `max_model_len` 至 2048
- 使用更小的模型（如 Qwen2.5-3B）

**Q: 推理速度慢？**
- 确认使用了 AWQ 量化（推理速度比 FP16 快 2-3 倍）
- 增大批处理大小
- 检查 GPU 是否被其他进程占用
