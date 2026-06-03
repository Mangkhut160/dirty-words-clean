# Mental Barrier — Hugging Face Spaces 部署方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 tonebarrier-server 部署到 Hugging Face Spaces，提供可公开访问的中英双语 Demo，展示完整的 DFA→LLM→Validator 三层管道工作流。

**Architecture:** FastAPI 应用打包为 Docker 镜像，通过 HF Spaces Docker SDK 部署（端口 7860）。Skill 脚本（dfa_filter.py、validator.py）随 Docker 镜像一起打包，不依赖宿主机路径。SQLite 写入 `/tmp/history.db`（容器重启后数据清空，Demo 场景可接受）。GitHub Actions 在 push 时自动同步到 HF Spaces。

**Tech Stack:** Python 3.11-slim, FastAPI, uvicorn, aiosqlite, openai SDK, Docker, GitHub Actions, Hugging Face Spaces (Docker SDK)

---

## 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `tonebarrier-server/Dockerfile` | HF Spaces Docker 镜像 |
| 新建 | `tonebarrier-server/README.md` | HF Spaces frontmatter（sdk: docker） |
| 修改 | `tonebarrier-server/config.py` | 移除硬编码 API key，修正路径和端口 |
| 修改 | `tonebarrier-server/server.py` | 添加 GET /health 端点 |
| 修改 | `tonebarrier-server/templates/index.html` | 添加语言切换按钮 + 工作流可视化区块 |
| 修改 | `tonebarrier-server/static/app.js` | 添加 i18n 字典 + 工作流动画逻辑 |
| 修改 | `tonebarrier-server/static/style.css` | 工作流可视化样式 + 语言切换按钮样式 |
| 新建 | `.github/workflows/hf-deploy.yml` | GitHub Actions 自动同步到 HF Spaces |

---

## Task 1：修复 config.py — 移除硬编码密钥，修正路径和端口

**Files:**
- Modify: `tonebarrier-server/config.py`

- [ ] **Step 1: 替换 config.py 全部内容**

```python
import os

def get_env(key, default=""):
    return os.environ.get(key, default)

# LLM 配置 — 必须通过环境变量注入，无默认值
LLM_API_KEY = get_env("LLM_API_KEY")
LLM_BASE_URL = get_env("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = get_env("LLM_MODEL", "deepseek-v4-flash")

# HF Spaces 要求端口 7860
SERVER_PORT = int(get_env("MENTAL_BARRIER_PORT", "7860"))
SERVER_HOST = "0.0.0.0"

# HF Spaces 容器内 /tmp 可写，重启后清空（Demo 场景可接受）
DB_PATH = get_env("DB_PATH", "/tmp/history.db")

# Skill 脚本路径 — Docker 内打包到 /app/skill/
_BASE = os.path.dirname(__file__)
SKILL_DIR = os.path.join(_BASE, "skill")
DFA_SCRIPT = os.path.join(SKILL_DIR, "scripts", "dfa_filter.py")
VALIDATOR_SCRIPT = os.path.join(SKILL_DIR, "scripts", "validator.py")
HOMOPHONE_GUIDE = os.path.join(SKILL_DIR, "references", "homophone_guide.md")
```

- [ ] **Step 2: 验证本地仍可启动（需要先设置环境变量）**

```bash
cd /Users/cxw114/Desktop/idea/tonebarrier-server
LLM_API_KEY=test python3 -c "import config; print(config.LLM_API_KEY, config.SERVER_PORT, config.DB_PATH)"
```

期望输出：`test 7860 /tmp/history.db`

---

## Task 2：添加 /health 端点

**Files:**
- Modify: `tonebarrier-server/server.py:49`（在 `@app.get("/")` 之前插入）

- [ ] **Step 1: 在 server.py 的 `@app.get("/")` 之前插入 health 端点**

```python
@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 2: 本地验证**

```bash
cd /Users/cxw114/Desktop/idea/tonebarrier-server
LLM_API_KEY=test uvicorn server:app --port 7860 &
sleep 2
curl http://localhost:7860/health
kill %1
```

期望输出：`{"status":"ok"}`

---

## Task 3：复制 Skill 脚本到 server 目录

pipeline.py 通过 subprocess 调用 `dfa_filter.py` 和 `validator.py`。Docker 镜像内不存在 `../.claude/skills/tonebarrier/` 路径，需要将脚本复制到 `tonebarrier-server/skill/`。

**Files:**
- Create: `tonebarrier-server/skill/scripts/dfa_filter.py`（从 `.claude/skills/tonebarrier/scripts/dfa_filter.py` 复制）
- Create: `tonebarrier-server/skill/scripts/validator.py`（从 `.claude/skills/tonebarrier/scripts/validator.py` 复制）
- Create: `tonebarrier-server/skill/references/profanity_dict.txt`（从 `.claude/skills/tonebarrier/references/profanity_dict.txt` 复制）
- Create: `tonebarrier-server/skill/references/profanity_en.txt`（从 `.claude/skills/tonebarrier/references/profanity_en.txt` 复制）
- Create: `tonebarrier-server/skill/references/homophone_guide.md`（从 `.claude/skills/tonebarrier/references/homophone_guide.md` 复制）

- [ ] **Step 1: 创建目录并复制文件**

```bash
SKILL_SRC="/Users/cxw114/Desktop/idea/.claude/skills/tonebarrier"
SERVER_DIR="/Users/cxw114/Desktop/idea/tonebarrier-server"

mkdir -p "$SERVER_DIR/skill/scripts" "$SERVER_DIR/skill/references"
cp "$SKILL_SRC/scripts/dfa_filter.py" "$SERVER_DIR/skill/scripts/"
cp "$SKILL_SRC/scripts/validator.py" "$SERVER_DIR/skill/scripts/"
cp "$SKILL_SRC/references/profanity_dict.txt" "$SERVER_DIR/skill/references/"
cp "$SKILL_SRC/references/profanity_en.txt" "$SERVER_DIR/skill/references/"
cp "$SKILL_SRC/references/homophone_guide.md" "$SERVER_DIR/skill/references/"
```

- [ ] **Step 2: 验证文件存在**

```bash
ls /Users/cxw114/Desktop/idea/tonebarrier-server/skill/scripts/
ls /Users/cxw114/Desktop/idea/tonebarrier-server/skill/references/
```

期望：`dfa_filter.py  validator.py` 和 `homophone_guide.md  profanity_dict.txt  profanity_en.txt`

- [ ] **Step 3: 本地测试管道（需要 LLM_API_KEY 有效）**

```bash
cd /Users/cxw114/Desktop/idea/tonebarrier-server
python3 -c "
import asyncio, sys, os
sys.path.insert(0, '.')
os.environ['LLM_API_KEY'] = 'test'
from pipeline import run_dfa
r = run_dfa('你们tmd这个破产品')
print(r)
"
```

期望：DFA 命中 `tmd`，`has_profanity: True`

---

## Task 4：编写 Dockerfile

**Files:**
- Create: `tonebarrier-server/Dockerfile`

- [ ] **Step 1: 创建 Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# HF Spaces 要求端口 7860
EXPOSE 7860

# 非 root 用户（HF Spaces 安全要求）
RUN useradd -m appuser && chown -R appuser /app
USER appuser

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860"]
```

- [ ] **Step 2: 本地构建验证（不需要推送）**

```bash
cd /Users/cxw114/Desktop/idea/tonebarrier-server
docker build -t tonebarrier-test .
```

期望：构建成功，无报错

- [ ] **Step 3: 本地运行验证**

```bash
docker run --rm -e LLM_API_KEY=test -p 7860:7860 tonebarrier-test &
sleep 3
curl http://localhost:7860/health
docker stop $(docker ps -q --filter ancestor=tonebarrier-test)
```

期望：`{"status":"ok"}`

---

## Task 5：创建 HF Spaces README.md（frontmatter）

HF Spaces 通过 README.md 的 YAML frontmatter 识别 Space 配置。

**Files:**
- Create: `tonebarrier-server/README.md`

- [ ] **Step 1: 创建 README.md**

```markdown
---
title: Mental Barrier — 情绪过滤引擎
emoji: 🧠
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: false
license: mit
app_port: 7860
---

# Mental Barrier — 情绪过滤引擎 / Emotion Filtering Engine

将充满辱骂、讽刺、情绪宣泄的客服投诉文本转化为冷静客观的自然语言表达。

Transforms profanity-laden, sarcastic customer complaints into calm, objective natural language.

## 使用说明 / Usage

在"手动测试"标签页输入客户投诉文本，点击"发送"查看过滤结果。

Enter customer complaint text in the "Manual Test" tab and click "Send" to see the filtered result.

## 环境变量 / Environment Variables

在 HF Spaces Settings → Repository secrets 中设置：

- `LLM_API_KEY`: DeepSeek API Key（必填 / Required）
- `LLM_BASE_URL`: API 端点（可选，默认 `https://api.deepseek.com/v1`）
- `LLM_MODEL`: 模型名称（可选，默认 `deepseek-v4-flash`）
```

---

## Task 6：i18n — 语言切换按钮和双语字符串

**Files:**
- Modify: `tonebarrier-server/templates/index.html`
- Modify: `tonebarrier-server/static/app.js`
- Modify: `tonebarrier-server/static/style.css`

### 6a：修改 index.html — 添加语言切换按钮和工作流区块

- [ ] **Step 1: 在 header 中添加语言切换按钮**

在 `<header>` 的 `<div id="status-bar">` 之后添加：

```html
<button id="lang-toggle" onclick="toggleLang()" style="margin-left:16px;padding:4px 12px;font-size:12px;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.3);border-radius:4px;color:#fff;cursor:pointer;">EN</button>
```

- [ ] **Step 2: 给所有需要翻译的元素添加 data-i18n 属性**

将 `<nav class="tabs">` 替换为：

```html
<nav class="tabs">
    <button class="tab active" data-tab="manual" data-i18n="tab_manual">手动测试</button>
    <button class="tab" data-tab="batch" data-i18n="tab_batch">批量测试</button>
    <button class="tab" data-tab="history" data-i18n="tab_history">调用历史</button>
</nav>
```

- [ ] **Step 3: 在 `<main>` 最前面插入工作流可视化区块**

```html
<section id="workflow-viz" class="workflow-viz">
    <div class="wf-step" id="wf-dfa">
        <div class="wf-icon">⚡</div>
        <div class="wf-label" data-i18n="wf_dfa">DFA 精确匹配</div>
        <div class="wf-sub" data-i18n="wf_dfa_sub">~0ms · 1200词词典</div>
        <div class="wf-time" id="wf-dfa-time"></div>
    </div>
    <div class="wf-arrow">→</div>
    <div class="wf-step" id="wf-llm">
        <div class="wf-icon">🧠</div>
        <div class="wf-label" data-i18n="wf_llm">LLM 语义审核</div>
        <div class="wf-sub" data-i18n="wf_llm_sub">谐音·讽刺·Emoji</div>
        <div class="wf-time" id="wf-llm-time"></div>
    </div>
    <div class="wf-arrow">→</div>
    <div class="wf-step" id="wf-val">
        <div class="wf-icon">✅</div>
        <div class="wf-label" data-i18n="wf_val">Validator 验证</div>
        <div class="wf-sub" data-i18n="wf_val_sub">实体保留检查</div>
        <div class="wf-time" id="wf-val-time"></div>
    </div>
</section>
```

- [ ] **Step 4: 给 textarea placeholder 和按钮添加 data-i18n**

```html
<textarea id="input-text" data-i18n-placeholder="placeholder_input" placeholder="输入客户投诉文本..." rows="4"></textarea>
```

```html
<button id="btn-send" data-i18n="btn_send" onclick="sendManual()">发送</button>
```

### 6b：修改 app.js — 添加 i18n 字典和工作流动画

- [ ] **Step 5: 在 app.js 顶部添加 i18n 字典和切换函数**

在文件最顶部插入：

```javascript
// i18n
const I18N = {
    zh: {
        tab_manual: '手动测试', tab_batch: '批量测试', tab_history: '调用历史',
        btn_send: '发送', btn_batch_run: '执行批量测试', btn_export: '导出 CSV',
        placeholder_input: '输入客户投诉文本...',
        wf_dfa: 'DFA 精确匹配', wf_dfa_sub: '~0ms · 1200词词典',
        wf_llm: 'LLM 语义审核', wf_llm_sub: '谐音·讽刺·Emoji',
        wf_val: 'Validator 验证', wf_val_sub: '实体保留检查',
        stat_calls: ' 次调用', stat_avg: '平均 ', stat_tokens: ' tokens',
        stat_latency_unit: 'ms',
        level_1: '级别 1 — 情绪平稳', level_2: '级别 2 — 轻微不满',
        level_3: '级别 3 — 情绪愤怒', level_4: '级别 4 — 情绪激烈',
        processing: '处理中...', select_file: '请选择 JSON 测试文件',
        batch_done: '批量测试完成', accuracy: '准确率',
        avg_tokens: '平均 tokens', avg_latency: '平均延迟',
    },
    en: {
        tab_manual: 'Manual Test', tab_batch: 'Batch Test', tab_history: 'History',
        btn_send: 'Send', btn_batch_run: 'Run Batch Test', btn_export: 'Export CSV',
        placeholder_input: 'Enter customer complaint text...',
        wf_dfa: 'DFA Exact Match', wf_dfa_sub: '~0ms · 1200-word dict',
        wf_llm: 'LLM Semantic Review', wf_llm_sub: 'Homophones·Sarcasm·Emoji',
        wf_val: 'Validator Check', wf_val_sub: 'Entity retention',
        stat_calls: ' calls', stat_avg: 'Avg ', stat_tokens: ' tokens',
        stat_latency_unit: 'ms',
        level_1: 'Level 1 — Calm', level_2: 'Level 2 — Mild',
        level_3: 'Level 3 — Angry', level_4: 'Level 4 — Aggressive',
        processing: 'Processing...', select_file: 'Please select a JSON test file',
        batch_done: 'Batch complete', accuracy: 'Accuracy',
        avg_tokens: 'Avg tokens', avg_latency: 'Avg latency',
    }
};

let currentLang = 'zh';

function t(key) { return I18N[currentLang][key] || key; }

function toggleLang() {
    currentLang = currentLang === 'zh' ? 'en' : 'zh';
    document.getElementById('lang-toggle').textContent = currentLang === 'zh' ? 'EN' : '中';
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.dataset.i18n;
        if (I18N[currentLang][key]) el.textContent = I18N[currentLang][key];
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.dataset.i18nPlaceholder;
        if (I18N[currentLang][key]) el.placeholder = I18N[currentLang][key];
    });
}
```

- [ ] **Step 6: 在 app.js 中添加工作流动画函数**

在 `showResult` 函数之后插入：

```javascript
function animateWorkflow(metrics) {
    const steps = ['dfa', 'llm', 'val'];
    const timeKeys = ['dfa_latency_ms', 'llm_latency_ms', 'validator_latency_ms'];
    steps.forEach((s, i) => {
        const el = document.getElementById('wf-' + s);
        const timeEl = document.getElementById('wf-' + s + '-time');
        el.classList.remove('active', 'done');
        timeEl.textContent = '';
    });

    let delay = 0;
    steps.forEach((s, i) => {
        const ms = metrics[timeKeys[i]] || 0;
        setTimeout(() => {
            document.getElementById('wf-' + s).classList.add('active');
        }, delay);
        delay += Math.max(ms, 200);
        setTimeout(() => {
            const el = document.getElementById('wf-' + s);
            el.classList.remove('active');
            el.classList.add('done');
            document.getElementById('wf-' + s + '-time').textContent = ms + 'ms';
        }, delay);
    });
}
```

- [ ] **Step 7: 在 showResult 函数末尾调用 animateWorkflow**

在 `showResult` 函数的最后一行（`document.getElementById('result-details')...` 之后）添加：

```javascript
    animateWorkflow(data.metrics);
```

### 6c：修改 style.css — 工作流可视化样式

- [ ] **Step 8: 在 style.css 末尾追加工作流样式**

```css
/* 工作流可视化 */
.workflow-viz {
    display: flex; align-items: center; justify-content: center;
    gap: 8px; padding: 16px 24px; background: #fff;
    border-bottom: 1px solid #e0e0e0; flex-wrap: wrap;
}
.wf-step {
    display: flex; flex-direction: column; align-items: center;
    padding: 10px 20px; border-radius: 8px; border: 2px solid #e0e0e0;
    min-width: 120px; transition: all 0.3s; background: #fafafa;
}
.wf-step.active { border-color: #1a1a2e; background: #e8eaf6; transform: scale(1.05); }
.wf-step.done { border-color: #4caf50; background: #e8f5e9; }
.wf-icon { font-size: 20px; margin-bottom: 4px; }
.wf-label { font-size: 13px; font-weight: 600; color: #333; }
.wf-sub { font-size: 11px; color: #888; margin-top: 2px; }
.wf-time { font-size: 11px; color: #4caf50; font-weight: 600; margin-top: 4px; min-height: 16px; }
.wf-arrow { font-size: 20px; color: #bbb; }
```

---

## Task 7：创建 GitHub Actions 自动同步工作流

**Files:**
- Create: `.github/workflows/hf-deploy.yml`

- [ ] **Step 1: 创建 GitHub Actions 工作流文件**

```yaml
name: 同步到 Hugging Face Spaces

on:
  push:
    branches: [main]
    paths:
      - 'tonebarrier-server/**'

jobs:
  sync-to-hf:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          lfs: true

      - name: 推送到 HF Spaces
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
        run: |
          git config --global user.email "github-actions@github.com"
          git config --global user.name "GitHub Actions"

          # 克隆 HF Spaces 仓库
          git clone https://user:${HF_TOKEN}@huggingface.co/spaces/YOUR_HF_USERNAME/tonebarrier hf-space

          # 同步 tonebarrier-server/ 内容到 HF Space 根目录
          rsync -av --delete \
            --exclude='.git' \
            --exclude='history.db' \
            --exclude='*.log' \
            --exclude='batch_results_*.json' \
            --exclude='batch_test_*.json' \
            tonebarrier-server/ hf-space/

          cd hf-space
          git add -A
          git diff --staged --quiet || git commit -m "sync: $(date '+%Y-%m-%d %H:%M') from GitHub"
          git push
```

> **注意**：将 `YOUR_HF_USERNAME` 替换为实际的 HF 用户名。需要在 GitHub 仓库 Settings → Secrets → Actions 中添加 `HF_TOKEN`（HF 的 write token）。

- [ ] **Step 2: 创建目录**

```bash
mkdir -p /Users/cxw114/Desktop/idea/.github/workflows
```

---

## Task 8：HF Spaces 手动初始化步骤（一次性操作）

这些步骤需要手动在浏览器中完成，无法自动化。

- [ ] **Step 1: 在 HF 创建 Space**
  1. 访问 https://huggingface.co/new-space
  2. Space name: `tonebarrier`
  3. SDK: **Docker**
  4. Visibility: Public
  5. 点击 Create Space

- [ ] **Step 2: 设置 Secret**
  1. 进入 Space → Settings → Repository secrets
  2. 添加 `LLM_API_KEY` = DeepSeek API Key

- [ ] **Step 3: 首次推送**

```bash
cd /Users/cxw114/Desktop/idea/tonebarrier-server
git init hf-deploy-tmp
cd hf-deploy-tmp
git remote add origin https://huggingface.co/spaces/YOUR_HF_USERNAME/tonebarrier
# 将 tonebarrier-server/ 内容复制进来
rsync -av --exclude='.git' --exclude='history.db' --exclude='*.log' \
    /Users/cxw114/Desktop/idea/tonebarrier-server/ .
git add -A
git commit -m "init: tonebarrier demo"
git push origin main
cd .. && rm -rf hf-deploy-tmp
```

- [ ] **Step 4: 在 GitHub 仓库添加 HF_TOKEN Secret**
  1. GitHub 仓库 → Settings → Secrets and variables → Actions
  2. 添加 `HF_TOKEN` = HF write token（从 https://huggingface.co/settings/tokens 获取）

---

## Task 9：UptimeRobot 保活配置（可选）

HF Spaces 免费版在无流量时会休眠（约 30 分钟）。UptimeRobot 免费版可每 5 分钟 ping 一次 /health 端点保持唤醒。

- [ ] **Step 1: 注册 UptimeRobot**
  1. 访问 https://uptimerobot.com 注册免费账号

- [ ] **Step 2: 添加监控**
  1. Add New Monitor
  2. Monitor Type: HTTP(s)
  3. Friendly Name: `tonebarrier-hf`
  4. URL: `https://YOUR_HF_USERNAME-tonebarrier.hf.space/health`
  5. Monitoring Interval: 5 minutes
  6. 保存

---

## 验收标准

部署完成后，以下检查项应全部通过：

- [ ] `https://YOUR_HF_USERNAME-tonebarrier.hf.space/health` 返回 `{"status":"ok"}`
- [ ] 首页正常加载，显示工作流可视化（三个步骤卡片）
- [ ] 点击 "EN" 按钮，所有 UI 文字切换为英文
- [ ] 输入 `你们tmd这个破产品用了三天就坏了` 点击发送，返回级别 4 结果
- [ ] 工作流卡片在处理时依次高亮（DFA → LLM → Validator）
- [ ] 输入英文投诉文本，正常处理
- [ ] 批量测试：上传 `ablation_test_set.json`，正常运行
- [ ] 调用历史页面正常显示记录
- [ ] push 到 GitHub main 分支后，GitHub Actions 自动触发同步

