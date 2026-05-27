# 精神内耗终结者 | Mental Barrier

[![Tests](https://img.shields.io/badge/tests-66%2F66%20passed-brightgreen)](tests/test_pipeline.py)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.6%2B-blue)](https://python.org)

**情绪过滤引擎 | Emotion Filtering Engine**

客户情绪降级与文本脱水 SKILL for Claude Code。将充满辱骂、讽刺、情绪宣泄的客服投诉文本转化为冷静客观的自然语言表达。

Customer complaint emotion de-escalation and text sanitization. Transforms profanity-laden, sarcastic, emotionally charged text into calm, objective natural language.

---

## 特性 | Features

- **零外部依赖 Zero dependencies** — 纯 Python 标准库 / Pure Python stdlib
- **双层过滤 Two-layer filtering** — DFA 精确匹配 + LLM 语义理解 / DFA exact match + LLM semantic review
- **关键信息保留 Entity preservation** — 订单号、金额、地址、电话等 16 种实体 / 16 entity types
- **对抗鲁棒 Adversarial robustness** — 7 种绕过检测 / 7 bypass detection types
- **纯自然语言输出 Natural language output** — [情绪判断] + 净化文本 / Emotion tag + sanitized text

---

## 使用 | Usage

```
/mental-barrier 你们tmd这个破产品用了三天就坏了赶紧退款
```

输出 Output：
```
[情绪判断] 客户情绪激烈，含攻击性语言 — 以下为过滤后内容

DFA 检测到 1 处情绪化表达（tmd），已过滤。

客户反馈购买的产品使用三天后出现故障，要求退款处理。
```

---

## 基准评测 | Benchmarks

| 指标 Metric | 值 Value | 目标 Target | 判定 Status |
|-------------|----------|-------------|-------------|
| DFA COLD F1 | 0.40 | ≥ 0.40 | PASS |
| DFA 精确率 Precision | 90.4% | ≥ 80% | PASS |
| 情绪准确率（严格）Strict Accuracy | 81.3% | ≥ 70% | PASS |
| 情绪准确率（业务）Business Accuracy | 92.9% | ≥ 85% | PASS |
| 脏话清除率 Profanity Removal | 97.2% | ≥ 85% | PASS |
| 实体保留率 Entity Retention | 95.8% | ≥ 90% | PASS |
| 格式合规率 Format Compliance | 97.6% | ≥ 90% | PASS |

> **准确率说明 Accuracy note**：严格准确率要求级别完全匹配。业务准确率允许 3↔4 互判（处理方式相同）。严重误判仅 7.1%。
>
> Strict requires exact match. Business allows 3↔4 interchange (same handling). Critical errors only 7.1%.

---

## 生产环境模拟 | Production Simulation

去掉 Claude Code 框架后的真实性能（详见 [mental-barrier-server/](../mental-barrier-server/)）：

Real performance without Claude Code framework (see [mental-barrier-server/](../mental-barrier-server/)):

| 指标 Metric | 生产模拟 Prod Sim | Claude Code | 提升 Improvement |
|-------------|-------------------|-------------|-----------------|
| 平均 Token | 994 | 12,066 | -92% |
| 平均延迟 Latency | 4.4s | 30s | -85% |
| 单条成本 Cost | ¥0.00055 | ~¥0.20 | -99.7% |
| 月成本 Monthly (10K/day) | ¥165 | ¥60,000 | -99.7% |

---

## 架构 | Architecture

```
输入 Input
  │
  ▼
┌────────────────────────────────────────┐
│  第1层 Layer 1: DFA 精确匹配 (~50ms)    │
│  402 中文 + 798 英文词                  │
│  Trie O(n) + ASCII 词边界 + 全角预处理   │
└────────────────────────────────────────┘
  │
  ▼
┌────────────────────────────────────────┐
│  第2层 Layer 2: LLM 语义审核            │
│  谐音变体 Homophones                   │
│  空格/符号绕过 Space/symbol bypass      │
│  Leet speak (sh1t/@ss/b!tch)          │
│  讽刺转化 Sarcasm conversion           │
│  Emoji 语义 Emoji semantics            │
│  中英混杂 CN-EN mixed                  │
└────────────────────────────────────────┘
  │
  ▼
输出 Output: [情绪判断] + 净化文本
```

---

## Emoji 情绪识别 | Emoji Recognition

DFA 不处理 emoji，由 LLM 层负责语义理解：

DFA doesn't process emoji. LLM layer handles semantic understanding:

| Emoji | 含义 Meaning | 处理 Handling |
|-------|-------------|---------------|
| 🖕 | 竖中指 Middle finger | 级别3+ Level 3+ |
| 💩 | 侮辱 Insult | 清除 Remove |
| 🤬 | 骂人 Swearing | 级别3 Level 3 |
| 👍😊 讽刺 Sarcastic | 正面emoji+负面语境 | 级别3 Level 3 |
| 👍😊 真实 Genuine | 正面emoji+正面语境 | 不处理 Passthrough |

---

## 文件结构 | File Structure

```
mental-barrier/
├── SKILL.md                 # 主指令 / Main instructions (241 lines)
├── README.md                # 本文件 / This file
├── scripts/
│   ├── dfa_filter.py        # DFA 匹配 / DFA matching (fullwidth support)
│   └── validator.py         # 实体验证 / Entity validator (16 types)
├── references/
│   ├── profanity_dict.txt   # 402 中文词 / CN words
│   ├── profanity_en.txt     # 798 英文词 / EN words
│   └── homophone_guide.md   # 谐音对照 / Homophone table
├── tests/
│   ├── test_cases.json      # 23 测试用例 / test cases
│   └── test_pipeline.py     # 自动测试 / Auto tests (66/66)
├── adversarial/             # 对抗评测 / Adversarial eval (182 cases)
│   ├── adversary_cases.json
│   ├── e2e_validate.py
│   └── batch_run_llm.py
└── benchmark/               # 基准报告 / Reports
    ├── BENCHMARK_REPORT.md
    ├── EVALUATION_REPORT.md
    └── UPGRADE_REPORT_V4.md
```

---

## 许可 | License

MIT
