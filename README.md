# dirty-words-clean

[![Tests](https://img.shields.io/badge/tests-66%2F66%20passed-brightgreen)](mental-barrier/tests/test_pipeline.py)
[![Accuracy](https://img.shields.io/badge/business%20accuracy-92.9%25-blue)](mental-barrier-server/batch_results_182.json)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**客服情绪过滤引擎 | Customer Emotion Filtering Engine**

将充满辱骂、讽刺、情绪宣泄的客服投诉文本转化为冷静客观的自然语言表达，同时保留所有关键业务信息。支持中文（含谐音字、拼音缩写、数字替换等变体）和英文。

Transforms profanity-laden, sarcastic, emotionally charged customer complaints into calm, objective natural language while preserving all business-critical entities. Supports Chinese (homophones, pinyin, number substitutions) and English.

---

## 核心指标 | Key Metrics

| 指标 Metric | 值 Value | 说明 Description |
|-------------|----------|-----------------|
| 业务准确率 Business Accuracy | **92.9%** | 允许级别3↔4互判 / Allowing level 3↔4 interchange |
| 严格准确率 Strict Accuracy | 81.3% | 情绪级别完全匹配 / Exact level match |
| 脏话清除率 Profanity Removal | 97.2% | 净化文本无残留 / No profanity in output |
| 实体保留率 Entity Retention | 95.8% | 订单号/电话/地址不丢失 / IDs/phones/addresses preserved |
| DFA 精确率 DFA Precision | 90.4% | 误报率仅2.69% / FPR only 2.69% |
| 平均 Token Avg Tokens | 994 | 单次LLM调用 / Per LLM call |
| 平均延迟 Avg Latency | 4.4s | 端到端 / End-to-end |
| 单条成本 Cost/call | ¥0.00055 | DeepSeek V4 Flash |

---

## 架构 | Architecture

```
输入 Input → DFA 精确匹配 Exact Match (50ms) → LLM 语义审核 Semantic Review (4s) → Validator → 输出 Output
                    ↓                                    ↓
             402中文 + 798英文词                    情绪降级 + 文本净化
             Trie O(n) + 词边界                   谐音/leet/讽刺/emoji
```

双层设计：DFA 负责精确匹配（高精确率），LLM 负责语义理解（谐音变体、讽刺、上下文）。

Two-layer design: DFA handles exact matching (high precision), LLM handles semantic understanding (homophones, sarcasm, context).

---

## 项目结构 | Project Structure

```
dirty-words-clean/
├── mental-barrier/              # 核心 SKILL / Core SKILL (standalone)
│   ├── SKILL.md                 # 主指令 / Main instructions (241 lines)
│   ├── scripts/                 # DFA + Validator
│   ├── references/              # 脏话词典 + 谐音表 / Dictionaries + homophone table
│   ├── tests/                   # 单元测试 / Unit tests (66/66)
│   ├── adversarial/             # 对抗评测 / Adversarial eval (182 cases)
│   └── benchmark/               # 基准报告 / Benchmark reports
├── mental-barrier-server/       # 生产模拟 Web UI / Production simulation
│   ├── server.py                # FastAPI 服务 / FastAPI server
│   ├── pipeline.py              # 管道编排 / Pipeline orchestration
│   ├── prompts.py               # 精简 prompt / Compact system prompt
│   ├── static/ + templates/     # Web UI
│   └── batch_results_182.json   # 全量测试结果 / Full test results
└── data/                        # 测试数据集 / Test datasets
```

---

## 快速开始 | Quick Start

### 方式一：Claude Code SKILL | Option 1: Claude Code SKILL

```bash
cp -r mental-barrier ~/.claude/skills/

# 使用 / Usage:
/mental-barrier 你们tmd这个破产品用了三天就坏了赶紧退款
/mental-barrier This fucking app is garbage fix this shit now
```

### 方式二：本地 Web 服务 | Option 2: Local Web Service

```bash
cd mental-barrier-server
pip3 install -r requirements.txt
cp config.py.example config.py
# 编辑 config.py 填入 LLM_API_KEY / Edit config.py with your API key

python3 server.py
# 浏览器打开 / Open http://localhost:8000
```

---

## 技术测试报告 | Technical Test Report

### 测试规模 | Test Scale

- 66 单元测试 / unit tests（DFA + Validator + 对抗回归 / adversarial regression）
- 182 对抗用例 / adversarial cases（8 类变体 / 8 variant categories）
- 全量 API 测试 / Full API test（182 条, DeepSeek V4 Flash）

### 按类别准确率 | Accuracy by Category

| 类别 Category | 准确率 Accuracy | 用例 Cases | 说明 Description |
|---------------|----------------|------------|-----------------|
| normal 正常文本 | 100% | 15 | 原文透传 / Passthrough |
| format_bypass 格式绕过 | 90.3% | 31 | 空格/符号分隔 / Space/symbol separated |
| homophone 谐音变体 | 82.4% | 51 | 中文谐音 / Chinese homophones |
| pinyin_mix 拼音混杂 | 80.0% | 15 | 拼音+中文 / Pinyin mixed |
| cnen_mix 中英混杂 | 75.0% | 20 | 中英混合脏话 / CN-EN mixed |
| leet 符号替换 | 75.0% | 20 | 数字/符号 / Number/symbol substitution |
| en_dfa_miss 英文俚语 | 73.3% | 15 | 词典外英文 / Out-of-dictionary English |
| sarcasm 讽刺 | 66.7% | 15 | 反语表达 / Irony/sarcasm |

### 准确率说明 | Accuracy Explanation

81.3% 是严格匹配（情绪级别完全一致）。在客服业务中：

81.3% requires exact level match. In customer service scenarios:

- 级别 3（愤怒）和 4（辱骂）处理方式相同（都净化），互判无业务影响
- Levels 3 (angry) and 4 (abusive) have identical handling (both sanitize), interchange has zero business impact
- 业务准确率 **92.9%**：允许 3↔4 互判后的可用率
- Business accuracy **92.9%**: usable rate allowing 3↔4 interchange
- 严重误判（该净化没净化）仅 13 条 = **7.1%**
- Critical errors (should sanitize but didn't) only 13 cases = **7.1%**

### 成本对比 | Cost Comparison

| 方案 Approach | 单条 Cost/call | 万次/天月成本 Monthly (10K/day) | 功能 Capability |
|---------------|---------------|-------------------------------|-----------------|
| Claude Code (Opus) | ¥0.20 | ¥60,000 | 完整 Full (dev) |
| **本项目 This project (full)** | **¥0.00055** | **¥165** | 完整 Full (production) |
| 本项目 This project (hybrid) | ¥0.00022 | ¥66 | 完整 Full (60% shortcircuit) |
| 云厂商 Cloud moderation | ¥0.001-0.002 | ¥300-600 | 仅分类 Classification only |

### 与云厂商的区别 | Difference from Cloud Providers

云厂商（腾讯云/阿里云/百度云）文本审核 API 只做**分类**（Pass/Block/Review），不做**净化**。本项目做完整的情绪降级：输入骂人的投诉，输出冷静客观的描述，保留所有业务实体。

Cloud providers only do **classification** (Pass/Block/Review), not **sanitization**. This project performs full emotion de-escalation: input an angry complaint, output a calm description, preserving all business entities.

---

## 许可 | License

MIT
