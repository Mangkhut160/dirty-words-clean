# Mental Barrier 生产环境模拟服务 — 设计文档

> 日期：2026-05-27
> 目标：构建本地 HTTP API 服务，去掉 Claude Code 框架开销，验证 tonebarrier skill 的真实 token 消耗和延迟

---

## 1. 目标

验证核心假设：去掉 Claude Code 框架（系统提示 ~4000 tokens + 工具调用协议 ~2500 tokens）后，单次调用从 ~12,000 tokens 降至 ~4,000-6,000 tokens，延迟从 ~30s 降至 ~3-5s。

成功标准：
- 服务可通过 `curl` 调用，输入客户投诉文本，输出净化结果
- 每次请求返回精确的 token 拆解和延迟统计
- 支持 full 模式和 hybrid 模式切换
- 与 Claude Code 子代理结果做 A/B 对比

---

## 2. 架构

```
┌─────────────────────────────────────────────────┐
│  浏览器 UI (localhost:8000)                      │
│                                                 │
│  ┌──────────────┐  ┌─────────────────────────┐  │
│  │ 手动输入面板  │  │ 批量测试面板             │  │
│  │ 输入文本     │  │ 上传 JSON / 选择预设     │  │
│  │ 选择模式     │  │ 批量执行 + 进度条        │  │
│  │ 实时结果     │  │ 汇总统计                 │  │
│  └──────────────┘  └─────────────────────────┘  │
│                                                 │
│  ┌──────────────────────────────────────────┐   │
│  │ 调用历史面板（后台日志）                    │   │
│  │ 每条记录：输入/输出/级别/token/延迟/模式   │   │
│  │ 筛选、排序、导出                          │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  FastAPI Backend (同一进程)           │
│                                     │
│  POST /api/filter      单条处理      │
│  POST /api/batch       批量处理      │
│  GET  /api/history     调用历史      │
│  GET  /api/stats       汇总统计      │
│  GET  /               UI 页面        │
└─────────────────────────────────────┘
    │
    ▼
DeepSeek V4 API (api.deepseek.com)
```

---

## 3. 文件结构

```
tonebarrier-server/
├── server.py          # FastAPI 主服务 + 路由 + 静态文件挂载
├── pipeline.py        # 管道逻辑（DFA + LLM + Validator 编排）
├── llm_client.py      # DeepSeek API 封装（异步、token 统计）
├── config.py          # 配置（API key、模型、端口）
├── prompts.py         # System prompt（从 SKILL.md 精简而来）
├── history.py         # 调用历史存储（SQLite）
├── requirements.txt   # fastapi, uvicorn, openai, jinja2, aiosqlite
├── static/
│   ├── style.css      # UI 样式
│   └── app.js         # 前端交互逻辑
├── templates/
│   └── index.html     # 主页面（手动输入 + 批量 + 历史三栏）
└── README.md          # 使用说明
```

---

## 4. API 设计

### POST /api/filter — 单条处理

请求：
```json
{
  "text": "你们tmd这个破产品用了三天就坏了赶紧退款",
  "mode": "full"
}
```

响应：
```json
{
  "id": "req_20260527_001",
  "level": 4,
  "level_label": "客户情绪激烈，含攻击性语言 — 以下为过滤后内容",
  "output": "[情绪判断] ...\n\n客户反馈...",
  "sanitized_text": "客户反馈购买的产品使用三天后出现故障，要求退款处理。",
  "dfa_hits": ["tmd"],
  "entities_preserved": true,
  "mode": "full",
  "metrics": {
    "total_tokens": 4200,
    "prompt_tokens": 3100,
    "completion_tokens": 1100,
    "system_prompt_tokens": 2800,
    "dfa_latency_ms": 62,
    "llm_latency_ms": 2300,
    "validator_latency_ms": 89,
    "total_latency_ms": 2451,
    "llm_skipped": false
  }
}
```

### POST /api/batch — 批量处理

请求：
```json
{
  "items": [
    {"id": "case_001", "text": "你们tmd...", "expected_level": 4},
    {"id": "case_002", "text": "订单破损请处理", "expected_level": 1}
  ],
  "mode": "full"
}
```

响应：
```json
{
  "total": 2,
  "completed": 2,
  "results": [...],
  "summary": {
    "avg_tokens": 4100,
    "avg_latency_ms": 2400,
    "accuracy": 1.0,
    "total_cost_yuan": 0.004
  }
}
```

### GET /api/history — 调用历史

查询参数：`?page=1&limit=20&mode=full&level=4`

返回分页的历史记录列表，每条包含完整的输入/输出/metrics。

### GET /api/stats — 汇总统计

返回：
```json
{
  "total_calls": 150,
  "avg_tokens": 4200,
  "avg_latency_ms": 2500,
  "by_mode": {"full": {...}, "hybrid": {...}},
  "by_level": {"1": {...}, "2": {...}, "3": {...}, "4": {...}},
  "cost_total_yuan": 0.32
}
```

---

## 5. UI 设计

单页应用，三个 Tab 面板：

### Tab 1: 手动测试
- 文本输入框（支持多行）
- 模式选择（full / hybrid）
- "发送"按钮
- 结果展示区：情绪级别（彩色标签）、净化文本、DFA 命中词、token/延迟指标

### Tab 2: 批量测试
- 上传 JSON 文件 或 选择预设测试集（evals.json / adversary_cases.json）
- 批量执行按钮 + 实时进度条
- 结果表格：每行一个用例，显示预期级别 vs 实际级别、通过/失败、token、延迟
- 底部汇总：准确率、平均 token、平均延迟、总成本

### Tab 3: 调用历史
- 表格展示所有历史调用（时间、输入摘要、级别、模式、token、延迟）
- 点击展开查看完整输入/输出
- 筛选：按模式、按级别、按时间范围
- 导出 CSV

### 顶部状态栏
- 服务状态（绿灯/红灯）
- 累计调用次数
- 平均 token / 平均延迟
- 总成本

技术实现：纯 HTML + Vanilla JS + CSS（不引入 React/Vue 等框架），通过 FastAPI 的 Jinja2 模板渲染，静态资源直接挂载。保持零前端构建步骤。

## 6. System Prompt 精简策略

从 SKILL.md（241 行 / 10.2KB / ~2900 tokens）中提取核心指令，目标 < 1500 tokens：

保留：
- 身份定义（1 句）
- 情绪级别表（含 V4 的精确判定规则）
- 情绪剥离规则（4 条核心规则）
- 输出格式（两段式）
- 2-3 个精选 few-shot（覆盖级别 1/3/4）

去掉：
- DFA 执行指令（由代码处理）
- Validator 执行指令（由代码处理）
- homophone_guide 读取指令（内联到 prompt）
- 工具调用相关说明
- 反面教材（用正面示例替代）

---

## 7. Hybrid 模式短路逻辑

DFA 结果 + 简单规则判断，满足条件时跳过 LLM：

| 条件 | 动作 | token 消耗 |
|------|------|-----------|
| DFA 无命中 + 无情绪关键词 | 级别 1，原文透传 | 0 |
| DFA 无命中 + 有情绪词（失望/不满） | 级别 2，原文透传 | 0 |
| DFA 命中 + 无实体 + 文本短（<50字） | 模板化输出 | 0 |
| 其余所有情况 | 调用 LLM | ~4000 |

情绪关键词列表（硬编码）：失望、不满、生气、无语、郁闷、烦、着急...

---

## 8. 依赖

```
fastapi>=0.100.0
uvicorn>=0.23.0
openai>=1.0.0
jinja2>=3.0.0
aiosqlite>=0.19.0
```

不需要 anthropic SDK（用 DeepSeek）。利用 openai SDK 的 OpenAI 兼容模式调用 DeepSeek。

---

## 9. 配置

通过环境变量：
```bash
export DEEPSEEK_API_KEY="sk-..."
export MENTAL_BARRIER_PORT=8000
export MENTAL_BARRIER_MODEL="deepseek-chat"  # 或 deepseek-reasoner
```

---

## 10. 测试计划

启动后用之前的 8 个 V4 测试用例 + 5 个 evals.json 用例跑一遍，对比：
- Token 消耗：预期从 12,000 降至 4,000-5,000
- 延迟：预期从 30s 降至 2-5s
- 准确率：应与 V4 子代理测试一致（情绪级别正确）

批量测试：加载 adversary_cases.json 的 182 个用例，通过 UI 批量面板执行，生成完整的成本报告。
