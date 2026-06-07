#!/usr/bin/env python3
"""
ToneBarrier — 自动化回归测试运行器。
加载 test_cases.json，对每条用例调用 dfa_filter.py 和 validator.py 并验证预期结果。

Automated regression test runner for the ToneBarrier skill.
Loads test_cases.json, calls dfa_filter.py and validator.py per case, and verifies expected results.

第1层（DFA）：精确匹配回归 — 23 条，检查命中/漏报/误报。
Layer 1 (DFA): Exact-match regression — 23 cases, checking hits, misses, and false positives.

第2层（验证器）：实体保留回归 — 3 条 + 对抗样本回归，检查 validator 判定。
Layer 2 (Validator): Entity-preservation regression — 3 cases + adversarial sample regression, checking validator judgments.

第3层（对抗回归）：DFA 行为验证 — 检查 DFA 对对抗变体的预期行为。
Layer 3 (Adversarial Regression): DFA behavior verification — checking DFA expected behavior against adversarial variants.

注意：完整 SKILL 端到端评测（含 LLM 情绪判断/净化质量）需通过 /tonebarrier 实际调用来完成，不在本脚本覆盖范围内。
Note: Full SKILL end-to-end evaluation (including LLM sentiment judgment/purification quality) must be done via actual /tonebarrier invocations, outside the scope of this script.
"""
import json
import subprocess
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
SKILL_DIR = os.path.join(REPO_ROOT, "skills", "tonebarrier")
TEST_CASES = os.path.join(SCRIPT_DIR, "test_cases.json")
DFA_FILTER = os.path.join(SKILL_DIR, "scripts", "dfa_filter.py")
VALIDATOR = os.path.join(SKILL_DIR, "scripts", "validator.py")


def run_dfa(text):
    result = subprocess.run(
        ["python3", DFA_FILTER],
        input=text.encode("utf-8"),
        capture_output=True,
        timeout=10,
    )
    return json.loads(result.stdout.decode("utf-8"))


def run_validator(original, sanitized):
    """
    调用 validator.py，返回解析后的 JSON 输出。

    Calls validator.py and returns the parsed JSON output.
    """
    payload = json.dumps({"original": original, "sanitized": sanitized})
    result = subprocess.run(
        ["python3", VALIDATOR],
        input=payload.encode("utf-8"),
        capture_output=True,
        timeout=10,
    )
    return json.loads(result.stdout.decode("utf-8"))


def run_tests():
    with open(TEST_CASES, encoding="utf-8") as f:
        cases = json.load(f)

    total_phase1 = len(cases)
    passed_phase1 = 0
    total_phase2 = 0
    passed_phase2 = 0

    # ===== 第1层：DFA 精确匹配测试 =====
    print("=" * 70)
    print("  第1层：DFA 精确匹配测试")
    print("=" * 70)

    for i, case in enumerate(cases, 1):
        case_id = case["id"]
        category = case["category"]
        input_text = case["input"]
        expected_dfa = case.get("expected_dfa_matches", [])
        expected_not = case.get("expected_dfa_not_matches", [])

        try:
            output = run_dfa(input_text)
        except Exception as e:
            print(f"\n[ERROR] [{case_id}] ({category}) — 运行异常: {e}")
            continue

        detected_words = [m["word"] for m in output.get("matches", [])]
        detected_set = set(detected_words)
        failures = []

        missing = [w for w in expected_dfa if w not in detected_set]
        if missing:
            failures.append(f"缺失匹配词: {', '.join(missing)}")

        # 检查额外命中（未在 expected_dfa 或 expected_not 中声明的命中词）。
        # Check for unexpected extra matches (words hit but not declared in expected_dfa or expected_not).
        if len(expected_dfa) > 0:
            unexpected_extra = [w for w in detected_words if w not in expected_dfa and w not in expected_not]
            if unexpected_extra:
                failures.append(f"额外命中（未声明的命中词）: {', '.join(unexpected_extra)}")
        elif len(expected_dfa) == 0 and len(detected_words) > 0:
            truly_unexpected = [w for w in detected_words if w not in expected_not]
            if truly_unexpected:
                failures.append(f"误报（期望无脏话但检出）: {', '.join(truly_unexpected)}")

        unexpected = [w for w in expected_not if w in detected_set]
        if unexpected:
            failures.append(f"不应检出但命中: {', '.join(unexpected)}")

        actual_has = output.get("has_profanity", False)
        has_any = len(detected_words) > 0
        if actual_has != has_any:
            failures.append(
                f"has_profanity 错误 (期望={'是' if has_any else '否'}, 实际={'是' if actual_has else '否'})"
            )

        summary = output.get("summary", "")
        if not summary:
            failures.append("缺少 summary 字段")

        case_passed = len(failures) == 0
        status = "[PASS]" if case_passed else "[FAIL]"
        detail = (" | " + "; ".join(failures)) if failures else ""

        print(f"\n[{i:02d}/{total_phase1:02d}] {status} [{case_id}] ({category}){detail}")
        print(f"  输入: {input_text[:60]}{'...' if len(input_text) > 60 else ''}")
        print(f"  命中: {detected_words}  期望: {expected_dfa}")
        if expected_not:
            print(f"  排除: {expected_not}")

        if case_passed:
            passed_phase1 += 1

    # ===== 第1.5层：级别一致性校验（DFA 可判定的规则） =====
    # Layer 1.5: Level consistency check (rules determinable by DFA).
    # 规则：有辱骂性脏话 → level 4，有感叹粗口 → level 3，无脏话 → level 1/2
    print("\n" + "=" * 70)
    print("  第1.5层：级别一致性校验（DFA 规则可判定部分）")
    print("=" * 70)

    # 感叹粗口（level 3）vs 辱骂性脏话（level 4）的区分词
    EXCLAMATORY_WORDS = {"卧槽", "窝草", "我靠", "我去", "damn", "bloody", "hell", "crap"}
    level_cases = [c for c in cases if "expected_level" in c]
    level_issues = []

    for case in level_cases:
        case_id = case["id"]
        expected_level = case["expected_level"]
        input_text = case["input"]

        try:
            output = run_dfa(input_text)
        except Exception:
            continue

        has_profanity = output.get("has_profanity", False)
        detected_words = set(m["word"] for m in output.get("matches", []))

        # 基本一致性规则
        if expected_level == 1 and has_profanity:
            # level 1 不应有任何脏话命中（除非是已知的误报排除词）
            level_issues.append(
                f"  [{case_id}] level=1 但 DFA 命中: {detected_words}"
            )
        elif expected_level == 4 and not has_profanity:
            # level 4 必须有脏话（否则不应标为 4）
            # 例外：leet speak/谐音等 DFA 可能漏报，LLM 补充
            pass  # DFA 漏报是正常的，不算不一致
        elif expected_level <= 2 and has_profanity:
            level_issues.append(
                f"  [{case_id}] level={expected_level} 但 DFA 命中: {detected_words}"
            )

    if level_issues:
        print(f"\n  发现 {len(level_issues)} 个级别不一致:")
        for issue in level_issues:
            print(issue)
        print("\n  注意：以上不一致可能是 DFA 误报或 expected_level 标注错误。")
        print("  请核对 SKILL.md 级别定义后修正 test_cases.json。")
    else:
        print("\n  级别一致性校验通过：所有 expected_level 与 DFA 结果无矛盾。")

    # ===== 第2层：验证器端到端测试（实体保留 + 净化质量） =====
    # Layer 2: Validator end-to-end testing (entity-preservation + purification quality).
    print("\n" + "=" * 70)
    print("  第2层：验证器端到端测试（实体保留 + 净化质量）")
    print("=" * 70)

    validator_cases = [c for c in cases if c.get("sanitized_reference")]
    total_phase2 = len(validator_cases)
    idx = 0

    # 额外回归：地址漂移和实体丢失场景。
    # Additional regression: address drift and entity loss scenarios.
    regression_cases = [
        {
            "id": "reg_address_prefix_lost",
            "category": "回归-删城市前缀应失败",
            "original": "送到北京市朝阳区建国路88号。",
            "sanitized": "送到朝阳区建国路88号。",
            "expect_pass": False,
        },
        {
            "id": "reg_address_city_swapped",
            "category": "回归-换城市应失败",
            "original": "上海市浦东新区张江路666号。",
            "sanitized": "苏州市浦东新区张江路666号。",
            "expect_pass": False,
        },
        {
            "id": "reg_all_info_preserved",
            "category": "回归-完整信息保留应通过",
            "original": "订单编号ORDER20240523金额2999元送到北京市朝阳区建国路88号联系电话13812345678。",
            "sanitized": "订单编号ORDER20240523金额2999元送到北京市朝阳区建国路88号联系电话13812345678。",
            "expect_pass": True,
        },
        {
            "id": "reg_order_id_mutated",
            "category": "回归-订单号含字母被篡改应失败",
            "original": "订单编号ABCD20240523的包裹发错了。",
            "sanitized": "订单编号WXYZ20240523的包裹发错了。",
            "expect_pass": False,
        },
        {
            "id": "reg_order_id_preserved",
            "category": "回归-订单号完整保留应通过",
            "original": "订单编号ABCD20240523的包裹发错了。",
            "sanitized": "订单编号ABCD20240523的包裹发错了。",
            "expect_pass": True,
        },
        {
            "id": "reg_cn_time_lost",
            "category": "回归-中文时间丢失应失败",
            "original": "用了三天就坏了要求退款。",
            "sanitized": "要求退款。",
            "expect_pass": False,
        },
        {
            "id": "reg_cn_time_preserved",
            "category": "回归-中文时间保留应通过",
            "original": "用了三天就坏了要求退款。",
            "sanitized": "用了三天就坏了要求退款。",
            "expect_pass": True,
        },
        {
            "id": "reg_en_time_lost",
            "category": "回归-英文时间丢失应失败",
            "original": "Waited three weeks for delivery, still nothing.",
            "sanitized": "Still nothing.",
            "expect_pass": False,
        },
        {
            "id": "reg_amount_digit_compare",
            "category": "回归-金额数字不同应失败",
            "original": "金额2999元的手机坏了。",
            "sanitized": "金额99元的手机坏了。",
            "expect_pass": False,
        },
        {
            "id": "reg_validator_does_not_check_profanity",
            "category": "回归-validator 只负责实体保留，不负责脏话清除",
            "original": "他妈的这个产品坏了",
            "sanitized": "他妈的这个产品坏了",
            "expect_pass": True,
        },
        {
            "id": "reg_amount_decimal_equivalent",
            "category": "回归-金额等价格式应通过",
            "original": "金额2999元的手机坏了。",
            "sanitized": "金额2999.00元的手机坏了。",
            "expect_pass": True,
        },
        {
            "id": "reg_en_time_word_equivalent",
            "category": "回归-英文数字时间等价格式应通过",
            "original": "It has been 2 weeks since my order was placed.",
            "sanitized": "It has been two weeks since my order was placed.",
            "expect_pass": True,
        },
        {
            "id": "reg_cn_time_digit_equivalent",
            "category": "回归-中文数字时间等价格式应通过",
            "original": "用了两天就坏了。",
            "sanitized": "用了2天就坏了。",
            "expect_pass": True,
        },
        {
            "id": "reg_cn_time_twelve_equivalent",
            "category": "回归-中文十位数字时间等价格式应通过",
            "original": "用了十二天就坏了。",
            "sanitized": "用了12天就坏了。",
            "expect_pass": True,
        },
        {
            "id": "reg_cn_date_word_equivalent",
            "category": "回归-中文日期等价格式应通过",
            "original": "十二月一日买的。",
            "sanitized": "12月1日买的。",
            "expect_pass": True,
        },
        {
            "id": "reg_cn_time_mutated",
            "category": "回归-中文时间被篡改应失败",
            "original": "用了三天就坏了。",
            "sanitized": "用了两天就坏了。",
            "expect_pass": False,
        },
        {
            "id": "reg_en_time_mutated",
            "category": "回归-英文时间被篡改应失败",
            "original": "Waited three weeks for delivery.",
            "sanitized": "Waited two weeks for delivery.",
            "expect_pass": False,
        },
        {
            "id": "reg_model_date_lost",
            "category": "回归-产品型号和时间丢失应失败",
            "original": "产品型号ABC-123于2024年5月1日购买后两天损坏",
            "sanitized": "购买后损坏",
            "expect_pass": False,
        },
        {
            "id": "reg_amount_corrupted",
            "category": "回归-金额被篡改应失败",
            "original": "金额2999元的手机坏了。",
            "sanitized": "金额99元的手机坏了。",
            "expect_pass": False,
        },
        {
            "id": "reg_order_id_truncated",
            "category": "回归-单号被截断应失败",
            "original": "单号20240523001的包裹。",
            "sanitized": "单号20240523的包裹。",
            "expect_pass": False,
        },
        {
            "id": "reg_model_mutated",
            "category": "回归-产品型号被篡改应失败",
            "original": "产品型号ABC-123坏了。",
            "sanitized": "产品型号XYZ-123坏了。",
            "expect_pass": False,
        },
        {
            "id": "reg_amount_preserved",
            "category": "回归-金额正确保留应通过",
            "original": "金额2999元的手机坏了。",
            "sanitized": "金额2999元的手机坏了。",
            "expect_pass": True,
        },
        {
            "id": "reg_en_numeric_time_lost",
            "category": "回归-英文数字时间丢失应失败",
            "original": "I waited 15 days for delivery and got nothing.",
            "sanitized": "I got nothing.",
            "expect_pass": False,
        },
        {
            "id": "reg_en_numeric_time_preserved",
            "category": "回归-英文数字时间保留应通过",
            "original": "I waited 15 days for delivery and got nothing.",
            "sanitized": "I waited 15 days for delivery and got nothing.",
            "expect_pass": True,
        },
        {
            "id": "reg_en_weeks_lost",
            "category": "回归-英文周数丢失应失败",
            "original": "It has been 2 weeks since my order was placed.",
            "sanitized": "My order was placed.",
            "expect_pass": False,
        },
    ]

    for case in validator_cases + regression_cases:
        idx += 1
        case_id = case["id"]
        category = case.get("category", "回归测试")
        original = case["original"] if "original" in case else case["input"]
        sanitized = case.get("sanitized_reference", case.get("sanitized"))

        failures = []

        try:
            vresult = run_validator(original, sanitized)
        except Exception as e:
            print(f"\n[ERROR] [{case_id}] — validator 运行异常: {e}")
            continue

        # 检查 validator 的 passed 判定是否与预期一致。
        # Check whether the validator's passed judgment matches expectations.
        expect_pass = case.get("expect_pass", True)
        if vresult["passed"] != expect_pass:
            if expect_pass:
                failures.append(
                    f"validator 应通过但失败: 丢失 {vresult['lost_count']} 个实体"
                )
            else:
                failures.append("validator 应失败但通过（地址漂移/实体丢失未被检测）")

        # 检查 sanitized 文本中是否包含/排除了预期内容。
        # Check whether the sanitized text contains/excludes expected content.
        expected_contains = case.get("expected_sanitized_contains", [])
        for item in expected_contains:
            if item not in sanitized:
                failures.append(f"净化文本缺少关键信息: '{item}'")

        expected_not = case.get("expected_sanitized_not_contains", [])
        for item in expected_not:
            if item in sanitized:
                failures.append(f"净化文本含应删除内容: '{item}'")

        case_passed = len(failures) == 0
        status = "[PASS]" if case_passed else "[FAIL]"
        detail = (" | " + "; ".join(failures)) if failures else ""

        print(f"\n[{idx:02d}/{total_phase2 + len(regression_cases):02d}] {status} [{case_id}] ({category}){detail}")
        print(f"  validator: {'passed' if vresult['passed'] else 'failed'} "
              f"(保留 {vresult['preserved_count']}/{vresult['original_entity_count']}, "
              f"丢失 {vresult['lost_count']})")
        if vresult.get("lost_entities"):
            print(f"  丢失实体: {vresult['lost_entities'][:5]}")

        if case_passed:
            passed_phase2 += 1

    # ===== 第2.5层：DFA 脏话清除风险回归 =====
    # Layer 2.5: DFA profanity-removal risk regression.
    # validator 只检查实体保留；这里单独检查应删除的脏话是否能被 DFA 命中。
    print("\n" + "=" * 70)
    print("  第2.5层：DFA 脏话清除风险回归")
    print("=" * 70)

    profanity_regression_cases = [
        {
            "id": "reg_profanity_dfa_hits_cn",
            "input": "他妈的这个产品坏了",
            "expected_dfa": ["他妈的"],
        },
        {
            "id": "reg_profanity_dfa_hits_a55_attack",
            "input": "your a55 support is useless",
            "expected_dfa": ["ass(leet)"],
        },
        {
            "id": "reg_profanity_dfa_hits_a55_support_context",
            "input": "this a55 support is useless",
            "expected_dfa": ["ass(leet)"],
        },
        {
            "id": "reg_profanity_dfa_ignores_a55_model",
            "input": "Need support for device A55.",
            "expected_dfa": [],
        },
        {
            "id": "reg_profanity_dfa_ignores_standalone_a55_model",
            "input": "I bought A55 yesterday and it reboots.",
            "expected_dfa": [],
        },
        {
            "id": "reg_profanity_dfa_ignores_a55_replacement",
            "input": "Please replace A55.",
            "expected_dfa": [],
        },
        {
            "id": "reg_profanity_dfa_ignores_ass2_firmware",
            "input": "Need support for ASS2 firmware on device A55.",
            "expected_dfa": [],
        },
    ]
    total_phase25 = len(profanity_regression_cases)
    passed_phase25 = 0
    for i, case in enumerate(profanity_regression_cases, 1):
        output = run_dfa(case["input"])
        detected_words = [m["word"] for m in output.get("matches", [])]
        detected_set = set(detected_words)
        expected = case["expected_dfa"]
        if expected:
            case_passed = all(word in detected_set for word in expected)
        else:
            case_passed = len(detected_words) == 0
        status = "[PASS]" if case_passed else "[FAIL]"
        print(f"\n[{i:02d}/{total_phase25:02d}] {status} [{case['id']}]")
        print(f"  输入: {case['input']}")
        print(f"  命中: {detected_words}  期望: {expected}")
        if case_passed:
            passed_phase25 += 1

    # ===== 第3层：DFA 对抗行为验证 =====
    # Layer 3: DFA adversarial behavior verification.
    # 检查 DFA 对对抗变体的预期命中/未命中行为。
    # Checks DFA expected hit/miss behavior against adversarial variants.
    # 注意：完整 LLM 端到端验证需通过 evaluation/tonebarrier/adversarial/e2e_validate.py 完成。
    # Note: Full LLM end-to-end verification must be done via evaluation/tonebarrier/adversarial/e2e_validate.py.
    print("\n" + "=" * 70)
    print("  第3层：DFA 对抗行为验证（DFA 对变体的预期命中/未命中检查）")
    print("  注意：完整 LLM 端到端验证需通过 evaluation/tonebarrier/adversarial/e2e_validate.py 完成")
    print("=" * 70)

    ADVERSARIAL_REGRESSION = os.path.join(REPO_ROOT, "evaluation", "tonebarrier", "adversarial", "adversary_regression.json")

    if os.path.exists(ADVERSARIAL_REGRESSION):
        with open(ADVERSARIAL_REGRESSION, encoding="utf-8") as f:
            adv_cases = json.load(f)

        total_phase3 = len(adv_cases)
        passed_phase3 = 0

        for i, case in enumerate(adv_cases, 1):
            case_id = case["id"]
            category = case["category"]
            input_text = case["input"]
            expected_dfa = case.get("expected_dfa_hit", False)

            output = run_dfa(input_text)
            detected = output.get("has_profanity", False)

            # 检查 DFA 结果是否与预期一致。
            # Check whether the DFA result matches expectations.
            # 对于对抗样本：DFA 应该漏报（这正是对抗变体的目的）。
            # For adversarial samples: DFA should miss (that is the point of adversarial variants).
            # 真正的测试是 LLM 是否能捕获——但这需要 /tonebarrier 调用。
            # The real test is whether the LLM can catch it — but that requires /tonebarrier invocation.
            # 因此这里仅验证 DFA 行为是否符合预期。
            # So here we only verify that DFA behavior matches expectations.
            dfa_correct = (detected == expected_dfa)

            case_passed = dfa_correct

            status = "[PASS]" if case_passed else "[FAIL]"
            detail = "" if case_passed else f" | DFA预期={'命中' if expected_dfa else '未命中'} 实际={'命中' if detected else '未命中'}"

            print(f"\n[{i:02d}/{total_phase3:02d}] {status} [{case_id}] ({category}){detail}")
            print(f"  输入: {input_text[:80]}{'...' if len(input_text) > 80 else ''}")
            print(f"  DFA: {'hit' if detected else 'miss'} (expected: {'hit' if expected_dfa else 'miss'})")

            if case_passed:
                passed_phase3 += 1
    else:
        total_phase3 = 0
        passed_phase3 = 0
        print("\n  (adversary_regression.json 不存在，跳过对抗回归)")

    # ===== 汇总报告 =====
    print("\n" + "=" * 70)
    print("  汇总报告")
    print("=" * 70)

    p1_total = total_phase1
    p2_total = total_phase2 + len(regression_cases)
    p3_total = total_phase3
    grand_total = p1_total + p2_total + total_phase25 + p3_total
    grand_passed = passed_phase1 + passed_phase2 + passed_phase25 + passed_phase3

    print(f"  第1层 (DFA):      {passed_phase1:2d}/{p1_total:2d} 通过")
    print(f"  第2层 (验证器):    {passed_phase2:2d}/{p2_total:2d} 通过")
    print(f"  第2.5层 (脏话回归): {passed_phase25:2d}/{total_phase25:2d} 通过")
    if p3_total > 0:
        print(f"  第3层 (对抗回归):  {passed_phase3:2d}/{p3_total:2d} 通过")
    print(f"  合计:             {grand_passed:2d}/{grand_total:2d} 通过")

    all_pass = (
        passed_phase1 == p1_total
        and passed_phase2 == p2_total
        and passed_phase25 == total_phase25
        and (p3_total == 0 or passed_phase3 == p3_total)
    )

    print()
    if all_pass:
        print("  [OK] 全部测试通过（DFA + 验证器端到端 + 对抗回归）。")
    else:
        print(f"  [FAIL] 存在失败用例，未达到 100% 通过率。")

    print()
    print("  重要提示：以上测试仅覆盖 DFA 层和验证器层。")
    print("  LLM 端到端评测不包括在本脚本中。请手动运行：")
    print("    python3 evaluation/tonebarrier/adversarial/batch_run_llm.py --model deepseek")
    print("    python3 evaluation/tonebarrier/adversarial/e2e_validate.py evaluation/tonebarrier/adversarial/llm_real_outputs_deepseek.json")
    print()
    print("  更详细的对抗评测见：")
    print("    python3 evaluation/tonebarrier/benchmark/report.py  （生成含 E2E 数据的完整报告）")

    print("=" * 70)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(run_tests())
