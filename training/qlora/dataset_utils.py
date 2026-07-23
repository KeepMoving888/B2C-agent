"""数据集处理工具

将 JSON 格式的客服对话数据转换为 QLoRA 微调所需的格式。
"""
import json
import os
from typing import Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class TrainExample:
    """训练样本"""
    instruction: str
    input: str
    output: str

    def to_prompt(self) -> str:
        """转换为 Qwen ChatML 格式的 prompt"""
        return f"<|im_start|>system\n{self.instruction}<|im_end|>\n<|im_start|>user\n{self.input}<|im_end|>\n<|im_start|>assistant\n"

    def to_text(self) -> str:
        """完整训练文本（prompt + output）"""
        return self.to_prompt() + self.output + "<|im_end|>"


def load_dataset(path: str) -> list[TrainExample]:
    """加载 JSON 数据集"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"数据集不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    examples = []
    for item in data:
        examples.append(TrainExample(
            instruction=item.get("instruction", ""),
            input=item.get("input", ""),
            output=item.get("output", ""),
        ))
    logger.info(f"加载数据集 {len(examples)} 条: {path}")
    return examples


def format_for_qlora(examples: list[TrainExample]) -> list[dict]:
    """转换为 QLoRA 训练所需的字典格式"""
    return [
        {
            "prompt": ex.to_prompt(),
            "completion": ex.output + "<|im_end|>",
            "text": ex.to_text(),
        }
        for ex in examples
    ]


def split_dataset(examples: list, val_ratio: float = 0.1):
    """划分训练集/验证集"""
    import random
    random.shuffle(examples)
    val_size = max(1, int(len(examples) * val_ratio))
    return examples[val_size:], examples[:val_size]
