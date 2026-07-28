"""反幻觉效果对比测试

对比开启 vs 关闭反幻觉校验的回复质量差异。
使用真实 DeepSeek API + RAG 检索，测试同一批 query 在两种模式下的表现。
"""
import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.rag.retriever import retrieve
from app.rag.anti_hallucination import AntiHallucinationChecker
from app.services.llm_service import chat_completion, is_vllm_available
from app.rag.prompts import build_suggest_prompt

# 测试用例：包含易产生幻觉的场景（数字/政策/规格）
TEST_CASES = [
    {
        "query": "蓝牙耳机的续航时间是多少小时？支持保修吗？",
        "lang": "zh",
        "intent": "商品咨询",
        "expected_facts": ["32小时", "12个月"],
        "note": "事实型查询，答案应在知识库中"
    },
    {
        "query": "退款多久到账？非质量问题怎么处理？",
        "lang": "zh",
        "intent": "售后退款",
        "expected_facts": ["3-5个工作日", "扣除运费"],
        "note": "政策型查询，需准确引用退款政策"
    },
    {
        "query": "智能手表支持血氧监测吗？防水等级是多少？",
        "lang": "zh",
        "intent": "商品咨询",
        "expected_facts": ["血氧", "IP68"],
        "note": "规格型查询，需准确引用产品参数"
    },
    {
        "query": "充电宝可以带上飞机吗？支持给笔记本充电吗？",
        "lang": "zh",
        "intent": "商品咨询",
        "expected_facts": ["航班允许", "PD 65W"],
        "note": "规格型查询，涉及合规和参数"
    },
    {
        "query": "跨境订单的关税由谁承担？有免税额度吗？",
        "lang": "zh",
        "intent": "合规政策",
        "expected_facts": ["收件人承担", "免税"],
        "note": "政策型查询，需准确引用关税政策"
    },
    {
        "query": "How long does the battery last for the earphones? What is the warranty period?",
        "lang": "en",
        "intent": "商品咨询",
        "expected_facts": ["32-hour", "12-month"],
        "note": "英文事实型查询"
    },
    {
        "query": "这台投影仪的分辨率是多少？支持4K吗？",
        "lang": "zh",
        "intent": "商品咨询",
        "expected_facts": ["1080P", "4K"],
        "note": "规格型查询"
    },
    {
        "query": "机械键盘是什么轴体？续航多久？",
        "lang": "zh",
        "intent": "商品咨询",
        "expected_facts": ["红轴", "90天"],
        "note": "规格型查询，需准确引用参数"
    },
]


def generate_reply_with_rag(query, lang, intent, enable_anti_halluc=True):
    """生成回复，可选择是否启用反幻觉校验"""
    docs = retrieve(query, lang=lang, top_k=3)
    sources = [{"id": d.get("id", ""), "content": d.get("content", "")[:100], "score": d.get("score", 0)} for d in docs]

    context = "\n".join([d.get("content", "") for d in docs])
    prompt = build_suggest_prompt(query, context, intent, lang)

    reply = chat_completion(prompt, max_tokens=300, temperature=0.3)

    anti_halluc_report = None
    if enable_anti_halluc and docs:
        checker = AntiHallucinationChecker()
        anti_halluc_report = checker.check(
            query=query,
            intent=intent,
            retrieved_docs=docs,
            reply=reply
        )

    return {
        "reply": reply,
        "sources": sources,
        "anti_hallucination_report": anti_halluc_report.model_dump() if anti_halluc_report else None,
    }


def evaluate_factual_accuracy(reply, expected_facts):
    """评估事实准确性：检查回复是否包含预期事实"""
    reply_lower = reply.lower()
    hits = 0
    details = []
    for fact in expected_facts:
        fact_lower = fact.lower()
        found = fact_lower in reply_lower
        if found:
            hits += 1
        details.append({"fact": fact, "found": found})
    accuracy = hits / len(expected_facts) if expected_facts else 0
    return {"accuracy": accuracy, "hits": hits, "total": len(expected_facts), "details": details}


def main():
    print("=" * 80)
    print("Anti-Hallucination Effect Comparison Test")
    print("=" * 80)
    print("LLM available: " + str(is_vllm_available()))
    print("Test cases: " + str(len(TEST_CASES)))
    print()

    results_with = []
    results_without = []

    for i, tc in enumerate(TEST_CASES, 1):
        print("\n[" + str(i) + "/" + str(len(TEST_CASES)) + "] " + tc["note"])
        print("  Query: " + tc["query"][:60] + "...")
        print("  Expected facts: " + str(tc["expected_facts"]))

        try:
            r_with = generate_reply_with_rag(tc["query"], tc["lang"], tc["intent"], enable_anti_halluc=True)
            acc_with = evaluate_factual_accuracy(r_with["reply"], tc["expected_facts"])
            ah = r_with.get("anti_hallucination_report", {})
            risk = ah.get("risk_level", "N/A") if ah else "N/A"
            conf = ah.get("confidence", 0) if ah else 0
            print("  [WITH anti-halluc] accuracy=" + str(round(acc_with["accuracy"], 2)) + " risk=" + str(risk) + " conf=" + str(round(conf, 2)))
            print("    Reply: " + r_with["reply"][:100] + "...")
            results_with.append({
                "query": tc["query"],
                "accuracy": acc_with["accuracy"],
                "risk_level": risk,
                "confidence": conf,
                "reply_preview": r_with["reply"][:150],
                "fact_details": acc_with["details"],
            })
        except Exception as e:
            print("  [WITH anti-halluc] ERROR: " + str(e))
            results_with.append({"query": tc["query"], "accuracy": 0, "error": str(e)})

        time.sleep(1)

        try:
            r_without = generate_reply_with_rag(tc["query"], tc["lang"], tc["intent"], enable_anti_halluc=False)
            acc_without = evaluate_factual_accuracy(r_without["reply"], tc["expected_facts"])
            print("  [WITHOUT anti-halluc] accuracy=" + str(round(acc_without["accuracy"], 2)))
            print("    Reply: " + r_without["reply"][:100] + "...")
            results_without.append({
                "query": tc["query"],
                "accuracy": acc_without["accuracy"],
                "reply_preview": r_without["reply"][:150],
                "fact_details": acc_without["details"],
            })
        except Exception as e:
            print("  [WITHOUT anti-halluc] ERROR: " + str(e))
            results_without.append({"query": tc["query"], "accuracy": 0, "error": str(e)})

        time.sleep(1)

    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)

    valid_with = [r for r in results_with if "error" not in r]
    valid_without = [r for r in results_without if "error" not in r]

    avg_acc_with = sum(r["accuracy"] for r in valid_with) / len(valid_with) if valid_with else 0
    avg_acc_without = sum(r["accuracy"] for r in valid_without) / len(valid_without) if valid_without else 0

    risk_dist = {}
    for r in valid_with:
        risk = r.get("risk_level", "unknown")
        risk_dist[risk] = risk_dist.get(risk, 0) + 1

    print("\nMetric                  With           Without        Diff")
    print("-" * 60)
    print("Avg factual accuracy    " + str(round(avg_acc_with, 2)) + "             " + str(round(avg_acc_without, 2)) + "             " + str(round(avg_acc_with - avg_acc_without, 2)))
    print("Valid cases             " + str(len(valid_with)) + "              " + str(len(valid_without)))
    print("Risk distribution       " + str(risk_dist))

    print("\n--- Per-case comparison ---")
    print("#    With   Without  Risk     Query")
    print("-" * 80)
    for i, (rw, rwo) in enumerate(zip(results_with, results_without), 1):
        acc_w = rw.get("accuracy", 0)
        acc_wo = rwo.get("accuracy", 0)
        risk = rw.get("risk_level", "N/A")
        query = rw.get("query", "")[:40]
        print(str(i).ljust(5) + str(round(acc_w, 2)).ljust(7) + str(round(acc_wo, 2)).ljust(9) + str(risk).ljust(9) + query)

    output = {
        "summary": {
            "total_cases": len(TEST_CASES),
            "avg_accuracy_with_anti_halluc": round(avg_acc_with, 4),
            "avg_accuracy_without_anti_halluc": round(avg_acc_without, 4),
            "accuracy_improvement": round(avg_acc_with - avg_acc_without, 4),
            "risk_distribution": risk_dist,
        },
        "details_with": results_with,
        "details_without": results_without,
    }

    output_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "eval", "anti_halluc_comparison.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\nResults saved: " + output_path)

    print("\n" + "=" * 80)
    print("Test complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
