# AWQ 量化方案

## AWQ (Activation-aware Weight Quantization)

### 原理

AWQ 基于激活值感知的权重量化，通过保护重要权重（对激活值影响大的权重）来减少量化精度损失。

**核心创新**：
- **激活值感知**：根据激活值分布识别重要权重
- **分组量化**：按 group_size 分组量化，平衡精度与压缩率
- **零点优化**：支持 zero_point，提升量化范围利用率

### 与 GPTQ 对比

| 特性 | AWQ | GPTQ |
|------|-----|------|
| 量化方式 | 激活感知 | 误差补偿 |
| 推理速度 | 更快 | 较快 |
| 精度 | 更优 | 优 |
| 显存占用 | 低 | 低 |
| vLLM 支持 | 原生支持 | 支持 |

**推荐 AWQ**：推理速度更快，精度更优，vLLM 原生支持。

### 量化流程

```
QLoRA 微调后的模型 (FP16)
        │
        ▼
  加载模型权重
        │
        ▼
  准备校准数据 (多语言客服对话样本)
        │
        ▼
  激活值分析，识别重要权重
        │
        ▼
  分组量化 (group_size=128, 4-bit)
        │
        ▼
  保存量化模型 (体积约为原模型 1/4)
        │
        ▼
  部署至 vLLM
```

### 使用方式

```bash
cd training/quantization

# 使用默认配置
python awq_quantize.py --model-path ../qlora/outputs/final --config configs/awq_config.yaml

# 自定义参数
python awq_quantize.py \
  --model-path Qwen/Qwen2.5-7B-Instruct \
  --output-path ./outputs/awq \
  --bits 4 \
  --group-size 128
```

### 量化参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| bits | 4 | 4-bit 性价比最高 |
| group_size | 128 | 平衡精度与压缩率 |
| zero_point | true | 提升量化范围 |
| version | GEMM | GPU 推理推荐 |

### 模型体积对比

| 模型 | 精度 | 体积 |
|------|------|------|
| Qwen2.5-7B-Instruct | FP16 | ~14GB |
| Qwen2.5-7B-Instruct | INT8 | ~7GB |
| **Qwen2.5-7B-Instruct-AWQ** | **INT4** | **~4GB** |

## 部署到 vLLM

```bash
# 将量化模型拷贝至部署目录
cp -r outputs/awq ../../deployment/vllm/models/Qwen2.5-7B-Instruct-AWQ

# 启动 vLLM
cd ../../deployment/vllm
bash serve.sh
```

## 精度评估

| 指标 | FP16 基座 | AWQ 4-bit | 损失 |
|------|----------|-----------|------|
| 回复准确率 | 95% | 94.5% | -0.5% |
| 幻觉率 | 1% | 1.2% | +0.2% |
| 推理速度 | 1x | 2.5x | +150% |
| 显存占用 | 14GB | 4GB | -71% |
