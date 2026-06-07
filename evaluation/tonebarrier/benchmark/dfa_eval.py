#!/usr/bin/env python3
import json
import os
import sys
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
SKILL_DIR = os.path.join(REPO_ROOT, "skills", "tonebarrier")
PROJECT_ROOT = REPO_ROOT
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
import dfa_filter


def load_jsonl(path):
    data = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def _build_dfa():
    ref_dir = os.path.join(SKILL_DIR, "references")
    return (
        dfa_filter.load_trie(os.path.join(ref_dir, "profanity_dict.txt")),
        dfa_filter.load_trie(os.path.join(ref_dir, "profanity_en.txt")),
    )


def _has_profanity(text, dfa_cn, dfa_en):
    cn = dfa_filter.dfa_search(dfa_cn, text)
    en = dfa_filter.dfa_search(dfa_en, text)
    return len(cn) > 0 or len(en) > 0


def _all_matches(text, dfa_cn, dfa_en):
    cn = dfa_filter.dfa_search(dfa_cn, text)
    en = dfa_filter.dfa_search(dfa_en, text)
    seen = set()
    matches = []
    for m in en + cn:
        key = (m["start"], m["end"])
        if key not in seen:
            seen.add(key)
            matches.append(m)
    return matches


def eval_toxicn(dfa_cn, dfa_en):
    path = os.path.join(PROJECT_ROOT, "datasets", "ToxiCN_test.json")
    data = load_jsonl(path)
    toxic_list = [x for x in data if x["toxic"] == 1]
    clean_list = [x for x in data if x["toxic"] == 0]
    tp = sum(1 for x in toxic_list if _has_profanity(x["content"], dfa_cn, dfa_en))
    fp = sum(1 for x in clean_list if _has_profanity(x["content"], dfa_cn, dfa_en))
    total_toxic = len(toxic_list)
    total_clean = len(clean_list)
    recall = tp / total_toxic if total_toxic else 0
    fpr = fp / total_clean if total_clean else 0
    return {
        "dataset": "ToxiCN",
        "toxic_count": total_toxic,
        "clean_count": total_clean,
        "true_positive": tp,
        "false_positive": fp,
        "recall": round(recall, 4),
        "false_positive_rate": round(fpr, 4),
    }


def eval_cold(dfa_cn, dfa_en):
    path = os.path.join(PROJECT_ROOT, "datasets", "COLD_train.jsonl")
    data = load_jsonl(path)
    tp = fp = tn = fn = 0
    by_topic = {}
    for item in data:
        topic = item["topic"]
        label = item["label"]
        predicted = 1 if _has_profanity(item["TEXT"], dfa_cn, dfa_en) else 0
        if topic not in by_topic:
            by_topic[topic] = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
        if label == 1 and predicted == 1:
            tp += 1
            by_topic[topic]["tp"] += 1
        elif label == 0 and predicted == 1:
            fp += 1
            by_topic[topic]["fp"] += 1
        elif label == 0 and predicted == 0:
            tn += 1
            by_topic[topic]["tn"] += 1
        elif label == 1 and predicted == 0:
            fn += 1
            by_topic[topic]["fn"] += 1
    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total else 0
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    fpr = fp / (fp + tn) if (fp + tn) else 0

    by_topic_result = {}
    for topic, counts in by_topic.items():
        p = counts["tp"] / (counts["tp"] + counts["fp"]) if (counts["tp"] + counts["fp"]) else 0
        r = counts["tp"] / (counts["tp"] + counts["fn"]) if (counts["tp"] + counts["fn"]) else 0
        f = 2 * p * r / (p + r) if (p + r) else 0
        by_topic_result[topic] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f, 4),
            "count": counts["tp"] + counts["fp"] + counts["tn"] + counts["fn"],
        }

    return {
        "dataset": "COLD",
        "total": total,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "by_topic": by_topic_result,
    }


def eval_word_frequency(dfa_cn, dfa_en):
    path = os.path.join(PROJECT_ROOT, "datasets", "negative_feedback", "merged", "app_negative_reviews.json")
    with open(path, encoding="utf-8") as f:
        reviews = json.load(f)
    total_reviews = len(reviews)
    texts_with_profanity = 0
    word_counter = Counter()
    total_word_hits = 0
    for item in reviews:
        text = item.get("text", "") or item.get("content", "")
        matches = _all_matches(text, dfa_cn, dfa_en)
        if matches:
            texts_with_profanity += 1
            for m in matches:
                word_counter[m["word"]] += 1
                total_word_hits += 1
    unique_words = len(word_counter)
    top_words = [{"word": w, "count": c} for w, c in word_counter.most_common(30)]
    hit_rate = texts_with_profanity / total_reviews if total_reviews else 0
    return {
        "total_reviews": total_reviews,
        "texts_with_profanity": texts_with_profanity,
        "hit_rate": round(hit_rate, 4),
        "total_word_hits": total_word_hits,
        "unique_words_hit": unique_words,
        "top_words": top_words,
    }


def main():
    print("=" * 60)
    print("DFA 脏话词典自动化评测")
    print("=" * 60)

    dfa_cn, dfa_en = _build_dfa()

    print("\n[1/3] 评测 ToxiCN (Recall)...")
    toxicn = eval_toxicn(dfa_cn, dfa_en)

    print("[2/3] 评测 COLD (Precision/Recall/F1)...")
    cold = eval_cold(dfa_cn, dfa_en)

    print("[3/3] 词频分布统计...")
    word_freq = eval_word_frequency(dfa_cn, dfa_en)

    results = {"toxicn": toxicn, "cold": cold, "word_frequency": word_freq}

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dfa_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("评测结果摘要")
    print("=" * 60)
    print(f"\nToxiCN:")
    print(f"  样本数: {toxicn['toxic_count']} (toxic) + {toxicn['clean_count']} (clean)")
    print(f"  Recall: {toxicn['recall']:.4f}")
    print(f"  FPR:    {toxicn['false_positive_rate']:.4f}")
    print(f"\nCOLD:")
    print(f"  样本数: {cold['total']}")
    print(f"  Accuracy: {cold['accuracy']:.4f}")
    print(f"  Precision: {cold['precision']:.4f}")
    print(f"  Recall: {cold['recall']:.4f}")
    print(f"  F1: {cold['f1']:.4f}")
    print(f"  FPR: {cold['false_positive_rate']:.4f}")
    print(f"\n  各 Topic 结果:")
    for topic, metrics in cold["by_topic"].items():
        print(f"    {topic}: P={metrics['precision']:.4f}, R={metrics['recall']:.4f}, F1={metrics['f1']:.4f}, N={metrics['count']}")
    print(f"\n词频分布:")
    print(f"  评测评论数: {word_freq['total_reviews']}")
    print(f"  命中脏话的文本数: {word_freq['texts_with_profanity']}")
    print(f"  命中率: {word_freq['hit_rate']:.4f}")
    print(f"  总命中次数: {word_freq['total_word_hits']}")
    print(f"  独立词条数: {word_freq['unique_words_hit']}")
    print(f"\n  Top 10 高频词:")
    for i, item in enumerate(word_freq["top_words"][:10]):
        print(f"    {i+1}. {item['word']}: {item['count']}")

    print(f"\n结果已保存至: {out_path}")


if __name__ == "__main__":
    main()
