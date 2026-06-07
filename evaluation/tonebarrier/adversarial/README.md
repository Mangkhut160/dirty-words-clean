# 对抗鲁棒性测试

## 概述

验证 tonebarrier SKILL 在对抗场景下的鲁棒性。当用户通过空格分隔、谐音字替换、数字替换等方式绕过 DFA 脏话检测时，LLM 层能否正确识别并过滤。

## 快速开始

### 1. 生成对抗样本
```bash
python3 evaluation/tonebarrier/adversarial/generate_adversary.py
```
输出: `adversary_cases.json` (~180 条)

### 2. 运行 DFA 层评测
```bash
python3 evaluation/tonebarrier/adversarial/run_adversary.py        # DFA执行 → 生成 run_results.json
python3 evaluation/tonebarrier/adversarial/run_adversary.py --report  # 打印分类汇总表
```
输出: `run_results.json` + 分类汇总表

> **注意**: `--report` 需要 `run_results.json` 已存在（由上述不带 `--report` 的步骤生成）。

### 3. 生成 LLM Judge 评测 prompt
```bash
python3 evaluation/tonebarrier/adversarial/judge_adversary.py
```
输出: `judge_prompts.json`

### 4. 运行 LLM 评测
对每条 prompt 运行 /tonebarrier，将输出填入 results.json，然后：
```bash
python3 evaluation/tonebarrier/adversarial/judge_adversary.py --import results.json
```
输出: `judge_results.json` + 四维打分汇总

### 5. 回归测试
```bash
python3 evaluation/tonebarrier/tests/test_pipeline.py  # 第3层自动包含对抗回归
```

## 对抗变体类型

| 类型 | 说明 | DFA 预期 |
|------|------|---------|
| 格式绕过 | 空格/符号/全角分隔脏话 | 几乎全漏 |
| 中文谐音 | 同音字替换 | 约 40% 命中 |
| Leet 替换 | 数字/符号替换字母 | 约 40% 命中 |
| 中英混杂 | 拼音+英文词根混合 | 约 20% 命中 |
| 拼音谐音混杂 | 拼音字母+中文谐音 | 约 25% 命中 |
| 讽刺语气 | 反语/阴阳怪气 | 0% (无脏话词) |
| 英文未命中 | 词典外的英文俚语 | 0% |
| 正常对照 | 无脏话的正常投诉 | 不应误报 |

## 指标目标

| 指标 | 目标 |
|------|------|
| LLM 综合检测率 | ≥ 80% |
| DFA→LLM 增益 | ≥ 50pp |
| 正常文本误杀率 | ≤ 5% |
| 格式合规率 | ≥ 95% |
