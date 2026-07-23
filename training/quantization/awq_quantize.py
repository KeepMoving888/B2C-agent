"""AWQ 量化脚本

将 QLoRA 微调后的模型进行 AWQ 量化，便于 vLLM 高效部署。
AWQ 量化相比 GPTQ 在推理速度与精度上更优，适合生产部署。

使用方式：
    python awq_quantize.py --model-path ../qlora/outputs/final --config configs/awq_config.yaml
    python awq_quantize.py --model-path Qwen/Qwen2.5-7B-Instruct --output-path ./outputs/awq

依赖：
    pip install autoawq>=0.2 transformers>=4.37 accelerate
"""
import os
import argparse
import yaml
from typing import Optional
from loguru import logger


def parse_args():
    parser = argparse.ArgumentParser(description="AWQ 量化")
    parser.add_argument("--config", type=str, default=None, help="配置文件路径")
    parser.add_argument("--model-path", type=str, required=True, help="待量化模型路径（QLoRA 输出或基座模型）")
    parser.add_argument("--output-path", type=str, default="./outputs/awq", help="量化模型输出路径")
    parser.add_argument("--bits", type=int, default=4, help="量化位数")
    parser.add_argument("--group-size", type=int, default=128, help="量化分组大小")
    parser.add_argument("--calib-data", type=str, default="pileval", help="校准数据集")
    return parser.parse_args()


def load_config(config_path: Optional[str]) -> dict:
    """加载 YAML 配置"""
    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def quantize(args):
    """执行 AWQ 量化"""
    cfg = load_config(args.config)
    model_path = cfg.get("model_path", args.model_path)
    output_path = cfg.get("output_path", args.output_path)
    bits = cfg.get("bits", args.bits)
    group_size = cfg.get("group_size", args.group_size)

    logger.info("=" * 60)
    logger.info("AWQ 量化")
    logger.info(f"输入模型: {model_path}")
    logger.info(f"输出路径: {output_path}")
    logger.info(f"量化位数: {bits}-bit")
    logger.info(f"分组大小: {group_size}")
    logger.info("=" * 60)

    # 检查依赖
    try:
        from awq import AutoAWQForCausalLM
        from transformers import AutoTokenizer
    except ImportError as e:
        logger.error(f"缺少依赖，请安装: pip install autoawq transformers accelerate\n{e}")
        return

    # 加载 tokenizer
    logger.info("加载 tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

    # 加载模型
    logger.info("加载模型...")
    model = AutoAWQForCausalLM.from_pretrained(model_path, trust_remote_code=True)

    # 量化配置
    quant_config = {
        "zero_point": True,
        "q_group_size": group_size,
        "w_bit": bits,
        "version": "GEMM",
    }

    # 校准数据
    calib_data = _prepare_calib_data(cfg.get("calib_data", args.calib_data))

    # 执行量化
    logger.info("开始量化...")
    model.quantize(tokenizer, quant_config=quant_config, calib_data=calib_data)

    # 保存量化模型
    os.makedirs(output_path, exist_ok=True)
    model.save_quantized(output_path)
    tokenizer.save_pretrained(output_path)
    logger.info(f"量化完成，模型已保存至 {output_path}")
    logger.info("可将量化模型部署至 vLLM，详见 deployment/vllm/serve.sh")


def _prepare_calib_data(name: str) -> list[str]:
    """准备校准数据"""
    if name == "pileval":
        # 使用内置校准数据
        return [
            "Hello, thank you for contacting customer service. How may I help you today?",
            "您的订单已发货，预计3-5个工作日送达，请留意物流更新。",
            "こんにちは、ご連絡ありがとうございます。注文の配送状況を確認いたしました。",
            "We apologize for the inconvenience. A replacement has been arranged.",
            "感谢您的耐心等待，退款已处理，3-5个工作日内到账。",
        ]
    return []


if __name__ == "__main__":
    quantize(parse_args())
