// HTML 转义，防止 XSS
function esc(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

// Tab 切换
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
        if (tab.dataset.tab === 'history') loadHistory();
    });
});

// 启动时加载统计
loadStats();

async function loadStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        document.getElementById('stat-calls').textContent = data.total_calls + ' 次调用';
        document.getElementById('stat-tokens').textContent = '平均 ' + data.avg_tokens + ' tokens';
        document.getElementById('stat-latency').textContent = '平均 ' + data.avg_latency_ms + 'ms';
        document.getElementById('stat-cost').textContent = '¥' + data.cost_total_yuan;
    } catch (e) {}
}

// 手动测试
async function sendManual() {
    const text = document.getElementById('input-text').value.trim();
    if (!text) return;
    const mode = document.getElementById('mode-select').value;
    const btn = document.getElementById('btn-send');
    btn.disabled = true;
    btn.textContent = '处理中...';

    try {
        const res = await fetch('/api/filter', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text, mode})
        });
        const data = await res.json();
        showResult(data);
        loadStats();
    } catch (e) {
        alert('请求失败: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '发送';
    }
}

function showResult(data) {
    const panel = document.getElementById('result-panel');
    panel.classList.remove('hidden');

    const badge = document.getElementById('result-level');
    badge.textContent = '级别 ' + data.level;
    badge.className = 'level-badge level-' + data.level;

    const m = data.metrics;
    document.getElementById('result-metrics').textContent =
        `${m.total_tokens} tokens | ${m.total_latency_ms}ms | DFA ${m.dfa_latency_ms}ms + LLM ${m.llm_latency_ms}ms + Val ${m.validator_latency_ms}ms`;

    document.getElementById('result-output').textContent = data.output;

    const details = [];
    if (data.dfa_hits.length) details.push('DFA 命中: ' + data.dfa_hits.join(', '));
    if (m.llm_skipped) details.push('⚡ LLM 已跳过（hybrid 短路）');
    if (!data.entities_preserved) details.push('⚠️ 实体可能丢失');
    document.getElementById('result-details').textContent = details.join(' | ');
}

// 批量测试
async function runBatch() {
    const fileInput = document.getElementById('batch-file');
    const mode = document.getElementById('batch-mode').value;

    if (!fileInput.files.length) {
        alert('请选择 JSON 测试文件');
        return;
    }

    const text = await fileInput.files[0].text();
    let items;
    try {
        const parsed = JSON.parse(text);
        // 支持多种格式
        if (Array.isArray(parsed)) {
            items = parsed.map((item, i) => ({
                id: item.id || `case_${i}`,
                text: item.input || item.text || '',
                expected_level: item.expected_level || null
            }));
        } else if (parsed.cases) {
            items = parsed.cases.map(c => ({
                id: c.id,
                text: c.input,
                expected_level: c.expected_level
            }));
        } else if (parsed.evals) {
            items = parsed.evals.map(e => ({
                id: `eval_${e.id}`,
                text: e.prompt,
                expected_level: null
            }));
        }
    } catch (e) {
        alert('JSON 解析失败: ' + e.message);
        return;
    }

    const btn = document.getElementById('btn-batch');
    btn.disabled = true;
    document.getElementById('batch-progress').classList.remove('hidden');

    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const tbody = document.getElementById('batch-tbody');
    tbody.innerHTML = '';
    document.getElementById('batch-table').classList.remove('hidden');

    // 逐条发送以显示进度
    const results = [];
    for (let i = 0; i < items.length; i++) {
        progressFill.style.width = ((i + 1) / items.length * 100) + '%';
        progressText.textContent = `${i + 1}/${items.length}`;

        try {
            const res = await fetch('/api/filter', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text: items[i].text, mode})
            });
            const data = await res.json();
            const correct = items[i].expected_level != null ? data.level === items[i].expected_level : null;
            results.push({...data, id: items[i].id, expected: items[i].expected_level, correct});

            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${esc(items[i].id)}</td>
                <td title="${esc(items[i].text)}">${esc(items[i].text.slice(0, 30))}...</td>
                <td>${items[i].expected_level || '-'}</td>
                <td>${data.level}</td>
                <td class="${correct === true ? 'pass' : correct === false ? 'fail' : ''}">${correct === true ? '✓' : correct === false ? '✗' : '-'}</td>
                <td>${data.metrics.total_tokens}</td>
                <td>${data.metrics.total_latency_ms}ms</td>
            `;
            tbody.appendChild(row);
        } catch (e) {
            results.push({id: items[i].id, error: e.message});
        }
    }

    // 汇总
    const withExpected = results.filter(r => r.expected != null);
    const correct = withExpected.filter(r => r.correct).length;
    const avgTokens = Math.round(results.reduce((s, r) => s + (r.metrics?.total_tokens || 0), 0) / results.length);
    const avgLatency = Math.round(results.reduce((s, r) => s + (r.metrics?.total_latency_ms || 0), 0) / results.length);

    const summary = document.getElementById('batch-summary');
    summary.classList.remove('hidden');
    summary.innerHTML = `
        <strong>批量测试完成</strong> — ${results.length} 条 |
        准确率: ${withExpected.length ? (correct/withExpected.length*100).toFixed(1) + '%' : 'N/A'} (${correct}/${withExpected.length}) |
        平均 tokens: ${avgTokens} |
        平均延迟: ${avgLatency}ms
    `;

    btn.disabled = false;
    loadStats();
}

// 调用历史
let historyPage = 1;

async function loadHistory(page) {
    if (page) historyPage = page;
    const mode = document.getElementById('history-mode').value;
    const level = document.getElementById('history-level').value;

    let url = `/api/history?page=${historyPage}&limit=20`;
    if (mode) url += `&mode=${mode}`;
    if (level) url += `&level=${level}`;

    const res = await fetch(url);
    const data = await res.json();

    const tbody = document.getElementById('history-tbody');
    tbody.innerHTML = '';
    for (const r of data.records) {
        const time = new Date(r.timestamp * 1000).toLocaleString('zh-CN');
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${time}</td>
            <td title="${esc(r.input_text)}">${esc(r.input_text.slice(0, 40))}</td>
            <td><span class="level-badge level-${r.level}">L${r.level}</span></td>
            <td>${r.mode}</td>
            <td>${r.total_tokens}</td>
            <td>${r.total_latency_ms}ms</td>
            <td>${r.llm_skipped ? '⚡是' : '否'}</td>
        `;
        row.style.cursor = 'pointer';
        row.addEventListener('click', () => {
            alert(`输入: ${r.input_text}\n\n输出: ${r.output}\n\nDFA命中: ${r.dfa_hits.join(', ')}`);
        });
        tbody.appendChild(row);
    }

    // 分页
    const totalPages = Math.ceil(data.total / data.limit);
    const pagination = document.getElementById('history-pagination');
    pagination.innerHTML = '';
    if (historyPage > 1) {
        const prev = document.createElement('button');
        prev.textContent = '上一页';
        prev.onclick = () => loadHistory(historyPage - 1);
        pagination.appendChild(prev);
    }
    const info = document.createElement('span');
    info.textContent = ` 第 ${historyPage}/${totalPages} 页 (共 ${data.total} 条) `;
    info.style.lineHeight = '32px';
    pagination.appendChild(info);
    if (historyPage < totalPages) {
        const next = document.createElement('button');
        next.textContent = '下一页';
        next.onclick = () => loadHistory(historyPage + 1);
        pagination.appendChild(next);
    }
}

function exportCSV() {
    window.open('/api/history?page=1&limit=10000', '_blank');
}
