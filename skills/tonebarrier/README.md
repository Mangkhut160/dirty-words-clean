# ToneBarrier

[![Tests](https://img.shields.io/badge/tests-81%2F81%20passed-brightgreen)](../../evaluation/tonebarrier/tests/test_pipeline.py)
[![Version](https://img.shields.io/badge/version-V4-orange)](../../evaluation/tonebarrier/benchmark/UPGRADE_REPORT_V4.md)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.6%2B-blue)](https://python.org)

<details open>
<summary><b>中文</b></summary>

## ToneBarrier — 客服情绪过滤引擎

客户情绪降级与文本脱水 SKILL for Claude Code。

将充满辱骂、讽刺、情绪宣泄的客服投诉文本转化为冷静客观的自然语言表达。支持中文（含谐音字、拼音缩写、数字替换等变体）和英文。

### 特性

- **零外部依赖** — 纯 Python 标准库，无需 pip install
- **双层过滤** — DFA 精确匹配（中文 402 词 + 英文 798 词，精确率 90.4%）+ LLM 语义理解
- **关键信息保留** — 订单号、金额、地址、联系方式、日期（中英双语）、产品型号等 16 种实体
- **对抗鲁棒** — 7 种对抗绕过检测：空格/符号分隔、谐音替换、Leet、中英混杂、拼音混杂、讽刺语义、词典外英文
- **纯自然语言输出** — 两段式格式：[情绪判断] + 净化后文本

### 安装

```bash
git clone https://github.com/Mangkhut160/dirty-words-clean.git
mkdir -p ~/.claude/skills
cp -r dirty-words-clean/skills/tonebarrier ~/.claude/skills/tonebarrier
```

项目级：

```bash
mkdir -p .claude/skills
cp -r dirty-words-clean/skills/tonebarrier .claude/skills/tonebarrier
```

安装后重启 Claude Code。

### 使用

```
/tonebarrier 你们tmd这个破产品用了三天就坏了赶紧退款
```

输出示例：

```
[情绪判断] 客户情绪激烈，含攻击性语言 — 以下为过滤后内容

DFA 检测到 1 处情绪化表达（tmd），已过滤。

客户反馈购买的产品使用三天后出现故障，要求退款处理。
```

### 架构

双层检测管道：

1. **DFA 精确匹配**（~0ms）— 1200 客服投诉专用脏话词典（中文 402 + 英文 798），Trie 树 O(n) 遍历，ASCII 词边界防误报，全角→半角预处理
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

**DFA 层（COLD 数据集, 25726 条）**

| 指标 | 值 | 目标 | 判定 |
|------|-----|------|------|
| 精确率 | 90.4% | ≥ 80% | PASS |
| 召回率 | 26.0% | — | — |
| F1 | 0.40 | ≥ 0.40 | PASS |
| 误报率 | 2.69% | ≤ 5% | PASS |

> **召回率说明**：COLD 数据集 96.7% 为隐式仇恨言论（无显性脏话），DFA 理论上限约 28.9%，当前 26.0% 已接近天花板。

**LLM 层 — 生产模拟（182 条, DeepSeek V4 Flash）**

| 指标 | 值 | 目标 | 判定 |
|------|-----|------|------|
| 情绪准确率（严格） | 81.3% | ≥ 70% | PASS |
| 情绪准确率（业务） | 92.9% | ≥ 85% | PASS |
| 脏话清除率 | 97.2% | ≥ 85% | PASS |
| 实体保留率 | 95.8% | ≥ 90% | PASS |
| 格式合规率 | 97.6% | ≥ 90% | PASS |

> **准确率说明**：严格准确率要求情绪级别完全匹配。业务准确率允许级别 3↔4 互判（两者处理方式相同，都需要净化）。真正影响业务的严重误判（该净化的没净化）仅占 2.7%。

> **V4 关键改进**：脏话清除率从 72.5%→97.2%（修复验证脚本 bug），情绪准确率 74.8%→76.4%（E2E 对抗评测）。详见 [UPGRADE_REPORT_V4.md](../../evaluation/tonebarrier/benchmark/UPGRADE_REPORT_V4.md)。

**消融测试（43 条, DeepSeek V4 Flash）**

对比完整 SKILL、仅 prompt 指令、无 SKILL 三种配置：

| 维度 | 完整 SKILL（A） | 仅 prompt（B） | 无 SKILL（C） |
|------|:--------------:|:-------------:|:------------:|
| 格式合规 | **100%** | 98% | 0% |
| 情绪标签正确 | **100%** | 86% | 0% |
| 原文透传（L1-2） | **100%** | 88% | 0% |
| 脏话清除（L3-4） | **100%** | 100% | 100% |
| 实体保留 | **100%** | 83% | 50% |
| DFA 摘要行（可审计） | **43%** | 0% | 0% |

> **结论**：脏话清除是 LLM 基础能力，三组均达 100%。格式合规和情绪分级完全依赖 prompt 指令（C 组 0%）。完整 SKILL 相比仅 prompt 的增量价值在于：few-shot 将情绪标签准确率从 86% 提升至 100%，validator 将实体保留从 83% 提升至 100%，DFA 摘要行提供可审计的检测证据。详见 消融测试报告（内部实验记录，未随公开仓库分发）。

### 生产环境模拟

去掉 Claude Code 框架开销后的真实性能（详见 [tonebarrier-server/](../../tonebarrier-server/)）：

| 指标 | 生产模拟 | Claude Code | 提升 |
|------|----------|-------------|------|
| 平均 Token | 994 | 12,066 | -92% |
| 平均延迟 | 4.4s | 30s | -85% |
| 单条成本 | ¥0.00055 | ~¥0.20 | -99.7% |
| 万次/天月成本 | ¥165 | ¥60,000 | -99.7% |

### 文件结构

```
skills/tonebarrier/
├── SKILL.md              # 主指令文件（YAML + Markdown, 241行, 8个few-shot）
├── README.md             # 本文件
├── scripts/
│   ├── dfa_filter.py     # DFA 精确匹配（零依赖, ASCII词边界, 全角预处理）
│   └── validator.py      # 实体保留验证（中英双语时间, 16种实体）
├── references/
│   ├── profanity_dict.txt # 402 中文客服投诉脏话词
│   ├── profanity_en.txt   # 798 英文脏话词
│   └── homophone_guide.md # 谐音变体参考（LLM 知识源）
└── README.md             # Skill 使用说明
```

评测与回归测试位于 `evaluation/tonebarrier/`：

```
evaluation/tonebarrier/
├── tests/                 # 自动化测试 (81/81 通过)
├── adversarial/           # 对抗评测（182 用例）
│   ├── adversary_cases.json
│   ├── adversary_regression.json  # 23 条回归用例
│   ├── e2e_validate.py
│   ├── batch_run_llm.py
│   ├── generate_adversary.py
│   ├── judge_adversary.py
│   ├── run_adversary.py
│   └── llm_real_outputs_*.json   # DeepSeek 等模型输出
└── benchmark/             # 基准报告
    ├── BENCHMARK_REPORT.md       # 综合评测报告
    ├── EVALUATION_REPORT.md      # 评估报告
    ├── UPGRADE_REPORT_V4.md      # V4 升级报告
    ├── dfa_eval.py               # DFA 评测脚本
    ├── skill_eval.py             # Skill 评测脚本
    └── report.py                 # 报告生成器
```

### 许可

MIT

</details>

<details>
<summary><b>English</b></summary>

## ToneBarrier — Customer Emotion Filtering Engine

A Claude Code SKILL for customer complaint emotion de-escalation and text sanitization.

Transforms profanity-laden, sarcastic, emotionally charged customer complaints into calm, objective natural language. Supports Chinese (homophones, pinyin abbreviations, number substitutions) and English.

### Features

- **Zero dependencies** — Pure Python stdlib, no pip install needed
- **Two-layer filtering** — DFA exact matching (CN 402 + EN 798 words, 90.4% precision) + LLM semantic review
- **Key information preservation** — Order IDs, amounts, addresses, contacts, dates (Chinese + English), product models (16 entity types)
- **Adversarial robustness** — 7 bypass types: spacing/symbols, homophones, leet, CN-EN mixing, pinyin mixing, sarcasm, out-of-dictionary English
- **Natural language output** — Two-part format: emotion tag + sanitized text

### Installation

```bash
git clone https://github.com/Mangkhut160/dirty-words-clean.git
mkdir -p ~/.claude/skills
cp -r dirty-words-clean/skills/tonebarrier ~/.claude/skills/tonebarrier
```

Or project-level:

```bash
mkdir -p .claude/skills
cp -r dirty-words-clean/skills/tonebarrier .claude/skills/tonebarrier
```

Restart Claude Code after installation.

### Usage

```
/tonebarrier This fucking app is garbage wasted my money fix this shit now or refund me
```

Example output:

```
[情绪判断] 客户情绪激烈，含攻击性语言 — 以下为过滤后内容

The customer is dissatisfied with the app quality and requesting either an immediate fix or a refund.
```

### Architecture

Two-layer detection pipeline:

1. **DFA exact matching** (~0ms) — 1200-word profanity dictionary (CN 402 + EN 798), Trie-based O(n) scan, ASCII word boundary protection, fullwidth→halfwidth normalization
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

**DFA Layer (COLD dataset, 25726 samples)**

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Precision | 90.4% | ≥ 80% | PASS |
| Recall | 26.0% | — | — |
| F1 | 0.40 | ≥ 0.40 | PASS |
| FPR | 2.69% | ≤ 5% | PASS |

> **Recall note**: 96.7% of COLD samples are implicit hate speech (no explicit profanity). DFA theoretical ceiling is ~28.9%; current 26.0% is near the limit.

**LLM Layer — Production Simulation (182 cases, DeepSeek V4 Flash)**

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Emotion Accuracy (strict) | 81.3% | ≥ 70% | PASS |
| Emotion Accuracy (business) | 92.9% | ≥ 85% | PASS |
| Profanity Removal | 97.2% | ≥ 85% | PASS |
| Entity Retention | 95.8% | ≥ 90% | PASS |
| Format Compliance | 97.6% | ≥ 90% | PASS |

> **Accuracy note**: Strict accuracy requires exact level match. Business accuracy allows level 3↔4 interchange (both trigger sanitization). Critical misclassifications (should sanitize but didn't) are only 2.7%.

> **V4 key improvements**: Profanity removal 72.5%→97.2% (fixed validator bug), emotion accuracy 74.8%→76.4% (E2E adversarial). See [UPGRADE_REPORT_V4.md](../../evaluation/tonebarrier/benchmark/UPGRADE_REPORT_V4.md).

**Ablation Study (43 cases, DeepSeek V4 Flash)**

Comparing full SKILL, prompt-only, and no-SKILL configurations:

| Metric | Full SKILL (A) | Prompt-only (B) | No SKILL (C) |
|--------|:--------------:|:---------------:|:------------:|
| Format compliance | **100%** | 98% | 0% |
| Emotion label accuracy | **100%** | 86% | 0% |
| Passthrough (L1-2) | **100%** | 88% | 0% |
| Profanity removal (L3-4) | **100%** | 100% | 100% |
| Entity retention | **100%** | 83% | 50% |
| DFA audit trail | **43%** | 0% | 0% |

> **Conclusion**: Profanity removal is a baseline LLM capability (all three reach 100%). Format compliance and emotion labeling depend entirely on prompt instructions (C group: 0%). The full SKILL's incremental value over prompt-only: few-shot examples raise emotion accuracy from 86% to 100%, validator raises entity retention from 83% to 100%, and DFA summary lines provide auditable detection evidence.

### Production Simulation

Real-world performance without Claude Code framework overhead (see [tonebarrier-server/](../../tonebarrier-server/)):

| Metric | Production Sim | Claude Code | Improvement |
|--------|---------------|-------------|-------------|
| Avg Tokens | 994 | 12,066 | -92% |
| Avg Latency | 4.4s | 30s | -85% |
| Cost/call | ¥0.00055 | ~¥0.20 | -99.7% |
| Monthly (10K/day) | ¥165 | ¥60,000 | -99.7% |

### File Structure

```
skills/tonebarrier/
├── SKILL.md              # Main skill file (YAML + Markdown, 241 lines, 8 few-shot)
├── README.md             # This file
├── scripts/
│   ├── dfa_filter.py     # DFA exact matching (zero deps, ASCII word boundary, fullwidth)
│   ├── validator.py      # Entity retention validator (bilingual time, 16 patterns)
│   ├── add_new_words.py  # Dictionary expansion tool
│   ├── analyze_missed_v2.py   # Missed detection analysis
│   ├── analyze_missed_words.py # Missed word analysis
│   └── evaluate_candidates.py  # Candidate word evaluation
├── references/
│   ├── profanity_dict.txt # 402 Chinese customer-complaint profanity words
│   ├── profanity_en.txt   # 798 English profanity words
│   └── homophone_guide.md # Homophone reference (LLM knowledge source)
├── tests/
│   ├── test_cases.json    # 23 test cases
│   └── test_pipeline.py   # Automated tests (81/81 passed)
├── adversarial/           # Adversarial evaluation (182 cases, multi-model)
│   ├── adversary_cases.json
│   ├── adversary_regression.json  # 23 regression cases
│   ├── e2e_validate.py
│   ├── batch_run_llm.py
│   ├── generate_adversary.py
│   ├── judge_adversary.py
│   ├── run_adversary.py
│   └── llm_real_outputs_*.json   # DeepSeek and other model outputs
└── benchmark/             # Benchmark reports
    ├── BENCHMARK_REPORT.md       # Comprehensive evaluation report
    ├── EVALUATION_REPORT.md      # Evaluation report
    ├── UPGRADE_REPORT_V4.md      # V4 upgrade report
    ├── dfa_eval.py               # DFA evaluation script
    ├── skill_eval.py             # Skill evaluation script
    └── report.py                 # Report generator
```

### License

MIT

</details>
