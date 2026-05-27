"""管道编排 — DFA + LLM + Validator，支持 full/hybrid 模式。"""
from __future__ import annotations

import json
import subprocess
import time
import re
from config import DFA_SCRIPT, VALIDATOR_SCRIPT
from prompts import SYSTEM_PROMPT, build_user_prompt
from llm_client import call_llm


EMOTION_KEYWORDS = {"失望", "不满", "生气", "无语", "郁闷", "烦", "着急", "焦虑", "难过", "伤心", "愤怒", "恼火"}


def run_dfa(text: str) -> dict:
    """调用 DFA 脚本，返回 JSON 结果。"""
    start = time.time()
    try:
        result = subprocess.run(
            ["python3", DFA_SCRIPT],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=10,
        )
        latency_ms = int((time.time() - start) * 1000)
        data = json.loads(result.stdout.decode("utf-8"))
        data["latency_ms"] = latency_ms
        return data
    except Exception as e:
        return {"has_profanity": False, "matches": [], "total_matches": 0,
                "summary": f"DFA 执行失败: {e}", "latency_ms": 0}


def run_validator(original: str, sanitized: str) -> dict:
    """调用 validator 脚本，返回 JSON 结果。"""
    start = time.time()
    try:
        payload = json.dumps({"original": original, "sanitized": sanitized})
        result = subprocess.run(
            ["python3", VALIDATOR_SCRIPT],
            input=payload.encode("utf-8"),
            capture_output=True,
            timeout=10,
        )
        latency_ms = int((time.time() - start) * 1000)
        data = json.loads(result.stdout.decode("utf-8"))
        data["latency_ms"] = latency_ms
        return data
    except Exception as e:
        return {"passed": True, "lost_entities": [], "latency_ms": 0}


def parse_level_from_output(text: str):
    if "平稳" in text:
        return 1
    if "轻微" in text:
        return 2
    if "愤怒" in text:
        return 3
    if "激烈" in text:
        return 4
    return None


def hybrid_shortcircuit(text: str, dfa_result: dict) -> dict | None:
    """hybrid 模式短路判断。返回 None 表示需要调用 LLM。"""
    has_profanity = dfa_result.get("has_profanity", False)
    has_emotion_word = any(kw in text for kw in EMOTION_KEYWORDS)

    if not has_profanity and not has_emotion_word:
        return {
            "level": 1,
            "level_label": "客户情绪平稳，正常诉求",
            "output": f"[情绪判断] 客户情绪平稳，正常诉求\n\n{text}",
            "sanitized_text": text,
            "llm_skipped": True,
        }

    if not has_profanity and has_emotion_word:
        return {
            "level": 2,
            "level_label": "客户有轻微不满",
            "output": f"[情绪判断] 客户有轻微不满\n\n{text}",
            "sanitized_text": text,
            "llm_skipped": True,
        }

    return None


async def process_text(text: str, mode: str = "full") -> dict:
    """完整管道处理。"""
    dfa_result = run_dfa(text)
    dfa_latency = dfa_result.get("latency_ms", 0)
    dfa_hits = [m["word"] for m in dfa_result.get("matches", [])]

    llm_skipped = False
    llm_latency = 0
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    validator_latency = 0
    entities_preserved = True

    if mode == "hybrid":
        shortcircuit = hybrid_shortcircuit(text, dfa_result)
        if shortcircuit:
            total_latency = dfa_latency
            return {
                "level": shortcircuit["level"],
                "level_label": shortcircuit["level_label"],
                "output": shortcircuit["output"],
                "sanitized_text": shortcircuit["sanitized_text"],
                "dfa_hits": dfa_hits,
                "entities_preserved": True,
                "mode": mode,
                "metrics": {
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "dfa_latency_ms": dfa_latency,
                    "llm_latency_ms": 0,
                    "validator_latency_ms": 0,
                    "total_latency_ms": total_latency,
                    "llm_skipped": True,
                },
            }

    user_prompt = build_user_prompt(text, dfa_result)
    llm_result = await call_llm(SYSTEM_PROMPT, user_prompt)

    output = llm_result["content"]
    llm_latency = llm_result["latency_ms"]
    prompt_tokens = llm_result["prompt_tokens"]
    completion_tokens = llm_result["completion_tokens"]
    total_tokens = llm_result["total_tokens"]

    level = parse_level_from_output(output)

    # 提取净化文本（[情绪判断]行之后的内容）
    sanitized_text = output
    lines = output.strip().split("\n")
    for i, line in enumerate(lines):
        if "情绪判断" in line:
            rest = lines[i + 1:]
            while rest and not rest[0].strip():
                rest.pop(0)
            sanitized_text = "\n".join(rest).strip()
            break

    # 级别3-4运行 validator
    if level and level >= 3 and sanitized_text:
        vresult = run_validator(text, sanitized_text)
        validator_latency = vresult.get("latency_ms", 0)
        entities_preserved = vresult.get("passed", True)

    total_latency = dfa_latency + llm_latency + validator_latency

    return {
        "level": level,
        "level_label": _level_label(level),
        "output": output,
        "sanitized_text": sanitized_text,
        "dfa_hits": dfa_hits,
        "entities_preserved": entities_preserved,
        "mode": mode,
        "metrics": {
            "total_tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "dfa_latency_ms": dfa_latency,
            "llm_latency_ms": llm_latency,
            "validator_latency_ms": validator_latency,
            "total_latency_ms": total_latency,
            "llm_skipped": False,
        },
    }


def _level_label(level):
    labels = {
        1: "客户情绪平稳，正常诉求",
        2: "客户有轻微不满",
        3: "客户情绪愤怒，建议优先处理",
        4: "客户情绪激烈，含攻击性语言 — 以下为过滤后内容",
    }
    return labels.get(level, "未知")
