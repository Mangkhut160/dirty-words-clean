#!/usr/bin/env python3
"""
基准测试报告生成器。
读取 dfa_results.json 和 skill_results.json，生成 BENCHMARK_REPORT.md。
如果某个文件不存在，则将该部分标记为"待评测"。
"""
import json
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DFA_RESULTS = os.path.join(SCRIPT_DIR, "dfa_results.json")
SKILL_RESULTS = os.path.join(SCRIPT_DIR, "skill_results.json")
E2E_RESULTS = os.path.join(SCRIPT_DIR, "..", "adversarial", "e2e_results.json")
OUTPUT = os.path.join(SCRIPT_DIR, "BENCHMARK_REPORT.md")


def load_json(path):
    """安全加载 JSON 文件，不存在或解析失败时返回 None。"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"警告: 无法解析 {path}: {e}", file=sys.stderr)
        return None


def format_pct(value, decimals=2):
    """将 0-1 的小数格式化为百分比字符串。"""
    if value is None:
        return "N/A"
    return f"{value * 100:.{decimals}f}%"


def format_rate(value, decimals=4):
    """格式化比率，保留指定小数位。"""
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}"


def render_dfa_section(dfa):
    """生成 DFA 层报告内容。返回 Markdown 字符串。"""
    if dfa is None:
        return (
            "## DFA 层评测\n\n"
            "> **状态：待评测** — 尚未运行 DFA 评估，请执行 `python3 benchmark/dfa_eval.py`。\n\n"
        )

    lines = ["## DFA 层评测\n"]

    generated = dfa.get("generated_at", "未知")
    lines.append(f"> 数据生成时间：{generated}\n")

    # --- ToxiCN 覆盖率 ---
    toxicn = dfa.get("toxicn", {})
    if toxicn:
        total_toxicn = toxicn.get("toxic_count", 0) + toxicn.get("clean_count", 0)
        lines.append("### ToxiCN 覆盖率\n")
        lines.append("| 指标 | 值 |")
        lines.append("|------|----|")
        lines.append(f"| 数据集 | {toxicn.get('dataset', 'ToxiCN')} |")
        lines.append(f"| 样本总数 (toxic + clean) | {total_toxicn} |")
        lines.append(f"| 有毒样本数 | {toxicn.get('toxic_count', 'N/A')} |")
        lines.append(f"| 干净样本数 | {toxicn.get('clean_count', 'N/A')} |")
        lines.append(f"| True Positive | {toxicn.get('true_positive', 'N/A')} |")
        lines.append(f"| False Positive | {toxicn.get('false_positive', 'N/A')} |")
        lines.append(f"| 召回率 (Recall) | {format_pct(toxicn.get('recall'))} |")
        lines.append(f"| 误报率 (FPR) | {format_pct(toxicn.get('false_positive_rate'))} |")
        lines.append("")

    # --- COLD 精确率/召回率 ---
    cold = dfa.get("cold", {})
    if cold:
        lines.append("### COLD 精确率/召回率\n")
        lines.append("| 指标 | 值 |")
        lines.append("|------|----|")
        lines.append(f"| 数据集 | {cold.get('dataset', 'COLD')} |")
        lines.append(f"| 样本总数 | {cold.get('total', 'N/A')} |")
        lines.append(f"| TP / FP / TN / FN | {cold.get('tp', 0)} / {cold.get('fp', 0)} / {cold.get('tn', 0)} / {cold.get('fn', 0)} |")
        lines.append(f"| 准确率 (Accuracy) | {format_pct(cold.get('accuracy'))} |")
        lines.append(f"| 精确率 (Precision) | {format_pct(cold.get('precision'))} |")
        lines.append(f"| 召回率 (Recall) | {format_pct(cold.get('recall'))} |")
        lines.append(f"| F1 | {format_rate(cold.get('f1'))} |")
        lines.append(f"| 误报率 (FPR) | {format_pct(cold.get('false_positive_rate'))} |")
        lines.append("")

    # --- 按主题细分 ---
    by_topic = cold.get("by_topic", {}) if cold else {}
    if by_topic:
        lines.append("### 按主题细分\n")
        lines.append("| 主题 | 样本数 | 精确率 | 召回率 | F1 |")
        lines.append("|------|--------|--------|--------|-----|")
        for topic, metrics in sorted(by_topic.items()):
            count = metrics.get("count", "N/A")
            precision = format_pct(metrics.get("precision"))
            recall = format_pct(metrics.get("recall"))
            f1 = format_rate(metrics.get("f1"))
            lines.append(f"| {topic} | {count} | {precision} | {recall} | {f1} |")
        lines.append("")

    # --- 高频词 Top 20 ---
    word_freq = dfa.get("word_frequency", {})
    top_words = word_freq.get("top_words", [])
    if top_words:
        lines.append("### 高频命中词 Top 20\n")
        lines.append(f"> 评测评论总数: {word_freq.get('total_reviews', 'N/A')}，")
        lines.append(f"命中脏话的文本数: {word_freq.get('texts_with_profanity', 'N/A')}，")
        lines.append(f"命中率: {format_pct(word_freq.get('hit_rate'))}，")
        lines.append(f"独立命中词条: {word_freq.get('unique_words_hit', 'N/A')}\n")
        lines.append("| 排名 | 词条 | 出现次数 |")
        lines.append("|------|------|----------|")
        for i, w in enumerate(top_words[:20], 1):
            word = w.get("word", "N/A")
            count = w.get("count", "N/A")
            lines.append(f"| {i} | `{word}` | {count} |")
        lines.append("")

    # --- 汇总统计 ---
    summary = dfa.get("summary", {})
    if summary:
        lines.append("### DFA 汇总\n")
        lines.append("| 指标 | 值 |")
        lines.append("|------|----|")
        lines.append(f"| 词典总词条数 | {summary.get('total_dict_words', 'N/A')} |")
        lines.append(f"| 评测总样本数 | {summary.get('total_toxicity_samples', 'N/A')} |")
        lines.append(f"| 整体召回率 | {format_pct(summary.get('overall_recall'))} |")
        lines.append(f"| 整体精确率 | {format_pct(summary.get('overall_precision'))} |")
        lines.append(f"| 整体 F1 | {format_rate(summary.get('overall_f1'))} |")
        lines.append(f"| 整体误报率 | {format_pct(summary.get('overall_false_positive_rate'))} |")
        lines.append("")

    return "\n".join(lines)


def render_llm_section(skill):
    """生成 LLM 层报告内容。返回 Markdown 字符串。"""
    if skill is None:
        return (
            "## LLM 层评测\n\n"
            "> **状态：待评测** — 尚未运行 SKILL 端到端评测，请执行：\n"
            "> ```bash\n"
            "> python3 benchmark/skill_eval.py prompts\n"
            "> # 对每条 prompt 运行 /tonebarrier，记录输出到 results.json\n"
            "> python3 benchmark/skill_eval.py validate results.json\n"
            "> ```\n\n"
        )

    lines = ["## LLM 层评测\n"]

    generated = skill.get("generated_at", "未知")
    lines.append(f"> 数据生成时间：{generated}\n")

    # Read metrics from summary sub-object (actual skill_results.json structure)
    sm = skill.get("summary", {})

    # --- 核心指标 ---
    lines.append("### 核心指标\n")
    lines.append("| 指标 | 值 | 目标 |")
    lines.append("|------|----|------|")
    lines.append(f"| 情绪一致率 | {format_pct(sm.get('emotion_accuracy'))} | >= 70% |")
    lines.append(f"| 实体保留通过率 | {format_pct(sm.get('entity_pass_rate'))} | >= 90% |")
    lines.append(f"| 格式合规率 | {format_pct(sm.get('format_compliance'))} | >= 90% |")
    lines.append(f"| 透传正确率 | {format_pct(sm.get('passthrough_rate'))} | >= 85% |")
    lines.append("")

    # --- 情绪混淆矩阵 ---
    ec = skill.get("emotion_confusion", {})
    cm = ec.get("matrix", [])
    if cm and len(cm) == 4:
        lines.append("### 情绪混淆矩阵\n")
        lines.append("| 真实 \\ 预测 | 级别1 | 级别2 | 级别3 | 级别4 |")
        lines.append("|-------------|-------|-------|-------|-------|")
        labels = ["级别1", "级别2", "级别3", "级别4"]
        for i, row in enumerate(cm):
            cells = " | ".join(str(c) for c in row)
            lines.append(f"| {labels[i]} | {cells} |")
        lines.append("")

    # --- 错误案例 ---
    errors = skill.get("errors", [])
    if errors:
        lines.append("### 错误列表\n")
        for err in errors:
            lines.append(f"- {err}")
        lines.append("")

    # --- 详细结果 ---
    details = skill.get("details", [])
    if details:
        lines.append("### 详细结果\n")
        lines.append("| 用例ID | 期望级别 | 判定级别 | 格式合规 | 实体通过 |")
        lines.append("|--------|----------|----------|----------|----------|")
        for d in details:
            cid = d.get("id", "N/A")
            expected = d.get("expected_level", "N/A")
            predicted = d.get("predicted_level", "N/A")
            fmt = "Y" if d.get("format_valid") else "N"
            ent = "Y" if d.get("entity_passed") else "N"
            lines.append(f"| {cid} | {expected} | {predicted} | {fmt} | {ent} |")
        lines.append("")

    # --- 汇总统计 ---
    lines.append("### LLM 汇总\n")
    lines.append("| 指标 | 值 |")
    lines.append("|------|----|")
    lines.append(f"| 评测样本总数 | {sm.get('total_cases', 'N/A')} |")
    lines.append(f"| 匹配结果数 | {sm.get('matched_results', 'N/A')} |")
    lines.append(f"| 情绪一致率 | {format_pct(sm.get('emotion_accuracy'))} |")
    lines.append(f"| 实体保留通过率 | {format_pct(sm.get('entity_pass_rate'))} |")
    lines.append(f"| 格式合规率 | {format_pct(sm.get('format_compliance'))} |")
    lines.append(f"| 透传正确率 | {format_pct(sm.get('passthrough_rate'))} |")
    lines.append("")

    return "\n".join(lines)


def render_e2e_section(e2e):
    """生成真实 LLM 端到端对抗评测报告内容。返回 Markdown 字符串。"""
    if e2e is None:
        return (
            "## 真实 LLM 端到端对抗评测\n\n"
            "> **状态：待评测** — 尚未运行端到端评测，请执行：\n"
            "> ```bash\n"
            "> python3 adversarial/batch_run_llm.py --model deepseek\n"
            "> python3 adversarial/e2e_validate.py adversarial/llm_real_outputs_deepseek.json\n"
            "> ```\n\n"
        )

    sm = e2e.get("summary", {})
    details = e2e.get("details", [])

    total_cases = sm.get("total_cases", 0)
    with_output = sm.get("with_output", 0)
    coverage = with_output / total_cases if total_cases > 0 else 0.0

    lines = ["## 真实 LLM 端到端对抗评测\n"]

    generated = e2e.get("generated_at")
    if generated:
        lines.append(f"> 数据生成时间：{generated}\n")

    # --- 覆盖率 ---
    lines.append("### 覆盖率\n")
    lines.append("| 指标 | 值 |")
    lines.append("|------|----|")
    lines.append(f"| 总用例数 | {total_cases} |")
    lines.append(f"| 有 LLM 输出 | {with_output} |")
    lines.append(f"| 缺失输出 | {sm.get('missing', 'N/A')} |")
    lines.append(f"| 覆盖率 | {format_pct(coverage)} |")
    lines.append("")

    # --- 核心指标 ---
    lines.append("### 核心指标\n")
    lines.append("| 指标 | 值 | 目标 |")
    lines.append("|------|----|------|")
    lines.append(f"| 情绪准确率 | {format_pct(sm.get('emotion_accuracy'))} | >= 70% |")
    lines.append(f"| 脏话清除率 | {format_pct(sm.get('profanity_removal_rate'))} | >= 90% |")
    lines.append(f"| 实体保留通过率 | {format_pct(sm.get('entity_pass_rate'))} | >= 90% |")
    lines.append(f"| 格式合规率 | {format_pct(sm.get('format_compliance'))} | >= 90% |")
    lines.append(f"| DFA→LLM 增益 | {format_pct(sm.get('dfa_to_llm_gain'))} | — |")
    lines.append("")

    # --- 按类别情绪准确率 ---
    if details:
        category_stats = {}
        for d in details:
            cat = d.get("category", "unknown")
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "correct": 0}
            category_stats[cat]["total"] += 1
            if d.get("emotion_correct", False):
                category_stats[cat]["correct"] += 1

        lines.append("### 按类别情绪准确率\n")
        lines.append("| 类别 | 样本数 | 准确率 |")
        lines.append("|------|--------|--------|")
        for cat in sorted(category_stats.keys()):
            stats = category_stats[cat]
            rate = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0
            lines.append(f"| {cat} | {stats['total']} | {format_pct(rate)} |")
        lines.append("")

    return "\n".join(lines)


def render_combined_section(dfa, skill, e2e=None):
    """生成汇总部分，含 pass/fail 判定。"""
    lines = ["## 汇总\n"]
    lines.append("| 层级 | 指标 | 值 | 目标 | 判定 |")
    lines.append("|------|------|----|------|------|")

    def _judge(value, threshold, label_higher=True):
        if value is None:
            return ("N/A", "—")
        if label_higher:
            ok = value >= threshold
        else:
            ok = value <= threshold
        return (format_rate(value), "PASS" if ok else "FAIL")

    # DFA 指标
    if dfa:
        cold = dfa.get("cold", {})
        cold_f1 = cold.get("f1") if cold else None
        cold_fpr = cold.get("false_positive_rate") if cold else None
    else:
        cold_f1 = None
        cold_fpr = None

    # LLM 指标 (nested under "summary" in actual skill_results.json)
    if skill:
        sm = skill.get("summary", {})
        emotion_acc = sm.get("emotion_accuracy")
        entity_pass = sm.get("entity_pass_rate")
    else:
        emotion_acc = None
        entity_pass = None

    # E2E 指标
    if e2e:
        e2e_sm = e2e.get("summary", {})
        e2e_emotion_acc = e2e_sm.get("emotion_accuracy")
        e2e_profanity_rate = e2e_sm.get("profanity_removal_rate")
        e2e_entity_pass = e2e_sm.get("entity_pass_rate")
        e2e_coverage = e2e_sm.get("with_output", 0) / e2e_sm.get("total_cases", 1)
    else:
        e2e_emotion_acc = None
        e2e_profanity_rate = None
        e2e_entity_pass = None
        e2e_coverage = None

    # COLD F1
    f1_val, f1_judge = _judge(cold_f1, 0.40)
    lines.append(f"| DFA | COLD F1 | {f1_val} | >= 0.40 | {f1_judge} |")

    # 情绪一致率
    emo_val, emo_judge = _judge(emotion_acc, 0.70)
    lines.append(f"| LLM | 情绪一致率 | {emo_val} | >= 0.40 | {emo_judge} |")

    # 实体保留率
    if entity_pass is not None:
        ep_val = format_pct(entity_pass)
        ep_judge = "PASS" if entity_pass >= 0.90 else "FAIL"
    else:
        ep_val = "N/A"
        ep_judge = "—"
    lines.append(f"| LLM | 实体保留通过率 | {ep_val} | >= 0.90 | {ep_judge} |")

    # 误报率 (COLD FPR)
    fpr_val, fpr_judge = _judge(cold_fpr, 0.05, label_higher=False)
    lines.append(f"| DFA | 误报率 (COLD FPR) | {fpr_val} | <= 0.05 | {fpr_judge} |")

    # E2E 覆盖率
    if e2e_coverage is not None:
        e2e_cov_val, e2e_cov_judge = _judge(e2e_coverage, 0.80)
        lines.append(f"| E2E | 覆盖率 | {e2e_cov_val} | >= 80% | {e2e_cov_judge} |")
    else:
        lines.append(f"| E2E | 覆盖率 | N/A | >= 80% | — |")

    # E2E 情绪准确率
    if e2e_emotion_acc is not None:
        e2e_emo_val, e2e_emo_judge = _judge(e2e_emotion_acc, 0.60)
        lines.append(f"| E2E | 情绪准确率 | {e2e_emo_val} | >= 60% | {e2e_emo_judge} |")
    else:
        lines.append(f"| E2E | 情绪准确率 | N/A | >= 60% | — |")

    # E2E 脏话清除率
    if e2e_profanity_rate is not None:
        e2e_pro_val, e2e_pro_judge = _judge(e2e_profanity_rate, 0.85)
        lines.append(f"| E2E | 脏话清除率 | {e2e_pro_val} | >= 85% | {e2e_pro_judge} |")
    else:
        lines.append(f"| E2E | 脏话清除率 | N/A | >= 85% | — |")

    # E2E 实体保留率
    if e2e_entity_pass is not None:
        e2e_ep_val, e2e_ep_judge = _judge(e2e_entity_pass, 0.90)
        lines.append(f"| E2E | 实体保留通过率 | {e2e_ep_val} | >= 90% | {e2e_ep_judge} |")
    else:
        lines.append(f"| E2E | 实体保留通过率 | N/A | >= 90% | — |")

    lines.append("")

    # 综合判定
    all_pending = dfa is None and skill is None and e2e is None
    if all_pending:
        lines.append("> **综合判定：待评测** — 尚未运行任何评估。\n")
    else:
        fails = []
        if e2e is None:
            fails.append("E2E 评测未运行（缺少 e2e_results.json）")
        # 检查 LLM 评测覆盖率
        if skill:
            sm_cov = skill.get("summary", {})
            matched = sm_cov.get("matched_results", 0)
            total_c = sm_cov.get("total_cases", 0)
            if total_c > 0 and matched / total_c < 0.80:
                fails.append(f"LLM 评测覆盖率 ({matched}/{total_c})")
        if f1_judge == "FAIL":
            fails.append("COLD F1")
        if emo_judge == "FAIL":
            fails.append("情绪一致率")
        if fpr_judge == "FAIL":
            fails.append("误报率")
        if ep_judge == "FAIL":
            fails.append("实体保留率")
        if e2e and e2e_cov_judge == "FAIL":
            fails.append("E2E 覆盖率")
        if e2e and e2e_emo_judge == "FAIL":
            fails.append("E2E 情绪准确率")
        if e2e and e2e_pro_judge == "FAIL":
            fails.append("E2E 脏话清除率")
        if e2e and e2e_ep_judge == "FAIL":
            fails.append("E2E 实体保留率")
        if f1_val == "N/A" and emo_val == "N/A" and e2e_emotion_acc is None:
            lines.append("> **综合判定：待评测** — 所有指标数据均不可用。\n")
        elif fails:
            lines.append(f"> **综合判定：未通过** — 以下指标未达标：{', '.join(fails)}。\n")
        else:
            lines.append("> **综合判定：通过** — 所有已评测指标均达到目标值。\n")

    return "\n".join(lines)


def generate_report():
    dfa = load_json(DFA_RESULTS)
    skill = load_json(SKILL_RESULTS)
    e2e = load_json(E2E_RESULTS)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    sections = [
        "# 精神内耗终结者 — Benchmark 评估报告",
        "",
        f"> 报告生成时间：{now}",
        "",
        "---",
        "",
        render_dfa_section(dfa),
        "---",
        "",
        render_llm_section(skill),
        "---",
        "",
        render_e2e_section(e2e),
        "---",
        "",
        render_combined_section(dfa, skill, e2e),
        "---",
        "",
        "## 数据来源",
        "",
    ]

    # 从实际数据中读取数据集规模
    toxin_count = dfa.get("toxicn", {}).get("toxic_count", "?") if dfa else "?"
    toxin_clean = dfa.get("toxicn", {}).get("clean_count", "?") if dfa else "?"
    cold_total = dfa.get("cold", {}).get("total", "?") if dfa else "?"

    sections += [
        "| 数据集 | 规模 | 用途 |",
        "|--------|------|------|",
        f"| ToxiCN | ~{toxin_count} 条 (toxic) + ~{toxin_clean} 条 (clean) | DFA 覆盖率 |",
        f"| COLD | ~{cold_total} 条 | DFA 精确率/召回率/F1 |",
        "| sample_dev_90 | 90 条 | LLM 端到端评测 |",
        "",
        "## 指标目标",
        "",
        "| 指标 | 目标值 |",
        "|------|--------|",
        "| COLD F1 | >= 0.40 |",
        "| 情绪一致率 | >= 0.40 |",
        "| 实体保留率 | >= 0.90 |",
        "| 误报率 | <= 0.05 |",
    ]

    report = "\n".join(sections)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"\n报告已保存至: {OUTPUT}")


if __name__ == "__main__":
    generate_report()
