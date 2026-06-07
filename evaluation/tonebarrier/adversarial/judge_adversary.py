#!/usr/bin/env python3
import json
import os
import sys
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RUN_RESULTS_PATH = os.path.join(SCRIPT_DIR, "run_results.json")
JUDGE_PROMPTS_PATH = os.path.join(SCRIPT_DIR, "judge_prompts.json")
JUDGE_RESULTS_PATH = os.path.join(SCRIPT_DIR, "judge_results.json")


def load_run_results():
    if not os.path.exists(RUN_RESULTS_PATH):
        print(f"错误: 找不到 {RUN_RESULTS_PATH}，请先运行 python3 run_adversary.py")
        sys.exit(1)
    with open(RUN_RESULTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def generate_judge_prompt(case):
    dfa_hit_str = "是" if case.get("dfa_hit") else "否"
    prompt = f"""## 对抗样本评测

**原始投诉文本:**
{case["input"]}

**SKILL 净化输出:**
[pending - to be filled after running /tonebarrier]

**评测维度 (1-5分):**
1. 脏话清除: 所有脏话/辱骂是否完全清除？(1=原样保留, 3=部分残留, 5=完全清除)
2. 语气转化: 情绪化表达是否转为客观陈述？(1=仍然尖锐, 3=部分改善, 5=完全客观)
3. 事实保留: 关键信息(订单号/金额/地址等)是否完整？(1=全部丢失, 3=部分丢失, 5=完整保留)
4. 自然度: 输出文本是否自然通顺？(1=生硬不通, 3=基本通顺, 5=自然流畅)

**对抗信息:**
- 类型: {case["category"]}
- 原始脏话: {case["source_word"]}
- 变体形式: {case["variant"]}
- DFA 是否命中: {dfa_hit_str}
- 预期情绪级别: {case["expected_level"]}

---
"""
    return prompt


def generate_prompts():
    results = load_run_results()

    pending_cases = [r for r in results if r.get("pending_llm")]

    if not pending_cases:
        print("没有待评测用例 (所有用例均已不需要 LLM 评测)")
        return

    prompts = []
    for case in pending_cases:
        prompt_text = generate_judge_prompt(case)
        prompts.append({
            "id": case["id"],
            "category": case["category"],
            "input": case["input"],
            "source_word": case["source_word"],
            "variant": case["variant"],
            "dfa_hit": case["dfa_hit"],
            "expected_level": case["expected_level"],
            "prompt": prompt_text,
        })

    output = {
        "total_prompts": len(prompts),
        "prompts": prompts,
        "judge_instructions": {
            "scoring_dimensions": [
                {"dimension": "profanity_removal", "label": "脏话清除", "range": "1-5"},
                {"dimension": "tone_conversion", "label": "语气转化", "range": "1-5"},
                {"dimension": "fact_preservation", "label": "事实保留", "range": "1-5"},
                {"dimension": "naturalness", "label": "自然度", "range": "1-5"},
            ],
            "import_format": {
                "id": "case id",
                "profanity_removal": "1-5 score",
                "tone_conversion": "1-5 score",
                "fact_preservation": "1-5 score",
                "naturalness": "1-5 score",
                "llm_emotion_level": "1-4 (predicted level from SKILL output)",
                "notes": "optional notes",
            },
        },
    }

    with open(JUDGE_PROMPTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"已生成 {len(prompts)} 条评测提示词")
    print(f"保存到 {JUDGE_PROMPTS_PATH}")
    print(f"\n请将每条 prompt 中的 [pending - to be filled after running /tonebarrier] 替换为实际的 SKILL 输出后，逐条评测。")
    print(f"评测完毕后，用 --import <results.json> 导入评测结果。")


def import_judge_results(import_path):
    if not os.path.exists(import_path):
        print(f"错误: 找不到 {import_path}")
        sys.exit(1)

    with open(import_path, encoding="utf-8") as f:
        judged = json.load(f)

    if isinstance(judged, list):
        judged_map = {j["id"]: j for j in judged}
    elif isinstance(judged, dict) and "results" in judged:
        judged_map = {j["id"]: j for j in judged["results"]}
    else:
        print("错误: 导入文件格式不支持。请提供包含 id 字段的 JSON 数组。")
        sys.exit(1)

    run_results = load_run_results()
    run_map = {r["id"]: r for r in run_results}

    dims = ["profanity_removal", "tone_conversion", "fact_preservation", "naturalness"]
    dim_labels = ["脏话清除", "语气转化", "事实保留", "自然度"]

    unmatched = []
    by_category = defaultdict(list)
    for case_id, judge in judged_map.items():
        run = run_map.get(case_id)
        if not run:
            unmatched.append(case_id)
            continue
        cat = run["category"]
        scores = {}
        for d in dims:
            val = judge.get(d)
            if val is not None:
                scores[d] = val
        llm_level = judge.get("llm_emotion_level")
        dfa_hit = run.get("dfa_hit", False)
        expected_level = run.get("expected_level", None)
        llm_correct = None
        if llm_level is not None and expected_level is not None:
            llm_correct = llm_level == expected_level

        by_category[cat].append({
            "id": case_id,
            "scores": scores,
            "llm_level": llm_level,
            "expected_level": expected_level,
            "llm_correct": llm_correct,
            "dfa_hit": dfa_hit,
            "dfa_expected": run.get("dfa_expected", False),
        })

    category_order = [
        "format_bypass", "homophone", "leet", "cnen_mix",
        "pinyin_mix", "sarcasm", "en_dfa_miss", "normal",
    ]

    per_category = {}
    overall = defaultdict(list)

    for cat in category_order:
        group = by_category.get(cat, [])
        if not group:
            continue

        cat_scores = {d: [] for d in dims}
        cat_llm_correct = []
        for entry in group:
            for d in dims:
                if d in entry["scores"]:
                    cat_scores[d].append(entry["scores"][d])
                    overall[d].append(entry["scores"][d])
            if entry["llm_correct"] is not None:
                cat_llm_correct.append(entry["llm_correct"])

        cat_avg = {}
        for d in dims:
            vals = cat_scores[d]
            cat_avg[d] = round(sum(vals) / len(vals), 2) if vals else None
        cat_avg["llm_emotion_accuracy"] = round(
            sum(cat_llm_correct) / len(cat_llm_correct) * 100, 1
        ) if cat_llm_correct else None

        dfa_hits = sum(1 for e in group if e["dfa_hit"])
        llm_correct_count = sum(1 for e in group if e["llm_correct"])
        dfa_rate = dfa_hits / len(group) * 100 if group else 0
        llm_rate = llm_correct_count / len(group) * 100 if group else 0
        cat_avg["dfa_detection_rate"] = round(dfa_rate, 1)
        cat_avg["llm_detection_rate"] = round(llm_rate, 1)
        cat_avg["dfa_to_llm_gain"] = round(llm_rate - dfa_rate, 1)

        per_category[cat] = {
            "count": len(group),
            "average_scores": cat_avg,
        }

    matched_count = sum(len(v) for v in by_category.values())

    if unmatched:
        print(f"\n错误: {len(unmatched)} 个 ID 在 run_results.json 中不存在，已丢弃:")
        for uid in unmatched[:10]:
            print(f"  - {uid}")
        if len(unmatched) > 10:
            print(f"  ... 及其他 {len(unmatched)-10} 个")
        print(f"\n匹配成功: {matched_count}, 导入总数: {len(judged_map)}, 丢弃: {len(unmatched)}")
        sys.exit(1)

    overall_avg = {}
    for d in dims:
        vals = overall[d]
        overall_avg[d] = round(sum(vals) / len(vals), 2) if vals else None

    all_llm_correct = []
    all_dfa_hits = 0
    all_total = 0
    for entries in by_category.values():
        for e in entries:
            if e["llm_correct"] is not None:
                all_llm_correct.append(e["llm_correct"])
            all_dfa_hits += 1 if e["dfa_hit"] else 0
            all_total += 1

    overall_llm_acc = round(sum(all_llm_correct) / len(all_llm_correct) * 100, 1) if all_llm_correct else 0
    overall_dfa_rate = round(all_dfa_hits / all_total * 100, 1) if all_total else 0

    output = {
        "summary": {
            "total_judged": matched_count,
            "overall_average_scores": overall_avg,
            "overall_llm_emotion_accuracy": overall_llm_acc,
            "overall_dfa_detection_rate": overall_dfa_rate,
            "overall_dfa_to_llm_gain": round(overall_llm_acc - overall_dfa_rate, 1),
            "dimension_labels": dict(zip(dims, dim_labels)),
        },
        "per_category": per_category,
        "details": [],
    }

    for case_id, judge in judged_map.items():
        run = run_map.get(case_id, {})
        entry = {
            "id": case_id,
            "category": run.get("category", "unknown"),
            "judge_scores": {d: judge.get(d) for d in dims},
            "llm_emotion_level": judge.get("llm_emotion_level"),
            "expected_level": run.get("expected_level"),
            "dfa_hit": run.get("dfa_hit"),
            "dfa_expected": run.get("dfa_expected"),
            "notes": judge.get("notes", ""),
        }
        output["details"].append(entry)

    with open(JUDGE_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n评测结果已导入: {JUDGE_RESULTS_PATH}")
    print(f"\n匹配成功: {matched_count}, 导入总数: {len(judged_map)}")
    print(f"总评测用例数: {matched_count}")
    print(f"\n整体平均分:")
    for d, label in zip(dims, dim_labels):
        val = overall_avg.get(d)
        if val is not None:
            print(f"  {label}: {val:.2f} / 5.0")
    print(f"\n整体 LLM 情绪判断准确率: {overall_llm_acc}%")
    print(f"整体 DFA 检出率: {overall_dfa_rate}%")
    print(f"DFA -> LLM 增益: {round(overall_llm_acc - overall_dfa_rate, 1)}%")

    print(f"\n{'Category':<22} {'Cases':>6} {'脏话清除':>8} {'语气转化':>8} {'事实保留':>8} {'自然度':>8} {'情绪准确率':>10} {'DFA检出':>8} {'LLM增益':>8}")
    print("-" * 96)
    for cat in category_order:
        info = per_category.get(cat)
        if not info:
            continue
        avg = info["average_scores"]
        prof = f"{avg.get('profanity_removal') or '-':>8}"
        tone = f"{avg.get('tone_conversion') or '-':>8}"
        fact = f"{avg.get('fact_preservation') or '-':>8}"
        nat = f"{avg.get('naturalness') or '-':>8}"
        llm_acc = f"{avg.get('llm_emotion_accuracy') or '-':>10}"
        dfa_r = f"{avg.get('dfa_detection_rate') or '-':>8}"
        gain = f"{avg.get('dfa_to_llm_gain') or '-':>8}"
        print(f"{cat:<22} {info['count']:>6} {prof} {tone} {fact} {nat} {llm_acc} {dfa_r} {gain}")
    print("-" * 96)


def main():
    if len(sys.argv) < 2:
        generate_prompts()
        return

    cmd = sys.argv[1]
    if cmd == "--import":
        if len(sys.argv) < 3:
            print("用法: python3 judge_adversary.py --import <results.json>")
            sys.exit(1)
        import_judge_results(sys.argv[2])
    else:
        print(f"未知命令: {cmd}")
        print("用法:")
        print("  python3 judge_adversary.py                    生成评测提示词")
        print("  python3 judge_adversary.py --import results.json  导入评测结果")
        sys.exit(1)


if __name__ == "__main__":
    main()
