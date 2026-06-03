# Mental Barrier — Production Simulation Service

> **[中文](README_CN.md)** | English

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek%20V4%20Flash-purple)](https://deepseek.com)

---

## Overview

Production simulation of the [tonebarrier SKILL](../tonebarrier/), removing Claude Code framework overhead and calling the LLM API directly.

## Key Metrics (182 cases, full coverage)

| Metric | Production Sim | Claude Code | Improvement |
|--------|---------------|-------------|-------------|
| Strict Accuracy | 81.3% | 76.4% | +4.9% |
| Business Accuracy | 92.9% | — | — |
| Avg Tokens | 994 | 12,066 | **-92%** |
| Avg Latency | 4.4s | 30s | **-85%** |
| Cost per call | ¥0.00055 | ~¥0.20 | **-99.7%** |
| Format failures | 0 | — | Retry mechanism |

## Quick Start

```bash
cd tonebarrier-server
pip3 install -r requirements.txt
cp config.py.example config.py
# Edit config.py with your LLM_API_KEY

python3 server.py
# Open http://localhost:8000
```

## Features

### Web UI (Three-panel Interface)

1. **Manual Test** — Input text, select mode (full/hybrid), view results with token/latency stats
2. **Batch Test** — Upload JSON, batch execute with progress bar, summary accuracy/cost
3. **Call History** — View all records, filter/paginate/export

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/filter` | POST | Single text processing |
| `/api/batch` | POST | Batch processing |
| `/api/history` | GET | Call history |
| `/api/stats` | GET | Aggregate statistics |
| `/docs` | GET | OpenAPI docs |

### Two Modes

| Mode | Description | Tokens | Latency |
|------|-------------|--------|---------|
| `full` | DFA → LLM → Validator | ~994 | ~4.4s |
| `hybrid` | Level 1-2 passthrough, no LLM | 0 | ~50ms |

## Architecture

```
POST /api/filter {text, mode}
         │
         ▼
┌──────────────────────┐
│  DFA Exact Match      │  ← tonebarrier/scripts/dfa_filter.py
│  (~50ms)             │
└──────────┬───────────┘
           │
      ┌────┴────┐
      │ hybrid? │
      └────┬────┘
      yes/ │ \no
     ┌───┐ │  ┌─────────────────────┐
     │Out│ │  │  DeepSeek V4 Flash   │
     │put│ │  │  (~4.4s)             │
     └───┘ │  └──────────┬──────────┘
           │             │
           │  ┌──────────┴──────────┐
           │  │  Validator (L3-4)    │
           │  └──────────┬──────────┘
           ▼             ▼
      ┌────────────────────────┐
      │  SQLite + JSON Response │
      └────────────────────────┘
```

## File Structure

```
tonebarrier-server/
├── server.py            # FastAPI main server
├── pipeline.py          # Pipeline (DFA + LLM + Validator)
├── llm_client.py        # LLM wrapper with retry
├── prompts.py           # Compact system prompt
├── config.py.example    # Config template (no secrets)
├── history.py           # SQLite call history
├── requirements.txt     # Dependencies
├── batch_test_182.json  # Test data
├── batch_results_182.json  # Test results
├── static/              # CSS + JS
└── templates/           # HTML
```

## License

MIT
