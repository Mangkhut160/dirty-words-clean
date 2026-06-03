# 精神内耗终结者 — Benchmark 评估框架

## 快速开始

### 1. 运行 DFA 评估（全自动）
```bash
cd .claude/skills/tonebarrier
python3 benchmark/dfa_eval.py
```
输出：`benchmark/dfa_results.json`

### 2. 运行 SKILL 端到端评测

```bash
# 生成评测 prompt
python3 benchmark/skill_eval.py prompts

# 对每条 prompt 运行 /tonebarrier，记录输出到 results.json
# 格式: [{"id": "xxx", "skill_output": "<SKILL输出>"}, ...]

# 校验结果
python3 benchmark/skill_eval.py validate results.json
```
输出：`benchmark/skill_results.json`

### 3. 生成综合报告

```bash
python3 benchmark/report.py
```
输出：`benchmark/BENCHMARK_REPORT.md`

## 数据来源

| 数据集 | 规模 | 用途 |
|--------|------|------|
| ToxiCN | ~1,000 条 | DFA 覆盖率 |
| COLD | ~7,000 条 | DFA 精确率/召回率/F1 |
| sample_dev_90 | 90 条 | LLM 端到端评测 |

## 指标目标

| 指标 | 目标值 |
|------|--------|
| COLD F1 | >= 0.70 |
| 情绪一致率 | >= 0.70 |
| 实体保留率 | >= 0.90 |
| 误报率 | <= 0.05 |

## 文件说明

| 文件 | 用途 |
|------|------|
| `dfa_eval.py` | DFA 层自动化评估脚本（ToxiCN + COLD） |
| `skill_eval.py` | LLM 层评测运行器（prompt 生成 + 结果校验） |
| `report.py` | 综合报告生成器（读取两个 JSON，生成 Markdown 报告） |
| `dfa_results.json` | DFA 评估指标结果 |
| `skill_results.json` | LLM 端到端评测结果 |
| `BENCHMARK_REPORT.md` | 最终的综合评估报告 |
