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

1. **DFA 精确匹配**（~0ms）— 400 客服投诉专用脏话词典，Trie 树 O(n) 遍历，ASCII 词边界防误报
2. **LLM 语义审核** — 谐音变体 + 空格绕过 + Leet 还原（@→a, !→i）+ 讽刺转化 + 语境理解

### 基准评测

| 指标 | 值 (DeepSeek V4) | 目标 |
|------|-----------------|------|
| DFA COLD F1 | 0.40 | — |
| DFA 精确率 | 90.4% | ≥ 80% |
| LLM 情绪准确率 | 74.8% | ≥ 70% |
| LLM 脏话清除率 | 72.5% | ≥ 70% |
| LLM 实体保留率 | 95.9% | ≥ 90% |
| LLM 格式合规率 | 97.6% | ≥ 90% |
| DFA→LLM 增益 | 61.6% | ≥ 50% |

### 文件结构

```
mental-barrier/
├── SKILL.md              # 主指令文件（YAML + Markdown, 282行, 10个few-shot）
├── README.md             # 本文件
├── scripts/
│   ├── dfa_filter.py     # DFA 精确匹配（零依赖, ASCII词边界）
│   └── validator.py      # 实体保留验证（中英双语时间, 16种实体）
├── references/
│   ├── profanity_dict.txt # 400 客服投诉专用脏话词
│   ├── profanity_en.txt   # 英文脏话词补充
│   └── homophone_guide.md # 谐音变体参考（LLM 知识源）
└── tests/
    ├── test_cases.json    # 23 条测试用例
    └── test_pipeline.py   # 自动化测试 (66/66 通过)
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

1. **DFA exact matching** (~0ms) — 400-word profanity dictionary, Trie-based O(n) scan, ASCII word boundary protection
2. **LLM semantic review** — Homophones + spacing bypass + leet normalization (@→a, !→i) + sarcasm conversion + context understanding

### Benchmarks

| Metric | Value (DeepSeek V4) | Target |
|--------|-----------------|--------|
| DFA COLD F1 | 0.40 | — |
| DFA Precision | 90.4% | ≥ 80% |
| LLM Emotion Accuracy | 74.8% | ≥ 70% |
| LLM Profanity Removal | 72.5% | ≥ 70% |
| LLM Entity Retention | 95.9% | ≥ 90% |
| LLM Format Compliance | 97.6% | ≥ 90% |
| DFA→LLM Gain | 61.6% | ≥ 50% |

### File Structure

```
mental-barrier/
├── SKILL.md              # Main skill file (YAML + Markdown, 282 lines, 10 few-shot)
├── README.md             # This file
├── scripts/
│   ├── dfa_filter.py     # DFA exact matching (zero deps, ASCII word boundary)
│   └── validator.py      # Entity retention validator (bilingual time, 16 patterns)
├── references/
│   ├── profanity_dict.txt # 400 customer-complaint profanity words
│   ├── profanity_en.txt   # English supplement
│   └── homophone_guide.md # Homophone reference (LLM knowledge source)
└── tests/
    ├── test_cases.json    # 23 test cases
    └── test_pipeline.py   # Automated tests (66/66 passed)
```

### License

MIT

</details>
