"""RAG 质量评估脚本

执行完整的 RAG 质量评估流程并输出格式化报告：
    1. 加载评估测试集（backend/app/data/eval/rag_eval_dataset.json）
    2. 对每条 query 执行检索，计算 Recall@K / MRR / Precision@K / NDCG@K / Context Relevance
    3. 输出整体聚合指标 + 按意图分组 + per-query 分析
    4. 验证反幻觉机制（对样例 query 构造测试回复并校验）

用法::

    python scripts/eval_rag.py
    python scripts/eval_rag.py --ks 1 3 5 10
    python scripts/eval_rag.py --json        # 输出 JSON 格式（便于 CI 集成）
    python scripts/eval_rag.py --no-anti-hallucination   # 跳过反幻觉演示

工作目录：项目根目录 multilang-cs-platform/
"""
import argparse
import json
import os
import sys

# 把 backend 目录加入 sys.path，便于直接 import app.*
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG 质量评估脚本")
    parser.add_argument(
        "--dataset", type=str, default=None,
        help="评估数据集 JSON 路径（默认 backend/app/data/eval/rag_eval_dataset.json）",
    )
    parser.add_argument(
        "--ks", type=int, nargs="+", default=[1, 3, 5],
        help="评估 K 值列表，默认 1 3 5",
    )
    parser.add_argument(
        "--top-k", type=int, default=5,
        help="检索拉取的 top_k 数量，默认 5（应 >= max(ks)）",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="以 JSON 格式输出报告（便于 CI / 程序化处理）",
    )
    parser.add_argument(
        "--no-anti-hallucination", action="store_true",
        help="跳过反幻觉机制演示",
    )
    return parser.parse_args()


def run_evaluation(args: argparse.Namespace) -> dict:
    """执行评估并返回报告字典"""
    from app.rag.evaluator import RAGEvaluator

    evaluator = RAGEvaluator(
        dataset_path=args.dataset,
        ks=args.ks,
        top_k=args.top_k,
    )
    report = evaluator.evaluate()
    return report.model_dump()


def verify_anti_hallucination() -> dict:
    """反幻觉机制验证：对若干样例 query 构造测试回复并执行反幻觉校验

    使用规则构造的测试回复（避免依赖 LLM），覆盖三种典型场景：
        - high confidence + high faithfulness  ：正常回复
        - 含未支持事实（幻觉）              ：一致性失败
        - 低置信度（检索未命中相关文档）     ：建议转人工
    """
    from app.rag.anti_hallucination import check_reply, annotate_reply
    from app.rag.retriever import retrieve

    # 三个典型场景
    samples = [
        {
            "title": "场景 1：高置信度 + 一致性通过（正常回复）",
            "query": "退款多久能到账？",
            "reply": "商品质量问题7天内可全额退款，3-5个工作日原路退回。",
            "intent": "售后退款",
        },
        {
            "title": "场景 2：含未支持事实（幻觉）",
            "query": "蓝牙耳机续航多久？",
            "reply": "蓝牙耳机 Pro 续航 50 小时，支持主动降噪，IPX5 防水，保修期 24 个月。",
            "intent": "商品咨询",
            "note": "50 小时 / 24 个月 是编造的事实，应在校验中被识别为 unsupported",
        },
        {
            "title": "场景 3：低置信度（query 与知识库不相关）",
            "query": "今天上海天气怎么样？",
            "reply": "上海今天晴，气温 25 度。",
            "intent": "",
            "note": "query 与知识库无关，检索分数低 → should_escalate=True",
        },
    ]

    results = []
    for sample in samples:
        retrieved = retrieve(sample["query"], intent=sample["intent"], top_k=3)
        report = check_reply(
            query=sample["query"],
            retrieved_docs=retrieved,
            reply=sample["reply"],
            intent=sample["intent"],
        )
        annotated = annotate_reply(report, sample["reply"])
        results.append({
            "title": sample["title"],
            "query": sample["query"],
            "reply_original": sample["reply"],
            "reply_annotated": annotated,
            "retrieved_ids": [d.get("id") for d in retrieved],
            "report": report.model_dump(),
            "note": sample.get("note", ""),
        })
    return {"samples": results}


def main():
    args = parse_args()

    # 抑制过度详细的日志，避免污染报告输出
    from loguru import logger
    logger.remove()
    logger.add(sys.stderr, level="WARNING")

    # ---------- 1. RAG 质量评估 ----------
    report_dict = run_evaluation(args)

    if args.json:
        # JSON 输出模式
        output = {"evaluation": report_dict}
        if not args.no_anti_hallucination:
            output["anti_hallucination_check"] = verify_anti_hallucination()
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    # 文本报告模式
    from app.rag.evaluator import RAGEvaluator, EvalReport
    # 重新格式化（避免 model_dump 丢失格式化逻辑）
    evaluator = RAGEvaluator(dataset_path=args.dataset, ks=args.ks, top_k=args.top_k)
    report = evaluator.evaluate()
    print(RAGEvaluator.format_report(report))

    # ---------- 2. 反幻觉机制验证 ----------
    if not args.no_anti_hallucination:
        print()
        print("=" * 70)
        print("反幻觉机制验证 (Anti-Hallucination Check)")
        print("=" * 70)
        check_result = verify_anti_hallucination()
        for sample in check_result["samples"]:
            print()
            print("-" * 70)
            print(f"【{sample['title']}】")
            print(f"  Query        : {sample['query']}")
            print(f"  原始回复     : {sample['reply_original']}")
            print(f"  标注后回复   : {sample['reply_annotated']}")
            print(f"  检索文档     : {sample['retrieved_ids']}")
            r = sample["report"]
            print(f"  置信度       : {r['confidence']:.4f} ({r['confidence_level']})")
            print(f"  一致性       : {r['faithfulness']:.4f} (passed={r['faithfulness_passed']})")
            print(f"  幻觉风险     : {r['hallucination_risk']}")
            print(f"  建议转人工   : {r['should_escalate']}")
            print(f"  抽取事实     : {r['facts_extracted']}")
            print(f"  支持事实     : {r['facts_supported']}")
            print(f"  未支持事实   : {r['facts_unsupported']}")
            print(f"  风险原因     : {r['risks']}")
            if sample["note"]:
                print(f"  说明         : {sample['note']}")
            print(f"  引用溯源     : ")
            for c in r["citations"]:
                snippet = c["content_snippet"][:80].replace("\n", " ")
                print(f"    - {c['doc_id']} (score={c['score']:.4f}): {snippet}...")
        print("=" * 70)


if __name__ == "__main__":
    main()
