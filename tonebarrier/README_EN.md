# Mental Barrier — Emotion Filtering Engine

> **[中文](README_CN.md)** | English

[![Tests](https://img.shields.io/badge/DFA_tests-123%2F123%20passed-brightgreen)](tests/test_pipeline.py)

---

## Overview

A Claude Code SKILL for customer complaint emotion de-escalation and text sanitization. Transforms profanity-laden, sarcastic, emotionally charged customer complaints into calm, objective natural language.

## Features

- **Zero dependencies** — Pure Python stdlib, no pip install needed
- **Two-layer filtering** — DFA exact matching (429 CN + 1,071 EN words, graded) + LLM semantic review
- **English enhanced** — Leet speak normalization (sh1t→shit), repeat compression (fuuuck→fuck), censor bypass (f\*\*k), abbreviations (stfu/gtfo)
- **Entity preservation** — Order IDs, amounts, addresses, contacts, dates (16 entity types)
- **Adversarial robustness** — 7 bypass types: spacing, homophones, leet, CN-EN mixing, pinyin, sarcasm, out-of-dictionary
- **Natural language output** — Two-part format: [emotion tag] + sanitized text
- **DFA tests 100% pass** — 83 regular + 40 boundary cases, zero false positives

## Installation (Claude Code)

```bash
# Option 1: Clone and copy
git clone https://github.com/Mangkhut160/dirty-words-clean.git
cp -r dirty-words-clean/tonebarrier your-project/.claude/skills/tonebarrier

# Option 2: Direct download
mkdir -p .claude/skills && cd .claude/skills
git clone https://github.com/Mangkhut160/dirty-words-clean.git --depth 1
mv dirty-words-clean/tonebarrier . && rm -rf dirty-words-clean
```

## Usage

```
/tonebarrier This fucking app is garbage fix this shit now
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

Real performance without Claude Code framework (see [tonebarrier-server/](../tonebarrier-server/)):

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
│  429 CN + 1,071 EN words (graded)    │
│  Trie O(n) + boundary + fullwidth    │
│  + leet normalization + repeat comp  │
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
tonebarrier/
├── SKILL.md                 # Main instruction file (241 lines, 8 few-shot)
├── scripts/
│   ├── dfa_filter.py        # DFA engine (fullwidth + leet + repeat compress)
│   └── validator.py         # Entity validator (16 types, CN/EN numeral equiv)
├── references/
│   ├── profanity_dict.txt   # 429 CN profanity words
│   ├── profanity_en.txt     # 1,071 EN profanity words (Level 3/4 graded)
│   └── homophone_guide.md   # Homophone reference
├── tests/
│   ├── test_cases.json      # 23 test cases
│   └── test_pipeline.py     # Auto tests
├── adversarial/             # Adversarial eval (182 cases)
└── benchmark/               # Benchmark reports
```

## Version Comparison

| | tonebarrier (Skill) | tonebarrier-server (Server) |
|---|---|---|
| Runtime | Inside Claude Code | Standalone FastAPI service |
| LLM | Claude itself | MiniMax M2.7 (API key required) |
| Best for | Development / experience / light use | Production / batch testing / cost validation |
| Dependencies | Zero (Python stdlib only) | pip install + API key |
| Cost | Included in Claude subscription | ¥0.00055/call |
| Live demo | — | [HF Spaces](https://huggingface.co/spaces/pzr114514/skills-demo) |

> **Recommendation**: For Claude Code experience, just use the `tonebarrier/` directory — zero config, works out of the box.

## License

MIT
