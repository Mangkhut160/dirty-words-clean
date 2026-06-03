// ========== i18n 国际化 ==========
// 默认英文；localStorage 存储用户上次选择（tonebarrier.lang）
const I18N = {
    en: {
        'title': 'ToneBarrier — Production Simulation',
        'h1': 'ToneBarrier',
        'stat-calls': '0 calls',
        'stat-tokens': 'avg 0 tokens',
        'stat-latency': 'avg 0ms',
        'tab-manual': 'Manual Test',
        'tab-batch': 'Batch Test',
        'tab-history': 'History',
        'placeholder-input': 'Enter a customer complaint text...',
        'mode-full': 'Full mode (complete pipeline)',
        'mode-hybrid': 'Hybrid mode (DFA short-circuit)',
        'mode-full-short': 'Full mode',
        'mode-hybrid-short': 'Hybrid mode',
        'btn-send': 'Send',
        'btn-run-batch': 'Run Batch',
        'btn-export-csv': 'Export CSV',
        'btn-sending': 'Sending...',
        'btn-processing': 'Processing...',
        'filter-all-modes': 'All modes',
        'filter-all-levels': 'All levels',
        'level-1': 'Level 1',
        'level-2': 'Level 2',
        'level-3': 'Level 3',
        'level-4': 'Level 4',
        'th-id': 'ID',
        'th-input': 'Input',
        'th-expected': 'Expected',
        'th-actual': 'Actual',
        'th-result': 'Result',
        'th-tokens': 'Tokens',
        'th-latency': 'Latency',
        'th-time': 'Time',
        'th-level': 'Level',
        'th-mode': 'Mode',
        'th-llm-skip': 'LLM Skip',
        'th-output': 'Output',
        'level-prefix': 'Level',
        'dfa-hits': 'DFA hits: ',
        'llm-skipped': '⚡ LLM skipped (hybrid short-circuit)',
        'entity-warn': '⚠️ Entity may be lost',
        'batch-file-hint': 'Upload .json test file:',
        'btn-choose-file': 'Choose File',
        'no-file-selected': 'No file selected',
        'batch-select-file': 'Please select a JSON test file',
        'batch-parse-fail': 'JSON parse failed: ',
        'batch-done': 'Batch test complete',
        'batch-items': 'items',
        'batch-accuracy': 'Accuracy',
        'batch-na': 'N/A',
        'batch-avg-tokens': 'avg tokens',
        'batch-avg-latency': 'avg latency',
        'request-fail': 'Request failed: ',
        'prev-page': 'Prev',
        'next-page': 'Next',
        'page-info': ' Page {cur}/{total} ({sum} total) ',
        'llm-yes': '⚡yes',
        'llm-no': 'no',
        'time-locale': 'en-US',
    },
    zh: {
        'title': '精神内耗终结者 — 生产环境模拟',
        'h1': '精神内耗终结者',
        'stat-calls': '0 次调用',
        'stat-tokens': '平均 0 tokens',
        'stat-latency': '平均 0ms',
        'tab-manual': '手动测试',
        'tab-batch': '批量测试',
        'tab-history': '调用历史',
        'placeholder-input': '输入客户投诉文本...',
        'mode-full': 'Full 模式（完整管道）',
        'mode-hybrid': 'Hybrid 模式（DFA 短路）',
        'mode-full-short': 'Full 模式',
        'mode-hybrid-short': 'Hybrid 模式',
        'btn-send': '发送',
        'btn-run-batch': '执行批量测试',
        'btn-export-csv': '导出 CSV',
        'btn-sending': '发送中...',
        'btn-processing': '处理中...',
        'filter-all-modes': '全部模式',
        'filter-all-levels': '全部级别',
        'level-1': '级别 1',
        'level-2': '级别 2',
        'level-3': '级别 3',
        'level-4': '级别 4',
        'th-id': 'ID',
        'th-input': '输入',
        'th-expected': '预期',
        'th-actual': '实际',
        'th-result': '结果',
        'th-tokens': 'Tokens',
        'th-latency': '延迟',
        'th-time': '时间',
        'th-level': '级别',
        'th-mode': '模式',
        'th-llm-skip': 'LLM跳过',
        'th-output': '输出',
        'level-prefix': '级别',
        'dfa-hits': 'DFA 命中: ',
        'llm-skipped': '⚡ LLM 已跳过（hybrid 短路）',
        'entity-warn': '⚠️ 实体可能丢失',
        'batch-file-hint': '上传 .json 测试文件：',
        'btn-choose-file': '选择文件',
        'no-file-selected': '未选择任何文件',
        'batch-select-file': '请选择 JSON 测试文件',
        'batch-parse-fail': 'JSON 解析失败: ',
        'batch-done': '批量测试完成',
        'batch-items': '条',
        'batch-accuracy': '准确率',
        'batch-na': 'N/A',
        'batch-avg-tokens': '平均 tokens',
        'batch-avg-latency': '平均延迟',
        'request-fail': '请求失败: ',
        'prev-page': '上一页',
        'next-page': '下一页',
        'page-info': ' 第 {cur}/{total} 页 (共 {sum} 条) ',
        'llm-yes': '⚡是',
        'llm-no': '否',
        'time-locale': 'zh-CN',
    },
};

const LANG_KEY = 'tonebarrier.lang';
let currentLang = localStorage.getItem(LANG_KEY) || 'en';

function t(key) {
    return I18N[currentLang][key] || I18N.en[key] || key;
}

function applyI18n() {
    // 文本
    document.querySelectorAll('[data-i18n]').forEach(el => {
        el.textContent = t(el.dataset.i18n);
    });
    // placeholder
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        el.placeholder = t(el.dataset.i18nPlaceholder);
    });
    // html lang
    document.documentElement.lang = currentLang === 'zh' ? 'zh-CN' : 'en';
    // 切换按钮高亮
    document.getElementById('lang-en').classList.toggle('active', currentLang === 'en');
    document.getElementById('lang-en').setAttribute('aria-pressed', currentLang === 'en');
    document.getElementById('lang-zh').classList.toggle('active', currentLang === 'zh');
    document.getElementById('lang-zh').setAttribute('aria-pressed', currentLang === 'zh');
}

function setLang(lang) {
    if (lang !== 'en' && lang !== 'zh') return;
    currentLang = lang;
    localStorage.setItem(LANG_KEY, lang);
    applyI18n();
    // 重渲染依赖语言的 UI
    loadStats();
    if (document.querySelector('.tab[data-tab="history"]').classList.contains('active')) {
        loadHistory();
    }
}

// 切换按钮事件
document.getElementById('lang-en').addEventListener('click', () => setLang('en'));
document.getElementById('lang-zh').addEventListener('click', () => setLang('zh'));

// 启动时立刻应用（默认 en）
applyI18n();

// 文件选择后显示文件名
document.getElementById('batch-file').addEventListener('change', function() {
    const nameEl = document.getElementById('batch-file-name');
    if (this.files.length) {
        nameEl.textContent = this.files[0].name;
        nameEl.style.color = '#333';
    } else {
        nameEl.textContent = t('no-file-selected');
        nameEl.style.color = '#888';
    }
});

// ========== 工具函数 ==========
function esc(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

// ========== Tab 切换 ==========
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
        if (tab.dataset.tab === 'history') loadHistory();
    });
});

// ========== 统计 ==========
loadStats();

async function loadStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        // calls/tokens/latency 是动态数字,只替换数字部分
        const calls = document.getElementById('stat-calls');
        const tokens = document.getElementById('stat-tokens');
        const latency = document.getElementById('stat-latency');
        if (currentLang === 'zh') {
            calls.textContent = data.total_calls + ' 次调用';
            tokens.textContent = '平均 ' + data.avg_tokens + ' tokens';
            latency.textContent = '平均 ' + data.avg_latency_ms + 'ms';
        } else {
            calls.textContent = data.total_calls + ' calls';
            tokens.textContent = 'avg ' + data.avg_tokens + ' tokens';
            latency.textContent = 'avg ' + data.avg_latency_ms + 'ms';
        }
        document.getElementById('stat-cost').textContent = '¥' + data.cost_total_yuan;
    } catch (e) {}
}

// ========== 手动测试 ==========
async function sendManual() {
    const text = document.getElementById('input-text').value.trim();
    if (!text) return;
    const mode = document.getElementById('mode-select').value;
    const btn = document.getElementById('btn-send');
    btn.disabled = true;
    btn.textContent = t('btn-sending');

    try {
        const res = await fetch('/api/filter', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text, mode, lang: currentLang})
        });
        const data = await res.json();
        showResult(data);
        loadStats();
    } catch (e) {
        alert(t('request-fail') + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = t('btn-send');
    }
}

function showResult(data) {
    const panel = document.getElementById('result-panel');
    panel.classList.remove('hidden');

    const badge = document.getElementById('result-level');
    badge.textContent = t('level-prefix') + ' ' + data.level;
    badge.className = 'level-badge level-' + data.level;

    const m = data.metrics;
    document.getElementById('result-metrics').textContent =
        `${m.total_tokens} tokens | ${m.total_latency_ms}ms | DFA ${m.dfa_latency_ms}ms + LLM ${m.llm_latency_ms}ms + Val ${m.validator_latency_ms}ms`;

    document.getElementById('result-output').textContent = data.output;

    const details = [];
    if (data.dfa_hits.length) details.push(t('dfa-hits') + data.dfa_hits.join(', '));
    if (m.llm_skipped) details.push(t('llm-skipped'));
    if (!data.entities_preserved) details.push(t('entity-warn'));
    document.getElementById('result-details').textContent = details.join(' | ');
}

// ========== 批量测试 ==========
async function runBatch() {
    const fileInput = document.getElementById('batch-file');
    const mode = document.getElementById('batch-mode').value;

    if (!fileInput.files.length) {
        alert(t('batch-select-file'));
        return;
    }

    const text = await fileInput.files[0].text();
    let items;
    try {
        const parsed = JSON.parse(text);
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
        alert(t('batch-parse-fail') + e.message);
        return;
    }

    const btn = document.getElementById('btn-batch');
    btn.disabled = true;
    btn.textContent = t('btn-processing');
    document.getElementById('batch-progress').classList.remove('hidden');

    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const tbody = document.getElementById('batch-tbody');
    tbody.innerHTML = '';
    document.getElementById('batch-table').classList.remove('hidden');

    const results = [];
    for (let i = 0; i < items.length; i++) {
        progressFill.style.width = ((i + 1) / items.length * 100) + '%';
        progressText.textContent = `${i + 1}/${items.length}`;

        try {
            const res = await fetch('/api/filter', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text: items[i].text, mode, lang: currentLang})
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

    const withExpected = results.filter(r => r.expected != null);
    const correct = withExpected.filter(r => r.correct).length;
    const avgTokens = Math.round(results.reduce((s, r) => s + (r.metrics?.total_tokens || 0), 0) / results.length);
    const avgLatency = Math.round(results.reduce((s, r) => s + (r.metrics?.total_latency_ms || 0), 0) / results.length);
    const accStr = withExpected.length ? (correct/withExpected.length*100).toFixed(1) + '%' : t('batch-na');

    const summary = document.getElementById('batch-summary');
    summary.classList.remove('hidden');
    summary.innerHTML = `
        <strong>${t('batch-done')}</strong> — ${results.length} ${t('batch-items')} |
        ${t('batch-accuracy')}: ${accStr} (${correct}/${withExpected.length}) |
        ${t('batch-avg-tokens')}: ${avgTokens} |
        ${t('batch-avg-latency')}: ${avgLatency}ms
    `;

    btn.disabled = false;
    btn.textContent = t('btn-run-batch');
    loadStats();
}

// ========== 历史 ==========
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
    const locale = t('time-locale');
    for (const r of data.records) {
        const time = new Date(r.timestamp * 1000).toLocaleString(locale);
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${time}</td>
            <td title="${esc(r.input_text)}">${esc(r.input_text.slice(0, 40))}</td>
            <td><span class="level-badge level-${r.level}">L${r.level}</span></td>
            <td>${r.mode}</td>
            <td>${r.total_tokens}</td>
            <td>${r.total_latency_ms}ms</td>
            <td>${r.llm_skipped ? t('llm-yes') : t('llm-no')}</td>
        `;
        row.style.cursor = 'pointer';
        row.addEventListener('click', () => {
            alert(`${t('th-input')}: ${r.input_text}\n\n${t('th-output')}: ${r.output}\n\n${t('dfa-hits')}${r.dfa_hits.join(', ')}`);
        });
        tbody.appendChild(row);
    }

    const totalPages = Math.ceil(data.total / data.limit);
    const pagination = document.getElementById('history-pagination');
    pagination.innerHTML = '';
    if (historyPage > 1) {
        const prev = document.createElement('button');
        prev.textContent = t('prev-page');
        prev.onclick = () => loadHistory(historyPage - 1);
        pagination.appendChild(prev);
    }
    const info = document.createElement('span');
    info.textContent = t('page-info').replace('{cur}', historyPage).replace('{total}', totalPages).replace('{sum}', data.total);
    info.style.lineHeight = '32px';
    pagination.appendChild(info);
    if (historyPage < totalPages) {
        const next = document.createElement('button');
        next.textContent = t('next-page');
        next.onclick = () => loadHistory(historyPage + 1);
        pagination.appendChild(next);
    }
}

function exportCSV() {
    window.open('/api/history?page=1&limit=10000', '_blank');
}
