---
title: ToneBarrier — 情绪过滤引擎
emoji: 🧠
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: false
license: mit
app_port: 7860
---

# ToneBarrier — 生产环境模拟服务

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek%20V4%20Flash-purple)](https://deepseek.com)
[![HF Spaces](https://img.shields.io/badge/Demo-HuggingFace%20Spaces-yellow)](https://huggingface.co/spaces/pzr114514/skills-demo)

> **在线演示**: https://huggingface.co/spaces/pzr114514/skills-demo （支持中英双语切换）

<details open>
<summary><b>中文</b></summary>

## 概述

本服务是 [ToneBarrier Skill](../skills/tonebarrier/) 的生产环境模拟，去掉 Claude Code 框架开销，直接通过 API 调用实现完整的情绪过滤管道。用于验证真实 token 消耗、延迟和成本。

### 核心指标（182 条全量测试）

| 指标 | 生产模拟 | Claude Code | 提升 |
|------|----------|-------------|------|
| 严格准确率 | 81.3% | 76.4% | +4.9% |
| 业务准确率 | 92.9% | — | — |
| 平均 Token | 994 | 12,066 | **-92%** |
| 平均延迟 | 4.4s | 30s | **-85%** |
| 单条成本 | ¥0.00055 | ~¥0.20 | **-99.7%** |
| 覆盖率 | 100% (182/182) | 69.8% (127/182) | +30% |
| 格式失败 | 0 条 | — | 重试机制保障 |

### DFA 引擎指标（83 条测试 + 40 条边界样例）

| 指标 | 数值 |
|------|------|
| 英文词典 | 1,071 条（Level 4: 1,009 + Level 3: 40），来源 surge-ai + dsojevic |
| 中文词典 | 429 条 |
| DFA 测试通过率 | **100%**（83/83 常规 + 40/40 边界） |
| Leet speak 检出 | sh1t, @ss, f4ck, a55 等 ✓ |
| 重复字符检出 | fuuuuck, shiiiit 等 ✓ |
| 审查绕过检出 | f\*\*k, s\*\*t 等 ✓ |
| 缩写检出 | stfu, gtfo, bs, ffs 等 ✓ |
| 误报率 | 0%（assassin, classic, cocktail, Dickens 等零误报） |

### 准确率说明

81.3% 是严格匹配（预期级别与实际级别完全一致）。在客服业务场景中：

- **级别 3 和 4 处理方式相同**（都需要净化），3↔4 互判不影响业务结果
- **业务准确率 92.9%**：允许 3↔4 互判后的可用率
- **真正影响业务的严重误判**（该净化的没净化，或不该净化的被净化了）仅 13 条，占 **7.1%**
- **重试机制**：空响应自动重试最多 2 次，格式失败从 4 条降至 0 条

### 错误模式

| 模式 | 次数 | 业务影响 | 说明 |
|------|------|----------|------|
| 4→3 | 9 | 无（都净化） | leet/空格绕过被低估 |
| 3→4 | 8 | 无（都净化） | 感叹粗口被高估 |
| 4→2 | 5 | **有**（漏净化） | 罕见变体未识别 |
| 3→2 | 5 | **有**（漏净化） | 讽刺未被识别 |
| 4→None | 4 | 有（格式错误） | 输出格式解析失败 |
| 其他 | 3 | 低 | 边界模糊 |

## 快速开始

### 安装

```bash
cd tonebarrier-server
pip3 install -r requirements.txt
```

### 配置

编辑 `config.py` 或设置环境变量：

```bash
export LLM_API_KEY="your-deepseek-api-key"
export LLM_BASE_URL="https://api.deepseek.com"
export LLM_MODEL="deepseek-chat"
```

### 启动

```bash
python3 server.py
# 浏览器打开 http://localhost:8000
```

## 功能

### Web UI（三栏界面）

1. **手动测试** — 输入文本，选择模式（full/hybrid），查看净化结果和 token/延迟统计
2. **批量测试** — 上传 JSON 文件，批量执行，实时进度条，汇总准确率/成本
3. **调用历史** — 查看每条调用记录，筛选/分页/导出

### API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/filter` | POST | 单条文本处理 |
| `/api/batch` | POST | 批量处理 |
| `/api/history` | GET | 调用历史查询 |
| `/api/stats` | GET | 汇总统计 |
| `/docs` | GET | OpenAPI 文档（自动生成） |

### 两种模式

| 模式 | 说明 | Token | 延迟 |
|------|------|-------|------|
| `full` | 完整管道：DFA → LLM → Validator | ~977 | ~5s |
| `hybrid` | DFA 短路：级别 1-2 直接透传，不调 LLM | 0 | ~50ms |

## 架构

```
POST /api/filter {text, mode}
         │
         ▼
┌─────────────────┐
│  DFA 精确匹配    │  ← 复用 skills/tonebarrier/scripts/dfa_filter.py
│  (~50ms, 0 token)│
└────────┬────────┘
         │
    ┌────┴────┐
    │ hybrid? │
    └────┬────┘
    yes/ │ \no
   ┌───┐ │  ┌──────────────────┐
   │短路│ │  │  DeepSeek V4 Flash │  ← 精简 system prompt (~977 tokens)
   │输出│ │  │  (~5s)             │
   └───┘ │  └────────┬─────────┘
         │           │
         │  ┌────────┴────────┐
         │  │  Validator       │  ← 复用 skills/tonebarrier/scripts/validator.py
         │  │  (级别3-4, ~70ms)│
         │  └────────┬────────┘
         │           │
         ▼           ▼
    ┌─────────────────────┐
    │  SQLite 记录 + 返回   │
    └─────────────────────┘
```

## 文件结构

```
tonebarrier-server/
├── server.py          # FastAPI 主服务（路由 + 静态文件 + 模板）
├── pipeline.py        # 管道编排（DFA + LLM + Validator）
├── llm_client.py      # DeepSeek API 封装（AsyncOpenAI 异步格式）
├── prompts.py         # 精简版 system prompt（从 SKILL.md 提取）
├── config.py          # 配置（API key / 模型 / 端口）
├── history.py         # SQLite 调用历史存储
├── requirements.txt   # Python 依赖
├── Dockerfile         # HF Spaces Docker 部署
├── skill/
│   ├── scripts/
│   │   ├── dfa_filter.py    # DFA 引擎（含 leet speak 归一化）
│   │   └── validator.py     # 实体保留验证器
│   └── references/
│       ├── profanity_dict.txt   # 中文脏话词典（429 条）
│       ├── profanity_en.txt     # 英文脏话词典（1,071 条，分级）
│       └── homophone_guide.md   # 谐音变体指南
├── static/
│   ├── style.css      # UI 样式
│   └── app.js         # 前端交互逻辑（中英双语 i18n）
└── templates/
    └── index.html     # 主页面（默认英文，可切换中文）
```

## 成本对比

| 方案 | 单条成本 | 万次/天月成本 | 功能 |
|------|----------|-------------|------|
| Claude Code (Opus) | ¥0.20 | ¥60,000 | 完整（开发环境） |
| **本服务 (full)** | **¥0.00055** | **¥165** | 完整（生产模拟） |
| 本服务 (hybrid) | ¥0.00022 | ¥66 | 完整（60% 短路） |
| 云厂商文本审核 | ¥0.001-0.002 | ¥300-600 | 仅分类，不净化 |

## 依赖

- Python 3.9+
- FastAPI + Uvicorn（HTTP 服务）
- OpenAI SDK（DeepSeek API 兼容，异步模式）
- aiosqlite（异步 SQLite）
- Jinja2（模板渲染）

## 部署到 Hugging Face Spaces

本项目已部署在 HF Spaces（Docker SDK 模式）：

```bash
# 克隆 HF Space 仓库
git clone https://huggingface.co/spaces/pzr114514/skills-demo

# 设置 Secret（在 Space Settings → Variables and secrets）
# LLM_API_KEY = your-deepseek-api-key

# 推送更新
cd skills-demo
git add -A && git commit -m "update" && git push
```

容器自动构建，端口 7860，约 1-2 分钟后可访问。

</details>

<details>
<summary><b>English</b></summary>

## Overview

This service is a production environment simulation of the [ToneBarrier Skill](../skills/tonebarrier/), removing Claude Code framework overhead and calling the LLM API directly. It validates real-world token consumption, latency, and cost.

> **Live Demo**: https://huggingface.co/spaces/pzr114514/skills-demo (bilingual EN/CN UI)

### Key Metrics (182 test cases, full coverage)

| Metric | Production Sim | Claude Code | Improvement |
|--------|---------------|-------------|-------------|
| Strict Accuracy | 81.3% | 76.4% | +4.9% |
| Business Accuracy | 92.9% | — | — |
| Avg Tokens | 994 | 12,066 | **-92%** |
| Avg Latency | 4.4s | 30s | **-85%** |
| Cost per call | ¥0.00055 | ~¥0.20 | **-99.7%** |
| Coverage | 100% (182/182) | 69.8% (127/182) | +30% |
| Format failures | 0 | — | Retry mechanism |

### DFA Engine Metrics (83 tests + 40 boundary cases)

| Metric | Value |
|--------|-------|
| English dictionary | 1,071 entries (Level 4: 1,009 + Level 3: 40), sourced from surge-ai + dsojevic |
| Chinese dictionary | 429 entries |
| DFA test pass rate | **100%** (83/83 regular + 40/40 boundary) |
| Leet speak detection | sh1t, @ss, f4ck, a55 etc. ✓ |
| Repeat char detection | fuuuuck, shiiiit etc. ✓ |
| Censor bypass detection | f\*\*k, s\*\*t etc. ✓ |
| Abbreviation detection | stfu, gtfo, bs, ffs etc. ✓ |
| False positive rate | 0% (assassin, classic, cocktail, Dickens — zero false positives) |

### Accuracy Explanation

81.3% is strict matching (predicted level exactly equals expected level). In customer service scenarios:

- **Levels 3 and 4 have identical handling** (both require sanitization), so 3↔4 confusion has zero business impact
- **Business accuracy 92.9%**: usable rate when allowing 3↔4 interchange
- **Critical misclassifications** (should sanitize but didn't, or shouldn't sanitize but did) are 13 cases = **7.1%**
- **Retry mechanism**: empty responses auto-retry up to 2 times, format failures reduced from 4 to 0

### Error Patterns

| Pattern | Count | Business Impact | Description |
|---------|-------|-----------------|-------------|
| 4→3 | 9 | None (both sanitize) | Leet/space bypass underestimated |
| 3→4 | 8 | None (both sanitize) | Exclamatory profanity overestimated |
| 4→2 | 5 | **Yes** (missed) | Rare variants unrecognized |
| 3→2 | 5 | **Yes** (missed) | Sarcasm not detected |
| 4→None | 4 | Yes (format error) | Output parsing failed |
| Other | 3 | Low | Ambiguous boundaries |

## Quick Start

### Install

```bash
cd tonebarrier-server
pip3 install -r requirements.txt
```

### Configure

Edit `config.py` or set environment variables:

```bash
export LLM_API_KEY="your-deepseek-api-key"
export LLM_BASE_URL="https://api.deepseek.com"
export LLM_MODEL="deepseek-chat"
```

### Run

```bash
python3 server.py
# Open http://localhost:8000 in browser
```

## Features

### Web UI (Three-panel Interface)

1. **Manual Test** — Input text, select mode (full/hybrid), view sanitized result with token/latency stats
2. **Batch Test** — Upload JSON file, batch execute with progress bar, summary accuracy/cost
3. **Call History** — View all call records, filter/paginate/export

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/filter` | POST | Single text processing |
| `/api/batch` | POST | Batch processing |
| `/api/history` | GET | Call history query |
| `/api/stats` | GET | Aggregate statistics |
| `/docs` | GET | OpenAPI docs (auto-generated) |

### Two Modes

| Mode | Description | Tokens | Latency |
|------|-------------|--------|---------|
| `full` | Full pipeline: DFA → LLM → Validator | ~977 | ~5s |
| `hybrid` | DFA shortcircuit: Level 1-2 passthrough, no LLM | 0 | ~50ms |

## Architecture

```
POST /api/filter {text, mode}
         │
         ▼
┌─────────────────┐
│  DFA Matching    │  ← Reuses skills/tonebarrier/scripts/dfa_filter.py
│  (~50ms, 0 token)│
└────────┬────────┘
         │
    ┌────┴────┐
    │ hybrid? │
    └────┬────┘
    yes/ │ \no
   ┌───┐ │  ┌──────────────────┐
   │Out│ │  │  DeepSeek V4 Flash │  ← Compact system prompt (~977 tokens)
   │put│ │  │  (~5s)             │
   └───┘ │  └────────┬─────────┘
         │           │
         │  ┌────────┴────────┐
         │  │  Validator       │  ← Reuses skills/tonebarrier/scripts/validator.py
         │  │  (Level 3-4 only)│
         │  └────────┬────────┘
         │           │
         ▼           ▼
    ┌─────────────────────┐
    │  SQLite log + Return │
    └─────────────────────┘
```

## File Structure

```
tonebarrier-server/
├── server.py          # FastAPI main server (routes + static + templates)
├── pipeline.py        # Pipeline orchestration (DFA + LLM + Validator)
├── llm_client.py      # DeepSeek API wrapper (AsyncOpenAI format)
├── prompts.py         # Compact system prompt (extracted from SKILL.md)
├── config.py          # Configuration (API key / model / port)
├── history.py         # SQLite call history storage
├── requirements.txt   # Python dependencies
├── Dockerfile         # HF Spaces Docker deployment
├── skill/
│   ├── scripts/
│   │   ├── dfa_filter.py    # DFA engine (with leet speak normalization)
│   │   └── validator.py     # Entity preservation validator
│   └── references/
│       ├── profanity_dict.txt   # Chinese profanity dict (429 entries)
│       ├── profanity_en.txt     # English profanity dict (1,071 entries, graded)
│       └── homophone_guide.md   # Homophone variant guide
├── static/
│   ├── style.css      # UI styles
│   └── app.js         # Frontend logic (bilingual i18n EN/CN)
└── templates/
    └── index.html     # Main page (default English, switchable to Chinese)
```

## Cost Comparison

| Approach | Cost/call | Monthly (10K/day) | Capability |
|----------|-----------|-------------------|------------|
| Claude Code (Opus) | ¥0.20 | ¥60,000 | Full (dev environment) |
| **This service (full)** | **¥0.00055** | **¥165** | Full (production sim) |
| This service (hybrid) | ¥0.00022 | ¥66 | Full (60% shortcircuit) |
| Cloud text moderation | ¥0.001-0.002 | ¥300-600 | Classification only |

## Dependencies

- Python 3.9+
- FastAPI + Uvicorn (HTTP server)
- OpenAI SDK (DeepSeek API compatible, async mode)
- aiosqlite (async SQLite)
- Jinja2 (template rendering)

## Deploy to Hugging Face Spaces

This project is deployed on HF Spaces (Docker SDK mode):

```bash
# Clone the HF Space repo
git clone https://huggingface.co/spaces/pzr114514/skills-demo

# Set Secret (in Space Settings → Variables and secrets)
# LLM_API_KEY = your-deepseek-api-key

# Push updates
cd skills-demo
git add -A && git commit -m "update" && git push
```

Container auto-builds on port 7860, accessible in ~1-2 minutes.

</details>
