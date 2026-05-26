#!/usr/bin/env python3
"""
批量调用 LLM API 运行 /mental-barrier 对抗评测。
支持多模型切换。

用法:
  python3 batch_run_llm.py --model minimax    # MiniMax M2.7
  python3 batch_run_llm.py --model deepseek   # DeepSeek V4
  python3 batch_run_llm.py                    # 默认 deepseek
"""
import json, os, sys, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 从 .env 加载 API key（如文件存在且 key 未设）
env_path = os.path.join(SCRIPT_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if k not in os.environ and v not in ("YOUR_API_KEY_HERE", ""):
                    os.environ[k] = v
SKILL_DIR = os.path.join(SCRIPT_DIR, "..")
CASES_PATH = os.path.join(SCRIPT_DIR, "adversary_cases.json")
SKILL_PATH = os.path.join(SKILL_DIR, "SKILL.md")

model = "deepseek"
for i, arg in enumerate(sys.argv):
    if arg == "--model" and i + 1 < len(sys.argv):
        model = sys.argv[i + 1]

configs = {
    "minimax": {
        "api_key": os.environ.get("MINIMAX_API_KEY", ""),
        "base_url": "https://api.minimaxi.com/anthropic",
        "model": "MiniMax-M2.7",
    },
    "deepseek": {
        "api_key": os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
        "base_url": "https://api.deepseek.com/anthropic",
        "model": "deepseek-v4-pro[1m]",
    },
    "liangrekui": {
        "api_key": os.environ.get("LIANGREKUI_API_KEY", ""),
        "base_url": "https://api.liangrekui.com/",
        "model": "claude-sonnet-4-6",
    },
    "gpt54": {
        "api_key": os.environ.get("LIANGREKUI_GPT_API_KEY", ""),
        "base_url": "https://api.liangrekui.com/",
        "model": "gpt-5.4",
    },
}

if model not in configs:
    print(f"未知模型: {model}。可选: {', '.join(configs.keys())}")
    sys.exit(1)

cfg = configs[model]
OUTPUT_PATH = os.path.join(SCRIPT_DIR, f"llm_real_outputs_{model}.json")

os.environ["ANTHROPIC_AUTH_TOKEN"] = cfg["api_key"]
os.environ["ANTHROPIC_BASE_URL"] = cfg["base_url"]

from anthropic import Anthropic

client = Anthropic(api_key=cfg["api_key"], base_url=cfg["base_url"])

with open(SKILL_PATH, encoding="utf-8") as f:
    skill_md = f.read()
system_prompt = skill_md.split("---", 2)[-1].strip()

with open(CASES_PATH, encoding="utf-8") as f:
    cases = json.load(f)["cases"]

existing = {}
if os.path.exists(OUTPUT_PATH):
    with open(OUTPUT_PATH, encoding="utf-8") as f:
        for r in json.load(f):
            existing[r["id"]] = r

results = list(existing.values())
pending = [c for c in cases if c["id"] not in existing]
total = len(pending)

print(f"模型: {cfg['model']}")
print(f"端点: {cfg['base_url']}")
print(f"输出: {OUTPUT_PATH}")
print(f"总数: {len(cases)} | 已有: {len(existing)} | 待处理: {total}")
print()

batch_size = 10
for batch_start in range(0, total, batch_size):
    batch = pending[batch_start : batch_start + batch_size]
    for i, case in enumerate(batch):
        idx = batch_start + i + 1
        cid = case["id"]
        text = case["input"]

        sys.stdout.write(f"[{idx:3d}/{total}] {cid} ... ")
        sys.stdout.flush()

        try:
            resp = client.messages.create(
                model=cfg["model"],
                max_tokens=512,
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": text}],
            )
            output = "".join(b.text for b in resp.content if hasattr(b, "text"))
            results.append({"id": cid, "skill_output": output})
            print("OK")
        except Exception as e:
            print(f"ERR: {e}")
            time.sleep(5)

        time.sleep(0.3)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  已保存 {len(results)} 条")

    if batch_start + batch_size < total:
        time.sleep(2)

print(f"\n完成。{len(results)} 条 → {OUTPUT_PATH}")
print(f"验证: python3 adversarial/e2e_validate.py {OUTPUT_PATH}")
