/**
 * Stock Analysis Web App - WebLLM Frontend
 * Handles model loading, data fetching, AI analysis, and UI updates.
 */

'use strict';

// ============================================================
// WebLLM Configuration
// ============================================================
const WEBLLM_CONFIG = {
    model: 'Qwen2-1.5B-Instruct-q4f16_1-MLC',
};

// ============================================================
// State
// ============================================================
const state = {
    selectedStock: null,
    selectedExchange: 'NSE',
    selectedAnalysisType: 'full',
    isAnalyzing: false,
    logs: [],
    modelLoaded: false,
    modelLoading: false,
    engine: null,
    stockData: null,
};

// ============================================================
// DOM References
// ============================================================
const $ = (id) => document.getElementById(id);

const dom = {
    stockSearch: $('stockSearch'),
    searchResults: $('searchResults'),
    searchSpinner: $('searchSpinner'),
    selectedStock: $('selectedStock'),
    popularStocks: $('popularStocks'),
    btnAnalyze: $('btnAnalyze'),
    emptyState: $('emptyState'),
    progressSection: $('progressSection'),
    resultsSection: $('resultsSection'),
    errorSection: $('errorSection'),
    progressFill: $('progressFill'),
    progressPhase: $('progressPhase'),
    progressPercent: $('progressPercent'),
    logsViewport: $('logsViewport'),
    logCount: $('logCount'),
    recBanner: $('recBanner'),
    recIcon: $('recIcon'),
    recAction: $('recAction'),
    recScore: $('recScore'),
    recConfidence: $('recConfidence'),
    summaryContent: $('summaryContent'),
    metricsGrid: $('metricsGrid'),
    reportContent: $('reportContent'),
    errorMessage: $('errorMessage'),
    btnCopyReport: $('btnCopyReport'),
    btnDownloadReport: $('btnDownloadReport'),
    btnClearLogs: $('btnClearLogs'),
    footerTime: $('footerTime'),
    serverStatus: $('serverStatus'),
    serverStatusText: $('serverStatusText'),
    modelStatusBar: $('modelStatusBar'),
    modelStatusDetail: $('modelStatusDetail'),
    modelProgressFill: $('modelProgressFill'),
    modelProgressText: $('modelProgressText'),
    modelProgressContainer: $('modelProgressContainer'),
};

// ============================================================
// Utility Functions
// ============================================================
function formatTime(isoStr) {
    const d = new Date(isoStr);
    return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function sanitize(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function getAgentClass(agent) {
    if (!agent || agent === 'system') return 'system';
    return agent.replace(/\s+/g, '_');
}

function getLevelClass(level) {
    return level || 'info';
}

function formatCurrency(val) {
    if (val === null || val === undefined) return 'N/A';
    const num = typeof val === 'string' ? parseFloat(val) : val;
    if (isNaN(num)) return val;
    if (num >= 10000000) return '\u20B9' + (num / 10000000).toFixed(2) + 'Cr';
    if (num >= 100000) return '\u20B9' + (num / 100000).toFixed(2) + 'L';
    return '\u20B9' + num.toFixed(2);
}

function formatPercent(val) {
    if (val === null || val === undefined) return 'N/A';
    const num = typeof val === 'string' ? parseFloat(val) : val;
    if (isNaN(num)) return val;
    return num.toFixed(2) + '%';
}

// ============================================================
// WebLLM Model Loading
// ============================================================
async function initWebLLM() {
    if (state.modelLoaded || state.modelLoading) return;
    state.modelLoading = true;

    try {
        addLog('Initializing WebLLM...', 'system', 'info');
        updateModelStatus('Loading WebLLM...', 'Initializing WebGPU');

        const { CreateMLCEngine } = await import('https://cdn.jsdelivr.net/npm/@mlc-ai/web-llm@0.2.77/+esm');

        addLog('Loading model: ' + WEBLLM_CONFIG.model, 'system', 'info');
        addLog('This may take a few minutes on first load...', 'system', 'info');

        dom.modelProgressContainer.style.display = 'flex';

        const initProgressCallback = (progress) => {
            if (progress.text) {
                dom.modelStatusDetail.textContent = progress.text;
            }
            if (progress.progress !== undefined) {
                const pct = Math.round(progress.progress * 100);
                dom.modelProgressFill.style.width = pct + '%';
                dom.modelProgressText.textContent = pct + '%';
            }
        };

        state.engine = await CreateMLCEngine(
            WEBLLM_CONFIG.model,
            { initProgressCallback }
        );

        state.modelLoaded = true;
        state.modelLoading = false;

        updateModelStatus('Model Ready', WEBLLM_CONFIG.model + ' loaded');
        dom.modelProgressFill.style.width = '100%';
        dom.modelProgressText.textContent = '100%';

        addLog('WebLLM model loaded successfully!', 'system', 'success');
        addLog('You can now analyze stocks', 'system', 'info');

        if (state.selectedStock) {
            dom.btnAnalyze.disabled = false;
        }

    } catch (err) {
        state.modelLoading = false;
        console.error('WebLLM initialization failed:', err);

        updateModelStatus('Model Failed', err.message || 'Unknown error');
        addLog('WebLLM failed: ' + err.message, 'system', 'error');
        addLog('Make sure your browser supports WebGPU (Chrome 113+)', 'system', 'info');

        dom.modelStatusBar.innerHTML = `
            <div class="model-status-icon">⚠️</div>
            <div class="model-status-text">
                <span class="model-status-title">WebLLM Unavailable</span>
                <span class="model-status-detail">WebGPU not supported. Try Chrome/Edge 113+</span>
            </div>
        `;
    }
}

function updateModelStatus(title, detail) {
    dom.modelStatusBar.innerHTML = `
        <div class="model-status-icon">⏳</div>
        <div class="model-status-text">
            <span class="model-status-title">${sanitize(title)}</span>
            <span class="model-status-detail">${sanitize(detail)}</span>
        </div>
    `;
}

// ============================================================
// Stock Search
// ============================================================
let searchTimeout = null;

dom.stockSearch.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    const q = dom.stockSearch.value.trim();

    if (q.length < 1) {
        dom.searchResults.classList.remove('active');
        dom.searchSpinner.classList.remove('active');
        return;
    }

    dom.searchSpinner.classList.add('active');
    searchTimeout = setTimeout(() => performSearch(q), 300);
});

async function performSearch(q) {
    try {
        const resp = await fetch('/api/stocks/search?q=' + encodeURIComponent(q));
        const data = await resp.json();
        dom.searchSpinner.classList.remove('active');

        if (data.results && data.results.length > 0) {
            renderSearchResults(data.results);
        } else {
            dom.searchResults.classList.remove('active');
        }
    } catch (err) {
        console.error('Search error:', err);
        dom.searchSpinner.classList.remove('active');
        dom.searchResults.classList.remove('active');
    }
}

function renderSearchResults(results) {
    dom.searchResults.innerHTML = '';

    results.forEach(item => {
        const div = document.createElement('div');
        div.className = 'search-result-item';
        div.innerHTML = `
            <span class="result-symbol">${sanitize(item.symbol)}</span>
            <span class="result-name">${sanitize(item.name || item.symbol)}</span>
            ${item.sector ? '<span class="result-sector">' + sanitize(item.sector) + '</span>' : ''}
            <span class="result-exchange">${sanitize(item.exchange)}</span>
        `;
        div.addEventListener('click', () => selectStock(item));
        dom.searchResults.appendChild(div);
    });

    dom.searchResults.classList.add('active');
}

function selectStock(item) {
    state.selectedStock = item;
    dom.searchResults.classList.remove('active');
    dom.stockSearch.value = '';

    dom.selectedStock.innerHTML = `
        <div class="selected-stock-badge">
            <span class="badge-symbol">${sanitize(item.symbol)}</span>
            <span class="badge-name">${sanitize(item.name || item.symbol)}</span>
            <span class="badge-exchange">${sanitize(item.exchange)}</span>
        </div>
        <button class="btn-remove" onclick="window.clearSelection()">✕</button>
    `;
    dom.selectedStock.classList.add('has-stock');

    if (item.exchange) {
        const exchange = item.exchange.toUpperCase();
        document.querySelectorAll('#exchange .radio-card').forEach(el => {
            const isActive = el.dataset.value === exchange;
            el.classList.toggle('active', isActive);
            if (isActive) el.querySelector('input').checked = true;
        });
        state.selectedExchange = exchange;
    }

    if (state.modelLoaded) {
        dom.btnAnalyze.disabled = false;
    }
}

window.clearSelection = function() {
    state.selectedStock = null;
    dom.selectedStock.innerHTML = '<span class="selected-stock-placeholder">No stock selected</span>';
    dom.selectedStock.classList.remove('has-stock');
    dom.btnAnalyze.disabled = true;
};

document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-wrapper')) {
        dom.searchResults.classList.remove('active');
    }
});

// ============================================================
// Popular Stocks
// ============================================================
async function loadPopularStocks() {
    try {
        const resp = await fetch('/api/stocks/popular');
        const data = await resp.json();

        dom.popularStocks.innerHTML = '';
        data.results.forEach(item => {
            const chip = document.createElement('span');
            chip.className = 'popular-chip';
            chip.textContent = item.symbol;
            chip.title = item.name;
            chip.addEventListener('click', () => selectStock(item));
            dom.popularStocks.appendChild(chip);
        });
    } catch (err) {
        console.error('Failed to load popular stocks:', err);
        dom.popularStocks.innerHTML = '<span class="popular-loading">Failed to load</span>';
    }
}

// ============================================================
// Radio Card Selection
// ============================================================
document.querySelectorAll('.radio-card').forEach(card => {
    card.addEventListener('click', () => {
        const group = card.closest('.radio-group');
        group.querySelectorAll('.radio-card').forEach(c => c.classList.remove('active'));
        card.classList.add('active');
        card.querySelector('input').checked = true;

        if (group.id === 'analysisType') {
            state.selectedAnalysisType = card.dataset.value;
        } else if (group.id === 'exchange') {
            state.selectedExchange = card.dataset.value;
        }
    });
});

// ============================================================
// Analysis Flow
// ============================================================
dom.btnAnalyze.addEventListener('click', startAnalysis);

async function startAnalysis() {
    if (!state.selectedStock || state.isAnalyzing) return;
    if (!state.modelLoaded) {
        addLog('Please wait for the AI model to finish loading', 'system', 'warning');
        return;
    }

    state.isAnalyzing = true;
    state.logs = [];

    dom.emptyState.style.display = 'none';
    dom.resultsSection.style.display = 'none';
    dom.errorSection.style.display = 'none';
    dom.progressSection.style.display = 'block';
    dom.btnClearLogs.style.display = 'none';
    dom.btnAnalyze.classList.add('loading');
    dom.btnAnalyze.querySelector('.btn-text').textContent = 'Analyzing...';
    dom.btnAnalyze.disabled = true;

    dom.progressFill.style.width = '0%';
    dom.progressPhase.textContent = 'Starting...';
    dom.progressPercent.textContent = '0%';
    dom.logsViewport.innerHTML = '';
    dom.logCount.textContent = '0 events';

    document.querySelectorAll('.phase-step').forEach(el => {
        el.classList.remove('active', 'completed', 'error');
    });

    try {
        // Phase 1: Fetch Data
        updatePhase('data_fetch', 'start');
        dom.progressPhase.textContent = 'Fetching Market Data...';
        dom.progressFill.style.width = '10%';
        dom.progressPercent.textContent = '10%';

        addLog('Fetching data for ' + state.selectedStock.symbol + '...', 'system', 'info');

        const resp = await fetch('/api/stocks/data/' + state.selectedStock.symbol + '?exchange=' + state.selectedExchange);
        if (!resp.ok) throw new Error('Server error: ' + resp.status);

        state.stockData = await resp.json();

        addLog('Data fetched for ' + state.stockData.company_name, 'system', 'success');
        if (state.stockData.current_price) {
            addLog('Current Price: ' + state.stockData.current_price, 'system', 'data');
        }
        if (state.stockData.sector) {
            addLog('Sector: ' + state.stockData.sector, 'system', 'data');
        }

        const tech = state.stockData.technical || {};
        if (tech.rsi) {
            addLog('RSI(14): ' + tech.rsi.value + ' (' + tech.rsi.signal + ')', 'Technical Analyst', 'info');
        }
        if (tech.macd) {
            addLog('MACD: ' + tech.macd.signal + ' (Line: ' + tech.macd.macd_line + ')', 'Technical Analyst', 'info');
        }
        if (tech.trend) {
            addLog('Trend: ' + tech.trend, 'Technical Analyst', 'info');
        }

        const fund = state.stockData.fundamental || {};
        if (fund.pe_ratio) {
            addLog('P/E Ratio: ' + fund.pe_ratio, 'Market Researcher', 'info');
        }
        if (fund.roce) {
            addLog('ROCE: ' + formatPercent(fund.roce), 'Market Researcher', 'info');
        }
        if (fund.debt_to_equity) {
            addLog('Debt/Equity: ' + fund.debt_to_equity, 'Market Researcher', 'info');
        }

        const news = state.stockData.sentiment?.news || [];
        if (news.length > 0) {
            addLog(news.length + ' recent news articles found', 'Sentiment Analyst', 'info');
            news.slice(0, 3).forEach(item => {
                addLog(item.title, 'Sentiment Analyst', 'info');
            });
        }

        const risk = state.stockData.risk || {};
        if (risk.beta) {
            addLog('Beta: ' + risk.beta, 'Risk Manager', 'info');
        }
        if (risk.risk_score) {
            addLog('Risk Score: ' + risk.risk_score + '/10', 'Risk Manager', 'info');
        }

        updatePhase('data_fetch', 'complete');
        dom.progressFill.style.width = '40%';
        dom.progressPercent.textContent = '40%';

        // Phase 2: AI Analysis
        updatePhase('ai_analysis', 'start');
        dom.progressPhase.textContent = 'Running AI Analysis...';
        dom.progressFill.style.width = '45%';
        dom.progressPercent.textContent = '45%';

        addLog('Starting WebLLM analysis...', 'system', 'info');

        const analysisResult = await runWebLLMAnalysis(state.stockData, state.selectedAnalysisType);

        updatePhase('ai_analysis', 'complete');
        dom.progressFill.style.width = '80%';
        dom.progressPercent.textContent = '80%';

        // Phase 3: Generate Report
        updatePhase('report', 'start');
        dom.progressPhase.textContent = 'Generating Report...';
        dom.progressFill.style.width = '85%';
        dom.progressPercent.textContent = '85%';

        addLog('Generating analysis report...', 'system', 'info');

        showResults(analysisResult);

        dom.progressFill.style.width = '100%';
        dom.progressPercent.textContent = '100%';
        dom.progressPhase.textContent = 'Complete!';
        updatePhase('report', 'complete');

    } catch (err) {
        console.error('Analysis failed:', err);
        showError(err.message);
    } finally {
        state.isAnalyzing = false;
        dom.btnAnalyze.classList.remove('loading');
        dom.btnAnalyze.querySelector('.btn-text').textContent = 'Analyze Stock';
        dom.btnAnalyze.disabled = false;
        dom.btnClearLogs.style.display = 'inline-flex';
    }
}

// ============================================================
// WebLLM Analysis
// ============================================================
async function runWebLLMAnalysis(data, analysisType) {
    const symbol = data.symbol;
    const companyName = data.company_name || symbol;
    const sector = data.sector || 'N/A';
    const price = data.current_price || 'N/A';
    const tech = data.technical || {};
    const fund = data.fundamental || {};
    const risk = data.risk || {};
    const news = data.sentiment?.news || [];

    let prompt = '';

    if (analysisType === 'quick') {
        prompt = 'You are a stock market analyst. Provide a QUICK OVERVIEW of ' + companyName + ' (' + symbol + ').\n\n' +
            'REAL MARKET DATA (use these exact values):\n' +
            '- Current Price: ' + price + '\n' +
            '- Sector: ' + sector + '\n' +
            '- P/E Ratio: ' + (fund.pe_ratio || 'N/A') + '\n' +
            '- Market Cap: ' + (fund.market_cap || 'N/A') + '\n' +
            '- RSI(14): ' + (tech.rsi?.value || 'N/A') + ' (' + (tech.rsi?.signal || 'N/A') + ')\n' +
            '- Trend: ' + (tech.trend || 'N/A') + '\n' +
            '- 52W High: ' + (risk['52w_high'] || 'N/A') + '\n' +
            '- 52W Low: ' + (risk['52w_low'] || 'N/A') + '\n\n' +
            'Provide:\n' +
            '1. Brief company overview\n' +
            '2. Key metrics snapshot\n' +
            '3. Quick verdict (BUY/SELL/HOLD) with confidence level\n' +
            '4. Score out of 10\n\n' +
            'Format your response with clear sections.';
    } else if (analysisType === 'fundamental') {
        prompt = 'You are a Market Researcher AI agent analyzing ' + companyName + ' (' + symbol + ').\n\n' +
            'REAL MARKET DATA (use these exact values):\n' +
            '- Current Price: ' + price + '\n' +
            '- Sector: ' + sector + '\n' +
            '- Industry: ' + (data.industry || 'N/A') + '\n' +
            '- Market Cap: ' + (fund.market_cap || 'N/A') + '\n' +
            '- P/E Ratio: ' + (fund.pe_ratio || 'N/A') + '\n' +
            '- P/B Ratio: ' + (fund.pb_ratio || 'N/A') + '\n' +
            '- ROCE: ' + (fund.roce || 'N/A') + '\n' +
            '- ROE: ' + (fund.roe || 'N/A') + '\n' +
            '- Debt/Equity: ' + (fund.debt_to_equity || 'N/A') + '\n' +
            '- Dividend Yield: ' + (fund.dividend_yield || 'N/A') + '\n' +
            '- Book Value: ' + (fund.book_value || 'N/A') + '\n' +
            '- EPS: ' + (fund.eps || 'N/A') + '\n' +
            '- Revenue: ' + (fund.revenue || 'N/A') + '\n' +
            '- Net Income: ' + (fund.net_income || 'N/A') + '\n' +
            '- OPM: ' + (fund.opm || 'N/A') + '\n' +
            '- Free Cash Flow: ' + (fund.free_cash_flow || 'N/A') + '\n' +
            '- 52W High: ' + (risk['52w_high'] || 'N/A') + '\n' +
            '- 52W Low: ' + (risk['52w_low'] || 'N/A') + '\n\n' +
            'Provide a comprehensive FUNDAMENTAL ANALYSIS:\n' +
            '1. Financial Health Assessment\n' +
            '2. Key Ratios Analysis (Valuation, Profitability, Efficiency)\n' +
            '3. Growth Trajectory\n' +
            '4. Peer Comparison Context\n' +
            '5. Strengths & Weaknesses\n' +
            '6. Final Recommendation (BUY/SELL/HOLD) with confidence\n' +
            '7. Score: X.X/10\n\n' +
            'IMPORTANT: Use ONLY the real data provided above. Do not make up numbers.';
    } else if (analysisType === 'technical') {
        prompt = 'You are a Technical Analyst AI agent analyzing ' + companyName + ' (' + symbol + ').\n\n' +
            'REAL MARKET DATA (use these exact values):\n' +
            '- Current Price: ' + price + '\n' +
            '- RSI(14): ' + (tech.rsi?.value || 'N/A') + ' (' + (tech.rsi?.signal || 'N/A') + ')\n' +
            '- MACD Line: ' + (tech.macd?.macd_line || 'N/A') + '\n' +
            '- MACD Signal: ' + (tech.macd?.signal_line || 'N/A') + '\n' +
            '- MACD Histogram: ' + (tech.macd?.histogram || 'N/A') + '\n' +
            '- MACD Signal Direction: ' + (tech.macd?.signal || 'N/A') + '\n' +
            '- MA(20): ' + (tech.moving_averages?.ma_20 || 'N/A') + '\n' +
            '- MA(50): ' + (tech.moving_averages?.ma_50 || 'N/A') + '\n' +
            '- MA(200): ' + (tech.moving_averages?.ma_200 || 'N/A') + '\n' +
            '- Bollinger Upper: ' + (tech.bollinger_bands?.upper || 'N/A') + '\n' +
            '- Bollinger Middle: ' + (tech.bollinger_bands?.middle || 'N/A') + '\n' +
            '- Bollinger Lower: ' + (tech.bollinger_bands?.lower || 'N/A') + '\n' +
            '- Bollinger Width: ' + (tech.bollinger_bands?.width_pct || 'N/A') + '%\n' +
            '- Volume Avg: ' + (tech.volume_analysis?.avg_volume || 'N/A') + '\n' +
            '- Volume Recent: ' + (tech.volume_analysis?.recent_volume || 'N/A') + '\n' +
            '- Volume Ratio: ' + (tech.volume_analysis?.volume_ratio || 'N/A') + '\n' +
            '- Volume Trend: ' + (tech.volume_analysis?.trend || 'N/A') + '\n' +
            '- Pivot: ' + (tech.pivot_points?.pivot || 'N/A') + '\n' +
            '- R1: ' + (tech.pivot_points?.resistance_1 || 'N/A') + '\n' +
            '- S1: ' + (tech.pivot_points?.support_1 || 'N/A') + '\n' +
            '- R2: ' + (tech.pivot_points?.resistance_2 || 'N/A') + '\n' +
            '- S2: ' + (tech.pivot_points?.support_2 || 'N/A') + '\n' +
            '- Recent High: ' + (tech.support_resistance?.recent_high || 'N/A') + '\n' +
            '- Recent Low: ' + (tech.support_resistance?.recent_low || 'N/A') + '\n' +
            '- Overall Trend: ' + (tech.trend || 'N/A') + '\n\n' +
            'Provide a comprehensive TECHNICAL ANALYSIS:\n' +
            '1. Trend Analysis (short, medium, long term)\n' +
            '2. Momentum Indicators (RSI, MACD)\n' +
            '3. Support & Resistance Levels\n' +
            '4. Volume Analysis\n' +
            '5. Bollinger Bands Analysis\n' +
            '6. Key Technical Levels to Watch\n' +
            '7. Final Recommendation (BUY/SELL/HOLD) with confidence\n' +
            '8. Score: X.X/10\n\n' +
            'IMPORTANT: Use ONLY the real data provided above. Do not make up numbers.';
    } else {
        const newsText = news.slice(0, 5).map((n, i) =>
            (i + 1) + '. ' + n.title + ' (' + n.source + ')'
        ).join('\n');

        prompt = 'You are a team of AI stock analysts analyzing ' + companyName + ' (' + symbol + '). You will play the role of ALL agents below and provide a comprehensive analysis.\n\n' +
            'REAL MARKET DATA (use these exact values):\n' +
            '- Current Price: ' + price + '\n' +
            '- Company: ' + companyName + '\n' +
            '- Sector: ' + sector + '\n' +
            '- Industry: ' + (data.industry || 'N/A') + '\n' +
            '- Market Cap: ' + (fund.market_cap || 'N/A') + '\n' +
            '- P/E Ratio: ' + (fund.pe_ratio || 'N/A') + '\n' +
            '- P/B Ratio: ' + (fund.pb_ratio || 'N/A') + '\n' +
            '- ROCE: ' + (fund.roce || 'N/A') + '\n' +
            '- ROE: ' + (fund.roe || 'N/A') + '\n' +
            '- Debt/Equity: ' + (fund.debt_to_equity || 'N/A') + '\n' +
            '- Dividend Yield: ' + (fund.dividend_yield || 'N/A') + '\n' +
            '- Book Value: ' + (fund.book_value || 'N/A') + '\n' +
            '- EPS: ' + (fund.eps || 'N/A') + '\n' +
            '- Revenue: ' + (fund.revenue || 'N/A') + '\n' +
            '- Net Income: ' + (fund.net_income || 'N/A') + '\n' +
            '- OPM: ' + (fund.opm || 'N/A') + '\n' +
            '- Free Cash Flow: ' + (fund.free_cash_flow || 'N/A') + '\n' +
            '- RSI(14): ' + (tech.rsi?.value || 'N/A') + ' (' + (tech.rsi?.signal || 'N/A') + ')\n' +
            '- MACD: ' + (tech.macd?.signal || 'N/A') + '\n' +
            '- MA(20): ' + (tech.moving_averages?.ma_20 || 'N/A') + '\n' +
            '- MA(50): ' + (tech.moving_averages?.ma_50 || 'N/A') + '\n' +
            '- MA(200): ' + (tech.moving_averages?.ma_200 || 'N/A') + '\n' +
            '- Bollinger Width: ' + (tech.bollinger_bands?.width_pct || 'N/A') + '%\n' +
            '- Volume Trend: ' + (tech.volume_analysis?.trend || 'N/A') + '\n' +
            '- Overall Trend: ' + (tech.trend || 'N/A') + '\n' +
            '- Beta: ' + (risk.beta || 'N/A') + '\n' +
            '- 52W High: ' + (risk['52w_high'] || 'N/A') + '\n' +
            '- 52W Low: ' + (risk['52w_low'] || 'N/A') + '\n' +
            '- Risk Score: ' + (risk.risk_score || 'N/A') + '/10\n\n' +
            (newsText ? 'RECENT NEWS:\n' + newsText + '\n\n' : '') +
            'Provide a COMPREHENSIVE FULL ANALYSIS with these sections:\n\n' +
            '## Market Researcher (Fundamental Analysis)\n' +
            '- Financial health assessment\n' +
            '- Key ratios analysis\n' +
            '- Growth metrics\n' +
            '- Peer comparison\n\n' +
            '## Technical Analyst (Technical Analysis)\n' +
            '- Trend analysis\n' +
            '- Momentum indicators\n' +
            '- Support/resistance levels\n' +
            '- Volume analysis\n\n' +
            '## Sentiment Analyst (News & Sentiment)\n' +
            '- Recent news impact\n' +
            '- Market sentiment\n' +
            '- Catalysts and risks\n\n' +
            '## Risk Manager (Risk Assessment)\n' +
            '- Volatility analysis\n' +
            '- Key risk factors\n' +
            '- Risk score interpretation\n\n' +
            '## Portfolio Manager (Portfolio Context)\n' +
            '- Sector allocation view\n' +
            '- Investment suitability\n\n' +
            '## Strategy Manager (Final Recommendation)\n' +
            '- Synthesize all inputs\n' +
            '- Weighted final recommendation\n' +
            '- Confidence level\n\n' +
            '## Critic (Challenge & Review)\n' +
            '- Challenge the recommendation\n' +
            '- Identify overlooked risks\n' +
            '- Final balanced verdict\n\n' +
            'FINAL OUTPUT FORMAT:\n' +
            '**Recommendation:** BUY/SELL/HOLD\n' +
            '**Score:** X.X/10\n' +
            '**Confidence:** High/Medium/Low\n' +
            '**Summary:** 2-3 sentence summary\n\n' +
            'IMPORTANT: Use ONLY the real data provided above. Do not make up numbers.';
    }

    addLog('Sending data to WebLLM for analysis...', 'system', 'info');

    const asyncChunkGenerator = await state.engine.chat.completions.create({
        messages: [
            { role: 'system', content: 'You are a professional stock market analyst AI. You analyze Indian stocks using real market data. Always provide accurate, data-driven analysis. Format your responses with clear markdown headings and bullet points.' },
            { role: 'user', content: prompt }
        ],
        temperature: 0.3,
        max_tokens: 4096,
        stream: true,
    });

    let fullResponse = '';
    let currentAgent = '';

    for await (const chunk of asyncChunkGenerator) {
        const content = chunk.choices[0]?.delta?.content || '';
        fullResponse += content;

        const agentMatch = fullResponse.match(/##\s*(Market|Technical|Sentiment|Risk|Portfolio|Strategy|Critic)/);
        if (agentMatch) {
            const newAgent = agentMatch[1].trim() + ' Analyst';
            if (newAgent !== currentAgent) {
                currentAgent = newAgent;
                addLog(currentAgent + ' is analyzing...', currentAgent, 'info');
            }
        }
    }

    addLog('AI analysis complete!', 'system', 'success');

    const recMatch = fullResponse.match(/\*\*Recommendation:\*\*\s*(BUY|SELL|HOLD)/i);
    const scoreMatch = fullResponse.match(/\*\*Score:\*\*\s*([\d.]+)\/10/);
    const confMatch = fullResponse.match(/\*\*Confidence:\*\*\s*(High|Medium|Low)/i);

    const recommendation = {
        action: recMatch ? recMatch[1].toUpperCase() : 'HOLD',
        score: scoreMatch ? parseFloat(scoreMatch[1]) : 5.0,
        confidence: confMatch ? confMatch[1] : 'Medium',
    };

    addLog('Recommendation: ' + recommendation.action + ' | Score: ' + recommendation.score + '/10 | Confidence: ' + recommendation.confidence, 'system', 'result');

    return {
        recommendation,
        fullAnalysis: fullResponse,
        symbol: symbol,
        companyName: companyName,
    };
}

// ============================================================
// Log Display
// ============================================================
function addLog(message, agent, level) {
    if (!agent) agent = 'system';
    if (!level) level = 'info';

    const entry = {
        timestamp: new Date().toISOString(),
        agent: agent,
        level: level,
        message: message
    };

    state.logs.push(entry);

    const div = document.createElement('div');
    div.className = 'log-entry agent-' + getAgentClass(agent) + ' level-' + getLevelClass(level);

    const time = formatTime(entry.timestamp);

    div.innerHTML = `
        <span class="log-time">${sanitize(time)}</span>
        <span class="log-agent">${sanitize(agent)}</span>
        <span class="log-message">${sanitize(message)}</span>
    `;

    dom.logsViewport.appendChild(div);
    dom.logCount.textContent = state.logs.length + ' events';
    dom.logsViewport.scrollTop = dom.logsViewport.scrollHeight;
}

// ============================================================
// Phase Indicators
// ============================================================
function updatePhase(phase, status) {
    const step = document.querySelector('.phase-step[data-phase="' + phase + '"]');
    if (!step) return;

    if (status === 'start') {
        step.classList.add('active');
    } else if (status === 'complete') {
        step.classList.remove('active');
        step.classList.add('completed');
    }
}

// ============================================================
// Show Results
// ============================================================
function showResults(result) {
    dom.progressSection.style.display = 'none';
    dom.resultsSection.style.display = 'block';

    const rec = result.recommendation || {};
    const action = (rec.action || 'HOLD').toUpperCase();
    const score = rec.score || 'N/A';
    const confidence = rec.confidence || 'N/A';

    dom.recBanner.className = 'recommendation-banner action-' + action;

    const recIcons = { BUY: '🟢', SELL: '🔴', HOLD: '🟡' };
    dom.recIcon.textContent = recIcons[action] || '🎯';
    dom.recAction.textContent = action;
    dom.recScore.textContent = score + '/10';
    dom.recConfidence.textContent = confidence + ' Confidence';

    dom.summaryContent.innerHTML = renderAnalysis(result.fullAnalysis || '');

    renderMetricsGrid();

    dom.reportContent.innerHTML = renderFullReport(result);

    dom.btnCopyReport.onclick = () => {
        navigator.clipboard.writeText(result.fullAnalysis || '');
        dom.btnCopyReport.innerHTML = '<span>✅</span> Copied!';
        setTimeout(() => {
            dom.btnCopyReport.innerHTML = '<span>📋</span> Copy';
        }, 2000);
    };

    dom.btnDownloadReport.onclick = () => {
        const blob = new Blob([result.fullAnalysis || ''], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = result.symbol + '_analysis.md';
        a.click();
        URL.revokeObjectURL(url);
        dom.btnDownloadReport.innerHTML = '<span>✅</span> Downloaded!';
        setTimeout(() => {
            dom.btnDownloadReport.innerHTML = '<span>⬇️</span> Download';
        }, 2000);
    };
}

// ============================================================
// Render Analysis (Markdown to HTML)
// ============================================================
function renderAnalysis(text) {
    if (!text) return '<p>No analysis available.</p>';

    let html = text
        .replace(/###\s+(.*)/g, '<h4>$1</h4>')
        .replace(/##\s+(.*)/g, '<h3>$1</h3>')
        .replace(/#\s+(.*)/g, '<h2>$1</h2>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/^- (.*)/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');

    return '<p>' + html + '</p>';
}

// ============================================================
// Render Metrics Grid
// ============================================================
function renderMetricsGrid() {
    const data = state.stockData;
    if (!data) return;

    const tech = data.technical || {};
    const fund = data.fundamental || {};
    const risk = data.risk || {};

    const metrics = [
        { label: 'Current Price', value: data.current_price ? '\u20B9' + data.current_price : 'N/A', icon: '💰' },
        { label: 'Market Cap', value: formatCurrency(fund.market_cap), icon: '🏢' },
        { label: 'P/E Ratio', value: fund.pe_ratio || 'N/A', icon: '📊' },
        { label: 'P/B Ratio', value: fund.pb_ratio || 'N/A', icon: '📈' },
        { label: 'ROCE', value: formatPercent(fund.roce), icon: '📉' },
        { label: 'ROE', value: formatPercent(fund.roe), icon: '📊' },
        { label: 'Debt/Equity', value: fund.debt_to_equity || 'N/A', icon: '⚖️' },
        { label: 'Dividend Yield', value: formatPercent(fund.dividend_yield), icon: '💵' },
        { label: 'EPS', value: fund.eps || 'N/A', icon: '📋' },
        { label: 'RSI(14)', value: tech.rsi ? tech.rsi.value + ' (' + tech.rsi.signal + ')' : 'N/A', icon: '📉' },
        { label: 'Trend', value: tech.trend || 'N/A', icon: '📈' },
        { label: 'Beta', value: risk.beta || 'N/A', icon: '🎯' },
        { label: '52W High', value: risk['52w_high'] || 'N/A', icon: '⬆️' },
        { label: '52W Low', value: risk['52w_low'] || 'N/A', icon: '⬇️' },
        { label: 'Risk Score', value: risk.risk_score ? risk.risk_score + '/10' : 'N/A', icon: '⚠️' },
    ];

    dom.metricsGrid.innerHTML = metrics.map(m => `
        <div class="metric-card">
            <div class="metric-icon">${m.icon}</div>
            <div class="metric-value">${sanitize(m.value)}</div>
            <div class="metric-label">${sanitize(m.label)}</div>
        </div>
    `).join('');
}

// ============================================================
// Render Full Report
// ============================================================
function renderFullReport(result) {
    const text = result.fullAnalysis || '';
    const html = renderAnalysis(text);

    return `
        <div class="report-iframe-container">
            <div class="report-content-inner">
                ${html}
            </div>
        </div>
    `;
}

// ============================================================
// Show Error
// ============================================================
function showError(message) {
    dom.progressSection.style.display = 'none';
    dom.resultsSection.style.display = 'none';
    dom.errorSection.style.display = 'block';
    dom.errorMessage.textContent = message || 'An unknown error occurred.';
    addLog('Error: ' + message, 'system', 'error');
}

// ============================================================
// Clear Logs
// ============================================================
dom.btnClearLogs.addEventListener('click', () => {
    state.logs = [];
    dom.logsViewport.innerHTML = '';
    dom.logCount.textContent = '0 events';
});

// ============================================================
// Footer Clock
// ============================================================
function updateFooterTime() {
    const now = new Date();
    dom.footerTime.textContent = now.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        dateStyle: 'medium',
        timeStyle: 'medium'
    });
}

// ============================================================
// Server Health Check
// ============================================================
async function checkServerHealth() {
    try {
        const resp = await fetch('/api/health');
        const data = await resp.json();
        if (data.status === 'ok') {
            dom.serverStatus.className = 'status-dot';
            dom.serverStatusText.textContent = 'Connected';
        } else {
            dom.serverStatus.className = 'status-dot offline';
            dom.serverStatusText.textContent = 'Degraded';
        }
    } catch (err) {
        dom.serverStatus.className = 'status-dot offline';
        dom.serverStatusText.textContent = 'Offline';
    }
}

// ============================================================
// Initialize
// ============================================================
async function init() {
    updateFooterTime();
    setInterval(updateFooterTime, 1000);

    checkServerHealth();
    setInterval(checkServerHealth, 30000);

    loadPopularStocks();

    // Start WebLLM loading after a short delay
    setTimeout(initWebLLM, 500);
}

// Start when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
