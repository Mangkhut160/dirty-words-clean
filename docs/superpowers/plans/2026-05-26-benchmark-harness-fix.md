# 修复 benchmark/report 结构性问题

> **面向执行代理：** 使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实施。步骤使用复选框（`- [ ]`）语法追踪进度。

**目标：** 修复 Codex 审查发现的 3 个 harness 层结构性问题，使 benchmark 数据和报告可信。

**架构：** 三个独立修复：统一数据集模式（skill_eval.py）、补全报告判定（report.py）、新增 LLM 端到端验证器（e2e_validate.py）+ 诚实重命名 Phase 3。

---

## 文件结构

```
修改:
  benchmark/skill_eval.py          # 统一 prompts/validate 数据集
  benchmark/report.py              # 实体保留率入 fails，加覆盖率检查，动态数据来源
  tests/test_pipeline.py           # Phase 3 诚实重命名

创建:
  adversarial/e2e_validate.py      # LLM 端到端对抗验证脚本
```

---

### 任务 1：统一 benchmark 数据集模式

**文件：** `benchmark/skill_eval.py:238-253`

- [ ] **步骤 1：修改 main() 命令解析**

替换第 238-253 行为：

```python
command = sys.argv[1]
use_full = "--full" in sys.argv

with open(EVAL_CASES_PATH, encoding="utf-8") as f:
    eval_data = json.load(f)

if use_full:
    cases = eval_data["full"]
    mode = "full"
else:
    cases = eval_data.get("sampled_30", eval_data["full"])
    mode = "sample"

if command == "prompts":
    print(f"模式: {mode} ({len(cases)} 条)")
    print_eval_prompts(cases)
elif command == "validate":
    if len(sys.argv) < 3:
        print("Error: validate requires a results.json path")
        sys.exit(1)
    results_path = sys.argv[2]
    print(f"模式: {mode} ({len(cases)} 条)")
    validate_results(cases, results_path)
```

- [ ] **步骤 2：重跑 validate 修正 skill_results.json**

```bash
python3 benchmark/skill_eval.py validate benchmark/results.json
```

预期：`matched_results=30, missing_results=0`（results.json 也是 30 条）。

---

### 任务 2：修复 report.py 完整判定

**文件：** `benchmark/report.py:276-293`

- [ ] **步骤 1：实体保留率加入 fails**

第 281-287 行替换为：

```python
fails = []
if f1_judge == "FAIL":
    fails.append("COLD F1")
if emo_judge == "FAIL":
    fails.append("情绪一致率")
if fpr_judge == "FAIL":
    fails.append("误报率")
if ep_judge == "FAIL":
    fails.append("实体保留率")
```

- [ ] **步骤 2：覆盖率检查**

在第 276 行前插入：

```python
coverage_ok = True
if skill:
    sm = skill.get("summary", {})
    matched = sm.get("matched_results", 0)
    total_c = sm.get("total_cases", 0)
    if total_c > 0 and matched / total_c < 0.80:
        fails.append(f"LLM 评测覆盖率 ({matched}/{total_c})")
```

- [ ] **步骤 3：数据来源从实际 JSON 读取**

将硬编码的数据来源 section 替换为从 dfa_results.json 读取实际计数。

- [ ] **步骤 4：重跑 report 验证**

```bash
python3 benchmark/report.py
```

预期：报告数据来源显示实际数字，综合判定包含实体保留率和覆盖率。

---

### 任务 3：创建 e2e_validate + 诚实重命名

**文件：** 创建 `adversarial/e2e_validate.py`，修改 `tests/test_pipeline.py:236-265`

- [ ] **步骤 1：创建 e2e_validate.py**

完整代码如设计方案。用法：`python3 e2e_validate.py <llm_outputs.json>`。

- [ ] **步骤 2：诚实重命名 Phase 3**

```python
print("  第3层：DFA 对抗行为验证（DFA 对变体的预期命中/未命中检查）")
print("  注意：完整 LLM 端到端验证需通过 adversarial/e2e_validate.py 完成")
```

- [ ] **步骤 3：验证测试套件**

```bash
python3 tests/test_pipeline.py
# → 57/57 通过
```

---

## 验收

```bash
python3 tests/test_pipeline.py                     # 57/57
python3 benchmark/skill_eval.py validate benchmark/results.json  # matched=30 missing=0
python3 benchmark/report.py                        # 结论包含全部指标
python3 adversarial/e2e_validate.py adversarial/llm_results.json  # LLM 端到端指标
```
