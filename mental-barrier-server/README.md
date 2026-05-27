# 精神内耗终结者 — 生产环境模拟服务 | Production Simulation

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek%20V4%20Flash-purple)](https://deepseek.com)

去掉 Claude Code 框架开销，直接 API 调用实现完整情绪过滤管道。验证真实 token 消耗、延迟和成本。

Production simulation removing Claude Code framework overhead. Validates real-world token consumption, latency, and cost.

---

## 核心指标 | Key Metrics (182 cases)

| 指标 Metric | 生产模拟 Prod Sim | Claude Code | 提升 Improvement |
|-------------|-------------------|-------------|-----------------|
| 严格准确率 Strict Accuracy | 81.3% | 76.4% | +4.9% |
| 业务准确率 Business Accuracy | 92.9% | — | — |
| 平均 Token Avg Tokens | 994 | 12,066 | **-92%** |
| 平均延迟 Avg Latency | 4.4s | 30s | **-85%** |
| 单条成本 Cost/call | ¥0.00055 | ~¥0.20 | **-99.7%** |
| 格式失败 Format failures | 0 | — | 重试机制 Retry |

---

## 快速开始 | Quick Start

```bash
cd mental-barrier-server
pip3 install -r requirements.txt
cp config.py.example config.py
# 编辑 config.py 填入 LLM_API_KEY / Edit with your API key

python3 server.py
# http://localhost:8000
```

---

## 功能 | Features

### Web UI 三栏界面 | Three-panel Interface

1. **手动测试 Manual Test** — 输入文本，选择模式，查看结果 / Input text, select mode, view results
2. **批量测试 Batch Test** — 上传 JSON，批量执行，进度条 / Upload JSON, batch execute, progress bar
3. **调用历史 Call History** — 每条记录详情，筛选导出 / Record details, filter, export

### API 接口 | Endpoints

| 接口 Endpoint | 方法 Method | 说明 Description |
|---------------|-------------|-----------------|
| `/api/filter` | POST | 单条处理 / Single text |
| `/api/batch` | POST | 批量处理 / Batch |
| `/api/history` | GET | 调用历史 / History |
| `/api/stats` | GET | 汇总统计 / Stats |
| `/docs` | GET | OpenAPI 文档 / Auto docs |

### 两种模式 | Two Modes

| 模式 Mode | 说明 Description | Token | 延迟 Latency |
|-----------|-----------------|-------|-------------|
| `full` | DFA → LLM → Validator | ~994 | ~4.4s |
| `hybrid` | 级别1-2直接透传 / Level 1-2 passthrough | 0 | ~50ms |

---

## 架构 | Architecture

```
POST /api/filter {text, mode}
         │
         ▼
┌──────────────────────┐
│  DFA 精确匹配         │  ← mental-barrier/scripts/dfa_filter.py
│  Exact Match (~50ms) │
└──────────┬───────────┘
           │
      ┌────┴────┐
      │ hybrid? │
      └────┬────┘
      yes/ │ \no
     ┌───┐ │  ┌─────────────────────┐
     │ 短 │ │  │  DeepSeek V4 Flash   │  ← prompts.py (~994 tokens)
     │ 路 │ │  │  LLM Call (~4.4s)    │
     └───┘ │  └──────────┬──────────┘
           │             │
           │  ┌──────────┴──────────┐
           │  │  Validator (L3-4)    │  ← mental-barrier/scripts/validator.py
           │  └──────────┬──────────┘
           │             │
           ▼             ▼
      ┌────────────────────────┐
      │  SQLite + JSON Response │
      └────────────────────────┘
```

---

## 文件结构 | File Structure

```
mental-barrier-server/
├── server.py            # FastAPI 主服务 / Main server
├── pipeline.py          # 管道编排 / Pipeline (DFA + LLM + Validator)
├── llm_client.py        # LLM 封装+重试 / LLM wrapper with retry
├── prompts.py           # 精简 prompt / Compact system prompt
├── config.py.example    # 配置模板 / Config template (no secrets)
├── history.py           # SQLite 存储 / Call history storage
├── requirements.txt     # 依赖 / Dependencies
├── batch_test_182.json  # 测试数据 / Test data
├── batch_results_182.json  # 测试结果 / Test results
├── static/
│   ├── style.css        # 样式 / Styles
│   └── app.js           # 前端逻辑 / Frontend logic
└── templates/
    └── index.html       # 主页面 / Main page
```

---

## 成本对比 | Cost Comparison

| 方案 Approach | 单条 Cost/call | 月成本 Monthly (10K/day) | 功能 Capability |
|---------------|---------------|--------------------------|-----------------|
| Claude Code (Opus) | ¥0.20 | ¥60,000 | 完整 Full (dev) |
| **本服务 full** | **¥0.00055** | **¥165** | 完整 Full (prod) |
| 本服务 hybrid | ¥0.00022 | ¥66 | 完整 Full (60% skip) |
| 云厂商 Cloud API | ¥0.001-0.002 | ¥300-600 | 仅分类 Classify only |

---

## 依赖 | Dependencies

- Python 3.9+
- FastAPI + Uvicorn
- OpenAI SDK (DeepSeek compatible)
- aiosqlite
- Jinja2
