"""QLoRA 4-bit 量化微调脚本

基于 Qwen2.5-7B 进行 QLoRA 4-bit 量化微调，大幅降低训练显存需求。
单卡 24GB 显存即可完成 7B 模型微调。

使用方式：
    python train.py --config configs/qwen2.5_7b_qlora.yaml
    python train.py --model-path Qwen/Qwen2.5-7B-Instruct --data-path ../data/sample_dataset.json

依赖：
    pip install transformers>=4.37 peft>=0.7 bitsandbytes>=0.41 accelerate>=0.25 trl>=0.7
"""
import os
import argparse
import yaml
from typing import Optional
from loguru import logger

from dataset_utils import load_dataset, format_for_qlora, split_dataset


def parse_args():
    parser = argparse.ArgumentParser(description="Qwen2.5-7B QLoRA 4-bit 微调")
    parser.add_argument("--config", type=str, default=None, help="配置文件路径")
    parser.add_argument("--model-path", type=str, default="Qwen/Qwen2.5-7B-Instruct", help="基座模型路径")
    parser.add_argument("--data-path", type=str, default="../data/sample_dataset.json", help="训练数据路径")
    parser.add_argument("--output-dir", type=str, default="./outputs", help="输出目录")
    parser.add_argument("--epochs", type=int, default=3, help="训练轮数")
    parser.add_argument("--batch-size", type=int, default=4, help="批大小")
    parser.add_argument("--lr", type=float, default=2e-4, help="学习率")
    parser.add_argument("--lora-r", type=int, default=64, help="LoRA秩")
    parser.add_argument("--lora-alpha", type=int, default=16, help="LoRA alpha")
    return parser.parse_args()


def load_config(config_path: Optional[str]) -> dict:
    """加载 YAML 配置"""
    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def train(args):
    """执行 QLoRA 微调"""
    cfg = load_config(args.config)
    model_path = cfg.get("model_path", args.model_path)
    data_path = cfg.get("data_path", args.data_path)
    output_dir = cfg.get("output_dir", args.output_dir)

    logger.info("=" * 60)
    logger.info("Qwen2.5-7B QLoRA 4-bit 微调")
    logger.info(f"基座模型: {model_path}")
    logger.info(f"训练数据: {data_path}")
    logger.info(f"输出目录: {output_dir}")
    logger.info("=" * 60)

    # 检查依赖
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from trl import SFTTrainer
    except ImportError as e:
        logger.error(f"缺少依赖，请安装: pip install transformers peft bitsandbytes accelerate trl torch\n{e}")
        return

    # 加载数据集
    examples = load_dataset(data_path)
    train_data = format_for_qlora(examples)
    train_split, val_split = split_dataset(train_data, val_ratio=0.1)
    logger.info(f"训练集 {len(train_split)} 条，验证集 {len(val_split)} 条")

    # 4-bit 量化配置
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    # 加载 tokenizer 与模型
    logger.info("加载 tokenizer 与模型...")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    # LoRA 配置
    lora_config = LoraConfig(
        r=cfg.get("lora_r", args.lora_r),
        lora_alpha=cfg.get("lora_alpha", args.lora_alpha),
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 训练参数
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=cfg.get("epochs", args.epochs),
        per_device_train_batch_size=cfg.get("batch_size", args.batch_size),
        per_device_eval_batch_size=cfg.get("batch_size", args.batch_size),
        gradient_accumulation_steps=4,
        learning_rate=cfg.get("lr", args.lr),
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        logging_steps=10,
        save_strategy="epoch",
        eval_strategy="epoch",
        bf16=True,
        optim="paged_adamw_8bit",
        report_to="none",
    )

    # 训练器
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_split,
        eval_dataset=val_split,
        formatting_func=lambda x: x["text"],
    )

    # 开始训练
    logger.info("开始训练...")
    trainer.train()

    # 保存 LoRA 权重
    save_path = os.path.join(output_dir, "final")
    trainer.save_model(save_path)
    tokenizer.save_pretrained(save_path)
    logger.info(f"训练完成，LoRA 权重已保存至 {save_path}")
    logger.info("后续可用 AWQ 量化进一步压缩模型，详见 training/quantization/awq_quantize.py")


if __name__ == "__main__":
    train(parse_args())
