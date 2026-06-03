#!/usr/bin/env python3
"""
分析 DFA 词典遗漏的脏话词汇。
1. 加载当前词典
2. 对 COLD 数据集中 label=1 但 DFA 未命中的样本，提取文本
3. 分词并统计高频词/短语
4. 对 ToxiCN toxic 但 DFA 未命中的样本，同样分析
5. 输出候选词汇列表
"""
import json
import os
import re
import sys
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(SCRIPT_DIR, "..")
REF_DIR = os.path.join(SKILL_DIR, "references")
BENCH_DIR = os.path.join(SKILL_DIR, "benchmark")
PROJECT_ROOT = os.path.join(SKILL_DIR, "..", "..", "..")

sys.path.insert(0, SCRIPT_DIR)
import dfa_filter


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


def is_chinese_char(ch):
    """Check if a character is in the CJK Unified Ideographs range."""
    return '一' <= ch <= '鿿'


def tokenize_bigrams(text):
    """Extract Chinese character bigrams and trigrams."""
    result = []
    # Character bigrams
    chars = list(text)
    for i in range(len(chars) - 1):
        if is_chinese_char(chars[i]) and is_chinese_char(chars[i+1]):
            result.append(chars[i] + chars[i+1])
    # Character trigrams
    for i in range(len(chars) - 2):
        if all(is_chinese_char(chars[j]) for j in range(i, i+3)):
            result.append(chars[i] + chars[i+1] + chars[i+2])
    return result


def extract_candidates_from_missed(missed_texts, dict_words, top_n=200):
    """Extract candidate words from missed texts using bigram/trigram frequency."""
    bigram_counter = Counter()
    trigram_counter = Counter()

    for text in missed_texts:
        bigrams = tokenize_bigrams(text)
        for bg in bigrams:
            if bg not in dict_words:
                bigram_counter[bg] += 1
            # Also collect trigrams
            if len(bg) == 3:
                if bg not in dict_words:
                    trigram_counter[bg] += 1

    # Also extract words using simple regex for common Chinese insult patterns
    # Pattern: 2-4 Chinese characters
    word_pattern = re.compile(r'[一-鿿]{2,4}')
    word_counter = Counter()
    for text in missed_texts:
        words = word_pattern.findall(text)
        for w in words:
            if w not in dict_words:
                word_counter[w] += 1

    return {
        "bigrams": bigram_counter.most_common(top_n),
        "trigrams": trigram_counter.most_common(top_n),
        "words": word_counter.most_common(top_n),
    }


def main():
    # Load dictionaries
    cn_dict = load_dict(os.path.join(REF_DIR, "profanity_dict.txt"))
    en_dict = load_dict(os.path.join(REF_DIR, "profanity_en.txt"))
    all_dict = cn_dict | en_dict
    print(f"当前词典大小: CN={len(cn_dict)}, EN={len(en_dict)}, 合并={len(all_dict)}")

    # Build DFAs
    dfa_cn = dfa_filter.load_trie(os.path.join(REF_DIR, "profanity_dict.txt"))
    dfa_en = dfa_filter.load_trie(os.path.join(REF_DIR, "profanity_en.txt"))

    # ----- COLD Analysis -----
    print("\n" + "=" * 60)
    print("COLD 数据集分析")
    print("=" * 60)

    cold_path = os.path.join(PROJECT_ROOT, "datasets", "COLD_train.jsonl")
    cold_data = load_jsonl(cold_path)
    print(f"COLD 总样本数: {len(cold_data)}")

    cold_missed_texts = []
    cold_by_topic_missed = {}
    cold_fp_texts = []

    for item in cold_data:
        text = item["TEXT"]
        topic = item["topic"]
        label = item["label"]
        predicted = 1 if (len(dfa_filter.dfa_search(dfa_cn, text)) > 0 or
                         len(dfa_filter.dfa_search(dfa_en, text)) > 0) else 0

        if label == 1 and predicted == 0:
            cold_missed_texts.append(text)
            if topic not in cold_by_topic_missed:
                cold_by_topic_missed[topic] = []
            cold_by_topic_missed[topic].append(text)
        elif label == 0 and predicted == 1:
            cold_fp_texts.append(text)

    print(f"COLD 遗漏样本 (FN): {len(cold_missed_texts)}")
    print(f"COLD 误报样本 (FP): {len(cold_fp_texts)}")
    for topic, texts in cold_by_topic_missed.items():
        print(f"  - {topic}: {len(texts)} 遗漏")

    # Extract candidates from COLD missed
    cold_candidates = extract_candidates_from_missed(cold_missed_texts, all_dict, top_n=300)

    print("\n--- COLD 遗漏高频 2-gram Top 50 ---")
    for word, count in cold_candidates["bigrams"][:50]:
        print(f"  {word}: {count}")

    print("\n--- COLD 遗漏高频 词汇 (2-4字) Top 50 ---")
    for word, count in cold_candidates["words"][:50]:
        print(f"  {word}: {count}")

    # Also analyze by topic
    for topic in ["gender", "region", "race"]:
        if topic in cold_by_topic_missed:
            topic_candidates = extract_candidates_from_missed(
                cold_by_topic_missed[topic], all_dict, top_n=50
            )
            print(f"\n--- {topic} 主题遗漏高频词汇 Top 20 ---")
            for word, count in topic_candidates["words"][:20]:
                print(f"  {word}: {count}")

    # ----- ToxiCN Analysis -----
    print("\n" + "=" * 60)
    print("ToxiCN 数据集分析")
    print("=" * 60)

    toxicn_path = os.path.join(PROJECT_ROOT, "datasets", "ToxiCN_test.json")
    toxicn_data = load_jsonl(toxicn_path)
    print(f"ToxiCN 总样本数: {len(toxicn_data)}")

    toxicn_missed_texts = []
    toxicn_fp_texts = []

    for item in toxicn_data:
        text = item["content"]
        toxic = item["toxic"]
        predicted = 1 if (len(dfa_filter.dfa_search(dfa_cn, text)) > 0 or
                         len(dfa_filter.dfa_search(dfa_en, text)) > 0) else 0

        if toxic == 1 and predicted == 0:
            toxicn_missed_texts.append(text)
        elif toxic == 0 and predicted == 1:
            toxicn_fp_texts.append(text)

    print(f"ToxiCN 遗漏样本: {len(toxicn_missed_texts)}")
    print(f"ToxiCN 误报样本: {len(toxicn_fp_texts)}")

    toxicn_candidates = extract_candidates_from_missed(toxicn_missed_texts, all_dict, top_n=300)

    print("\n--- ToxiCN 遗漏高频 2-gram Top 50 ---")
    for word, count in toxicn_candidates["bigrams"][:50]:
        print(f"  {word}: {count}")

    print("\n--- ToxiCN 遗漏高频 词汇 (2-4字) Top 50 ---")
    for word, count in toxicn_candidates["words"][:50]:
        print(f"  {word}: {count}")

    # ----- Sample missed texts -------
    print("\n" + "=" * 60)
    print("COLD 遗漏样本示例 (前30条)")
    print("=" * 60)
    for i, text in enumerate(cold_missed_texts[:30]):
        # Truncate long texts
        display = text[:120] + "..." if len(text) > 120 else text
        print(f"[{i+1}] {display}")

    print("\n" + "=" * 60)
    print("ToxiCN 遗漏样本示例 (前30条)")
    print("=" * 60)
    for i, text in enumerate(toxicn_missed_texts[:30]):
        display = text[:120] + "..." if len(text) > 120 else text
        print(f"[{i+1}] {display}")

    # ----- Cross-reference: words in both COLD and ToxiCN missed -----
    print("\n" + "=" * 60)
    print("COLD 和 ToxiCN 共同遗漏的高频词 (strong candidates)")
    print("=" * 60)
    cold_word_set = set(w for w, _ in cold_candidates["words"][:200])
    toxicn_word_set = set(w for w, _ in toxicn_candidates["words"][:200])
    common = cold_word_set & toxicn_word_set
    # Rank by combined frequency
    cold_freq = dict(cold_candidates["words"][:200])
    toxicn_freq = dict(toxicn_candidates["words"][:200])
    common_ranked = sorted(common, key=lambda w: cold_freq.get(w, 0) + toxicn_freq.get(w, 0), reverse=True)
    for w in common_ranked[:80]:
        print(f"  {w}: COLD={cold_freq.get(w,0)}, ToxiCN={toxicn_freq.get(w,0)}")


if __name__ == "__main__":
    main()
