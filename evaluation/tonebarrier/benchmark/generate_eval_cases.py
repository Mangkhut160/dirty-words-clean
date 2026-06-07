#!/usr/bin/env python3
import json
import os
import re
import random
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..", "..", "..", "..")
DATASET_PATH = os.path.join(PROJECT_ROOT, "datasets", "negative_feedback", "merged", "sample_dev_90.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "eval_cases.json")

ANGER_TO_EMOTION = {0: 1, 1: 2, 2: 2, 3: 3, 4: 4, 5: 4}

ENTITY_PATTERNS = [
    (r"订单(?:[号编]|编号)\s*[：:]*\s*[A-Za-z0-9\-_]+", "订单号"),
    (r"[¥￥]\s*\d+\.?\d*", "金额"),
    (r"\d+\.?\d*\s*元", "金额"),
    (r"1[3-9]\d{9}", "手机号"),
    (r"(?:[一-鿿]{1,4}(?:省|市|区|县|自治州))[^，。\t\n]{2,}(?:[路街巷大道村组号楼]|栋|单元|室)", "地址"),
    (r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?", "日期"),
    (r"[A-Za-z0-9]+[-_][A-Za-z0-9]+", "产品型号"),
]


def extract_entities(text):
    entities = []
    for pattern, label in ENTITY_PATTERNS:
        for m in re.finditer(pattern, text):
            entities.append(label)
    return entities


def stratified_sample(records, target=30, min_per_score=4):
    groups = defaultdict(list)
    for r in records:
        groups[r["features"]["anger_score"]].append(r)

    selected = []
    selected_ids = set()

    for score in sorted(groups.keys()):
        candidates = [r for r in groups[score] if r["id"] not in selected_ids]
        if not candidates:
            continue
        n = min(min_per_score, len(candidates))

        by_source = defaultdict(list)
        for r in candidates:
            by_source[r["source"]].append(r)
        for src in by_source:
            by_source[src].sort(key=lambda x: x["length"])

        taken = []
        sources = sorted(by_source.keys())
        si = 0
        while len(taken) < n:
            src = sources[si % len(sources)]
            src_list = by_source[src]
            if src_list:
                taken.append(src_list.pop(0))
            si += 1
            if si > n * len(sources):
                break

        for r in taken:
            selected.append(r)
            selected_ids.add(r["id"])

    remaining = {}
    for score in sorted(groups.keys()):
        available = [r for r in groups[score] if r["id"] not in selected_ids]
        if available:
            remaining[score] = available

    score_keys = sorted(remaining.keys())
    ri = 0
    while len(selected) < target and score_keys:
        score = score_keys[ri % len(score_keys)]
        available = remaining[score]
        if available:
            r = available.pop(0)
            selected.append(r)
            selected_ids.add(r["id"])
        else:
            del remaining[score]
            score_keys = sorted(remaining.keys())
            ri = -1
        ri += 1

    return selected


def build_case(record):
    emotion_level = ANGER_TO_EMOTION[record["features"]["anger_score"]]
    entities = extract_entities(record["text"])
    return {
        "id": record["id"],
        "source": record["source"],
        "input": record["text"],
        "anger_score": record["features"]["anger_score"],
        "expected_level": emotion_level,
        "entities": entities,
        "entity_count": len(entities),
    }


def main():
    random.seed(42)

    with open(DATASET_PATH, encoding="utf-8") as f:
        records = json.load(f)

    full_cases = [build_case(r) for r in records]

    sampled = stratified_sample(records, target=30, min_per_score=4)
    sampled_cases = [build_case(r) for r in sampled]

    output = {
        "full": full_cases,
        "sampled_30": sampled_cases,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Generated {len(full_cases)} full cases and {len(sampled_cases)} sampled cases")
    print(f"Saved to {OUTPUT_PATH}")

    sample_dist = defaultdict(int)
    for c in sampled_cases:
        sample_dist[c["anger_score"]] += 1
    print(f"Sampled anger_score distribution: {dict(sorted(sample_dist.items()))}")


if __name__ == "__main__":
    main()
