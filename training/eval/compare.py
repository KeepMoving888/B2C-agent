"""QLoRA 微调前后效果对比分析

对比三类模型在客服场景下的效果：
    - 基座模型（Qwen2.5-7B-Instruct）
    - 微调模型（Qwen2.5-7B-QLoRA-CS）
    - 量化模型（Qwen2.5-7B-QLoRA-CS-AWQ）

对比维度：
    - BLEU-4 / ROUGE-L：回复与参考答案的重叠度
    - 质量总分：多维度加权质量评分
    - 延迟(ms)：完整生成时间
    - 显存(GB)：推理峰值显存

两种运行模式：
    1) compare 模式（默认）：加载预置 benchmark_results.json，无需 GPU
    2) live 模式：实时调用 vLLM 对三套部署做对比（需 vLLM 可用）

使用方式：
    from compare import compare_models, format_comparison_table
    report = compare_models()                       # 预置对比
    report = compare_models(mode="live", ...)       # 实时对比
    print(format_comparison_table(report))
"""
from __future__ import annotations

import json
import os
from typing import Optional

from loguru import logger

# 支持两种导入方式：作为模块导入 / 作为脚本直接运行
try:
    from evaluator import (
        Evaluator,
        EvalSample,
        Latency,
        load_eval_dataset,
    )
except ImportError:  # pragma: no cover - 兜底路径
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from evaluator import (  # type: ignore
        Evaluator,
        EvalSample,
        Latency,
        load_eval_dataset,
    )


# ============================================================
# 路径常量
# ============================================================

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_TRAINING_DIR = os.path.dirname(_EVAL_DIR)
_BENCHMARK_PATH = os.path.join(_EVAL_DIR, "benchmark_results.json")
_EVAL_DATASET_PATH = os.path.join(_TRAINING_DIR, "data", "eval_dataset.json")


# ============================================================
# 预置基准数据加载
# ============================================================

def load_benchmark(path: str = _BENCHMARK_PATH) -> dict:
    """加载预置基准结果

    Args:
        path: benchmark_results.json 路径

    Returns:
        基准数据 dict
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"基准结果文件不存在: {path}\n"
            f"请先运行 training/eval/ 下的评估流程生成基准数据。"
        )
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"加载基准结果: {path}")
    if data.get("metadata", {}).get("note"):
        logger.info(f"基准说明: {data['metadata']['note']}")
    return data


# ============================================================
# 改进幅度计算
# ============================================================

def _improvement_pct(base: float, target: float, higher_is_better: bool = True) -> float:
    """计算改进百分比

    Args:
        base: 基线值
        target: 目标值
        higher_is_better: True=数值越高越好；False=数值越低越好（如延迟、显存）

    Returns:
        改进百分比，正数表示改进，负数表示退化
        例如 base=0.234, target=0.412 → +76.07%
    """
    if base == 0:
        return float("inf") if target > 0 else 0.0
    diff_pct = (target - base) / abs(base) * 100.0
    if higher_is_better:
        return diff_pct
    else:
        return -diff_pct  # 越低越好时，target<base 视为正向改进


# ============================================================
# 对比报告生成
# ============================================================

def compare_models(
    mode: str = "compare",
    benchmark_path: str = _BENCHMARK_PATH,
    eval_dataset_path: str = _EVAL_DATASET_PATH,
    vllm_base_url: str = "http://localhost:8001/v1",
    vllm_api_key: str = "EMPTY",
    base_model: str = "Qwen2.5-7B-Instruct",
    finetuned_model: str = "Qwen2.5-7B-QLoRA-CS",
    quantized_model: str = "Qwen2.5-7B-QLoRA-CS-AWQ",
) -> dict:
    """对比基座/微调/量化三类模型

    Args:
        mode: "compare" 加载预置数据 | "live" 实时调用 vLLM
        benchmark_path: 预置基准文件路径
        eval_dataset_path: 评估数据集路径
        vllm_base_url: vLLM 服务地址（live 模式）
        vllm_api_key: vLLM API Key（live 模式）
        base_model / finetuned_model / quantized_model: 模型名（live 模式）

    Returns:
        对比报告 dict，结构：
            {
              "metadata": {...},
              "metrics": {<指标>: {"base":..., "finetuned":..., "quantized":..., "improvement_ft_pct":..., "improvement_q_pct":...}},
              "per_dimension": {...},
              "training_loss_curve": [...],
              "mode": "compare" | "live",
              "source": "benchmark_results.json" | "live-eval"
            }
    """
    if mode == "compare":
        return _compare_from_benchmark(benchmark_path)
    elif mode == "live":
        return _compare_live(
            eval_dataset_path,
            vllm_base_url,
            vllm_api_key,
            base_model,
            finetuned_model,
            quantized_model,
        )
    else:
        raise ValueError(f"未知 mode: {mode}，支持 'compare' 或 'live'")


def _compare_from_benchmark(benchmark_path: str) -> dict:
    """从预置基准文件加载对比数据，并计算改进幅度"""
    data = load_benchmark(benchmark_path)

    metrics = data.get("metrics", {})
    per_dimension = data.get("per_dimension", {})

    # 指标方向：True=越高越好；False=越低越好
    metric_direction = {
        "bleu_4": True,
        "rouge_l": True,
        "quality_score": True,
        "latency_ms": False,
        "vram_gb": False,
    }

    enriched_metrics: dict[str, dict] = {}
    for key, vals in metrics.items():
        higher_is_better = metric_direction.get(key, True)
        base = vals.get("base", 0.0)
        ft = vals.get("finetuned", 0.0)
        q = vals.get("quantized", 0.0)
        enriched_metrics[key] = {
            "base": base,
            "finetuned": ft,
            "quantized": q,
            # 微调相对基座的改进
            "improvement_ft_pct": round(_improvement_pct(base, ft, higher_is_better), 2),
            # 量化相对微调的改进（通常为退化，体现量化代价）
            "improvement_q_pct": round(_improvement_pct(ft, q, higher_is_better), 2),
            # 量化相对基座的改进（综合体现微调+量化后的净收益）
            "improvement_q_vs_base_pct": round(_improvement_pct(base, q, higher_is_better), 2),
            "higher_is_better": higher_is_better,
        }

    # per_dimension 同样补充改进幅度
    enriched_per_dimension: dict[str, dict] = {}
    for key, vals in per_dimension.items():
        base = vals.get("base", 0.0)
        ft = vals.get("finetuned", 0.0)
        q = vals.get("quantized", 0.0)
        enriched_per_dimension[key] = {
            "base": base,
            "finetuned": ft,
            "quantized": q,
            "improvement_ft_pct": round(_improvement_pct(base, ft, True), 2),
            "improvement_q_pct": round(_improvement_pct(ft, q, True), 2),
        }

    return {
        "metadata": data.get("metadata", {}),
        "metrics": enriched_metrics,
        "per_dimension": enriched_per_dimension,
        "training_loss_curve": data.get("training_loss_curve", []),
        "mode": "compare",
        "source": benchmark_path,
    }


def _compare_live(
    eval_dataset_path: str,
    vllm_base_url: str,
    vllm_api_key: str,
    base_model: str,
    finetuned_model: str,
    quantized_model: str,
) -> dict:
    """实时调用 vLLM 做三模型对比

    三个模型均通过同一 vLLM 服务（不同 model 名）调用，
    分别在评估数据集上生成回复并计算指标。
    """
    samples = load_eval_dataset(eval_dataset_path)
    evaluator = Evaluator()

    model_specs = [
        ("base", base_model),
        ("finetuned", finetuned_model),
        ("quantized", quantized_model),
    ]

    reports: dict[str, dict] = {}
    for tag, model_name in model_specs:
        logger.info(f"评估模型 [{tag}] {model_name} ...")
        report = evaluator.evaluate_live(
            samples=samples,
            vllm_base_url=vllm_base_url,
            vllm_api_key=vllm_api_key,
            model=model_name,
        )
        if "error" in report:
            logger.error(f"模型 {tag} 评估失败: {report['error']}")
            return {"error": report["error"], "failed_model": tag}
        reports[tag] = report["aggregate"]

    # 汇总三模型指标
    agg = reports
    metrics = {
        "bleu_4": {
            "base": agg["base"]["bleu"]["bleu_4"],
            "finetuned": agg["finetuned"]["bleu"]["bleu_4"],
            "quantized": agg["quantized"]["bleu"]["bleu_4"],
        },
        "rouge_l": {
            "base": agg["base"]["rouge"]["rouge_l_f1"],
            "finetuned": agg["finetuned"]["rouge"]["rouge_l_f1"],
            "quantized": agg["quantized"]["rouge"]["rouge_l_f1"],
        },
        "quality_score": {
            "base": agg["base"]["quality"]["overall"],
            "finetuned": agg["finetuned"]["quality"]["overall"],
            "quantized": agg["quantized"]["quality"]["overall"],
        },
        "latency_ms": {
            "base": agg["base"]["latency"]["total_ms"],
            "finetuned": agg["finetuned"]["latency"]["total_ms"],
            "quantized": agg["quantized"]["latency"]["total_ms"],
        },
        # 显存需通过 nvidia-smi 或 vLLM 日志获取，此处标记为 N/A
        "vram_gb": {"base": None, "finetuned": None, "quantized": None},
    }

    per_dimension = {}
    for dim in ["relevance", "accuracy", "completeness", "tone", "multilingual"]:
        per_dimension[dim] = {
            "base": agg["base"]["quality"][dim],
            "finetuned": agg["finetuned"]["quality"][dim],
            "quantized": agg["quantized"]["quality"][dim],
        }

    # 补充改进幅度
    metric_direction = {
        "bleu_4": True, "rouge_l": True, "quality_score": True,
        "latency_ms": False, "vram_gb": False,
    }
    for key, vals in metrics.items():
        higher_is_better = metric_direction.get(key, True)
        base = vals["base"] or 0.0
        ft = vals["finetuned"] or 0.0
        q = vals["quantized"] or 0.0
        vals["improvement_ft_pct"] = round(_improvement_pct(base, ft, higher_is_better), 2)
        vals["improvement_q_pct"] = round(_improvement_pct(ft, q, higher_is_better), 2)
        vals["improvement_q_vs_base_pct"] = round(_improvement_pct(base, q, higher_is_better), 2)
        vals["higher_is_better"] = higher_is_better

    for key, vals in per_dimension.items():
        vals["improvement_ft_pct"] = round(_improvement_pct(vals["base"], vals["finetuned"], True), 2)
        vals["improvement_q_pct"] = round(_improvement_pct(vals["finetuned"], vals["quantized"], True), 2)

    return {
        "metadata": {
            "note": "实时评估结果（live 模式）",
            "base_model": base_model,
            "finetuned_model": finetuned_model,
            "quantized_model": quantized_model,
            "n_samples": agg["base"].get("n_samples", 0),
        },
        "metrics": metrics,
        "per_dimension": per_dimension,
        "training_loss_curve": [],  # live 模式无训练曲线
        "mode": "live",
        "source": f"vllm@{vllm_base_url}",
        "raw_reports": reports,
    }


# ============================================================
# 报告格式化输出
# ============================================================

def _fmt_pct(pct: float) -> str:
    """格式化百分比"""
    if pct == float("inf"):
        return "+∞"
    if pct == float("-inf"):
        return "-∞"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def format_comparison_table(report: dict) -> str:
    """格式化对比报告为可读表格文本

    Args:
        report: compare_models() 返回的对比报告

    Returns:
        格式化的多行字符串
    """
    lines: list[str] = []
    meta = report.get("metadata", {})
    metrics = report.get("metrics", {})
    per_dim = report.get("per_dimension", {})

    # 头部
    lines.append("=" * 78)
    lines.append("QLoRA 微调前后效果对比报告")
    lines.append("=" * 78)
    if meta.get("note"):
        lines.append(f"说明: {meta['note']}")
    lines.append(f"基座模型:   {meta.get('base_model', 'N/A')}")
    lines.append(f"微调模型:   {meta.get('finetuned_model', 'N/A')}")
    lines.append(f"量化模型:   {meta.get('quantized_model', 'N/A')}")
    lines.append(f"评估模式:   {report.get('mode', 'compare')}")
    lines.append(f"数据来源:   {report.get('source', 'N/A')}")
    lines.append("")

    # 主指标对比表
    lines.append("-" * 78)
    lines.append(f"{'指标':<16}{'基座模型':>12}{'微调后':>12}{'量化后':>12}{'微调改进':>12}{'量化vs微调':>12}")
    lines.append("-" * 78)

    # 指标显示名与格式化方式
    metric_display = [
        ("bleu_4",        "BLEU-4",      "{:.4f}"),
        ("rouge_l",       "ROUGE-L",     "{:.4f}"),
        ("quality_score", "质量总分",     "{:.2f}"),
        ("latency_ms",    "延迟(ms)",    "{:.0f}"),
        ("vram_gb",       "显存(GB)",    "{:.1f}"),
    ]
    for key, name, fmt in metric_display:
        m = metrics.get(key, {})
        base = m.get("base")
        ft = m.get("finetuned")
        q = m.get("quantized")
        ft_pct = m.get("improvement_ft_pct", 0.0)
        q_pct = m.get("improvement_q_pct", 0.0)

        base_s = fmt.format(base) if base is not None else "N/A"
        ft_s = fmt.format(ft) if ft is not None else "N/A"
        q_s = fmt.format(q) if q is not None else "N/A"
        lines.append(
            f"{name:<16}{base_s:>12}{ft_s:>12}{q_s:>12}"
            f"{_fmt_pct(ft_pct):>12}{_fmt_pct(q_pct):>12}"
        )
    lines.append("-" * 78)
    lines.append("注：微调改进 = (微调-基座)/|基座|；量化vs微调 = (量化-微调)/|微调|")
    lines.append("    质量类指标越高越好；延迟/显存越低越好（正数表示改进）")
    lines.append("")

    # 各维度质量评分
    if per_dim:
        lines.append("-" * 78)
        lines.append("多维度质量评分（0-5 分）")
        lines.append("-" * 78)
        lines.append(f"{'维度':<16}{'基座模型':>12}{'微调后':>12}{'量化后':>12}{'微调改进':>12}{'量化vs微调':>12}")
        lines.append("-" * 78)
        dim_display = [
            ("relevance",    "相关性"),
            ("accuracy",     "准确性"),
            ("completeness", "完整性"),
            ("tone",         "语气"),
            ("multilingual", "多语言"),
        ]
        for key, name in dim_display:
            d = per_dim.get(key, {})
            base = d.get("base", 0.0)
            ft = d.get("finetuned", 0.0)
            q = d.get("quantized", 0.0)
            ft_pct = d.get("improvement_ft_pct", 0.0)
            q_pct = d.get("improvement_q_pct", 0.0)
            lines.append(
                f"{name:<16}{base:>12.2f}{ft:>12.2f}{q:>12.2f}"
                f"{_fmt_pct(ft_pct):>12}{_fmt_pct(q_pct):>12}"
            )
        lines.append("-" * 78)
        lines.append("")

    # 关键结论
    lines.append("=" * 78)
    lines.append("关键结论")
    lines.append("=" * 78)
    bleu = metrics.get("bleu_4", {})
    qual = metrics.get("quality_score", {})
    lat = metrics.get("latency_ms", {})
    vram = metrics.get("vram_gb", {})

    if bleu.get("improvement_ft_pct"):
        lines.append(
            f"  1. 微调后 BLEU-4 提升 {_fmt_pct(bleu['improvement_ft_pct'])} "
            f"({bleu.get('base', 0):.4f} → {bleu.get('finetuned', 0):.4f})"
        )
    if qual.get("improvement_ft_pct"):
        lines.append(
            f"  2. 微调后质量总分提升 {_fmt_pct(qual['improvement_ft_pct'])} "
            f"({qual.get('base', 0):.2f} → {qual.get('finetuned', 0):.2f})"
        )
    if lat.get("improvement_q_pct"):
        lines.append(
            f"  3. 量化后延迟变化 {_fmt_pct(lat['improvement_q_pct'])} "
            f"({lat.get('finetuned', 0):.0f}ms → {lat.get('quantized', 0):.0f}ms)"
        )
    if vram.get("base") and vram.get("quantized"):
        lines.append(
            f"  4. 量化后显存从 {vram.get('base', 0):.1f}GB 降至 {vram.get('quantized', 0):.1f}GB"
            f"（降低 {(1 - vram.get('quantized', 0)/vram.get('base', 1))*100:.1f}%）"
        )
    lines.append("")

    return "\n".join(lines)


def format_loss_curve(curve: list[dict]) -> str:
    """格式化训练 loss 曲线数据为文本图表

    Args:
        curve: [{"step":..., "loss":..., "eval_loss":...}, ...]

    Returns:
        多行字符串，包含简易 ASCII 图表
    """
    if not curve:
        return "（无训练曲线数据）"

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("训练 Loss 曲线（示例数据）")
    lines.append("=" * 60)

    max_loss = max(max(c.get("loss", 0), c.get("eval_loss", 0)) for c in curve)
    bar_width = 40

    for point in curve:
        step = point.get("step", 0)
        loss = point.get("loss", 0.0)
        eval_loss = point.get("eval_loss", 0.0)
        # ASCII 柱状图
        loss_bar = "█" * int(loss / max_loss * bar_width) if max_loss > 0 else ""
        eval_bar = "▒" * int(eval_loss / max_loss * bar_width) if max_loss > 0 else ""
        lines.append(f"  step {step:>4} | loss={loss:.3f} {loss_bar}")
        lines.append(f"           | eval ={eval_loss:.3f} {eval_bar}")

    lines.append("")
    lines.append(f"  图例: █ train loss   ▒ eval loss   (共 {len(curve)} 个数据点)")
    lines.append("=" * 60)
    return "\n".join(lines)


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    # 直接运行：展示预置对比报告
    report = compare_models(mode="compare")
    print(format_comparison_table(report))
    if report.get("training_loss_curve"):
        print()
        print(format_loss_curve(report["training_loss_curve"]))
