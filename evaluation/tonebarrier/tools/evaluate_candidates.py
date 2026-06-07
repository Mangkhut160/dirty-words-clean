#!/usr/bin/env python3
"""
评估候选词汇的潜在收益和风险。
1. 对每个候选词，计算如果加入词典能覆盖多少 FN（真阳性增量）
2. 检查候选词在干净样本中的匹配情况（FP 风险）
3. 考虑多候选词带来的去重增量
"""
import json
import os
import sys
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
SKILL_DIR = os.path.join(REPO_ROOT, "skills", "tonebarrier")
REF_DIR = os.path.join(SKILL_DIR, "references")
PROJECT_ROOT = REPO_ROOT

sys.path.insert(0, SCRIPT_DIR)
import dfa_filter

# Curated candidate list based on analysis
CANDIDATES = [
    # Internet pejoratives (high frequency in COLD)
    "直男癌", "黑鬼", "喷子", "渣男", "舔狗", "圣母婊", "娘炮", "穷逼",
    "女权癌", "直女癌", "渣女", "键盘侠", "杠精", "黑子", "双标狗",
    "地图炮", "腐癌",
    # Racial/ethnic slurs
    "鬼子", "日本鬼子", "洋鬼子", "假洋鬼子", "白皮猪", "黑蛆", "蛆",
    "黄皮", "倭狗", "嘿畜",
    # Animal-based insults
    "母狗", "疯狗", "走狗", "狗腿子", "狗屎", "蠢猪",
    # Gender/body insults
    "荡妇", "矮子", "肥猪",
    # Common insults
    "乡巴佬", "土鳖", "土包子", "下三滥", "穷鬼", "穷光蛋", "奴才", "汉奸",
    # Homophone/leet variants
    "沙雕", "傻叉", "傻蛋", "制杖", "恶熏", "辣鸡", "挠弹", "卧日",
    "泥煤", "你丫", "丫的", "尼玛币",
    # Anger/complaint expressions
    "太坑了", "烂透了", "坑货", "坑比",
    # Miscellaneous insults
    "蠢蛋", "欠抽", "欠扁", "找骂", "找抽", "滚犊子",
    # Additional common expressions
    "逼的",  # common compound
    "婊里婊气",
    "畜狌",  # beast
    "废物点心",  # variant of 废物
    "烂货",  # already? 烂货 is at line 241
    "卖逼", "卖比",
    "草尼玛",  # variant
    "鈤你",  # variant
    "你玛的",
    "妈拉个巴子",
    "日了狗了",
    "艹你妈",
]

# Remove duplicates with existing dict
def load_dict(path):
    words = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            w = line.strip().lower()
            if w and len(w) >= 2:
                words.add(w)
    return words


def load_jsonl(path):
    data = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def check_overlap(candidates, existing_dict):
    """Check which candidates overlap with existing dict entries (including substring)."""
    new = []
    overlapping = []
    for c in candidates:
        if c in existing_dict:
            overlapping.append(c)
        else:
            # Also check if it's a substring of some existing entry
            is_new = True
            for d in existing_dict:
                if c in d or d in c:
                    if c != d:
                        # Overlapping but not identical, still add
                        pass
            if is_new:
                new.append(c)
    return new, overlapping


def main():
    cn_dict = load_dict(os.path.join(REF_DIR, "profanity_dict.txt"))
    en_dict = load_dict(os.path.join(REF_DIR, "profanity_en.txt"))
    all_dict = cn_dict | en_dict

    # Filter candidates
    new_candidates, overlapping = check_overlap(CANDIDATES, all_dict)
    if overlapping:
        print(f"跳过已存在的词: {overlapping}")
    print(f"候选词数量: {len(new_candidates)}")

    # Load DFA
    dfa_cn = dfa_filter.load_trie(os.path.join(REF_DIR, "profanity_dict.txt"))
    dfa_en = dfa_filter.load_trie(os.path.join(REF_DIR, "profanity_en.txt"))

    # Load COLD data
    cold_path = os.path.join(PROJECT_ROOT, "datasets", "COLD_train.jsonl")
    cold_data = load_jsonl(cold_path)

    # Per-candidate analysis
    candidate_fn = Counter()
    candidate_fp = Counter()

    for item in cold_data:
        text = item["TEXT"]
        label = item["label"]

        # Check current DFA
        predicted_current = 1 if (len(dfa_filter.dfa_search(dfa_cn, text)) > 0 or
                                  len(dfa_filter.dfa_search(dfa_en, text)) > 0) else 0

        # Check each candidate
        for cand in new_candidates:
            if cand in text:
                if label == 1 and predicted_current == 0:
                    candidate_fn[cand] += 1
                elif label == 0 and predicted_current == 0:
                    # Would become new FP if added and wasn't already detected
                    candidate_fp[cand] += 1

    print("\n候选词 FN 覆盖 (按 COLD 命中数降序):")
    print(f"{'候选词':<12s} {'FN覆盖':<8s} {'FP风险':<8s}")
    print("-" * 35)
    for cand, count in candidate_fn.most_common():
        fp = candidate_fp.get(cand, 0)
        flag = " ***HIGH_FP***" if fp > 5 else ""
        print(f"{cand:<12s} {count:<8d} {fp:<8d}{flag}")

    # Estimate combined recall improvement
    print("\n--- 组合覆盖分析 ---")
    # Find all COLD FN texts
    fn_texts = []
    for item in cold_data:
        text = item["TEXT"]
        label = item["label"]
        if label == 1:
            predicted = 1 if (len(dfa_filter.dfa_search(dfa_cn, text)) > 0 or
                             len(dfa_filter.dfa_search(dfa_en, text)) > 0) else 0
            if predicted == 0:
                fn_texts.append(text)

    # Check how many FN texts would be covered by new candidates
    covered_texts = set()
    for i, text in enumerate(fn_texts):
        for cand in new_candidates:
            if cand in text:
                covered_texts.add(i)
                break

    total_fn = len(fn_texts)
    newly_covered = len(covered_texts)
    print(f"当前 FN 总数: {total_fn}")
    print(f"新词能覆盖的 FN: {newly_covered} (+{newly_covered/total_fn*100:.1f}%)")

    # Check new FPs created
    fp_texts = []
    for item in cold_data:
        text = item["TEXT"]
        label = item["label"]
        if label == 0:
            predicted = 1 if (len(dfa_filter.dfa_search(dfa_cn, text)) > 0 or
                             len(dfa_filter.dfa_search(dfa_en, text)) > 0) else 0
            if predicted == 0:  # currently clean
                fp_texts.append(text)

    new_fp_texts = set()
    for i, text in enumerate(fp_texts):
        for cand in new_candidates:
            if cand in text:
                new_fp_texts.add(i)
                break

    total_tn = len(fp_texts)  # these are currently clean (=TN)
    new_fp = len(new_fp_texts)
    print(f"当前干净样本数 (TN): {total_tn}")
    print(f"新增误报: {new_fp} (+{new_fp/total_tn*100:.3f}%)")

    # Print new FP examples for review
    if new_fp_texts:
        print(f"\n新增 FP 示例 (前20条):")
        count = 0
        for i in sorted(new_fp_texts)[:20]:
            text = fp_texts[i]
            matching = [c for c in new_candidates if c in text]
            display = text[:100] + ("..." if len(text) > 100 else "")
            print(f"  命中: {matching} | {display}")
            count += 1
            if count >= 20:
                break

    # ToxiCN analysis
    print("\n--- ToxiCN 覆盖分析 ---")
    toxicn_path = os.path.join(PROJECT_ROOT, "datasets", "ToxiCN_test.json")
    toxicn_data = load_jsonl(toxicn_path)

    toxicn_fn_texts = []
    for item in toxicn_data:
        text = item["content"]
        if item["toxic"] == 1:
            predicted = 1 if (len(dfa_filter.dfa_search(dfa_cn, text)) > 0 or
                             len(dfa_filter.dfa_search(dfa_en, text)) > 0) else 0
            if predicted == 0:
                toxicn_fn_texts.append(text)

    toxicn_covered = set()
    for i, text in enumerate(toxicn_fn_texts):
        for cand in new_candidates:
            if cand in text:
                toxicn_covered.add(i)
                break

    print(f"ToxiCN 当前 FN: {len(toxicn_fn_texts)}")
    print(f"新词覆盖的 FN: {len(toxicn_covered)} (+{len(toxicn_covered)/len(toxicn_fn_texts)*100:.1f}%)")

    # Final projection
    print("\n" + "=" * 60)
    print("预估改善")
    print("=" * 60)

    # COLD baseline
    baseline_tp = 2831
    baseline_fp = 299
    baseline_fn = 9892
    baseline_tn = 12704

    new_tp = baseline_tp + newly_covered
    new_fp_total = baseline_fp + new_fp
    new_fn = baseline_fn - newly_covered
    new_tn = baseline_tn - new_fp

    new_precision = new_tp / (new_tp + new_fp_total) if (new_tp + new_fp_total) else 0
    new_recall = new_tp / (new_tp + new_fn) if (new_tp + new_fn) else 0
    new_f1 = 2 * new_precision * new_recall / (new_precision + new_recall) if (new_precision + new_recall) else 0
    new_fpr = new_fp_total / (new_fp_total + new_tn) if (new_fp_total + new_tn) else 0

    print(f"\nCOLD 预估:")
    print(f"  TP: {baseline_tp} → {new_tp}")
    print(f"  FP: {baseline_fp} → {new_fp_total}")
    print(f"  FN: {baseline_fn} → {new_fn}")
    print(f"  Precision: 90.45% → {new_precision*100:.2f}%")
    print(f"  Recall: 22.25% → {new_recall*100:.2f}%")
    print(f"  F1: 0.3572 → {new_f1:.4f}")
    print(f"  FPR: 2.30% → {new_fpr*100:.2f}%")

    # ToxiCN baseline
    toxicn_baseline_tp = 108
    toxicn_total_toxic = 1274
    toxicn_total_clean = 1137
    toxicn_baseline_fp = 19

    toxicn_new_tp = toxicn_baseline_tp + len(toxicn_covered)
    toxicn_new_recall = toxicn_new_tp / toxicn_total_toxic if toxicn_total_toxic else 0

    print(f"\nToxiCN 预估:")
    print(f"  Recall: 8.48% → {toxicn_new_recall*100:.2f}%")

    # Final recommendation: which candidates to include
    print("\n" + "=" * 60)
    print("推荐加入的词 (按 FN 覆盖降序，排除高 FP 风险词)")
    print("=" * 60)

    high_fp_threshold = 5
    recommended = [(cand, fn, candidate_fp.get(cand, 0))
                   for cand, fn in candidate_fn.most_common()
                   if candidate_fp.get(cand, 0) <= high_fp_threshold]
    skip = [(cand, fn, candidate_fp.get(cand, 0))
            for cand, fn in candidate_fn.most_common()
            if candidate_fp.get(cand, 0) > high_fp_threshold]

    print("\n推荐添加:")
    for cand, fn, fp in recommended:
        print(f"  {cand:<12s} (FN+{fn}, FP+{fp})")

    if skip:
        print("\n跳过 (FP 风险高):")
        for cand, fn, fp in skip:
            print(f"  {cand:<12s} (FN+{fn}, FP+{fp})")

    print(f"\n推荐添加总计: {len(recommended)} 词")


if __name__ == "__main__":
    main()
