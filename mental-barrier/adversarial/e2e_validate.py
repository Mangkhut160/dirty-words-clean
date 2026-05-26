#!/usr/bin/env python3
"""
端到端验证脚本 — 验证 /mental-barrier SKILL 的 LLM 输出质量。

从 llm_outputs.json 加载 SKILL 实际输出，对照 adversary_cases.json 的
预期标签，逐项检查情绪判断准确率、脏话清除率、实体保留率和 DFA→LLM 增益。

用法：
    python3 e2e_validate.py <llm_outputs.json>

输入格式（llm_outputs.json）：
    [{"id": "case_id", "skill_output": "full /mental-barrier output text"}, ...]

输出：
    - 终端打印汇总表
    - 保存 e2e_results.json（与输入文件同目录）

纯 Python 标准库实现，零外部依赖。
"""
import json
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(SCRIPT_DIR, "..")
ADVERSARY_CASES = os.path.join(SCRIPT_DIR, "adversary_cases.json")
VALIDATOR = os.path.join(SKILL_DIR, "scripts", "validator.py")
DFA_FILTER = os.path.join(SKILL_DIR, "scripts", "dfa_filter.py")

# 质量门禁阈值
COVERAGE_THRESHOLD = 0.50      # 覆盖率：至少 50% 的用例有 LLM 输出
EMOTION_THRESHOLD = 0.60       # 情绪准确率：至少 60%
PROFANITY_THRESHOLD = 0.85     # 脏话清除率：至少 85%
ENTITY_THRESHOLD = 0.90        # 实体保留率：至少 90%
FORMAT_THRESHOLD = 0.90        # 格式合规率：至少 90%


# ---------------------------------------------------------------------------
# 子进程调用
# ---------------------------------------------------------------------------

def run_dfa(text):
    """调用 dfa_filter.py，返回解析后的 JSON 输出。"""
    result = subprocess.run(
        ["python3", DFA_FILTER],
        input=text.encode("utf-8"),
        capture_output=True,
        timeout=30,
    )
    return json.loads(result.stdout.decode("utf-8"))


def run_validator(original, sanitized):
    """调用 validator.py，返回解析后的 JSON 输出。"""
    payload = json.dumps({"original": original, "sanitized": sanitized})
    result = subprocess.run(
        ["python3", VALIDATOR],
        input=payload.encode("utf-8"),
        capture_output=True,
        timeout=30,
    )
    return json.loads(result.stdout.decode("utf-8"))


# ---------------------------------------------------------------------------
# 解析函数
# ---------------------------------------------------------------------------

def parse_skill_output(text):
    """从 /mental-barrier 输出文本中解析情绪级别和净化文本。

    返回 dict:
        {
            "level": int | None,      # 1-4 情绪级别
            "sanitized": str,         # 净化后的文本（标签以下的全部内容）
            "valid": bool,            # 格式是否合规（含 [情绪判断] 且级别可解析）
        }
    """
    lines = text.strip().split("\n")

    tag_line = None
    tag_idx = None
    for i, line in enumerate(lines):
        if "情绪判断" in line:
            tag_line = line
            tag_idx = i
            break

    if tag_line is None:
        return {"level": None, "sanitized": "", "valid": False}

    # 解析情绪级别（关键词匹配，按优先级）
    level = None
    if "平稳" in tag_line:
        level = 1
    elif "轻微" in tag_line:
        level = 2
    elif "愤怒" in tag_line:
        level = 3
    elif "激烈" in tag_line:
        level = 4

    # 取标签行之后的内容作为净化文本，跳过紧随标签行的空行
    sanitized_lines = lines[tag_idx + 1:]
    while sanitized_lines and not sanitized_lines[0].strip():
        sanitized_lines.pop(0)
    sanitized = "\n".join(sanitized_lines).strip()

    valid = level is not None

    return {"level": level, "sanitized": sanitized, "valid": valid}


def check_profanity_removal(sanitized, source_words):
    """三重检查脏话是否清除：source_word + 变体标准化 + DFA。"""
    if not sanitized:
        return True, []
    raw = sanitized
    sanitized_lower = sanitized.lower()
    # 标准化：去空格、去全角、去符号 → 还原绕过变体
    normalized = sanitized_lower
    for ch in " ._-*@$!#":
        normalized = normalized.replace(ch, "")
    normalized = normalized.translate(str.maketrans(
        "abcdefghijklmnopqrstuvwxyz",
        "abcdefghijklmnopqrstuvwxyz"
    ))
    remaining = []
    for word in source_words:
        if not word:
            continue
        w = word.lower()
        # 查原始子串
        if w in sanitized_lower:
            remaining.append(word)
            continue
        # 查标准化后的文本（捕获 t m d → tmd）
        nw = re.sub(r"[ ._\-*@$!#]", "", w)
        if nw and nw in normalized:
            remaining.append(word)
            continue
    # DFA 扫描
    dfa = run_dfa(raw)
    if dfa.get("has_profanity"):
        for m in dfa.get("matches", []):
            if m["word"] not in remaining:
                remaining.append(m["word"])
    return len(remaining) == 0, remaining


def extract_emotion_level_number(tag_line):
    """从 [情绪判断] 标签行中提取数字级别（备用方法，用于鲁棒解析）。"""
    match = re.search(r"级别\s*(\d)", tag_line)
    if match:
        return int(match.group(1))
    match = re.search(r"level\s*(\d)", tag_line, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


# ---------------------------------------------------------------------------
# 主逻辑
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("用法: python3 e2e_validate.py <llm_outputs.json>", file=sys.stderr)
        sys.exit(1)

    llm_outputs_path = sys.argv[1]

    # 加载输入文件
    if not os.path.exists(llm_outputs_path):
        print(f"[ERROR] 输入文件不存在: {llm_outputs_path}", file=sys.stderr)
        sys.exit(1)

    with open(llm_outputs_path, encoding="utf-8") as f:
        llm_outputs = json.load(f)

    if not os.path.exists(ADVERSARY_CASES):
        print(f"[ERROR] 对抗用例文件不存在: {ADVERSARY_CASES}", file=sys.stderr)
        sys.exit(1)

    with open(ADVERSARY_CASES, encoding="utf-8") as f:
        adversary_data = json.load(f)

    adversary_cases = adversary_data["cases"]
    adversary_map = {c["id"]: c for c in adversary_cases}

    # 构建 LLM 输出映射
    llm_map = {}
    for item in llm_outputs:
        llm_map[item["id"]] = item.get("skill_output", "")

    # -------------------------------------------------------------------
    # 逐项验证
    # -------------------------------------------------------------------
    details = []
    total = len(adversary_cases)
    with_output = 0
    missing = 0

    emotion_correct = 0
    profanity_clean = 0
    profanity_applicable = 0
    entity_pass = 0
    entity_applicable = 0
    format_valid = 0

    dfa_missed_count = 0
    dfa_missed_llm_caught = 0

    for case in adversary_cases:
        case_id = case["id"]
        category = case["category"]
        original = case["input"]
        expected_level = case.get("expected_level")
        expected_dfa_hit = case.get("expected_dfa_hit", True)

        # 源脏话词（兼容 source_word 和 source_words 两种字段名）
        source_words = case.get("source_words", [])
        if not source_words:
            sw = case.get("source_word", "")
            if sw:
                source_words = [sw]

        skill_output = llm_map.get(case_id, "")
        if not skill_output:
            missing += 1
            details.append({
                "id": case_id,
                "category": category,
                "status": "missing",
                "original": original[:100],
                "expected_level": expected_level,
                "parsed_level": None,
                "sanitized": None,
                "emotion_correct": False,
                "profanity_clean": None,
                "entity_preserved": None,
                "format_valid": False,
                "dfa_missed_llm_caught": False,
                "dfa_has_profanity": None,
                "errors": ["LLM 输出缺失"],
            })
            continue

        with_output += 1

        # 解析 /mental-barrier 输出
        parsed = parse_skill_output(skill_output)
        parsed_level = parsed["level"]
        sanitized = parsed["sanitized"]
        fmt_valid = parsed["valid"]
        detail_errors = []

        if fmt_valid:
            format_valid += 1
        else:
            detail_errors.append("格式不合规（缺少 [情绪判断] 标签或无法解析情绪级别）")

        # ---- 情绪判断准确率 ----
        emo_ok = (parsed_level == expected_level)
        if emo_ok:
            emotion_correct += 1
        else:
            detail_errors.append(
                f"情绪级别不匹配：预期={expected_level}，实际={parsed_level}"
            )

        # ---- 脏话清除率（仅对需要净化的级别检查）----
        profanity_ok = None
        if parsed_level is not None and parsed_level >= 3 and source_words:
            profanity_applicable += 1
            clean, remaining = check_profanity_removal(sanitized, source_words)
            profanity_ok = clean
            if clean:
                profanity_clean += 1
            else:
                detail_errors.append(f"脏话未清除: {', '.join(remaining)}")
        elif parsed_level is not None and parsed_level <= 2:
            # 级别 1-2 为原文透传，源词存在是预期行为
            profanity_applicable += 1
            profanity_clean += 1
            profanity_ok = True

        # ---- 实体保留率 ----
        entity_ok = None
        if sanitized:
            entity_applicable += 1
            try:
                vresult = run_validator(original, sanitized)
                entity_ok = vresult.get("passed", False)
                if entity_ok:
                    entity_pass += 1
                else:
                    lost = vresult.get("lost_entities", [])
                    detail_errors.append(
                        f"实体丢失: {lost[:5]}{'...' if len(lost) > 5 else ''}"
                    )
            except Exception as e:
                detail_errors.append(f"validator 运行异常: {e}")
                entity_applicable -= 1  # 不计数

        # ---- DFA→LLM 增益 ----
        dfa_result = None
        dfa_has = None
        llm_caught = False
        try:
            dfa_result = run_dfa(original)
            dfa_has = dfa_result.get("has_profanity", False)
        except Exception:
            dfa_has = None

        if dfa_has is False:
            dfa_missed_count += 1
            # LLM 是否捕获：需要解析到级别 3-4，且与预期级别匹配
            if parsed_level is not None and parsed_level >= 3 and parsed_level == expected_level:
                dfa_missed_llm_caught += 1
                llm_caught = True
        elif dfa_has is True:
            # DFA 命中了，不计入增益但也不必扣分
            pass

        details.append({
            "id": case_id,
            "category": category,
            "status": "ok" if not detail_errors else "issues",
            "original": original[:100],
            "expected_level": expected_level,
            "expected_dfa_hit": expected_dfa_hit,
            "parsed_level": parsed_level,
            "sanitized": sanitized[:200] if sanitized else None,
            "source_words": source_words,
            "emotion_correct": emo_ok,
            "profanity_clean": profanity_ok,
            "entity_preserved": entity_ok,
            "format_valid": fmt_valid,
            "dfa_missed_llm_caught": llm_caught,
            "dfa_has_profanity": dfa_has,
            "errors": detail_errors,
        })

    # -------------------------------------------------------------------
    # 汇总计算
    # -------------------------------------------------------------------
    emotion_accuracy = emotion_correct / with_output if with_output > 0 else 0.0
    profanity_removal_rate = profanity_clean / profanity_applicable if profanity_applicable > 0 else 1.0
    entity_pass_rate = entity_pass / entity_applicable if entity_applicable > 0 else 1.0
    format_compliance = format_valid / with_output if with_output > 0 else 0.0
    dfa_to_llm_gain = (
        dfa_missed_llm_caught / dfa_missed_count if dfa_missed_count > 0 else 1.0
    )

    # -------------------------------------------------------------------
    # 终端汇总表
    # -------------------------------------------------------------------
    coverage = with_output / total if total > 0 else 0.0

    print()
    print("=" * 70)
    print("  e2e_validate.py — 端到端验证报告")
    print("=" * 70)
    print(f"  总用例数:             {total}")
    print(f"  有 LLM 输出:          {with_output}")
    print(f"  缺失输出:             {missing}")
    print(f"  覆盖率:               {coverage:6.1%}  ({with_output}/{total})")
    print()
    print(f"  情绪判断准确率:       {emotion_accuracy:6.1%}  ({emotion_correct}/{with_output})")
    print(f"  脏话清除率:           {profanity_removal_rate:6.1%}  ({profanity_clean}/{profanity_applicable})")
    print(f"  实体保留通过率:       {entity_pass_rate:6.1%}  ({entity_pass}/{entity_applicable})")
    print(f"  格式合规率:           {format_compliance:6.1%}  ({format_valid}/{with_output})")
    print(f"  DFA→LLM 增益:         {dfa_to_llm_gain:6.1%}  ({dfa_missed_llm_caught}/{dfa_missed_count})")
    print("=" * 70)

    # 分类统计
    print()
    print("  按类别情绪准确率:")
    print("  " + "-" * 50)
    category_stats = {}
    for d in details:
        cat = d["category"]
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "correct": 0}
        category_stats[cat]["total"] += 1
        if d["emotion_correct"]:
            category_stats[cat]["correct"] += 1

    for cat in sorted(category_stats.keys()):
        stats = category_stats[cat]
        rate = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0
        bar = "#" * int(rate * 20)
        print(f"  {cat:<20s} {rate:5.1%}  {bar}")

    # 列出存在问题的用例
    issues = [d for d in details if d["errors"]]
    if issues:
        print()
        print(f"  存在问题用例 ({len(issues)} 条):")
        print("  " + "-" * 50)
        for d in issues:
            print(f"  [{d['id']}] ({d['category']})")
            for err in d["errors"]:
                print(f"    - {err}")

    # -------------------------------------------------------------------
    # 保存结果
    # -------------------------------------------------------------------
    output_dir = os.path.dirname(os.path.abspath(llm_outputs_path))
    output_path = os.path.join(output_dir, "e2e_results.json")

    summary = {
        "total_cases": total,
        "with_output": with_output,
        "missing": missing,
        "emotion_accuracy": round(emotion_accuracy, 4),
        "profanity_removal_rate": round(profanity_removal_rate, 4),
        "entity_pass_rate": round(entity_pass_rate, 4),
        "format_compliance": round(format_compliance, 4),
        "dfa_to_llm_gain": round(dfa_to_llm_gain, 4),
    }

    results = {
        "summary": summary,
        "details": details,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print()
    print(f"  详细结果已保存至: {output_path}")

    # -------------------------------------------------------------------
    # 质量门禁检查
    # -------------------------------------------------------------------
    exit_code = 0
    print()
    print("=" * 70)
    print("  质量门禁检查")
    print("=" * 70)
    if total > 0:
        if coverage < COVERAGE_THRESHOLD:
            print(f"  [FAIL] 覆盖率 {coverage:.1%} < {COVERAGE_THRESHOLD:.0%}")
            exit_code = 1
        else:
            print(f"  [PASS] 覆盖率 {coverage:.1%} >= {COVERAGE_THRESHOLD:.0%}")

        if emotion_accuracy < EMOTION_THRESHOLD:
            print(f"  [FAIL] 情绪准确率 {emotion_accuracy:.1%} < {EMOTION_THRESHOLD:.0%}")
            exit_code = 1
        else:
            print(f"  [PASS] 情绪准确率 {emotion_accuracy:.1%} >= {EMOTION_THRESHOLD:.0%}")

        if profanity_removal_rate < PROFANITY_THRESHOLD:
            print(f"  [FAIL] 脏话清除率 {profanity_removal_rate:.1%} < {PROFANITY_THRESHOLD:.0%}")
            exit_code = 1
        else:
            print(f"  [PASS] 脏话清除率 {profanity_removal_rate:.1%} >= {PROFANITY_THRESHOLD:.0%}")

        if entity_pass_rate < ENTITY_THRESHOLD:
            print(f"  [FAIL] 实体保留率 {entity_pass_rate:.1%} < {ENTITY_THRESHOLD:.0%}")
            exit_code = 1
        else:
            print(f"  [PASS] 实体保留率 {entity_pass_rate:.1%} >= {ENTITY_THRESHOLD:.0%}")

        if format_compliance < FORMAT_THRESHOLD:
            print(f"  [FAIL] 格式合规率 {format_compliance:.1%} < {FORMAT_THRESHOLD:.0%}")
            exit_code = 1
        else:
            print(f"  [PASS] 格式合规率 {format_compliance:.1%} >= {FORMAT_THRESHOLD:.0%}")

    print("=" * 70)
    if exit_code == 0:
        print("  所有门禁通过。")
    else:
        print("  存在未通过的门禁项。")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
