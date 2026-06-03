# dirty-words-clean — Customer Emotion Filtering Engine

> 中文 **[中文](README_CN.md)** | English

[![Tests](https://img.shields.io/badge/tests-66%2F66%20passed-brightgreen)](tonebarrier/tests/test_pipeline.py)
[![Accuracy](https://img.shields.io/badge/business%20accuracy-92.9%25-blue)](tonebarrier-server/batch_results_182.json)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)

---

## Overview

Transforms profanity-laden, sarcastic, emotionally charged customer complaints into calm, objective natural language while preserving all business-critical entities (order IDs, amounts, addresses, phone numbers, etc.).

Supports Chinese (homophones, pinyin abbreviations, number substitutions) and English.

---

## Key Metrics

| Metric | Value | Description |
|--------|-------|-------------|
| Business Accuracy | **92.9%** | Allowing level 3↔4 interchange (same handling) |
| Strict Accuracy | 81.3% | Exact emotion level match |
| Profanity Removal | 97.2% | No profanity in sanitized output |
| Entity Retention | 95.8% | Order IDs/phones/addresses preserved |
| DFA Precision | 90.4% | False positive rate only 2.69% |
| Avg Tokens | 994 | Per LLM call |
| Avg Latency | 4.4s | End-to-end |
| Cost per call | ¥0.00055 | DeepSeek V4 Flash |

---

## Architecture

```
Input → DFA Exact Match (50ms) → LLM Semantic Review (4s) → Validator → Output
              ↓                          ↓
       402 CN + 798 EN words      Emotion de-escalation
       Trie O(n) + boundaries     Homophones/leet/sarcasm/emoji
```

Two-layer design: DFA handles exact matching (high precision, low recall), LLM handles semantic understanding (homophone variants, sarcasm, context reasoning).

---

## Project Structure

```
dirty-words-clean/
├── tonebarrier/              # Core SKILL (standalone)
│   ├── SKILL.md                 # Main instruction file (241 lines)
│   ├── scripts/                 # DFA + Validator scripts
│   ├── references/              # Profanity dictionaries + homophone table
│   ├── tests/                   # Unit tests (66/66 passed)
│   ├── adversarial/             # Adversarial evaluation (182 cases)
│   └── benchmark/               # Benchmark reports
├── tonebarrier-server/       # Production simulation (Web UI)
│   ├── server.py                # FastAPI server
│   ├── pipeline.py              # Pipeline orchestration
│   ├── prompts.py               # Compact system prompt
│   ├── static/ + templates/     # Web UI
│   └── batch_results_182.json   # Full test results
└── data/                        # Test datasets
```

---

## Quick Start

### Option 1: Claude Code SKILL

```bash
cp -r tonebarrier ~/.claude/skills/

# Usage:
/tonebarrier This fucking app is garbage fix this shit now
```

### Option 2: Local Web Service

```bash
cd tonebarrier-server
pip3 install -r requirements.txt
cp config.py.example config.py
# Edit config.py with your LLM_API_KEY

python3 server.py
# Open http://localhost:8000
```

---

## Technical Test Report

### Test Scale

- 66 unit tests (DFA + Validator + adversarial regression)
- 182 adversarial cases (8 categories: homophones, leet, space bypass, CN-EN mix, pinyin mix, sarcasm, EN slang, normal)
- Full API call test (182 cases, DeepSeek V4 Flash, total cost ¥0.10)

### Accuracy by Category

| Category | Strict Accuracy | Cases | Description |
|----------|----------------|-------|-------------|
| normal | 100% | 15 | Normal complaints, passthrough |
| format_bypass | 90.3% | 31 | Space/symbol separated bypass |
| homophone | 82.4% | 51 | Chinese homophone variants |
| pinyin_mix | 80.0% | 15 | Pinyin mixed |
| cnen_mix | 75.0% | 20 | Chinese-English mixed profanity |
| leet | 75.0% | 20 | Number/symbol substitution |
| en_dfa_miss | 73.3% | 15 | English out-of-dictionary |
| sarcasm | 66.7% | 15 | Sarcasm/irony |

### Accuracy Explanation

81.3% requires exact level match. In customer service scenarios:

- **Levels 3 (angry) and 4 (abusive) have identical handling** (both trigger sanitization), so interchange has zero business impact
- **Business accuracy 92.9%**: usable rate allowing 3↔4 interchange
- **Critical errors** (should sanitize but didn't) only 13 cases = 7.1%
- **Retry mechanism**: empty responses auto-retry up to 2 times, format failures = 0

### Error Patterns

| Pattern | Count | Business Impact | Description |
|---------|-------|-----------------|-------------|
| 4→3 | 9 | None (both sanitize) | Leet/space bypass underestimated |
| 3→4 | 8 | None (both sanitize) | Exclamatory profanity overestimated |
| 4→2 | 5 | Yes (missed) | Rare variants unrecognized |
| 3→2 | 5 | Yes (missed) | Sarcasm not detected |
| Other | 7 | Low | Format/boundary |

### Cost Comparison

| Approach | Cost/call | Monthly (10K/day) | Capability |
|----------|-----------|-------------------|------------|
| Claude Code (Opus) | ¥0.20 | ¥60,000 | Full (dev environment) |
| **This project (full)** | **¥0.00055** | **¥165** | Full (de-escalation + sanitization) |
| This project (hybrid) | ¥0.00022 | ¥66 | Full (60% shortcircuit) |
| Cloud text moderation | ¥0.001-0.002 | ¥300-600 | Classification only |

### Difference from Cloud Providers

Cloud providers (Tencent Cloud/Alibaba Cloud/Baidu Cloud) text moderation APIs only do **classification** (return Pass/Block/Review + labels), not **sanitization**. This project performs full emotion de-escalation: input an angry complaint, output a calm objective description, preserving all business entities.

---

## License

MIT
