# 精神内耗终结者 — 生产环境模拟服务

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek%20V4%20Flash-purple)](https://deepseek.com)

<details open>
<summary><b>中文</b></summary>

## 概述

本服务是 [mental-barrier SKILL](./../.claude/skills/mental-barrier/) 的生产环境模拟，去掉 Claude Code 框架开销，直接通过 API 调用实现完整的情绪过滤管道。用于验证真实 token 消耗、延迟和成本。

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
cd mental-barrier-server
pip3 install -r requirements.txt
```

### 配置

复制配置模板并填入 API key：

```bash
cp config.py.example config.py
# 编辑 config.py 填入你的 LLM_API_KEY
```

或通过环境变量：

```bash
export LLM_API_KEY="sk-your-deepseek-key"
export LLM_BASE_URL="https://api.deepseek.com/v1"
export LLM_MODEL="deepseek-v4-flash"
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
│  DFA 精确匹配    │  ← 复用 mental-barrier/scripts/dfa_filter.py
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
         │  │  Validator       │  ← 复用 mental-barrier/scripts/validator.py
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
mental-barrier-server/
├── server.py          # FastAPI 主服务（路由 + 静态文件 + 模板）
├── pipeline.py        # 管道编排（DFA + LLM + Validator）
├── llm_client.py      # DeepSeek API 封装（OpenAI SDK 格式）
├── prompts.py         # 精简版 system prompt（从 SKILL.md 提取）
├── config.py          # 配置（API key / 模型 / 端口）
├── history.py         # SQLite 调用历史存储
├── requirements.txt   # Python 依赖
├── batch_test_182.json       # 182 条测试数据
├── batch_results_182.json    # 全量测试结果
├── static/
│   ├── style.css      # UI 样式
│   └── app.js         # 前端交互逻辑
└── templates/
    └── index.html     # 主页面
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
- OpenAI SDK（DeepSeek API 兼容）
- aiosqlite（异步 SQLite）
- Jinja2（模板渲染）

</details>

<details>
<summary><b>English</b></summary>

## Overview

This service is a production environment simulation of the [mental-barrier SKILL](./../.claude/skills/mental-barrier/), removing Claude Code framework overhead and calling the LLM API directly. It validates real-world token consumption, latency, and cost.

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
cd mental-barrier-server
pip3 install -r requirements.txt
```

### Configure

Edit `config.py` or set environment variables:

```bash
export LLM_API_KEY="sk-your-deepseek-key"
export LLM_BASE_URL="https://api.deepseek.com/v1"
export LLM_MODEL="deepseek-v4-flash"
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
│  DFA Matching    │  ← Reuses mental-barrier/scripts/dfa_filter.py
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
         │  │  Validator       │  ← Reuses mental-barrier/scripts/validator.py
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
mental-barrier-server/
├── server.py          # FastAPI main server (routes + static + templates)
├── pipeline.py        # Pipeline orchestration (DFA + LLM + Validator)
├── llm_client.py      # DeepSeek API wrapper (OpenAI SDK format)
├── prompts.py         # Compact system prompt (extracted from SKILL.md)
├── config.py          # Configuration (API key / model / port)
├── history.py         # SQLite call history storage
├── requirements.txt   # Python dependencies
├── batch_test_182.json       # 182 test cases
├── batch_results_182.json    # Full test results
├── static/
│   ├── style.css      # UI styles
│   └── app.js         # Frontend interaction logic
└── templates/
    └── index.html     # Main page
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
- OpenAI SDK (DeepSeek API compatible)
- aiosqlite (async SQLite)
- Jinja2 (template rendering)

</details>
