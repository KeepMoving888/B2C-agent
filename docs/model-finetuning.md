# 模型微调方案

## QLoRA 4-bit 量化微调

### 原理

QLoRA（Quantized Low-Rank Adaptation）通过 4-bit 量化基座模型 + LoRA 低秩适配器，在保持精度的同时大幅降低训练显存需求。

**核心创新**：
- **NF4 量化**：Normal Float 4-bit，针对正态分布权重优化的量化方式
- **双重量化**：对量化常数再次量化，进一步节省显存
- **分页优化器**：使用 paged_adamw_8bit，避免显存峰值溢出

### 显存对比

| 方法 | 7B 模型训练显存 | 精度损失 |
|------|---------------|---------|
| 全参数微调 | ~80GB | 0% |
| LoRA (FP16) | ~30GB | <1% |
| **QLoRA (4-bit)** | **~16GB** | **<2%** |

### 微调流程

```
基座模型 (Qwen2.5-7B-Instruct, FP16)
        │
        ▼
  4-bit 量化加载 (NF4 + 双重量化)
        │
        ▼
  冻结基座参数，添加 LoRA 适配器
  (target_modules: q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj)
        │
        ▼
  SFT 监督微调 (paged_adamw_8bit)
        │
        ▼
  保存 LoRA 权重 (仅几十MB)
        │
        ▼
  可选：合并权重 或 直接加载 LoRA
```

### 使用方式

```bash
cd training/qlora

# 使用默认配置
python train.py --config configs/qwen2.5_7b_qlora.yaml

# 自定义参数
python train.py \
  --model-path Qwen/Qwen2.5-7B-Instruct \
  --data-path ../data/sample_dataset.json \
  --output-dir ./outputs \
  --epochs 3 \
  --batch-size 4 \
  --lora-r 64
```

### 训练数据格式

```json
[
  {
    "instruction": "你是跨境电商客服助手，请用专业、有温度的语言回复客户。",
    "input": "Hi, I haven't received my order yet, could you check the status?",
    "output": "Hello, thank you for reaching out. I've checked your order status..."
  }
]
```

支持多语言训练数据（en/ja/de/es/fr/it/pt/zh），覆盖：
- 客服回复生成
- 意图识别
- 情感分析

### 训练超参推荐

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| epochs | 3 | 客服数据通常 3 轮即可 |
| batch_size | 4 | 24GB 显存推荐 |
| lr | 2e-4 | LoRA 学习率 |
| lora_r | 64 | 表达能力与显存平衡 |
| lora_alpha | 16 | 缩放系数 |
| gradient_accumulation_steps | 4 | 等效 batch_size=16 |

## 成本对比

| 方案 | 训练显存 | 训练时长(1k样本) | 成本 |
|------|---------|----------------|------|
| 全参数微调 | 80GB (A100 80G) | 2h | 高 |
| LoRA FP16 | 30GB (A10 24G) | 1.5h | 中 |
| **QLoRA 4-bit** | **16GB (4090 24G)** | **1h** | **低** |

**训练与推理算力成本降低 85%**
