# 精神内耗终结者 — Mental Barrier

[![Tests](https://img.shields.io/badge/tests-66%2F66%20passed-brightgreen)](tests/test_pipeline.py)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.6%2B-blue)](https://python.org)

<details open>
<summary><b>中文</b></summary>

## 精神内耗终结者 — 情绪过滤引擎

客户情绪降级与文本脱水 SKILL for Claude Code。

将充满辱骂、讽刺、情绪宣泄的客服投诉文本转化为冷静客观的自然语言表达。支持中文（含谐音字、拼音缩写、数字替换等变体）和英文。

### 特性

- **零外部依赖** — 纯 Python 标准库，无需 pip install
- **双层过滤** — DFA 精确匹配（400 词，精确率 90.4%）+ LLM 语义理解
- **关键信息保留** — 订单号、金额、地址、联系方式、日期（中英双语）、产品型号等 16 种实体
- **对抗鲁棒** — 7 种对抗绕过检测：空格/符号分隔、谐音替换、Leet、中英混杂、拼音混杂、讽刺语义、词典外英文
- **纯自然语言输出** — 两段式格式：[情绪判断] + 净化后文本

### 安装

```bash
cp mental-barrier.skill ~/.claude/skills/
cd ~/.claude/skills && tar -xzf mental-barrier.skill
```

项目级：

```bash
cp mental-barrier.skill .claude/skills/
cd .claude/skills && tar -xzf mental-barrier.skill
```

安装后重启 Claude Code。

### 使用

```
/mental-barrier 你们tmd这个破产品用了三天就坏了赶紧退款
```

输出示例：

```
[情绪判断] 客户情绪激烈，含攻击性语言 — 以下为过滤后内容

DFA 检测到 1 处情绪化表达（tmd），已过滤。

客户反馈购买的产品使用三天后出现故障，要求退款处理。
```

### 架构

双层检测管道：

1. **DFA 精确匹配**（~0ms）— 400 客服投诉专用脏话词典，Trie 树 O(n) 遍历，ASCII 词边界防误报，全角→半角预处理
2. **LLM 语义审核** — 谐音变体 + 空格绕过 + Leet 还原（@→a, !→i）+ 讽刺转化 + Emoji 语义理解 + 语境判断

### Emoji 情绪识别

DFA 层不处理 emoji（纯文本精确匹配），由 LLM 层负责 emoji 语义理解：

| Emoji | 含义 | 处理方式 |
|-------|------|---------|
| 🖕 | 竖中指（攻击性） | 识别为情绪化表达，级别 3+ |
| 💩 | 粪便/shit（侮辱） | 识别为脏话等价物，清除 |
| 🤬 | 骂人脸（愤怒） | 识别为情绪宣泄，级别 3 |
| 👍😊 用于讽刺 | 正面 emoji + 负面语境 | 识别为讽刺，级别 3 |
| 👍😊 真正好评 | 正面 emoji + 正面语境 | 不处理，原文透传 |

关键能力：LLM 能区分 emoji 的**真实意图**和**字面含义**——同样的 👍 在好评中是正面的，在投诉中是讽刺的。

### 基准评测

| 指标 | 值 (DeepSeek V4 Flash) | 目标 | 判定 |
|------|----------------------|------|------|
| DFA COLD F1 | 0.40 | ≥ 0.40 | PASS |
| DFA 精确率 | 90.4% | ≥ 80% | PASS |
| LLM 情绪准确率（严格） | 81.3% | ≥ 70% | PASS |
| LLM 情绪准确率（业务） | 92.9% | ≥ 85% | PASS |
| LLM 脏话清除率 | 97.2% | ≥ 85% | PASS |
| LLM 实体保留率 | 95.8% | ≥ 90% | PASS |
| LLM 格式合规率 | 97.6% | ≥ 90% | PASS |

> **准确率说明**：严格准确率要求情绪级别完全匹配。业务准确率允许级别 3↔4 互判（两者处理方式相同，都需要净化）。真正影响业务的严重误判（该净化的没净化）仅占 2.7%。

### 生产环境模拟

去掉 Claude Code 框架开销后的真实性能（详见 [mental-barrier-server/](../../mental-barrier-server/)）：

| 指标 | 生产模拟 | Claude Code | 提升 |
|------|----------|-------------|------|
| 平均 Token | 994 | 12,066 | -92% |
| 平均延迟 | 4.4s | 30s | -85% |
| 单条成本 | ¥0.00055 | ~¥0.20 | -99.7% |
| 万次/天月成本 | ¥165 | ¥60,000 | -99.7% |

### 文件结构

```
mental-barrier/
├── SKILL.md              # 主指令文件（YAML + Markdown, 241行, 8个few-shot）
├── README.md             # 本文件
├── scripts/
│   ├── dfa_filter.py     # DFA 精确匹配（零依赖, ASCII词边界, 全角预处理）
│   └── validator.py      # 实体保留验证（中英双语时间, 16种实体）
├── references/
│   ├── profanity_dict.txt # 402 客服投诉专用脏话词
│   ├── profanity_en.txt   # 798 英文脏话词
│   └── homophone_guide.md # 谐音变体参考（LLM 知识源）
├── tests/
│   ├── test_cases.json    # 23 条测试用例
│   └── test_pipeline.py   # 自动化测试 (66/66 通过)
├── adversarial/           # 对抗评测（182 用例）
│   ├── adversary_cases.json
│   ├── e2e_validate.py
│   └── batch_run_llm.py
└── benchmark/             # 基准报告
    ├── BENCHMARK_REPORT.md
    └── UPGRADE_REPORT_V4.md
```

### 许可

MIT

</details>

<details>
<summary><b>English</b></summary>

## Mental Barrier — Emotion Filtering Engine

A Claude Code SKILL for customer complaint emotion de-escalation and text sanitization.

Transforms profanity-laden, sarcastic, emotionally charged customer complaints into calm, objective natural language. Supports Chinese (homophones, pinyin abbreviations, number substitutions) and English.

### Features

- **Zero dependencies** — Pure Python stdlib, no pip install needed
- **Two-layer filtering** — DFA exact matching (400 words, 90.4% precision) + LLM semantic review
- **Key information preservation** — Order IDs, amounts, addresses, contacts, dates (Chinese + English), product models (16 entity types)
- **Adversarial robustness** — 7 bypass types: spacing/symbols, homophones, leet, CN-EN mixing, pinyin mixing, sarcasm, out-of-dictionary English
- **Natural language output** — Two-part format: emotion tag + sanitized text

### Installation

```bash
cp mental-barrier.skill ~/.claude/skills/
cd ~/.claude/skills && tar -xzf mental-barrier.skill
```

Or project-level:

```bash
cp mental-barrier.skill .claude/skills/
cd .claude/skills && tar -xzf mental-barrier.skill
```

Restart Claude Code after installation.

### Usage

```
/mental-barrier This fucking app is garbage wasted my money fix this shit now or refund me
```

Example output:

```
[情绪判断] 客户情绪激烈，含攻击性语言 — 以下为过滤后内容

The customer is dissatisfied with the app quality and requesting either an immediate fix or a refund.
```

### Architecture

Two-layer detection pipeline:

1. **DFA exact matching** (~0ms) — 400-word profanity dictionary, Trie-based O(n) scan, ASCII word boundary protection, fullwidth→halfwidth normalization
2. **LLM semantic review** — Homophones + spacing bypass + leet normalization (@→a, !→i) + sarcasm conversion + emoji semantic understanding + context reasoning

### Emoji Emotion Recognition

The DFA layer does not process emoji (text-only exact matching). The LLM layer handles emoji semantic understanding:

| Emoji | Meaning | Handling |
|-------|---------|----------|
| 🖕 | Middle finger (offensive) | Recognized as emotional expression, level 3+ |
| 💩 | Poop/shit (insult) | Recognized as profanity equivalent, removed |
| 🤬 | Swearing face (rage) | Recognized as emotional outburst, level 3 |
| 👍😊 used sarcastically | Positive emoji + negative context | Recognized as sarcasm, level 3 |
| 👍😊 genuine praise | Positive emoji + positive context | Not processed, passthrough |

Key capability: The LLM distinguishes between the **actual intent** and **literal meaning** of emoji — the same 👍 is positive in a genuine review but sarcastic in a complaint.

### Benchmarks

| Metric | Value (DeepSeek V4 Flash) | Target | Status |
|--------|--------------------------|--------|--------|
| DFA COLD F1 | 0.40 | ≥ 0.40 | PASS |
| DFA Precision | 90.4% | ≥ 80% | PASS |
| LLM Emotion Accuracy (strict) | 81.3% | ≥ 70% | PASS |
| LLM Emotion Accuracy (business) | 90.7% | ≥ 85% | PASS |
| LLM Profanity Removal | 97.2% | ≥ 85% | PASS |
| LLM Entity Retention | 95.8% | ≥ 90% | PASS |
| LLM Format Compliance | 97.6% | ≥ 90% | PASS |

> **Accuracy note**: Strict accuracy requires exact level match. Business accuracy allows level 3↔4 interchange (both trigger sanitization). Critical misclassifications (should sanitize but didn't) are only 2.7%.

### Production Simulation

Real-world performance without Claude Code framework overhead (see [mental-barrier-server/](../../mental-barrier-server/)):

| Metric | Production Sim | Claude Code | Improvement |
|--------|---------------|-------------|-------------|
| Avg Tokens | 994 | 12,066 | -92% |
| Avg Latency | 4.4s | 30s | -85% |
| Cost/call | ¥0.00055 | ~¥0.20 | -99.7% |
| Monthly (10K/day) | ¥165 | ¥60,000 | -99.7% |

### File Structure

```
mental-barrier/
├── SKILL.md              # Main skill file (YAML + Markdown, 241 lines, 8 few-shot)
├── README.md             # This file
├── scripts/
│   ├── dfa_filter.py     # DFA exact matching (zero deps, ASCII word boundary, fullwidth)
│   └── validator.py      # Entity retention validator (bilingual time, 16 patterns)
├── references/
│   ├── profanity_dict.txt # 402 customer-complaint profanity words
│   ├── profanity_en.txt   # 798 English profanity words
│   └── homophone_guide.md # Homophone reference (LLM knowledge source)
├── tests/
│   ├── test_cases.json    # 23 test cases
│   └── test_pipeline.py   # Automated tests (66/66 passed)
├── adversarial/           # Adversarial evaluation (182 cases)
│   ├── adversary_cases.json
│   ├── e2e_validate.py
│   └── batch_run_llm.py
└── benchmark/             # Benchmark reports
    ├── BENCHMARK_REPORT.md
    └── UPGRADE_REPORT_V4.md
```

### License

MIT

</details>
