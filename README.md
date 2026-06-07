# ToneBarrier

[![Tests](https://img.shields.io/badge/tests-81%2F81%20passed-brightgreen)](evaluation/tonebarrier/tests/test_pipeline.py)
[![Accuracy](https://img.shields.io/badge/business%20accuracy-92.9%25-blue)](tonebarrier-server/batch_results_182.json)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

> **[中文文档](README_CN.md)** | **[English Documentation](README_EN.md)**

---

客服情绪过滤引擎 — 将辱骂、讽刺、情绪宣泄的投诉文本转化为冷静客观的自然语言。

Customer emotion filtering engine — transforms profanity-laden complaints into calm, objective natural language.

| Metric | Value |
|--------|-------|
| Business Accuracy | **92.9%** |
| Avg Tokens | 994 |
| Avg Latency | 4.4s |
| Cost/call | ¥0.00055 |

## Repository Layout

```text
ToneBarrier/
├── skills/tonebarrier/      # Claude Code Skill, copyable installation unit
├── evaluation/tonebarrier/  # Tests, adversarial evaluation, benchmark reports
├── tonebarrier-server/      # FastAPI production simulation and Web UI
├── docs/                    # Design and implementation notes
└── .github/workflows/       # Deployment workflow
```

## Install the Claude Code Skill

```bash
git clone https://github.com/Mangkhut160/dirty-words-clean.git
mkdir -p ~/.claude/skills
cp -r dirty-words-clean/skills/tonebarrier ~/.claude/skills/tonebarrier
```

Project-level install:

```bash
mkdir -p .claude/skills
cp -r dirty-words-clean/skills/tonebarrier .claude/skills/tonebarrier
```

## Run the Web Service

```bash
cd tonebarrier-server
pip3 install -r requirements.txt
cp config.py.example config.py
# Edit config.py with your DeepSeek API key
python3 server.py
```
