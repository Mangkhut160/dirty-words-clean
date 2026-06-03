# 英文/中英混合评测标签校准 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前英文/中英混合 200 条评测集从“硬套中文 1/2/3/4 情绪等级”改造成多标签评测体系，并基于已有线上结果重新生成可信报告，不重跑 LLM。

**Architecture:** 保留现有 `online_eval_en_mixed_200.json` 和线上结果文件作为原始基线，新建校准后的样本文件与离线重算脚本。脚本只读取已有 `results.jsonl`，根据校准标签重新计算 action、toxicity、harassment、DFA、实体保留和误伤边界指标，避免再次消耗线上 LLM token。

**Tech Stack:** Python 3、标准库 `json/pathlib/collections`、pytest、Markdown 报告、现有 tonebarrier 数据集目录结构。

---

## 背景与成功标准

### 当前问题

当前 `datasets/online_eval_en_mixed_200.json` 的 `expected_level` 对英文普通投诉标注偏高，例如扣款错误、物流延迟、发错货、设备故障等文本，很多本质是“业务问题严重但表达克制”，不应该直接标成 Level 3。继续使用严格等级准确率会把模型的合理判断算错，导致报告误导。

### 目标改造方向

英文/中英混合样本不再以 `expected_level` 作为主指标，而是改成多标签：

- `expected_action`: `pass | deescalate | sanitize | block`
- `expected_toxicity`: `none | mild | toxic | severe`
- `expected_sentiment`: `neutral | negative | angry`
- `expected_harassment`: 继续保留
- `expected_dfa_hit`: 继续保留
- `expected_entities`: 明确需要保护的实体文本
- `level_policy`: 说明当前样本是否仍参与中文式 level 严格评测

### 成功标准

- 新增校准样本文件：`datasets/online_eval_en_mixed_200_calibrated.json`
- 新增离线重算脚本：`datasets/recalculate_en_mixed_calibrated_metrics.py`
- 新增单元测试：`tests/test_en_mixed_calibrated_metrics.py`
- 新增校准报告：`datasets/online_eval_results/online_eval_en_mixed_200_calibrated_report.md`
- 不重跑 LLM，不读取或输出任何 API Key
- 英文普通投诉不再计入 `strict_level_accuracy`
- 报告主指标改为 action/toxicity/harassment/entity/false-positive boundary
- `pytest tests/test_en_mixed_calibrated_metrics.py -v` 通过

---

## 文件结构

### 创建文件

- `datasets/recalculate_en_mixed_calibrated_metrics.py`
  - 读取校准样本和已有线上结果 JSONL
  - 按 `id` 合并 expected 与 actual
  - 计算新指标
  - 输出 summary JSON 与 Markdown report

- `datasets/online_eval_en_mixed_200_calibrated.json`
  - 当前 200 条样本的校准版本
  - 保留原始输入、语言、类别、source、tags、notes
  - 新增多标签字段
  - 英文普通投诉的 `expected_level` 改为 `null`

- `tests/test_en_mixed_calibrated_metrics.py`
  - 单测离线重算逻辑
  - 覆盖 action 映射、level 参与策略、实体检查、空 actual level、toxicity 召回

### 修改文件

- `datasets/README.md`
  - 说明英文/中英混合评测不再使用 `strict_level_accuracy` 作为主指标
  - 说明 calibrated 文件和报告的使用方法

- `docs/superpowers/plans/2026-06-02-english-mixed-eval-label-calibration.md`
  - 本计划文件

### 不修改文件

- `tonebarrier-server/pipeline.py`
  - 本阶段不改模型输出逻辑

- `tonebarrier-server/harassment/detector.py`
  - 本阶段不修检测器，只重新定义可信评测口径

- `tonebarrier-review/adversarial/.env`
  - 本阶段不读取、不打印、不提交密钥；如果后续要清理密钥，单独开安全清理任务

---

## 设计细节

### action 定义

```text
pass       文本可原样通过，不需要净化
           例：正常客服请求、实体保护样本、克制投诉

deescalate 有负面情绪，但不含明确辱骂/威胁/涉黄；可缓和表达
           例：unacceptable、extremely frustrated、ridiculous

sanitize   含辱骂、脏话、涉黄、攻击性称呼，应净化
           例：fuck、shit、tmd、cnm、idiot、垃圾用于人身攻击

block      明确威胁、强骚扰、仇恨/歧视、严重涉黄导流等高风险内容
```

### actual action 映射

先使用现有 pipeline 的 `actual_level` 做最小映射：

```python
LEVEL_TO_ACTION = {
    1: "pass",
    2: "deescalate",
    3: "deescalate",
    4: "sanitize",
    None: "unknown",
}
```

说明：

- Level 3 先映射为 `deescalate`，因为当前系统的 Level 3 是“强情绪/建议处理”，不一定需要脏词净化。
- Level 4 映射为 `sanitize`。
- `block` 暂不由现有 pipeline level 推导，除非后续 pipeline 增加高危分类。

### level_policy 定义

```json
{
  "level_policy": {
    "include_in_strict_level_accuracy": false,
    "reason": "英文普通投诉按 action/sentiment/entity 评估，不参与中文式 1/2/3/4 严格等级评估"
  }
}
```

规则：

- 英文普通投诉、英文实体保护、英文客服正常对照：`include_in_strict_level_accuracy=false`
- 明确 toxic/profanity/harassment/adversarial 样本：可以保留 `expected_level=4` 且 `include_in_strict_level_accuracy=true`
- 中英混合普通业务：一般不参与 strict level
- 中英混合攻击/绕过：参与 strict level 或至少参与 action/toxicity

---

## Task 1: 编写离线指标核心函数测试

**Files:**
- Create: `tests/test_en_mixed_calibrated_metrics.py`
- Create: `datasets/recalculate_en_mixed_calibrated_metrics.py`

- [ ] **Step 1: 写失败测试文件**

创建 `tests/test_en_mixed_calibrated_metrics.py`：

```python
from datasets.recalculate_en_mixed_calibrated_metrics import (
    action_correct,
    actual_action_from_level,
    entity_preserved,
    include_in_strict_level,
    summarize_rows,
)


def test_actual_action_from_level_maps_current_pipeline_levels():
    assert actual_action_from_level(1) == "pass"
    assert actual_action_from_level(2) == "deescalate"
    assert actual_action_from_level(3) == "deescalate"
    assert actual_action_from_level(4) == "sanitize"
    assert actual_action_from_level(None) == "unknown"


def test_action_correct_accepts_equivalent_deescalate_for_level_3():
    row = {
        "expected_action": "deescalate",
        "actual_level": 3,
    }

    assert action_correct(row) is True


def test_action_correct_rejects_sanitize_when_expected_pass():
    row = {
        "expected_action": "pass",
        "actual_level": 4,
    }

    assert action_correct(row) is False


def test_include_in_strict_level_respects_policy():
    excluded = {
        "expected_level": None,
        "level_policy": {
            "include_in_strict_level_accuracy": False,
            "reason": "英文普通投诉不参与 strict level",
        },
    }
    included = {
        "expected_level": 4,
        "level_policy": {
            "include_in_strict_level_accuracy": True,
            "reason": "明确辱骂样本参与 strict level",
        },
    }

    assert include_in_strict_level(excluded) is False
    assert include_in_strict_level(included) is True


def test_entity_preserved_checks_expected_entity_texts_in_sanitized_text():
    row = {
        "expected_entities": ["ORD-2026-0007", "$129.99", "2026-06-01"],
        "pipeline": {
            "sanitized_text": "Order ORD-2026-0007 was charged $129.99 on 2026-06-01.",
        },
    }

    assert entity_preserved(row) is True


def test_entity_preserved_returns_false_when_expected_entity_missing():
    row = {
        "expected_entities": ["ORD-2026-0007", "$129.99"],
        "pipeline": {
            "sanitized_text": "Order ORD-2026-0007 was charged.",
        },
    }

    assert entity_preserved(row) is False


def test_summarize_rows_uses_action_as_primary_metric_and_skips_excluded_strict_level():
    rows = [
        {
            "id": "normal-complaint",
            "language": "en",
            "category": "英文实体保护",
            "expected_level": None,
            "actual_level": 1,
            "expected_action": "pass",
            "expected_toxicity": "none",
            "expected_harassment": False,
            "expected_dfa_hit": False,
            "expected_entities": ["ORD-1"],
            "level_policy": {"include_in_strict_level_accuracy": False, "reason": "英文普通投诉"},
            "pipeline": {"sanitized_text": "ORD-1 arrived late.", "dfa_hits": []},
            "harassment": {"is_harassment": False},
        },
        {
            "id": "toxic-attack",
            "language": "en",
            "category": "英文骚扰/攻击样本",
            "expected_level": 4,
            "actual_level": 4,
            "expected_action": "sanitize",
            "expected_toxicity": "toxic",
            "expected_harassment": True,
            "expected_dfa_hit": True,
            "expected_entities": [],
            "level_policy": {"include_in_strict_level_accuracy": True, "reason": "明确攻击"},
            "pipeline": {"sanitized_text": "[已净化]", "dfa_hits": ["fuck"]},
            "harassment": {"is_harassment": True},
        },
    ]

    summary = summarize_rows(rows)

    assert summary["total"] == 2
    assert summary["action_accuracy"] == 1.0
    assert summary["strict_level_total"] == 1
    assert summary["strict_level_accuracy"] == 1.0
    assert summary["entity_preserved_rate"] == 1.0
    assert summary["harassment_accuracy"] == 1.0
```

- [ ] **Step 2: 创建最小模块让 import 失败点清晰**

创建 `datasets/recalculate_en_mixed_calibrated_metrics.py`：

```python
"""重算英文/中英混合校准评测指标。"""


def actual_action_from_level(level):
    raise NotImplementedError


def action_correct(row):
    raise NotImplementedError


def include_in_strict_level(row):
    raise NotImplementedError


def entity_preserved(row):
    raise NotImplementedError


def summarize_rows(rows):
    raise NotImplementedError
```

- [ ] **Step 3: 运行测试确认失败**

Run:

```bash
pytest tests/test_en_mixed_calibrated_metrics.py -v
```

Expected:

```text
FAILED tests/test_en_mixed_calibrated_metrics.py::test_actual_action_from_level_maps_current_pipeline_levels - NotImplementedError
```

- [ ] **Step 4: 提交测试骨架**

```bash
git add tests/test_en_mixed_calibrated_metrics.py datasets/recalculate_en_mixed_calibrated_metrics.py
git commit -m "test: 添加英文混合校准指标测试"
```

---

## Task 2: 实现离线指标核心函数

**Files:**
- Modify: `datasets/recalculate_en_mixed_calibrated_metrics.py`
- Test: `tests/test_en_mixed_calibrated_metrics.py`

- [ ] **Step 1: 实现核心函数**

替换 `datasets/recalculate_en_mixed_calibrated_metrics.py` 内容为：

```python
"""重算英文/中英混合校准评测指标。

该脚本只读取已有线上评测结果，不重新调用 LLM。
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CALIBRATED_SAMPLE_PATH = ROOT / "datasets" / "online_eval_en_mixed_200_calibrated.json"
RESULT_JSONL = ROOT / "datasets" / "online_eval_results" / "online_eval_en_mixed_200_results.jsonl"
OUT_DIR = ROOT / "datasets" / "online_eval_results"
SUMMARY_JSON = OUT_DIR / "online_eval_en_mixed_200_calibrated_summary.json"
REPORT_MD = OUT_DIR / "online_eval_en_mixed_200_calibrated_report.md"

LEVEL_TO_ACTION = {
    1: "pass",
    2: "deescalate",
    3: "deescalate",
    4: "sanitize",
    None: "unknown",
}
TOXIC_ACTIONS = {"sanitize", "block"}


def actual_action_from_level(level: int | None) -> str:
    """把当前 pipeline 的 level 映射成校准后的 action。"""
    return LEVEL_TO_ACTION.get(level, "unknown")


def action_correct(row: dict[str, Any]) -> bool | None:
    """判断 action 是否正确；缺少期望时不计入。"""
    expected = row.get("expected_action")
    if not expected:
        return None
    return actual_action_from_level(row.get("actual_level")) == expected


def include_in_strict_level(row: dict[str, Any]) -> bool:
    """是否纳入旧 1/2/3/4 strict level 指标。"""
    policy = row.get("level_policy") or {}
    if policy.get("include_in_strict_level_accuracy") is True:
        return row.get("expected_level") is not None
    return False


def safe_bool_equal(expected: bool | None, actual: bool | None) -> bool | None:
    """expected 为 null 时跳过该指标。"""
    if expected is None:
        return None
    return bool(expected) == bool(actual)


def entity_preserved(row: dict[str, Any]) -> bool | None:
    """检查 expected_entities 中的实体文本是否仍在 sanitized_text 中。"""
    expected_entities = row.get("expected_entities") or []
    if not expected_entities:
        return None
    pipeline = row.get("pipeline") or {}
    sanitized_text = pipeline.get("sanitized_text") or ""
    return all(entity in sanitized_text for entity in expected_entities)


def toxicity_correct(row: dict[str, Any]) -> bool | None:
    """用 action 近似判断 toxic 样本是否被净化类处理。"""
    expected = row.get("expected_toxicity")
    if not expected:
        return None
    actual_action = actual_action_from_level(row.get("actual_level"))
    if expected in {"toxic", "severe"}:
        return actual_action in TOXIC_ACTIONS
    if expected == "none":
        return actual_action not in TOXIC_ACTIONS
    if expected == "mild":
        return actual_action in {"pass", "deescalate"}
    return None


def rate(values: list[bool]) -> float | None:
    """计算布尔列表准确率，空列表返回 None。"""
    if not values:
        return None
    return round(sum(1 for value in values if value) / len(values), 4)


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总校准指标。"""
    action_values: list[bool] = []
    strict_values: list[bool] = []
    harassment_values: list[bool] = []
    dfa_values: list[bool] = []
    entity_values: list[bool] = []
    toxicity_values: list[bool] = []
    false_positive_boundary_values: list[bool] = []

    by_language = Counter()
    by_category: dict[str, dict[str, Any]] = defaultdict(lambda: {"total": 0, "action": []})
    failures: list[dict[str, Any]] = []

    for row in rows:
        by_language[row.get("language", "unknown")] += 1
        category = row.get("category", "unknown")
        by_category[category]["total"] += 1

        action_value = action_correct(row)
        if action_value is not None:
            action_values.append(action_value)
            by_category[category]["action"].append(action_value)
            if not action_value:
                failures.append({
                    "id": row.get("id"),
                    "category": category,
                    "expected_action": row.get("expected_action"),
                    "actual_action": actual_action_from_level(row.get("actual_level")),
                    "actual_level": row.get("actual_level"),
                    "input": row.get("input"),
                })

        if include_in_strict_level(row):
            strict_values.append(row.get("expected_level") == row.get("actual_level"))

        harassment_value = safe_bool_equal(
            row.get("expected_harassment"),
            (row.get("harassment") or {}).get("is_harassment"),
        )
        if harassment_value is not None:
            harassment_values.append(harassment_value)

        dfa_value = safe_bool_equal(
            row.get("expected_dfa_hit"),
            bool((row.get("pipeline") or {}).get("dfa_hits")),
        )
        if dfa_value is not None:
            dfa_values.append(dfa_value)

        entity_value = entity_preserved(row)
        if entity_value is not None:
            entity_values.append(entity_value)

        toxicity_value = toxicity_correct(row)
        if toxicity_value is not None:
            toxicity_values.append(toxicity_value)

        if "boundary_false_positive" in (row.get("tags") or []):
            false_positive_boundary_values.append(actual_action_from_level(row.get("actual_level")) != "sanitize")

    category_summary = {}
    for category, item in by_category.items():
        category_summary[category] = {
            "total": item["total"],
            "action_accuracy": rate(item["action"]),
        }

    return {
        "total": len(rows),
        "action_accuracy": rate(action_values),
        "strict_level_total": len(strict_values),
        "strict_level_accuracy": rate(strict_values),
        "toxicity_accuracy": rate(toxicity_values),
        "harassment_accuracy": rate(harassment_values),
        "dfa_accuracy": rate(dfa_values),
        "entity_preserved_rate": rate(entity_values),
        "false_positive_boundary_accuracy": rate(false_positive_boundary_values),
        "by_language": dict(by_language),
        "by_category": category_summary,
        "action_failures": failures[:50],
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL。"""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def merge_expected_with_results(sample_payload: dict[str, Any], result_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """用校准 expected 覆盖线上结果中的旧 expected 字段。"""
    expected_by_id = {case["id"]: case for case in sample_payload["cases"]}
    merged = []
    for result in result_rows:
        case_id = result["id"]
        expected = expected_by_id[case_id]
        row = dict(result)
        for key, value in expected.items():
            row[key] = value
        merged.append(row)
    return merged


def write_report(summary: dict[str, Any], path: Path) -> None:
    """写 Markdown 报告。"""
    lines = [
        "# 英文与中英混合校准评测报告",
        "",
        f"样本文件：`{CALIBRATED_SAMPLE_PATH}`",
        f"结果文件：`{RESULT_JSONL}`",
        "",
        "## 总览",
        "",
        f"- 总样本数：{summary['total']}",
        f"- Action 准确率：{summary['action_accuracy']}",
        f"- Strict Level 样本数：{summary['strict_level_total']}",
        f"- Strict Level 准确率：{summary['strict_level_accuracy']}",
        f"- Toxicity 准确率：{summary['toxicity_accuracy']}",
        f"- 骚扰检测准确率：{summary['harassment_accuracy']}",
        f"- DFA 命中准确率：{summary['dfa_accuracy']}",
        f"- 实体保留率：{summary['entity_preserved_rate']}",
        f"- 边界误伤准确率：{summary['false_positive_boundary_accuracy']}",
        "",
        "## 语言分布",
        "",
    ]

    for language, count in summary["by_language"].items():
        lines.append(f"- {language}: {count}")

    lines.extend(["", "## 类别结果", ""])
    for category, item in summary["by_category"].items():
        lines.append(f"- {category}: total={item['total']}, action={item['action_accuracy']}")

    lines.extend(["", "## Action 失败样本（最多前 50 条）", ""])
    for failure in summary["action_failures"]:
        lines.append(
            f"- `{failure['id']}` {failure['category']}: "
            f"expected_action={failure['expected_action']} "
            f"actual_action={failure['actual_action']} "
            f"actual_level={failure['actual_level']} "
            f"input={failure['input']}"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """重算并写出校准报告。"""
    sample_payload = json.loads(CALIBRATED_SAMPLE_PATH.read_text(encoding="utf-8"))
    result_rows = load_jsonl(RESULT_JSONL)
    merged = merge_expected_with_results(sample_payload, result_rows)
    summary = summarize_rows(merged)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(summary, REPORT_MD)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行测试**

Run:

```bash
pytest tests/test_en_mixed_calibrated_metrics.py -v
```

Expected:

```text
7 passed
```

- [ ] **Step 3: 提交核心逻辑**

```bash
git add datasets/recalculate_en_mixed_calibrated_metrics.py tests/test_en_mixed_calibrated_metrics.py
git commit -m "feat: 实现英文混合校准指标重算逻辑"
```

---

## Task 3: 生成校准版样本文件

**Files:**
- Create: `datasets/online_eval_en_mixed_200_calibrated.json`
- Test: `tests/test_en_mixed_calibrated_metrics.py`

- [ ] **Step 1: 用脚本从原始样本生成校准样本初稿**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path

root = Path('/Users/cxw114/Desktop/idea')
src = root / 'datasets' / 'online_eval_en_mixed_200.json'
dst = root / 'datasets' / 'online_eval_en_mixed_200_calibrated.json'
payload = json.loads(src.read_text(encoding='utf-8'))

PASS_CATEGORIES = {
    '英文实体保护',
    '中英混合正常业务',
    '英文正常/弱投诉',
    '英文客服正常对照',
    '英文骚扰检测正常对照',
}
TOXIC_CATEGORIES = {
    '中英混合攻击/绕过',
    '对抗样本/cnen_mix',
    '对抗样本/leet',
    '对抗样本/en_dfa_miss',
    '对抗样本/format_bypass',
    '英文骚扰/攻击样本',
}
BOUNDARY_TAGS = {'entity', 'order', 'amount', 'date', 'boundary'}

ENTITY_MARKERS = [
    'ORD-', 'ORDER-', 'INV_', 'TCK-', 'SKU-', '1Z999', '$', '@', '+1-',
    '221B Baker Street', 'Galaxy', 'IPHONE', 'A55', 'ASS2', 'AV cable', '2B pencil',
]

for case in payload['cases']:
    category = case.get('category')
    tags = set(case.get('tags') or [])
    text = case.get('input', '')

    expected_entities = [marker for marker in ENTITY_MARKERS if marker in text]

    if category in PASS_CATEGORIES:
        case['expected_level'] = None
        case['expected_action'] = 'pass'
        case['expected_toxicity'] = 'none'
        case['expected_sentiment'] = 'negative' if category in {'英文实体保护', '英文正常/弱投诉', '中英混合正常业务'} else 'neutral'
        case['level_policy'] = {
            'include_in_strict_level_accuracy': False,
            'reason': '英文/中英普通业务样本按 action、entity、误伤边界评估，不参与中文式 strict level',
        }
    elif category in TOXIC_CATEGORIES or case.get('expected_level') == 4:
        case['expected_action'] = 'sanitize'
        case['expected_toxicity'] = 'toxic'
        case['expected_sentiment'] = 'angry'
        case['level_policy'] = {
            'include_in_strict_level_accuracy': True,
            'reason': '明确攻击、辱骂、涉黄或对抗样本保留 strict level 辅助评估',
        }
    elif case.get('expected_level') == 3:
        case['expected_level'] = None
        case['expected_action'] = 'deescalate'
        case['expected_toxicity'] = 'mild'
        case['expected_sentiment'] = 'angry'
        case['level_policy'] = {
            'include_in_strict_level_accuracy': False,
            'reason': '强投诉情绪按 deescalate 评估，不参与 strict level',
        }
    else:
        case['expected_level'] = None
        case['expected_action'] = 'pass'
        case['expected_toxicity'] = 'none'
        case['expected_sentiment'] = 'neutral'
        case['level_policy'] = {
            'include_in_strict_level_accuracy': False,
            'reason': '默认按 action 评估，不参与 strict level',
        }

    case['expected_entities'] = expected_entities
    if expected_entities or tags.intersection(BOUNDARY_TAGS):
        case['tags'] = sorted(tags | {'boundary_false_positive'})

payload['name'] = 'online_eval_en_mixed_200_calibrated'
payload['description'] = '英文与中英混合线上评测集的校准版本：英文普通投诉不再使用中文式 1/2/3/4 level 作为主指标，改用 action、toxicity、sentiment、entity、harassment 等多标签。'
payload['version'] = '2026-06-02'
payload['schema']['expected_level'] = '仅对明确攻击/辱骂/涉黄/对抗样本保留；英文普通投诉为 null，不参与 strict level 主指标'
payload['schema']['expected_action'] = 'pass|deescalate|sanitize|block，英文/中英混合主评测标签'
payload['schema']['expected_toxicity'] = 'none|mild|toxic|severe'
payload['schema']['expected_sentiment'] = 'neutral|negative|angry'
payload['schema']['expected_entities'] = '需要在 sanitized_text 中保留的实体文本列表'
payload['schema']['level_policy'] = '是否纳入旧 strict level accuracy 以及原因'

dst.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(dst)
PY
```

Expected:

```text
/Users/cxw114/Desktop/idea/datasets/online_eval_en_mixed_200_calibrated.json
```

- [ ] **Step 2: 人工抽查关键样本**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path

path = Path('/Users/cxw114/Desktop/idea/datasets/online_eval_en_mixed_200_calibrated.json')
payload = json.loads(path.read_text(encoding='utf-8'))
for case_id in [
    'online_en_mixed_001',
    'online_en_mixed_009',
    'online_en_mixed_024',
    'online_en_mixed_026',
    'online_en_mixed_048',
    'online_en_mixed_188',
]:
    case = next(c for c in payload['cases'] if c['id'] == case_id)
    print(case_id, case.get('expected_level'), case['expected_action'], case['expected_toxicity'], case['level_policy']['include_in_strict_level_accuracy'], case.get('expected_entities'))
PY
```

Expected pattern:

```text
online_en_mixed_001 None pass none False [...]
online_en_mixed_009 None pass none False [...]
online_en_mixed_024 None pass none False [...]
online_en_mixed_026 4 sanitize toxic True []
online_en_mixed_048 4 sanitize toxic True []
online_en_mixed_188 4 sanitize toxic True []
```

如果 `online_en_mixed_026` 是 “This app is porn...” 且实际业务希望判为内容风险而非用户辱骂，则保留 `sanitize`；如果希望它只是应用分类投诉，则改为 `expected_action=deescalate`、`expected_toxicity=mild`，并移出 strict level。

- [ ] **Step 3: 校验样本总数和字段完整性**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path

path = Path('/Users/cxw114/Desktop/idea/datasets/online_eval_en_mixed_200_calibrated.json')
payload = json.loads(path.read_text(encoding='utf-8'))
required = {'expected_action', 'expected_toxicity', 'expected_sentiment', 'expected_entities', 'level_policy'}
missing = []
for case in payload['cases']:
    absent = sorted(required - set(case))
    if absent:
        missing.append((case['id'], absent))
print('total=', len(payload['cases']))
print('missing=', missing[:10])
PY
```

Expected:

```text
total= 200
missing= []
```

- [ ] **Step 4: 提交校准样本**

```bash
git add datasets/online_eval_en_mixed_200_calibrated.json
git commit -m "data: 添加英文混合校准评测集"
```

---

## Task 4: 基于已有线上结果重算校准报告

**Files:**
- Modify: `datasets/recalculate_en_mixed_calibrated_metrics.py`
- Create: `datasets/online_eval_results/online_eval_en_mixed_200_calibrated_summary.json`
- Create: `datasets/online_eval_results/online_eval_en_mixed_200_calibrated_report.md`

- [ ] **Step 1: 运行重算脚本**

Run:

```bash
python datasets/recalculate_en_mixed_calibrated_metrics.py
```

Expected:

```text
{
  "total": 200,
  "action_accuracy": ...,
  "strict_level_total": ...,
  "strict_level_accuracy": ...,
  "toxicity_accuracy": ...,
  "harassment_accuracy": ...,
  "dfa_accuracy": ...,
  "entity_preserved_rate": ...,
  "false_positive_boundary_accuracy": ...
}
```

- [ ] **Step 2: 验证报告文件存在且不包含密钥**

Run:

```bash
python - <<'PY'
from pathlib import Path

paths = [
    Path('/Users/cxw114/Desktop/idea/datasets/online_eval_results/online_eval_en_mixed_200_calibrated_summary.json'),
    Path('/Users/cxw114/Desktop/idea/datasets/online_eval_results/online_eval_en_mixed_200_calibrated_report.md'),
]
for path in paths:
    text = path.read_text(encoding='utf-8')
    assert 'sk-' not in text
    assert 'API_KEY' not in text
    print(path.name, 'ok', len(text))
PY
```

Expected:

```text
online_eval_en_mixed_200_calibrated_summary.json ok ...
online_eval_en_mixed_200_calibrated_report.md ok ...
```

- [ ] **Step 3: 抽查报告核心口径**

Run:

```bash
python - <<'PY'
from pathlib import Path

report = Path('/Users/cxw114/Desktop/idea/datasets/online_eval_results/online_eval_en_mixed_200_calibrated_report.md').read_text(encoding='utf-8')
for required in [
    'Action 准确率',
    'Strict Level 样本数',
    'Toxicity 准确率',
    '实体保留率',
    '边界误伤准确率',
]:
    assert required in report
print('report headings ok')
PY
```

Expected:

```text
report headings ok
```

- [ ] **Step 4: 提交校准报告**

```bash
git add datasets/online_eval_results/online_eval_en_mixed_200_calibrated_summary.json datasets/online_eval_results/online_eval_en_mixed_200_calibrated_report.md
git commit -m "report: 生成英文混合校准评测报告"
```

---

## Task 5: 更新数据集文档，明确新旧口径

**Files:**
- Modify: `datasets/README.md`

- [ ] **Step 1: 在 README 增加校准评测说明**

在 `datasets/README.md` 追加以下章节：

```markdown
## 英文/中英混合校准评测口径

`online_eval_en_mixed_200.json` 是原始线上评测集，保留了首次构建时的 `expected_level`。该字段对英文普通投诉样本存在标注偏高问题：英文里很多“扣款错误、物流延迟、设备故障”属于业务严重但表达克制，不应直接按中文客服情绪等级标成 Level 3。

因此英文/中英混合主评测请优先使用：

- `online_eval_en_mixed_200_calibrated.json`
- `online_eval_results/online_eval_en_mixed_200_calibrated_summary.json`
- `online_eval_results/online_eval_en_mixed_200_calibrated_report.md`

校准版主指标为：

| 指标 | 含义 |
| --- | --- |
| `action_accuracy` | pass/deescalate/sanitize/block 是否符合预期 |
| `toxicity_accuracy` | toxic/severe 样本是否被净化类处理，none/mild 是否避免误杀 |
| `harassment_accuracy` | 本地骚扰检测是否符合预期 |
| `dfa_accuracy` | DFA 命中是否符合预期 |
| `entity_preserved_rate` | 订单号、金额、日期、型号等实体是否保留 |
| `false_positive_boundary_accuracy` | 2B pencil、AV cable、ASS2 firmware 等边界词是否避免误杀 |

旧的 `strict_level_accuracy` 只作为辅助指标，并且只统计 `level_policy.include_in_strict_level_accuracy=true` 的明确攻击、辱骂、涉黄或对抗样本。不要再用英文普通投诉的 Level 1/2/3 严格一致性评价模型主效果。

重算命令：

```bash
python datasets/recalculate_en_mixed_calibrated_metrics.py
```

该命令只读取已有线上结果：

```text
datasets/online_eval_results/online_eval_en_mixed_200_results.jsonl
```

不会重新调用 LLM，也不会读取或输出任何 API Key。
```

- [ ] **Step 2: 检查 Markdown 中没有密钥**

Run:

```bash
python - <<'PY'
from pathlib import Path

text = Path('/Users/cxw114/Desktop/idea/datasets/README.md').read_text(encoding='utf-8')
assert 'sk-' not in text
assert 'API_KEY=' not in text
print('datasets README ok')
PY
```

Expected:

```text
datasets README ok
```

- [ ] **Step 3: 提交文档**

```bash
git add datasets/README.md
git commit -m "docs: 说明英文混合校准评测口径"
```

---

## Task 6: 增加回归测试，防止英文普通投诉重新参与 strict level

**Files:**
- Modify: `tests/test_en_mixed_calibrated_metrics.py`
- Test: `datasets/online_eval_en_mixed_200_calibrated.json`

- [ ] **Step 1: 增加数据集结构测试**

向 `tests/test_en_mixed_calibrated_metrics.py` 追加：

```python
import json
from pathlib import Path


def test_calibrated_dataset_has_200_cases_and_required_fields():
    path = Path("datasets/online_eval_en_mixed_200_calibrated.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "expected_action",
        "expected_toxicity",
        "expected_sentiment",
        "expected_entities",
        "level_policy",
    }

    assert payload["total"] == 200
    assert len(payload["cases"]) == 200
    for case in payload["cases"]:
        assert required.issubset(case.keys())


def test_english_business_categories_do_not_participate_in_strict_level_accuracy():
    path = Path("datasets/online_eval_en_mixed_200_calibrated.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    excluded_categories = {
        "英文实体保护",
        "英文正常/弱投诉",
        "英文客服正常对照",
        "中英混合正常业务",
    }

    for case in payload["cases"]:
        if case["category"] in excluded_categories:
            assert case["expected_level"] is None
            assert case["expected_action"] in {"pass", "deescalate"}
            assert case["level_policy"]["include_in_strict_level_accuracy"] is False


def test_toxic_or_adversarial_categories_keep_sanitize_action():
    path = Path("datasets/online_eval_en_mixed_200_calibrated.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    toxic_categories = {
        "中英混合攻击/绕过",
        "对抗样本/cnen_mix",
        "对抗样本/leet",
        "对抗样本/en_dfa_miss",
        "对抗样本/format_bypass",
        "英文骚扰/攻击样本",
    }

    for case in payload["cases"]:
        if case["category"] in toxic_categories and case.get("expected_toxicity") == "toxic":
            assert case["expected_action"] == "sanitize"
```

- [ ] **Step 2: 运行测试**

Run:

```bash
pytest tests/test_en_mixed_calibrated_metrics.py -v
```

Expected:

```text
10 passed
```

- [ ] **Step 3: 提交回归测试**

```bash
git add tests/test_en_mixed_calibrated_metrics.py
git commit -m "test: 防止英文普通投诉参与 strict level 指标"
```

---

## Task 7: 全量验证与最终检查

**Files:**
- Test: `tests/test_en_mixed_calibrated_metrics.py`
- Test: `datasets/recalculate_en_mixed_calibrated_metrics.py`
- Inspect: `git status`

- [ ] **Step 1: 运行校准指标单测**

Run:

```bash
pytest tests/test_en_mixed_calibrated_metrics.py -v
```

Expected:

```text
10 passed
```

- [ ] **Step 2: 重新生成校准报告**

Run:

```bash
python datasets/recalculate_en_mixed_calibrated_metrics.py
```

Expected:

```text
输出 JSON summary，total 为 200，且生成 calibrated_summary/report 文件
```

- [ ] **Step 3: 确认输出文件不含密钥**

Run:

```bash
python - <<'PY'
from pathlib import Path

paths = [
    Path('datasets/online_eval_en_mixed_200_calibrated.json'),
    Path('datasets/recalculate_en_mixed_calibrated_metrics.py'),
    Path('datasets/online_eval_results/online_eval_en_mixed_200_calibrated_summary.json'),
    Path('datasets/online_eval_results/online_eval_en_mixed_200_calibrated_report.md'),
    Path('datasets/README.md'),
    Path('tests/test_en_mixed_calibrated_metrics.py'),
]
for path in paths:
    text = path.read_text(encoding='utf-8')
    assert 'sk-' not in text, path
    assert 'API_KEY=' not in text, path
print('secret scan ok')
PY
```

Expected:

```text
secret scan ok
```

- [ ] **Step 4: 查看工作区状态**

Run:

```bash
git status --short
```

Expected:

```text
只出现本计划相关文件，或没有未提交变更
```

- [ ] **Step 5: 如果还有本计划相关未提交文件，提交最终结果**

```bash
git add datasets/online_eval_en_mixed_200_calibrated.json datasets/recalculate_en_mixed_calibrated_metrics.py datasets/online_eval_results/online_eval_en_mixed_200_calibrated_summary.json datasets/online_eval_results/online_eval_en_mixed_200_calibrated_report.md datasets/README.md tests/test_en_mixed_calibrated_metrics.py
git commit -m "feat: 校准英文混合评测指标体系"
```

---

## 不在本计划内的后续任务

以下问题已经从当前 200 条评测中暴露，但不应混进本次“标签校准”改造：

1. 修复 harassment detector 对中英混合拆字、空格绕过、拼音变体召回弱的问题。
2. 修复 DFA 对 `porn`、`AV资源` 等内容风险词的策略问题。
3. 修复 `ASS2 firmware`、`2B pencil`、`AV cable` 等边界误伤。
4. 引入外部英文 toxicity 数据集，例如 Jigsaw、Civil Comments、HateXplain。
5. 引入英文 emotion 数据集，例如 GoEmotions，用于校准 anger/annoyance/frustration。
6. 清理 `.env` 中硬编码密钥，并将敏感配置迁移到本地环境变量或未跟踪模板文件。

这些应分别开独立计划，避免当前任务过度扩张。

---

## 自检

### Spec coverage

- 英文 level 是否取消：已通过 `expected_level=null` 和 `level_policy.include_in_strict_level_accuracy=false` 处理英文普通投诉。
- 外部数据集结论：本计划不直接导入外部数据集，先校准现有 200 条，后续再单独引入 Jigsaw/GoEmotions 等。
- 不重跑 LLM：脚本只读取已有 `results.jsonl`。
- 报告主指标变化：新增 action/toxicity/entity/boundary 指标。
- 测试覆盖：核心函数测试 + 数据集结构回归测试。
- 密钥保护：所有报告和文档检查 `sk-` / `API_KEY=`。

### Placeholder scan

没有 `TBD`、`TODO`、`implement later`、`similar to Task N` 等占位描述。所有代码步骤都给出完整代码或完整命令。

### Type consistency

- `expected_action`、`expected_toxicity`、`expected_sentiment`、`expected_entities`、`level_policy` 在脚本、测试、README 中名称一致。
- `actual_action_from_level()`、`action_correct()`、`include_in_strict_level()`、`entity_preserved()`、`summarize_rows()` 在测试和实现中名称一致。
- 输出文件路径在脚本、报告、验证命令中一致。
