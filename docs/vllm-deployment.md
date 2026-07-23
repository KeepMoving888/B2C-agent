# vLLM 高并发推理部署

## vLLM 核心优势

- **PagedAttention**：分页注意力机制，显存利用率提升 3-5 倍
- **连续批处理**：动态批处理请求，吞吐量提升 2-4 倍
- **OpenAI 兼容**：直接复用 OpenAI SDK，零代码迁移
- **AWQ 加速**：原生支持 AWQ 量化，推理速度 2-3 倍

## 部署方式

### 方式一：Docker 部署（推荐）

```bash
cd deployment/vllm

# 准备模型权重
cp -r ../../training/quantization/outputs/awq ./models/Qwen2.5-7B-Instruct-AWQ

# 启动服务
bash serve.sh
```

### 方式二：直接安装

```bash
pip install vllm

# 启动服务
python -m vllm.entrypoints.openai.api_server \
  --model Qwen2.5-7B-Instruct-AWQ \
  --quantization awq \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.9 \
  --port 8001
```

## 性能调优

### 关键参数

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `gpu_memory_utilization` | GPU 显存利用率 | 0.9（单卡） |
| `max_model_len` | 最大上下文长度 | 4096 |
| `max_num_seqs` | 最大并发序列数 | 256 |
| `tensor_parallel_size` | 张量并行数 | 1（单卡） |
| `enable_continuous_batching` | 连续批处理 | true |

### 高并发优化

1. **连续批处理**：vLLM 默认开启，动态合并请求
2. **增大 max_num_seqs**：提升并发吞吐
3. **多卡部署**：`tensor_parallel_size=GPU数`
4. **前置负载均衡**：Nginx / HAProxy 分发

## 性能指标

| 配置 | QPS | 延迟(P50) | 延迟(P99) |
|------|-----|----------|----------|
| Qwen2.5-7B FP16 (A100 40G) | 45 | 180ms | 450ms |
| Qwen2.5-7B AWQ (A100 40G) | 110 | 90ms | 220ms |
| Qwen2.5-7B AWQ (4090 24G) | 85 | 120ms | 280ms |

**峰值可支撑单日 1W+ 会话**

## 接口验证

```bash
# 健康检查
curl http://localhost:8001/health

# 推理测试
curl http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2.5-7B-Instruct-AWQ",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "max_tokens": 512
  }'
```

## 监控

```bash
# 查看服务日志
docker logs -f vllm-server

# 查看 GPU 使用率
nvidia-smi -l 1

# 查看请求统计
curl http://localhost:8001/metrics
```

## 常见问题

**Q: 显存不足？**
- 降低 `gpu_memory_utilization` 至 0.8
- 降低 `max_model_len` 至 2048
- 使用更小模型（Qwen2.5-3B）

**Q: 推理速度慢？**
- 确认使用 AWQ 量化
- 增大批处理
- 检查 GPU 占用

**Q: 首次启动慢？**
- vLLM 首次加载需编译 CUDA kernel，属正常现象
- 后续启动会缓存
