#!/usr/bin/env python3
"""
针对性分析遗漏样本中的辱骂/脏话词汇。
策略：
1. 从遗漏样本中提取所有 2-5 字中文片段
2. 从实际 app 差评数据中提取高频词作为对照
3. 手动标注候选：聚焦真正的脏话/侮辱词，排除中性话题词
4. 用词边界和上下文来确认是否真的是侮辱性用法
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


# Potential profanity/insult patterns to search for
# These are known Chinese insults that might be missing
CANDIDATE_PATTERNS = [
    # Variants of existing insults
    "傻狗", "傻叉", "傻蛋", "蠢蛋", "蠢驴", "蠢猪",
    "制杖", "智帐", "智张",  # homophone of 智障
    "沙雕", "沙比", "沙币",  # variants of 傻屌/傻逼
    "煞比", "煞叉",  # variants
    "尼玛币", "尼马币",  # variant of 你妈逼
    "卧日", "我曰", "我鈤",  # variant of 我日
    "泥煤", "泥马",  # euphemism
    "你丫", "丫的", "丫挺",  # Beijing colloquial
    "逼样儿", "逼样子",

    # Internet insults
    "舔狗", "舔男", "舔女",  # simp
    "孝子", "孝女", "尼孝子",  # bootlicker (derogatory)
    "娘炮", "娘pao", "娘泡",  # sissy
    "直男癌", "直女癌",  # gender insult
    "圣母女婊", "圣母婊",  # sanctimonious
    "双标狗", "双标男", "双标女",  # hypocrite
    "喷子", "喷狗",  # troll
    "键盘侠", "键政",  # keyboard warrior
    "杠精", "柠檬精",  # argumentative/jealous
    "黑子", "黑粉",  # hater
    "假洋鬼子",  # fake foreigner
    "黑蛆", "白蛆",  # racist slur
    "蛆",  # used as insult (maggot)
    "白皮猪", "黑皮猪",  # racial slur
    "黑鬼", "白鬼", "洋鬼", "日本鬼",  # racial slurs
    "黄皮",  # racial

    # Anger/curse in customer context
    "太坑了", "烂透了", "气死了", "气炸了",
    "差劲", "差劲死", "恶心死", "恶心死了",
    "不要脸到", "臭不要脸的",
    "坑死", "坑死了", "坑爹的",
    "无良", "黑心", "奸商", "黑商",
    "骗钱", "骗子", "骗人的",  # these border on factual but often used as invective
    "坑货", "坑比", "坑逼",

    # General insults
    "孙子",  # used as insult ("you're my grandson")
    "奴才", "狗奴才",
    "下三滥", "下三烂",
    "不三不四",
    "王八", "王八犊子",  # short form
    "土鳖", "土包子", "乡巴佬", "乡下人",  # bumpkin/hick
    "瘪三", "小瘪三",
    "疯狗", "走狗", "狗腿子", "狗东西", "狗杂种", "狗篮子",
    "狗屎", "狗屁的",
    "傻帽", "傻冒", "傻老帽",
    "蠢蛋", "蠢才", "蠢材",
    "懒鬼", "懒汉", "懒虫",
    "穷鬼", "穷逼", "穷酸", "穷光蛋",
    "矮冬瓜", "矮子", "矮矬",
    "肥猪", "肥婆", "胖猪",

    # Gender-specific
    "婊", "婊里婊气",  # bitch-related (婊子 already in dict)
    "荡妇", "淫妇", "骚娘们",
    "渣男", "渣女", "人渣",  # (人渣 already in dict)
    "剩女", "光棍",  # borderline

    # Misc
    "恶心人", "恶心吧啦",
    "活该",  # "serves you right"
    "报应",  # karma (used as insult)
    "活腻了", "活腻歪了",
    "不知好歹", "给脸不要脸",
    "死一边去", "滚一边去", "滚犊子",
    "欠抽", "欠扁", "欠骂",
    "找骂", "找抽", "找打",  # 找打 already in dict
    "一副德行", "什么德行",
    "狗眼看人低",
    "不是个东西",  # 不是东西 already in dict

    # Homophone/leet variants
    "恶熏",  # intentional misspelling of 恶心
    "挠弹", "老挠弹",  # 脑残 variant
    "弱鸡", "菜鸡", "捞比",
    "尼美", "泥嘛",
    "踏马的",  # variant of 他妈的
    "卧嘈",  # variant
    "窝嘈",  # variant
    "艹你", "草泥",  # variants
]

# Also search for specific n-grams involving key insult characters
INSULT_SEEDS = ["逼", "傻", "蠢", "贱", "屌", "操", "日", "艹", "叼", "鸟", "蛋",
                "狗", "猪", "驴", "鬼", "虫", "蛆", "屎", "尿", "屁",
                "婊", "骚", "淫", "奸", "贼", "匪", "棍", "赖", "混",
                "废", "烂", "渣", "癌", "炮", "婊", "畜", "孬"]


def find_insult_ngrams(text, max_len=4):
    """Find all 2-4 char sequences in text that contain insult-seed characters."""
    results = []
    chars = list(text)
    for i in range(len(chars)):
        for length in range(2, max_len + 1):
            if i + length <= len(chars):
                ngram = ''.join(chars[i:i+length])
                # Check if any character is in insult seeds
                if any(ch in INSULT_SEEDS for ch in ngram):
                    results.append(ngram)
    return results


def main():
    cn_dict = load_dict(os.path.join(REF_DIR, "profanity_dict.txt"))
    en_dict = load_dict(os.path.join(REF_DIR, "profanity_en.txt"))
    all_dict = cn_dict | en_dict

    dfa_cn = dfa_filter.load_trie(os.path.join(REF_DIR, "profanity_dict.txt"))
    dfa_en = dfa_filter.load_trie(os.path.join(REF_DIR, "profanity_en.txt"))

    # Load COLD and get missed texts
    cold_data = load_jsonl(os.path.join(PROJECT_ROOT, "datasets", "COLD_train.jsonl"))
    cold_missed = []
    for item in cold_data:
        text = item["TEXT"]
        label = item["label"]
        if label == 1:
            predicted = 1 if (len(dfa_filter.dfa_search(dfa_cn, text)) > 0 or
                             len(dfa_filter.dfa_search(dfa_en, text)) > 0) else 0
            if predicted == 0:
                cold_missed.append({"text": text, "topic": item["topic"]})

    # Load ToxiCN and get missed texts
    toxicn_data = load_jsonl(os.path.join(PROJECT_ROOT, "datasets", "ToxiCN_test.json"))
    toxicn_missed = []
    for item in toxicn_data:
        if item["toxic"] == 1:
            text = item["content"]
            predicted = 1 if (len(dfa_filter.dfa_search(dfa_cn, text)) > 0 or
                             len(dfa_filter.dfa_search(dfa_en, text)) > 0) else 0
            if predicted == 0:
                toxicn_missed.append({"text": text, "topic": item.get("topic", "")})

    # ====== Part 1: Search for candidate patterns ======
    print("=" * 70)
    print("PART 1: 搜索候选侮辱词汇模式")
    print("=" * 70)

    pattern_hits_cold = Counter()
    pattern_hits_toxicn = Counter()
    pattern_examples = {}

    for pattern in CANDIDATE_PATTERNS:
        if pattern in all_dict:
            continue
        count_cold = 0
        count_toxicn = 0
        for item in cold_missed:
            if pattern in item["text"]:
                count_cold += 1
                if pattern not in pattern_examples:
                    # Find context
                    idx = item["text"].find(pattern)
                    start = max(0, idx - 15)
                    end = min(len(item["text"]), idx + len(pattern) + 15)
                    pattern_examples[pattern] = item["text"][start:end]
        for item in toxicn_missed:
            if pattern in item["text"]:
                count_toxicn += 1

        if count_cold > 0 or count_toxicn > 0:
            pattern_hits_cold[pattern] = count_cold
            pattern_hits_toxicn[pattern] = count_toxicn

    # Sort by total hits
    all_candidates = sorted(pattern_hits_cold.keys(),
                           key=lambda p: pattern_hits_cold[p] + pattern_hits_toxicn[p],
                           reverse=True)

    for pattern in all_candidates:
        c = pattern_hits_cold[pattern]
        t = pattern_hits_toxicn[pattern]
        ex = pattern_examples.get(pattern, "")
        print(f"  [{pattern}] COLD={c}, ToxiCN={t}  示例: ...{ex}...")

    # ====== Part 2: Find frequent insult-ngrams from missed texts ======
    print("\n" + "=" * 70)
    print("PART 2: 发现新的侮辱性 n-gram")
    print("=" * 70)

    ngram_counter_cold = Counter()
    ngram_counter_toxicn = Counter()

    for item in cold_missed:
        ngrams = find_insult_ngrams(item["text"])
        for ng in ngrams:
            if ng not in all_dict:
                ngram_counter_cold[ng] += 1

    for item in toxicn_missed:
        ngrams = find_insult_ngrams(item["text"])
        for ng in ngrams:
            if ng not in all_dict:
                ngram_counter_toxicn[ng] += 1

    print("\n--- COLD 遗漏中的侮辱性 n-gram Top 60 ---")
    for word, count in ngram_counter_cold.most_common(60):
        # Show examples for promising words
        examples = []
        for item in cold_missed[:500]:
            if word in item["text"] and len(examples) < 2:
                idx = item["text"].find(word)
                start = max(0, idx - 10)
                end = min(len(item["text"]), idx + len(word) + 10)
                examples.append(item["text"][start:end])
        ex_str = " | ".join(examples) if examples else ""
        print(f"  {word}: {count}  [{ex_str}]")

    print("\n--- ToxiCN 遗漏中的侮辱性 n-gram Top 60 ---")
    for word, count in ngram_counter_toxicn.most_common(60):
        examples = []
        for item in toxicn_missed[:500]:
            if word in item["text"] and len(examples) < 2:
                idx = item["text"].find(word)
                start = max(0, idx - 10)
                end = min(len(item["text"]), idx + len(word) + 10)
                examples.append(item["text"][start:end])
        ex_str = " | ".join(examples) if examples else ""
        print(f"  {word}: {count}  [{ex_str}]")

    # ====== Part 3: Analyze FP (false positives) to check if dict words cause issues ======
    print("\n" + "=" * 70)
    print("PART 3: 误报分析 (当前词典的 FP 来源)")
    print("=" * 70)

    fp_texts = []
    for item in cold_data:
        text = item["TEXT"]
        label = item["label"]
        if label == 0:
            predicted = 1 if (len(dfa_filter.dfa_search(dfa_cn, text)) > 0 or
                             len(dfa_filter.dfa_search(dfa_en, text)) > 0) else 0
            if predicted == 1:
                fp_texts.append(text)

    # Show FP matches
    fp_word_counter = Counter()
    for text in fp_texts:
        cn_matches = dfa_filter.dfa_search(dfa_cn, text)
        en_matches = dfa_filter.dfa_search(dfa_en, text)
        for m in cn_matches + en_matches:
            fp_word_counter[m["word"]] += 1

    print(f"总误报数: {len(fp_texts)}")
    print("FP 中被命中的高频词:")
    for word, count in fp_word_counter.most_common(30):
        print(f"  {word}: {count}")

    # Show some FP examples with context
    print("\nFP 样本示例 (前15条):")
    for i, text in enumerate(fp_texts[:15]):
        cn_matches = dfa_filter.dfa_search(dfa_cn, text)
        en_matches = dfa_filter.dfa_search(dfa_en, text)
        matched_words = [m["word"] for m in cn_matches + en_matches]
        display = text[:100]
        print(f"  [{i+1}] 命中: {matched_words} | {display}...")

    # ====== Part 4: Analyze the app negative reviews for missing customer-complaint profanity ======
    print("\n" + "=" * 70)
    print("PART 4: App 差评中的未命中分析")
    print("=" * 70)
    reviews_path = os.path.join(PROJECT_ROOT, "datasets", "negative_feedback", "merged", "app_negative_reviews.json")
    if os.path.exists(reviews_path):
        with open(reviews_path, encoding="utf-8") as f:
            reviews = json.load(f)

        missed_reviews = []
        hit_review_words = Counter()
        for item in reviews:
            text = item.get("text", "") or item.get("content", "")
            cn_matches = dfa_filter.dfa_search(dfa_cn, text)
            en_matches = dfa_filter.dfa_search(dfa_en, text)
            matches = cn_matches + en_matches
            if not matches :
                missed_reviews.append(text)
            else:
                for m in matches:
                    hit_review_words[m["word"]] += 1

        print(f"App 差评总数: {len(reviews)}")
        print(f"有命中的: {len(reviews) - len(missed_reviews)}")
        print(f"无命中的: {len(missed_reviews)}")

        # Find anger expressions in missed reviews
        anger_patterns = re.compile(r'[一-鿿]{2,5}')
        anger_counter = Counter()
        for text in missed_reviews:
            words = anger_patterns.findall(text)
            for w in words:
                if w not in all_dict:
                    anger_counter[w] += 1

        print("\n未命中差评中的高频词 Top 50:")
        for word, count in anger_counter.most_common(50):
            # Show examples
            ex = ""
            for t in missed_reviews[:300]:
                if word in t:
                    idx = t.find(word)
                    start = max(0, idx - 10)
                    end = min(len(t), idx + len(word) + 10)
                    ex = t[start:end]
                    break
            print(f"  {word}: {count}  [{ex}]")


if __name__ == "__main__":
    main()
