# ToneBarrier — 客服情绪过滤引擎

> **[English](README_EN.md)** | 中文

[![Tests](https://img.shields.io/badge/tests-81%2F81%20passed-brightgreen)](evaluation/tonebarrier/tests/test_pipeline.py)
[![Accuracy](https://img.shields.io/badge/业务准确率-92.9%25-blue)](tonebarrier-server/batch_results_182.json)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)

---

## 项目简介

将充满辱骂、讽刺、情绪宣泄的客服投诉文本转化为冷静客观的自然语言表达，同时保留所有关键业务信息（订单号、金额、地址、电话等）。

支持中文（含谐音字、拼音缩写、数字替换等变体）和英文。

---

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

---

## 架构

```
输入文本 → DFA 精确匹配 (50ms) → LLM 语义审核 (4s) → Validator → 输出
                ↓                        ↓
         402 中文 + 798 英文词      情绪降级 + 文本净化
         Trie O(n) + 词边界       谐音/leet/讽刺/emoji
```

双层设计：DFA 负责精确匹配（高精确率、低召回率），LLM 负责语义理解（谐音变体、讽刺、上下文判断）。

---

## 项目结构

```
ToneBarrier/
├── skills/tonebarrier/       # 轻量 Claude Code Skill（可直接安装）
│   ├── SKILL.md                 # 主指令文件（241行）
│   ├── scripts/                 # DFA + Validator 脚本
│   ├── references/              # 脏话词典 + 谐音对照表
│   ├── tests/                   # 自动化回归测试（81/81 通过）
│   ├── adversarial/             # 对抗评测（182 用例）
│   └── benchmark/               # 基准报告
├── tonebarrier-server/       # 生产环境模拟（Web UI）
│   ├── server.py                # FastAPI 服务
│   ├── pipeline.py              # 管道编排
│   ├── prompts.py               # 精简版 system prompt
│   ├── static/ + templates/     # Web UI
│   └── batch_results_182.json   # 全量测试结果
└── data/                        # 测试数据集
```

---

## 快速开始

### 方式一：Claude Code SKILL

```bash
git clone https://github.com/Mangkhut160/dirty-words-clean.git
mkdir -p ~/.claude/skills
cp -r dirty-words-clean/skills/tonebarrier ~/.claude/skills/tonebarrier

# 使用：
/tonebarrier 你们tmd这个破产品用了三天就坏了赶紧退款
```

### 方式二：本地 Web 服务

```bash
cd tonebarrier-server
pip3 install -r requirements.txt
cp config.py.example config.py
# 编辑 config.py 填入 LLM_API_KEY

python3 server.py
# 浏览器打开 http://localhost:8000
```

---

## 技术测试报告

### 测试规模

- 81 条自动化回归检查（DFA + Validator + 对抗回归）
- 182 对抗用例（8 类变体：谐音/leet/空格绕过/中英混杂/拼音混杂/讽刺/英文俚语/正常文本）
- 全量 API 调用测试（182 条，DeepSeek V4 Flash，总成本 ¥0.10）

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

### 准确率说明

81.3% 是严格匹配（情绪级别完全一致）。在客服业务中：

- **级别 3（愤怒）和 4（辱骂）处理方式相同**（都需要净化），互判无业务影响
- **业务准确率 92.9%**：允许 3↔4 互判后的可用率
- **严重误判**（该净化没净化）仅 13 条 = 7.1%
- **重试机制**：空响应自动重试最多 2 次，格式失败 0 条

### 错误模式

| 模式 | 次数 | 业务影响 | 说明 |
|------|------|----------|------|
| 4→3 | 9 | 无（都净化） | leet/空格绕过被低估 |
| 3→4 | 8 | 无（都净化） | 感叹粗口被高估 |
| 4→2 | 5 | 有（漏净化） | 罕见变体未识别 |
| 3→2 | 5 | 有（漏净化） | 讽刺未被识别 |
| 其他 | 7 | 低 | 格式/边界 |

### 成本对比

| 方案 | 单条成本 | 万次/天月成本 | 功能 |
|------|----------|-------------|------|
| Claude Code (Opus) | ¥0.20 | ¥60,000 | 完整（开发环境） |
| **本项目 (full)** | **¥0.00055** | **¥165** | 完整（情绪降级+净化） |
| 本项目 (hybrid) | ¥0.00022 | ¥66 | 完整（60% 短路） |
| 云厂商文本审核 | ¥0.001-0.002 | ¥300-600 | 仅分类，不净化 |

### 与云厂商的区别

云厂商（腾讯云/阿里云/百度云）的文本审核 API 只做**分类**（返回 Pass/Block/Review + 标签），不做**净化**。本项目做的是完整的情绪降级：输入一段骂人的投诉，输出一段冷静客观的描述，同时保留所有业务实体。

---

## 许可

MIT
