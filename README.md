# dirty-words-clean — 客服情绪过滤引擎

[![Tests](https://img.shields.io/badge/tests-66%2F66%20passed-brightgreen)](mental-barrier/tests/test_pipeline.py)
[![Accuracy](https://img.shields.io/badge/business%20accuracy-92.9%25-blue)](mental-barrier-server/batch_results_182.json)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

<details open>
<summary><b>中文</b></summary>

## 项目简介

将充满辱骂、讽刺、情绪宣泄的客服投诉文本转化为冷静客观的自然语言表达，同时保留所有关键业务信息（订单号、金额、地址、电话等）。

支持中文（含谐音字、拼音缩写、数字替换等变体）和英文。

## 核心指标

| 指标 | 值 | 说明 |
|------|-----|------|
| 业务准确率 | **92.9%** | 允许级别 3↔4 互判（处理方式相同） |
| 严格准确率 | 81.3% | 情绪级别完全匹配 |
| 脏话清除率 | 97.2% | 净化文本中无脏话残留 |
| 实体保留率 | 95.8% | 订单号/电话/地址等不丢失 |
| DFA 精确率 | 90.4% | 误报率仅 2.69% |
| 平均 Token | 994 | 单次 LLM 调用消耗 |
| 平均延迟 | 4.4s | 端到端处理时间 |
| 单条成本 | ¥0.00055 | DeepSeek V4 Flash |

## 架构

```
输入文本 → DFA 精确匹配 (50ms) → LLM 语义审核 (4s) → Validator → 输出
                ↓                        ↓
         402 中文 + 798 英文词      情绪降级 + 文本净化
         Trie O(n) + 词边界       谐音/leet/讽刺/emoji
```

双层设计：DFA 负责精确匹配（高精确率、低召回率），LLM 负责语义理解（谐音变体、讽刺、上下文判断）。

## 项目结构

```
dirty-words-clean/
├── mental-barrier/              # 核心 SKILL（可独立使用）
│   ├── SKILL.md                 # 主指令文件（241行）
│   ├── scripts/                 # DFA + Validator 脚本
│   ├── references/              # 脏话词典 + 谐音对照表
│   ├── tests/                   # 单元测试（66/66 通过）
│   ├── adversarial/             # 对抗评测（182 用例）
│   └── benchmark/               # 基准报告
├── mental-barrier-server/       # 生产环境模拟（Web UI）
│   ├── server.py                # FastAPI 服务
│   ├── pipeline.py              # 管道编排
│   ├── prompts.py               # 精简版 system prompt
│   ├── static/ + templates/     # Web UI
│   └── batch_results_182.json   # 全量测试结果
└── data/                        # 测试数据集
```

## 快速开始

### 方式一：Claude Code SKILL（开发环境）

```bash
# 将 mental-barrier/ 复制到 .claude/skills/ 目录
cp -r mental-barrier ~/.claude/skills/

# 在 Claude Code 中使用
/mental-barrier 你们tmd这个破产品用了三天就坏了赶紧退款
```

### 方式二：本地 Web 服务（生产模拟）

```bash
cd mental-barrier-server
pip3 install -r requirements.txt
cp config.py.example config.py
# 编辑 config.py 填入 LLM_API_KEY

python3 server.py
# 浏览器打开 http://localhost:8000
```

## 技术测试报告

### 测试规模

- 66 单元测试（DFA + Validator + 对抗回归）
- 182 对抗用例（8 类变体：谐音/leet/空格绕过/中英混杂/拼音混杂/讽刺/英文俚语/正常文本）
- 全量 API 调用测试（182 条，DeepSeek V4 Flash）

### 按类别准确率

| 类别 | 严格准确率 | 用例数 | 说明 |
|------|-----------|--------|------|
| normal | 100% | 15 | 正常投诉，原文透传 |
| format_bypass | 90.3% | 31 | 空格/符号分隔绕过 |
| homophone | 82.4% | 51 | 中文谐音变体 |
| pinyin_mix | 80.0% | 15 | 拼音混杂 |
| cnen_mix | 75.0% | 20 | 中英混杂脏话 |
| leet | 75.0% | 20 | 数字/符号替换 |
| en_dfa_miss | 73.3% | 15 | 英文词典外脏话 |
| sarcasm | 66.7% | 15 | 讽刺/反语 |

### 成本对比

| 方案 | 单条成本 | 万次/天月成本 | 功能 |
|------|----------|-------------|------|
| Claude Code (Opus) | ¥0.20 | ¥60,000 | 完整（开发环境） |
| **本项目 (full)** | **¥0.00055** | **¥165** | 完整（情绪降级+净化） |
| 本项目 (hybrid) | ¥0.00022 | ¥66 | 完整（60% 短路） |
| 云厂商文本审核 | ¥0.001-0.002 | ¥300-600 | 仅分类，不净化 |

### 与云厂商的区别

云厂商（腾讯云/阿里云/百度云）的文本审核 API 只做**分类**（返回 Pass/Block/Review + 标签），不做**净化**。本项目做的是完整的情绪降级：输入一段骂人的投诉，输出一段冷静客观的描述，同时保留所有业务实体。

## 许可

MIT

</details>

<details>
<summary><b>English</b></summary>

## Overview

Transforms profanity-laden, sarcastic, emotionally charged customer complaints into calm, objective natural language while preserving all business-critical entities (order IDs, amounts, addresses, phone numbers, etc.).

Supports Chinese (homophones, pinyin abbreviations, number substitutions) and English.

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

## Architecture

```
Input → DFA Exact Match (50ms) → LLM Semantic Review (4s) → Validator → Output
              ↓                          ↓
       402 CN + 798 EN words      Emotion de-escalation
       Trie O(n) + boundaries     Homophones/leet/sarcasm/emoji
```

Two-layer design: DFA handles exact matching (high precision, low recall), LLM handles semantic understanding (homophone variants, sarcasm, context reasoning).

## Project Structure

```
dirty-words-clean/
├── mental-barrier/              # Core SKILL (standalone)
│   ├── SKILL.md                 # Main instruction file (241 lines)
│   ├── scripts/                 # DFA + Validator scripts
│   ├── references/              # Profanity dictionaries + homophone table
│   ├── tests/                   # Unit tests (66/66 passed)
│   ├── adversarial/             # Adversarial evaluation (182 cases)
│   └── benchmark/               # Benchmark reports
├── mental-barrier-server/       # Production simulation (Web UI)
│   ├── server.py                # FastAPI server
│   ├── pipeline.py              # Pipeline orchestration
│   ├── prompts.py               # Compact system prompt
│   ├── static/ + templates/     # Web UI
│   └── batch_results_182.json   # Full test results
└── data/                        # Test datasets
```

## Quick Start

### Option 1: Claude Code SKILL (Development)

```bash
cp -r mental-barrier ~/.claude/skills/

# Use in Claude Code
/mental-barrier This fucking app is garbage fix this shit now
```

### Option 2: Local Web Service (Production Simulation)

```bash
cd mental-barrier-server
pip3 install -r requirements.txt
cp config.py.example config.py
# Edit config.py with your LLM_API_KEY

python3 server.py
# Open http://localhost:8000
```

## Technical Test Report

### Test Scale

- 66 unit tests (DFA + Validator + adversarial regression)
- 182 adversarial cases (8 categories: homophones, leet, space bypass, CN-EN mix, pinyin mix, sarcasm, EN slang, normal)
- Full API call test (182 cases, DeepSeek V4 Flash)

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

### Cost Comparison

| Approach | Cost/call | Monthly (10K/day) | Capability |
|----------|-----------|-------------------|------------|
| Claude Code (Opus) | ¥0.20 | ¥60,000 | Full (dev environment) |
| **This project (full)** | **¥0.00055** | **¥165** | Full (de-escalation + sanitization) |
| This project (hybrid) | ¥0.00022 | ¥66 | Full (60% shortcircuit) |
| Cloud text moderation | ¥0.001-0.002 | ¥300-600 | Classification only |

### Difference from Cloud Providers

Cloud providers (Tencent Cloud/Alibaba Cloud/Baidu Cloud) text moderation APIs only do **classification** (return Pass/Block/Review + labels), not **sanitization**. This project performs full emotion de-escalation: input an angry complaint, output a calm objective description, while preserving all business entities.

## License

MIT

</details>
