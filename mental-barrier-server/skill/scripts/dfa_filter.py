#!/usr/bin/env python3
"""
DFA 精确匹配过滤器 — 第1层。
从 stdin 读取输入文本，输出 JSON 格式的脏话检测结果。
包含自然语言摘要字段，供 LLM 直接参考。
纯 Python 标准库实现，零外部依赖。
用法：echo "文本" | python3 dfa_filter.py

DFA exact match filter — Layer 1.
Reads input text from stdin, outputs JSON-format profanity detection results.
Includes a natural language summary field for direct LLM reference.
Pure Python standard library implementation, zero external dependencies.
Usage: echo "text" | python3 dfa_filter.py
"""
import sys
import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REF_DIR = os.path.join(SCRIPT_DIR, "..", "references")

# 全角→半角映射表（Unicode fullwidth → ASCII halfwidth）
# Fullwidth to halfwidth mapping (catches ｆｕｃｋ → fuck etc.)
_FW_OFFSET = 0xFEE0
_FULLWIDTH_MAP = {chr(i + _FW_OFFSET): chr(i) for i in range(0x21, 0x7F)}


def normalize_fullwidth(text):
    """全角英数字符转半角，保留中文和其他字符不变。
    Converts fullwidth ASCII variants to halfwidth, preserves CJK and other chars."""
    return text.translate(str.maketrans(_FULLWIDTH_MAP))


# === English normalization for leet speak, repeat chars, censor symbols ===

LEET_MAP = {'1': 'i', '3': 'e', '4': 'a', '5': 's', '0': 'o',
            '@': 'a', '$': 's', '!': 'i', '7': 't', '8': 'b'}

_REPEAT2_RE = re.compile(r'(.)\1{2,}')
_CENSOR_RE = re.compile(r'(?<=[a-z])[*_.\-](?=[a-z])')


def normalize_leet(text):
    """Replace leet speak characters with letters, but only within word-like sequences."""
    result = []
    i = 0
    while i < len(text):
        if text[i] in LEET_MAP:
            has_alpha_neighbor = (
                (i > 0 and text[i-1].isalpha()) or
                (i + 1 < len(text) and text[i+1].isalpha())
            )
            if has_alpha_neighbor:
                result.append(LEET_MAP[text[i]])
            else:
                result.append(text[i])
        else:
            result.append(text[i])
        i += 1
    return ''.join(result)


def strip_censor_chars(text):
    """Strip censor characters between letters. f*ck→fck, s.h.i.t→shit"""
    return _CENSOR_RE.sub('', text)


def compress_repeats(text):
    """Compress 3+ consecutive identical characters. Returns both 1-char and 2-char variants."""
    return _REPEAT2_RE.sub(r'\1', text)


def normalize_english(text):
    """Full English normalization pipeline: censor strip → leet → repeat compress.
    Returns a list of normalized variants to scan."""
    t = strip_censor_chars(text.lower())
    t = normalize_leet(t)
    v1 = re.sub(r'(.)\1{2,}', r'\1', t)      # fuuuck → fuck
    v2 = re.sub(r'(.)\1{2,}', r'\1\1', t)    # fuuuck → fuuck
    variants = {v1, v2, t}
    variants.discard(text.lower())
    return list(variants)


def load_trie(path):
    """将脏话词加载为 DFA 字典树（Trie）。每个节点一个字符，__END__ 标记词尾。

    Load profanity words as a DFA Trie tree. Each node holds one character, __END__ marks word end."""
    root = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            word = line.strip().lower()
            if not word or len(word) < 2 or word.isdigit() or word.startswith('#'):
                continue
            node = root
            for ch in word:
                if ch not in node:
                    node[ch] = {}
                node = node[ch]
            node["__END__"] = word
    return root


def is_alpha_boundary(text, start, end):
    """检查纯英文词是否有词边界——前后不能同时是英文字母。
    防止 "class"→"ass"、"USB-C"→"sb"、"damaged"→"ma" 等子串误报。
    仅对 ASCII 字母组成的词做边界检查（中文 isalpha 也返回 True）。

    Check if a pure English word has word boundaries — both sides must not be English letters.
    Prevents substring false positives like "class"→"ass", "USB-C"→"sb", "damaged"→"ma".
    Only performs boundary checks on words composed of ASCII letters (Chinese isalpha also returns True)."""
    word = text[start:end]
    if not word.isascii() or not word.isalpha():
        return True
    if start > 0 and text[start - 1].isascii() and text[start - 1].isalpha():
        return False
    if end < len(text) and text[end].isascii() and text[end].isalpha():
        return False
    return True


def dfa_search(root, text):
    """单次遍历 DFA 字典树，返回 [{word, start, end}]。
    遇到匹配后跳过已匹配区域，不重复检测子串。
    对纯英文词增加词边界检查，防止子串误报。

    Single-pass traversal of the DFA Trie tree, returns [{word, start, end}].
    Skips matched regions after a hit, avoiding duplicate substring detection.
    Adds word boundary checks for pure English words to prevent substring false positives."""
    text_lower = text.lower()
    matches = []
    i = 0
    while i < len(text_lower):
        node = root
        j = i
        found = None
        while j < len(text_lower) and text_lower[j] in node:
            node = node[text_lower[j]]
            j += 1
            if "__END__" in node:
                candidate = node["__END__"]
                if is_alpha_boundary(text_lower, i, j):
                    found = {"word": candidate, "start": i, "end": j}
        if found:
            matches.append(found)
            i = found["end"]
        else:
            i += 1
    return matches


def main():
    text = sys.stdin.read().strip()
    if not text:
        output = {
            "error": "输入文本为空",
            "total_matches": 0,
            "matches": [],
            "summary": "输入文本为空，无需过滤。",
            "has_profanity": False,
        }
        print(json.dumps(output, ensure_ascii=False))
        return

    dfa_cn = load_trie(os.path.join(REF_DIR, "profanity_dict.txt"))
    dfa_en = load_trie(os.path.join(REF_DIR, "profanity_en.txt"))

    # 全角预处理：在标准化文本上额外跑一次 DFA，捕获 ｆｕｃｋ 等 Unicode 变体
    # Fullwidth preprocessing: run DFA on normalized text to catch Unicode variants
    normalized = normalize_fullwidth(text)
    has_fullwidth = (normalized != text)

    cn_matches = dfa_search(dfa_cn, text)
    en_matches = dfa_search(dfa_en, text)

    # 如果存在全角字符，在标准化文本上补充扫描
    # If fullwidth chars exist, supplement scan on normalized text
    if has_fullwidth:
        cn_norm = dfa_search(dfa_cn, normalized)
        en_norm = dfa_search(dfa_en, normalized)
        existing_pos = {(m["start"], m["end"]) for m in cn_matches + en_matches}
        for m in cn_norm + en_norm:
            if (m["start"], m["end"]) not in existing_pos:
                m["word"] = m["word"] + "(fullwidth)"
                cn_matches.append(m)

    # 英文归一化预处理：leet speak + 重复压缩 + 审查符号剥离
    # English normalization: catch sh1t, f*ck, fuuuck etc.
    en_variants = normalize_english(text)
    for variant in en_variants:
        en_norm_matches = dfa_search(dfa_en, variant)
        existing_pos = {(m["start"], m["end"]) for m in en_matches}
        for m in en_norm_matches:
            if (m["start"], m["end"]) not in existing_pos:
                m["word"] = m["word"] + "(leet)"
                en_matches.append(m)

    # 合并去重（按位置），英文词典优先（避免 CN 词典中的英文词条被误标）
    # Merge and deduplicate (by position), English dictionary takes priority (avoid English entries in CN dict being mislabeled)
    all_matches = []
    en_positions = {(m["start"], m["end"]) for m in en_matches}
    seen_positions = set()
    for m in en_matches + cn_matches:
        pos_key = (m["start"], m["end"])
        if pos_key not in seen_positions:
            seen_positions.add(pos_key)
            source = "dfa_en" if pos_key in en_positions else "dfa_cn"
            all_matches.append({
                "type": source,
                "word": m["word"],
                "start": m["start"],
                "end": m["end"],
            })
    all_matches.sort(key=lambda x: x["start"])

    # 生成自然语言摘要（供 LLM 直接阅读融入输出）
    # Generate natural language summary (for LLM to directly read and incorporate into output)
    if all_matches:
        unique_words = list(dict.fromkeys(m["word"] for m in all_matches))
        word_preview = "、".join(unique_words[:8])
        if len(unique_words) > 8:
            word_preview += f" 等 {len(unique_words)} 个"
        summary = (
            f"DFA 精确匹配检测到 {len(all_matches)} 处命中，"
            f"涉及 {len(unique_words)} 个不同词条：{word_preview}。"
        )
    else:
        summary = "DFA 精确匹配未检出已知脏话词条，文本中无直接脏话命中。"

    output = {
        "original_length": len(text),
        "total_matches": len(all_matches),
        "has_profanity": len(all_matches) > 0,
        "matches": all_matches,
        "summary": summary,
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
