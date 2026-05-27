# Mental Barrier — Emotion Filtering Engine

> **[中文](README_CN.md)** | English

[![Tests](https://img.shields.io/badge/tests-66%2F66%20passed-brightgreen)](tests/test_pipeline.py)

---

## Overview

A Claude Code SKILL for customer complaint emotion de-escalation and text sanitization. Transforms profanity-laden, sarcastic, emotionally charged customer complaints into calm, objective natural language.

## Features

- **Zero dependencies** — Pure Python stdlib, no pip install needed
- **Two-layer filtering** — DFA exact matching (402 words, 90.4% precision) + LLM semantic review
- **Entity preservation** — Order IDs, amounts, addresses, contacts, dates (16 entity types)
- **Adversarial robustness** — 7 bypass types: spacing, homophones, leet, CN-EN mixing, pinyin, sarcasm, out-of-dictionary
- **Natural language output** — Two-part format: [emotion tag] + sanitized text

## Usage

```
/mental-barrier This fucking app is garbage fix this shit now
```

Output:
```
[情绪判断] 客户情绪激烈，含攻击性语言 — 以下为过滤后内容

The customer is dissatisfied with the app quality and requesting an immediate fix or refund.
```

## Benchmarks

| Metric | Value (DeepSeek V4 Flash) | Target | Status |
|--------|--------------------------|--------|--------|
| DFA COLD F1 | 0.40 | ≥ 0.40 | PASS |
| DFA Precision | 90.4% | ≥ 80% | PASS |
| Emotion Accuracy (strict) | 81.3% | ≥ 70% | PASS |
| Emotion Accuracy (business) | 92.9% | ≥ 85% | PASS |
| Profanity Removal | 97.2% | ≥ 85% | PASS |
| Entity Retention | 95.8% | ≥ 90% | PASS |
| Format Compliance | 97.6% | ≥ 90% | PASS |

> **Accuracy note**: Strict accuracy requires exact level match. Business accuracy allows level 3↔4 interchange (both trigger sanitization). Critical misclassifications only 7.1%.

## Production Simulation

Real performance without Claude Code framework (see [mental-barrier-server/](../mental-barrier-server/)):

| Metric | Production Sim | Claude Code | Improvement |
|--------|---------------|-------------|-------------|
| Avg Tokens | 994 | 12,066 | -92% |
| Avg Latency | 4.4s | 30s | -85% |
| Cost/call | ¥0.00055 | ~¥0.20 | -99.7% |
| Monthly (10K/day) | ¥165 | ¥60,000 | -99.7% |

## Architecture

```
Input
  │
  ▼
┌─────────────────────────────────────┐
│  Layer 1: DFA Exact Match (~50ms)    │
│  402 CN + 798 EN words               │
│  Trie O(n) + word boundary + fullwidth│
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│  Layer 2: LLM Semantic Review        │
│  Homophones / Space bypass / Leet    │
│  Sarcasm / Emoji / CN-EN mixed       │
└─────────────────────────────────────┘
  │
  ▼
Output: [Emotion Tag] + Sanitized Text
```

## File Structure

```
mental-barrier/
├── SKILL.md                 # Main instruction file (241 lines, 8 few-shot)
├── scripts/
│   ├── dfa_filter.py        # DFA matching (fullwidth support)
│   └── validator.py         # Entity validator (16 types)
├── references/
│   ├── profanity_dict.txt   # 402 CN profanity words
│   ├── profanity_en.txt     # 798 EN profanity words
│   └── homophone_guide.md   # Homophone reference
├── tests/
│   ├── test_cases.json      # 23 test cases
│   └── test_pipeline.py     # Auto tests (66/66)
├── adversarial/             # Adversarial eval (182 cases)
└── benchmark/               # Benchmark reports
```

## License

MIT
