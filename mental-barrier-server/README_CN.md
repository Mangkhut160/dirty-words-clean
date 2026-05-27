# 精神内耗终结者 — 生产环境模拟服务

> **[English](README_EN.md)** | 中文

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek%20V4%20Flash-purple)](https://deepseek.com)

---

## 概述

本服务是 [mental-barrier SKILL](../mental-barrier/) 的生产环境模拟，去掉 Claude Code 框架开销，直接通过 API 调用实现完整的情绪过滤管道。

## 核心指标（182 条全量测试）

| 指标 | 生产模拟 | Claude Code | 提升 |
|------|----------|-------------|------|
| 严格准确率 | 81.3% | 76.4% | +4.9% |
| 业务准确率 | 92.9% | — | — |
| 平均 Token | 994 | 12,066 | **-92%** |
| 平均延迟 | 4.4s | 30s | **-85%** |
| 单条成本 | ¥0.00055 | ~¥0.20 | **-99.7%** |
| 格式失败 | 0 条 | — | 重试机制保障 |

## 快速开始

```bash
cd mental-barrier-server
pip3 install -r requirements.txt
cp config.py.example config.py
# 编辑 config.py 填入 LLM_API_KEY

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
| `/docs` | GET | OpenAPI 文档 |

### 两种模式

| 模式 | 说明 | Token | 延迟 |
|------|------|-------|------|
| `full` | 完整管道：DFA → LLM → Validator | ~994 | ~4.4s |
| `hybrid` | DFA 短路：级别 1-2 直接透传 | 0 | ~50ms |

## 架构

```
POST /api/filter {text, mode}
         │
         ▼
┌─────────────────┐
│  DFA 精确匹配    │  ← mental-barrier/scripts/dfa_filter.py
│  (~50ms)        │
└────────┬────────┘
         │
    ┌────┴────┐
    │ hybrid? │
    └────┬────┘
    yes/ │ \no
   ┌───┐ │  ┌──────────────────┐
   │短路│ │  │  DeepSeek V4 Flash │
   │输出│ │  │  (~4.4s)           │
   └───┘ │  └────────┬─────────┘
         │           │
         │  ┌────────┴────────┐
         │  │  Validator       │
         │  │  (级别3-4)       │
         │  └────────┬────────┘
         ▼           ▼
    ┌─────────────────────┐
    │  SQLite 记录 + 返回   │
    └─────────────────────┘
```

## 文件结构

```
mental-barrier-server/
├── server.py            # FastAPI 主服务
├── pipeline.py          # 管道编排（DFA + LLM + Validator）
├── llm_client.py        # LLM 封装 + 重试机制
├── prompts.py           # 精简版 system prompt
├── config.py.example    # 配置模板（无密钥）
├── history.py           # SQLite 调用历史
├── requirements.txt     # 依赖
├── batch_test_182.json  # 测试数据
├── batch_results_182.json  # 测试结果
├── static/              # CSS + JS
└── templates/           # HTML
```

## 许可

MIT
