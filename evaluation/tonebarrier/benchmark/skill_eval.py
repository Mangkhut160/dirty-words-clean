#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
SKILL_DIR = os.path.join(REPO_ROOT, "skills", "tonebarrier")
VALIDATOR_PATH = os.path.join(SKILL_DIR, "scripts", "validator.py")
EVAL_CASES_PATH = os.path.join(SCRIPT_DIR, "eval_cases.json")
RESULTS_OUTPUT_PATH = os.path.join(SCRIPT_DIR, "skill_results.json")

EMOTION_TAG_RE = re.compile(r"^\[情绪判断\]\s*(.+)$", re.MULTILINE)
DFA_LINE_RE = re.compile(r"^DFA\s", re.MULTILINE)


def parse_skill_output(output_text):
    if not output_text or not output_text.strip():
        return {
            "level": None,
            "sanitized": "",
            "format_valid": False,
            "error": "empty output",
        }

    tag_match = EMOTION_TAG_RE.search(output_text)
    if not tag_match:
        return {
            "level": None,
            "sanitized": output_text.strip(),
            "format_valid": False,
            "error": "missing [情绪判断] tag",
        }

    tag_text = tag_match.group(1)
    if "情绪平稳" in tag_text:
        level = 1
    elif "轻微不满" in tag_text:
        level = 2
    elif "情绪愤怒" in tag_text:
        level = 3
    elif "情绪激烈" in tag_text:
        level = 4
    else:
        return {
            "level": None,
            "sanitized": output_text.strip(),
            "format_valid": False,
            "error": f"unrecognized emotion tag: {tag_text[:50]}",
        }

    tag_end = tag_match.end()
    remaining = output_text[tag_end:].strip()

    lines = remaining.split("\n")
    content_lines = []
    for line in lines:
        stripped = line.strip()
        if DFA_LINE_RE.match(stripped):
            continue
        content_lines.append(line)

    sanitized = "\n".join(content_lines).strip()

    return {
        "level": level,
        "sanitized": sanitized,
        "format_valid": True,
        "error": None,
    }


def check_entity_preservation(original, sanitized):
    payload = json.dumps({"original": original, "sanitized": sanitized})
    try:
        result = subprocess.run(
            ["python3", VALIDATOR_PATH],
            input=payload.encode("utf-8"),
            capture_output=True,
            timeout=10,
        )
        return json.loads(result.stdout.decode("utf-8"))
    except Exception as e:
        return {"passed": False, "error": str(e), "original_entity_count": 0, "preserved_count": 0, "lost_count": 0, "lost_entities": []}


def print_eval_prompts(cases):
    for i, case in enumerate(cases, 1):
        entities_str = ", ".join(case["entities"][:8])
        if len(case["entities"]) > 8:
            entities_str += f" ... (+{len(case['entities']) - 8})"

        print(f"{'=' * 70}")
        print(f"[{i:02d}/{len(cases):02d}] {case['id']} | source={case['source']} | expected_level={case['expected_level']} | entities=[{entities_str}]")
        print(f"{'=' * 70}")
        print(case["input"])
        print()
    print(f"{'=' * 70}")
    print(f"Total: {len(cases)} cases")


def validate_results(cases, results_path):
    with open(results_path, encoding="utf-8") as f:
        results = json.load(f)

    case_map = {c["id"]: c for c in cases}
    results_map = {}
    for r in results:
        results_map[r["id"]] = r

    emotion_correct = 0
    entity_pass = 0
    format_ok = 0
    passthrough_correct = 0
    passthrough_total = 0
    total_matched = 0
    errors = []

    confusion = [[0] * 4 for _ in range(4)]

    detail_results = []

    for case in cases:
        case_id = case["id"]
        expected_level = case["expected_level"]
        expected_entities = case.get("entity_count", 0)

        if case_id not in results_map:
            errors.append(f"{case_id}: missing in results file")
            continue

        result = results_map[case_id]
        skill_output = result.get("skill_output", "")
        parsed = parse_skill_output(skill_output)
        predicted_level = parsed["level"]
        sanitized = parsed["sanitized"]
        is_format_valid = parsed["format_valid"]

        total_matched += 1
        if is_format_valid:
            format_ok += 1
        else:
            errors.append(f"{case_id}: format invalid - {parsed.get('error', 'unknown')}")

        if predicted_level == expected_level:
            emotion_correct += 1

        if predicted_level is not None and 1 <= predicted_level <= 4 and 1 <= expected_level <= 4:
            confusion[predicted_level - 1][expected_level - 1] += 1

        validator_result = check_entity_preservation(case["input"], sanitized)
        entity_ok = validator_result.get("passed", False)
        if entity_ok:
            entity_pass += 1
        else:
            lost = validator_result.get("lost_entities", [])
            errors.append(f"{case_id}: entity check failed - lost {validator_result.get('lost_count', 0)} entities: {lost[:5]}")

        if expected_level <= 2:
            passthrough_total += 1
            if case["input"].strip() == sanitized.strip():
                passthrough_correct += 1
            else:
                errors.append(f"{case_id}: expected passthrough (level={expected_level}) but text was modified")

        detail_results.append({
            "id": case_id,
            "expected_level": expected_level,
            "predicted_level": predicted_level,
            "format_valid": is_format_valid,
            "entity_passed": entity_ok,
            "entity_detail": {
                "original_count": validator_result.get("original_entity_count", 0),
                "preserved_count": validator_result.get("preserved_count", 0),
                "lost_count": validator_result.get("lost_count", 0),
            },
        })

    total_cases = len(cases)
    missing_count = total_cases - total_matched

    # Count missing cases with level <= 2 as passthrough failures
    for case in cases:
        if case["id"] not in results_map and case.get("expected_level", 99) <= 2:
            passthrough_total += 1

    coverage_rate = total_matched / total_cases if total_cases > 0 else 0.0

    emotion_accuracy = emotion_correct / total_cases if total_cases > 0 else 0.0
    entity_pass_rate = entity_pass / total_cases if total_cases > 0 else 0.0
    format_compliance = format_ok / total_cases if total_cases > 0 else 0.0
    passthrough_rate = passthrough_correct / passthrough_total if passthrough_total > 0 else 0.0

    output = {
        "summary": {
            "total_cases": total_cases,
            "matched_results": total_matched,
            "missing_results": missing_count,
            "coverage_rate": round(coverage_rate, 4),
            "emotion_accuracy": round(emotion_accuracy, 4),
            "entity_pass_rate": round(entity_pass_rate, 4),
            "format_compliance": round(format_compliance, 4),
            "passthrough_rate": round(passthrough_rate, 4),
        },
        "emotion_confusion": {
            "matrix": confusion,
            "labels": ["level_1", "level_2", "level_3", "level_4"],
        },
        "errors": errors,
        "details": detail_results,
    }

    with open(RESULTS_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Validation complete. {total_matched}/{total_cases} cases matched ({coverage_rate:.2%}).")
    print(f"  Emotion accuracy:  {emotion_accuracy:.2%}")
    print(f"  Entity pass rate:  {entity_pass_rate:.2%}")
    print(f"  Format compliance: {format_compliance:.2%}")
    print(f"  Passthrough rate:  {passthrough_rate:.2%}")
    print(f"  Errors: {len(errors)}")
    print(f"  Confusion matrix (rows=predicted, cols=expected):")
    print("          L1   L2   L3   L4")
    for i, row in enumerate(confusion):
        print(f"    L{i+1}:  {row[0]:3d}  {row[1]:3d}  {row[2]:3d}  {row[3]:3d}")
    print(f"Results saved to {RESULTS_OUTPUT_PATH}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 skill_eval.py prompts                  → print evaluation prompts (sampled_30)")
        print("  python3 skill_eval.py prompts --full           → print evaluation prompts (full 90)")
        print("  python3 skill_eval.py validate results.json    → validate LLM outputs (sampled_30)")
        print("  python3 skill_eval.py validate results.json --full → validate LLM outputs (full 90)")
        sys.exit(1)

    command = sys.argv[1]
    use_full = "--full" in sys.argv

    with open(EVAL_CASES_PATH, encoding="utf-8") as f:
        eval_data = json.load(f)

    if use_full:
        cases = eval_data["full"]
        mode = "full"
    else:
        cases = eval_data.get("sampled_30", eval_data["full"])
        mode = "sample"

    if command == "prompts":
        print(f"模式: {mode} ({len(cases)} 条)")
        print_eval_prompts(cases)

    elif command == "validate":
        if len(sys.argv) < 3:
            print("Error: validate requires a results.json path")
            sys.exit(1)
        results_path = sys.argv[2]
        print(f"模式: {mode} ({len(cases)} 条)")
        validate_results(cases, results_path)

    else:
        print(f"Unknown command: {command}")
        print("Usage: python3 skill_eval.py prompts|validate [--full]")
        sys.exit(1)


if __name__ == "__main__":
    main()
