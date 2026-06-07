#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
SKILL_DIR = os.path.join(REPO_ROOT, "skills", "tonebarrier")
DFA_FILTER = os.path.join(SKILL_DIR, "scripts", "dfa_filter.py")
CASES_PATH = os.path.join(SCRIPT_DIR, "adversary_cases.json")
RESULTS_PATH = os.path.join(SCRIPT_DIR, "run_results.json")


def load_cases():
    if not os.path.exists(CASES_PATH):
        print(f"错误: 找不到 {CASES_PATH}")
        sys.exit(1)
    with open(CASES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


def run_dfa(text):
    try:
        result = subprocess.run(
            ["python3", DFA_FILTER],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=10,
        )
        stdout = result.stdout.decode("utf-8").strip()
        if not stdout:
            return False, []
        data = json.loads(stdout)
        if "error" in data:
            return False, []
        has_profanity = data.get("has_profanity", False)
        matches = [m["word"] for m in data.get("matches", [])]
        return has_profanity, matches
    except Exception:
        return False, []


def simulate_skill_output(case):
    level = case["expected_level"]
    if level <= 2:
        emotion_line = "客户情绪平稳，正常诉求" if level == 1 else "客户有轻微不满"
        sanitized = case["input"]
    elif level == 3:
        emotion_line = "客户情绪愤怒，建议优先处理"
        sanitized = "[pending_llm_eval]"
    else:
        emotion_line = "客户情绪激烈，含攻击性语言 — 以下为过滤后内容"
        sanitized = "[pending_llm_eval]"
    return {
        "emotion_line": emotion_line,
        "sanitized": sanitized,
        "pending_llm": True,
    }


def phase1_dfa(cases):
    results = []
    for case in cases:
        dfa_hit, dfa_matches = run_dfa(case["input"])
        dfa_expected = case.get("expected_dfa_hit", False)
        dfa_correct = dfa_hit == dfa_expected
        results.append({
            "id": case["id"],
            "category": case["category"],
            "input": case["input"],
            "source_word": case["source_word"],
            "variant": case["variant"],
            "expected_level": case["expected_level"],
            "dfa_hit": dfa_hit,
            "dfa_expected": dfa_expected,
            "dfa_correct": dfa_correct,
            "dfa_matches": dfa_matches,
            "dfa_match_count": len(dfa_matches),
        })
    return results


def phase2_skill(results):
    for r in results:
        case = {
            "id": r["id"],
            "category": r["category"],
            "input": r["input"],
            "expected_level": r["expected_level"],
        }
        skill = simulate_skill_output(case)
        r["skill_emotion_line"] = skill["emotion_line"]
        r["skill_sanitized"] = skill["sanitized"]
        r["pending_llm"] = skill["pending_llm"]
    return results


def phase3_scoring(results):
    for r in results:
        r["rule_metrics"] = {
            "dfa_detection_correct": r["dfa_correct"],
            "pending_llm": r["pending_llm"],
        }
    return results


def run_all(cases):
    results = phase1_dfa(cases)
    results = phase2_skill(results)
    results = phase3_scoring(results)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"已保存 {len(results)} 条结果到 {RESULTS_PATH}")
    return results


def print_report():
    if not os.path.exists(RESULTS_PATH):
        print(f"错误: 找不到 {RESULTS_PATH}，请先运行 python3 run_adversary.py")
        sys.exit(1)
    with open(RESULTS_PATH, encoding="utf-8") as f:
        results = json.load(f)

    groups = defaultdict(list)
    for r in results:
        groups[r["category"]].append(r)

    category_order = [
        "format_bypass", "homophone", "leet", "cnen_mix",
        "pinyin_mix", "sarcasm", "en_dfa_miss", "normal",
    ]

    header = f"{'Category':<22} {'Cases':>6} {'DFA_Hit%':>9} {'DFA_Expected%':>14} {'Pending_LLM':>12}"
    sep = "-" * len(header)

    print(sep)
    print(header)
    print(sep)

    total_cases = 0
    total_dfa_hit = 0
    total_dfa_expected = 0
    total_pending = 0

    for cat in category_order:
        group = groups.get(cat, [])
        if not group:
            continue
        n = len(group)
        dfa_hit_n = sum(1 for r in group if r["dfa_hit"])
        dfa_exp_n = sum(1 for r in group if r["dfa_expected"])
        pending_n = sum(1 for r in group if r["pending_llm"])

        hit_pct = dfa_hit_n / n * 100 if n else 0
        exp_pct = dfa_exp_n / n * 100 if n else 0

        print(f"{cat:<22} {n:>6} {hit_pct:>8.1f}% {exp_pct:>13.1f}% {pending_n:>12}")

        total_cases += n
        total_dfa_hit += dfa_hit_n
        total_dfa_expected += dfa_exp_n
        total_pending += pending_n

    print(sep)
    total_hit_pct = total_dfa_hit / total_cases * 100 if total_cases else 0
    total_exp_pct = total_dfa_expected / total_cases * 100 if total_cases else 0
    print(f"{'TOTAL':<22} {total_cases:>6} {total_hit_pct:>8.1f}% {total_exp_pct:>13.1f}% {total_pending:>12}")
    print(sep)

    dfa_correct_n = sum(1 for r in results if r["dfa_correct"])
    dfa_accuracy = dfa_correct_n / total_cases * 100 if total_cases else 0
    print(f"\nDFA 预期一致率 (dfa_correct): {dfa_correct_n}/{total_cases} = {dfa_accuracy:.1f}%")

    cats_with_details = []
    for cat in category_order:
        group = groups.get(cat, [])
        if not group:
            continue
        n = len(group)
        correct = sum(1 for r in group if r["dfa_correct"])
        false_pos = sum(1 for r in group if r["dfa_hit"] and not r["dfa_expected"])
        false_neg = sum(1 for r in group if not r["dfa_hit"] and r["dfa_expected"])
        cats_with_details.append((cat, n, correct, false_pos, false_neg))

    print(f"\n{'Category':<22} {'Cases':>6} {'DFA正确':>8} {'假阳性':>6} {'假阴性':>6} {'正确率':>8}")
    print("-" * 62)
    for cat, n, correct, fp, fn in cats_with_details:
        rate = correct / n * 100 if n else 0
        print(f"{cat:<22} {n:>6} {correct:>8} {fp:>6} {fn:>6} {rate:>7.1f}%")
    print("-" * 62)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--report":
        print_report()
        return

    cases = load_cases()
    print(f"加载 {len(cases)} 条对抗测试用例")

    results = run_all(cases)

    print_report()


if __name__ == "__main__":
    main()
