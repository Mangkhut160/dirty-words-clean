# 精神内耗终结者 — 情绪过滤引擎

> **[English](README_EN.md)** | 中文

[![Tests](https://img.shields.io/badge/tests-66%2F66%20passed-brightgreen)](tests/test_pipeline.py)

---

## 概述

客户情绪降级与文本脱水 SKILL for Claude Code。将充满辱骂、讽刺、情绪宣泄的客服投诉文本转化为冷静客观的自然语言表达。

## 特性

- **零外部依赖** — 纯 Python 标准库，无需 pip install
- **双层过滤** — DFA 精确匹配（429 中文 + 1,071 英文词，分级）+ LLM 语义理解
- **英文增强** — Leet speak 归一化（sh1t→shit）、重复压缩（fuuuck→fuck）、审查绕过（f\*\*k）、缩写（stfu/gtfo）
- **关键信息保留** — 订单号、金额、地址、联系方式、日期等 16 种实体
- **对抗鲁棒** — 7 种对抗绕过检测：空格/符号分隔、谐音替换、Leet、中英混杂、拼音混杂、讽刺语义、词典外英文
- **纯自然语言输出** — 两段式格式：[情绪判断] + 净化后文本
- **DFA 测试 100% 通过** — 83 条常规 + 40 条边界样例，零误报

## 使用

### 在 Claude Code 中安装

```bash
# 方式1：克隆仓库后复制
git clone https://github.com/Mangkhut160/dirty-words-clean.git
cp -r dirty-words-clean/mental-barrier your-project/.claude/skills/mental-barrier

# 方式2：直接下载到项目
mkdir -p .claude/skills && cd .claude/skills
git clone https://github.com/Mangkhut160/dirty-words-clean.git --depth 1
mv dirty-words-clean/mental-barrier . && rm -rf dirty-words-clean
```

### 调用

```
/mental-barrier 你们tmd这个破产品用了三天就坏了赶紧退款
```

输出：
```
[情绪判断] 客户情绪激烈，含攻击性语言 — 以下为过滤后内容

DFA 检测到 1 处情绪化表达（tmd），已过滤。

客户反馈购买的产品使用三天后出现故障，要求退款处理。
```

## 基准评测

| 指标 | 值 (DeepSeek V4 Flash) | 目标 | 判定 |
|------|----------------------|------|------|
| DFA COLD F1 | 0.40 | ≥ 0.40 | PASS |
| DFA 精确率 | 90.4% | ≥ 80% | PASS |
| 情绪准确率（严格） | 81.3% | ≥ 70% | PASS |
| 情绪准确率（业务） | 92.9% | ≥ 85% | PASS |
| 脏话清除率 | 97.2% | ≥ 85% | PASS |
| 实体保留率 | 95.8% | ≥ 90% | PASS |
| 格式合规率 | 97.6% | ≥ 90% | PASS |

> **准确率说明**：严格准确率要求情绪级别完全匹配。业务准确率允许级别 3↔4 互判（两者处理方式相同，都需要净化）。严重误判仅占 7.1%。

## 生产环境模拟

去掉 Claude Code 框架开销后的真实性能（详见 [mental-barrier-server/](../mental-barrier-server/)）：

| 指标 | 生产模拟 | Claude Code | 提升 |
|------|----------|-------------|------|
| 平均 Token | 994 | 12,066 | -92% |
| 平均延迟 | 4.4s | 30s | -85% |
| 单条成本 | ¥0.00055 | ~¥0.20 | -99.7% |
| 万次/天月成本 | ¥165 | ¥60,000 | -99.7% |

## 架构

```
输入文本
  │
  ▼
┌─────────────────────────────────────┐
│  第1层：DFA 精确匹配 (~50ms)         │
│  429 中文 + 1,071 英文词（分级）      │
│  Trie O(n) + 词边界 + 全角 + Leet归一化│
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│  第2层：LLM 语义审核                 │
│  谐音变体 / 空格绕过 / Leet          │
│  讽刺转化 / Emoji / 中英混杂         │
└─────────────────────────────────────┘
  │
  ▼
输出：[情绪判断] + 净化文本
```

## 文件结构

```
mental-barrier/
├── SKILL.md                 # 主指令文件（241行，8个few-shot）
├── scripts/
│   ├── dfa_filter.py        # DFA 精确匹配（全角 + Leet归一化 + 重复压缩）
│   └── validator.py         # 实体保留验证（16种实体，支持中英数字等价）
├── references/
│   ├── profanity_dict.txt   # 429 中文脏话词
│   ├── profanity_en.txt     # 1,071 英文脏话词（Level 3/4 分级）
│   └── homophone_guide.md   # 谐音变体参考
├── tests/
│   ├── test_cases.json      # 23 条测试用例
│   └── test_pipeline.py     # 自动化测试
├── adversarial/             # 对抗评测（182 用例）
└── benchmark/               # 基准报告
```

## 版本对比

| | mental-barrier (Skill) | mental-barrier-server (Server) |
|---|---|---|
| 运行方式 | Claude Code 内直接调用 | 独立 FastAPI 服务 |
| LLM | Claude 自身 | MiniMax M2.7（需 API key） |
| 适合场景 | 开发/体验/少量使用 | 生产部署/批量测试/成本验证 |
| 依赖 | 零（纯 Python 标准库） | pip install + API key |
| 成本 | 包含在 Claude 订阅内 | ¥0.00055/条 |
| 在线演示 | — | [HF Spaces](https://huggingface.co/spaces/pzr114514/skills-demo) |

> **推荐**：如果只是想在 Claude Code 里体验，直接用 `mental-barrier/` 目录即可，零配置开箱即用。

## 许可

MIT
