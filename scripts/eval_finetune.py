"""QLoRA 微调前后效果对比评估 - 命令行入口

深化点3：QLoRA 微调前后效果对比评估

支持两种运行模式：
    1) compare 模式（默认，无需 GPU）：
       加载 training/eval/benchmark_results.json 预置基准数据，
       输出对比表格、改进百分比、训练 loss 曲线。

    2) live 模式（需 vLLM 服务可用）：
       实时调用 vLLM OpenAI 兼容接口，分别用基座/微调/量化三套模型
       在评估数据集上生成回复并计算 BLEU/ROUGE/质量/延迟指标。

使用方式：
    # 显示预置对比结果（无需 GPU）
    python scripts/eval_finetune.py --mode compare

    # 实时调用 vLLM 对比（需 vLLM 可用）
    python scripts/eval_finetune.py --mode live --vllm-url http://localhost:8001/v1

    # 自定义基准文件路径
    python scripts/eval_finetune.py --mode compare --benchmark path/to/benchmark.json

    # 导出完整报告为 JSON
    python scripts/eval_finetune.py --mode compare --export report.json

依赖：
    pip install loguru
    # live 模式额外需要：
    pip install openai
"""
import os
import sys
import json
import argparse

# 将 training/eval 加入 sys.path，便于导入评估模块
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EVAL_DIR = os.path.join(_PROJECT_ROOT, "training", "eval")
sys.path.insert(0, _EVAL_DIR)

from loguru import logger  # noqa: E402

from evaluator import (  # noqa: E402
    Evaluator,
    load_eval_dataset,
    bleu_score,
    rouge_score,
    tokenize,
)
from compare import (  # noqa: E402
    compare_models,
    format_comparison_table,
    format_loss_curve,
    _BENCHMARK_PATH,
    _EVAL_DATASET_PATH,
)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="QLoRA 微调前后效果对比评估（深化点3）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python scripts/eval_finetune.py --mode compare
  python scripts/eval_finetune.py --mode live --vllm-url http://localhost:8001/v1
  python scripts/eval_finetune.py --mode compare --export report.json
        """,
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="compare",
        choices=["compare", "live"],
        help="评估模式：compare=加载预置数据 | live=实时调用 vLLM",
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        default=_BENCHMARK_PATH,
        help="预置基准结果文件路径（compare 模式）",
    )
    parser.add_argument(
        "--eval-dataset",
        type=str,
        default=_EVAL_DATASET_PATH,
        help="评估数据集路径（live 模式）",
    )
    parser.add_argument(
        "--vllm-url",
        type=str,
        default="http://localhost:8001/v1",
        help="vLLM OpenAI 兼容接口地址（live 模式）",
    )
    parser.add_argument(
        "--vllm-api-key",
        type=str,
        default="EMPTY",
        help="vLLM API Key（默认 EMPTY）",
    )
    parser.add_argument(
        "--base-model",
        type=str,
        default="Qwen2.5-7B-Instruct",
        help="基座模型名（live 模式）",
    )
    parser.add_argument(
        "--finetuned-model",
        type=str,
        default="Qwen2.5-7B-QLoRA-CS",
        help="微调模型名（live 模式）",
    )
    parser.add_argument(
        "--quantized-model",
        type=str,
        default="Qwen2.5-7B-QLoRA-CS-AWQ",
        help="量化模型名（live 模式）",
    )
    parser.add_argument(
        "--export",
        type=str,
        default=None,
        help="将完整对比报告导出为 JSON 文件",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="运行 BLEU/ROUGE 实现自测",
    )
    return parser.parse_args()


def run_self_test():
    """BLEU/ROUGE 实现自测

    验证评估器实现的正确性：
        - 完全匹配 → 1.0
        - 完全不相关 → 0.0
        - 部分匹配 → (0, 1)
    """
    print("=" * 60)
    print("BLEU / ROUGE 实现自测")
    print("=" * 60)

    ref_text = "您好，您的订单已发货，预计3-5个工作日送达。"
    ref = tokenize(ref_text)

    cases = [
        ("完全匹配", ref_text),
        ("部分匹配", "订单已经发出，差不多一周内到。"),
        ("完全不相关", "今天天气不错。"),
    ]

    print(f"\n参考答案: {ref_text}")
    print(f"分词结果: {ref}\n")

    print(f"{'场景':<12}{'BLEU-1':>10}{'BLEU-2':>10}{'BLEU-4':>10}"
          f"{'ROUGE-1':>10}{'ROUGE-2':>10}{'ROUGE-L':>10}")
    print("-" * 72)
    for name, cand_text in cases:
        cand = tokenize(cand_text)
        b = bleu_score([ref], cand)
        r = rouge_score([ref], cand)
        print(f"{name:<12}"
              f"{b['bleu_1']:>10.3f}"
              f"{b['bleu_2']:>10.3f}"
              f"{b['bleu_4']:>10.3f}"
              f"{r['rouge_1']['f1']:>10.3f}"
              f"{r['rouge_2']['f1']:>10.3f}"
              f"{r['rouge_l']['f1']:>10.3f}")
    print("-" * 72)
    print("期望：完全匹配=1.000，完全不相关=0.000，部分匹配介于 (0,1)\n")


def run_compare_mode(args) -> dict:
    """compare 模式：加载预置基准数据"""
    logger.info("运行模式: compare（加载预置基准数据）")
    report = compare_models(
        mode="compare",
        benchmark_path=args.benchmark,
    )
    print(format_comparison_table(report))

    # 训练 loss 曲线
    if report.get("training_loss_curve"):
        print(format_loss_curve(report["training_loss_curve"]))

    # 数据集统计
    try:
        samples = load_eval_dataset(args.eval_dataset)
        lang_dist: dict[str, int] = {}
        intent_dist: dict[str, int] = {}
        for s in samples:
            lang_dist[s.lang] = lang_dist.get(s.lang, 0) + 1
            intent_dist[s.intent] = intent_dist.get(s.intent, 0) + 1
        print()
        print("=" * 60)
        print(f"评估数据集统计: {args.eval_dataset}")
        print("=" * 60)
        print(f"  样本总数: {len(samples)}")
        print(f"  语言分布: {lang_dist}")
        print(f"  意图分布: {intent_dist}")
        print()
    except FileNotFoundError:
        logger.warning(f"评估数据集不存在: {args.eval_dataset}")

    return report


def run_live_mode(args) -> dict:
    """live 模式：实时调用 vLLM 做三模型对比"""
    logger.info("运行模式: live（实时调用 vLLM）")
    logger.info(f"vLLM 地址: {args.vllm_url}")
    logger.info(f"基座模型:   {args.base_model}")
    logger.info(f"微调模型:   {args.finetuned_model}")
    logger.info(f"量化模型:   {args.quantized_model}")

    # 探测 vLLM 可用性
    try:
        from openai import OpenAI
        client = OpenAI(base_url=args.vllm_url, api_key=args.vllm_api_key, timeout=5)
        client.models.list()
        logger.info("vLLM 服务连通正常")
    except ImportError:
        logger.error("缺少 openai 依赖，请安装: pip install openai")
        sys.exit(1)
    except Exception as e:
        logger.error(f"vLLM 服务不可用: {type(e).__name__}: {e}")
        logger.error("请确认 vLLM 已启动，或改用 --mode compare 查看预置对比结果")
        sys.exit(1)

    report = compare_models(
        mode="live",
        eval_dataset_path=args.eval_dataset,
        vllm_base_url=args.vllm_url,
        vllm_api_key=args.vllm_api_key,
        base_model=args.base_model,
        finetuned_model=args.finetuned_model,
        quantized_model=args.quantized_model,
    )

    if "error" in report:
        logger.error(f"live 评估失败: {report.get('error')}")
        sys.exit(1)

    print(format_comparison_table(report))
    return report


def main():
    """主入口"""
    args = parse_args()

    print()
    print("#" * 78)
    print("# 深化点3：QLoRA 微调前后效果对比评估")
    print("#" * 78)
    print()

    # 自测
    if args.self_test:
        run_self_test()
        return

    # 主流程
    if args.mode == "compare":
        report = run_compare_mode(args)
    else:
        report = run_live_mode(args)

    # 导出报告
    if args.export:
        export_path = os.path.abspath(args.export)
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"完整对比报告已导出: {export_path}")

    print()
    print("#" * 78)
    print("# 评估完成")
    print("#" * 78)


if __name__ == "__main__":
    main()
