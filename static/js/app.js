// ============================================
// 前端应用逻辑 - Render 部署版
// ============================================

// 当前数据
let currentData = {
    indices: [],
    stocks: [],
    lastUpdate: null,
};

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
    // 加载大盘指数
    await loadIndices();
    // 从数据库读取最新分析
    await loadStocks();
});

// 加载大盘指数
async function loadIndices() {
    showLoading('indices');
    try {
        const indices = await getIndices();
        currentData.indices = indices;
        renderIndices(indices);
    } catch (e) {
        showError('indices', '加载失败');
    }
}

// 加载股票列表（从数据库读取已分析的数据）
async function loadStocks() {
    showLoading('stocks');
    try {
        const stocks = await getLatestAnalysis();
        currentData.stocks = stocks;
        currentData.lastUpdate = new Date().toISOString();
        renderStocks(stocks);
        updateUpdateTime();
        console.log('股票数据加载:', stocks.length, '只');
    } catch (e) {
        console.error('加载失败:', e);
        showError('stocks', '加载失败: ' + e.message);
    }
}

// 刷新全部数据
async function analyzeAll() {
    showLoading('indices');
    showLoading('stocks');
    try {
        // 触发后端分析所有股票
        const results = await refreshAll();
        currentData.stocks = results;
        currentData.lastUpdate = new Date().toISOString();
        renderStocks(results);
        updateUpdateTime();
        showToast('✅ 刷新完成');
    } catch (e) {
        console.error('刷新失败:', e);
        showToast('❌ 刷新失败');
    }
}

// 分析推文
async function analyzeTweets() {
    showLoading('stocks');
    try {
        const result = await refreshTweets();
        if (result && result.analysis) {
            currentData.stocks = result.analysis;
            currentData.lastUpdate = new Date().toISOString();
            renderStocks(result.analysis);
            updateUpdateTime();
            showToast(`✅ 推文分析完成，发现 ${result.stocks_found.length} 只股票`);
        }
    } catch (e) {
        console.error('推文分析失败:', e);
        showToast('❌ 推文分析失败');
    }
}

// 渲染大盘指数
function renderIndices(indices) {
    const container = document.getElementById('indices');
    if (!container) return;

    if (!indices || indices.length === 0) {
        container.innerHTML = '<h2>🏛️ 大盘指数</h2><p class="empty">暂无数据</p>';
        return;
    }

    container.innerHTML = `
        <h2>🏛️ 大盘指数</h2>
        <div class="indices-grid">
            ${indices.map(idx => `
                <div class="index-card">
                    <span class="index-name">${idx.name}</span>
                    <span class="index-price">$${idx.price?.toFixed(2) || '--'}</span>
                </div>
            `).join('')}
        </div>
    `;
}

// 渲染股票列表
function renderStocks(stocks) {
    const container = document.getElementById('stocks');
    if (!container) return;

    if (!stocks || stocks.length === 0) {
        container.innerHTML = '<h2>📊 关注股票</h2><p class="empty">暂无数据，点击上方"推文分析"或"刷新全部"</p>';
        return;
    }

    container.innerHTML = `
        <h2>📊 关注股票</h2>
        <div class="stocks-list">
            ${stocks.map(stock => `
                <div class="stock-card" onclick="showDetail('${stock.symbol}')">
                    <div class="stock-header">
                        <span class="stock-symbol">${stock.symbol}</span>
                        <span class="stock-name">${stock.name || ''}</span>
                        <span class="verdict-badge ${getVerdictClass(stock.verdict)}">${stock.verdict || '中性'}</span>
                    </div>
                    <div class="stock-body">
                        <div class="price-row">
                            <span class="stock-price">$${stock.price?.toFixed(2) || '--'}</span>
                            <span class="daily-change ${stock.daily_change >= 0 ? 'up' : stock.daily_change < 0 ? 'down' : ''}">
                                ${stock.daily_change >= 0 ? '▲' : stock.daily_change < 0 ? '▼' : ''} 
                                ${stock.daily_change != null ? Math.abs(stock.daily_change).toFixed(2) + '%' : '--'}
                            </span>
                        </div>
                        <div class="stats-row">
                            <span>10天: ${stock.ten_day_trend ? (stock.ten_day_trend >= 0 ? '+' : '') + stock.ten_day_trend.toFixed(1) + '%' : '--'}</span>
                            <span>RSI: ${stock.rsi_14?.toFixed(1) || '--'}</span>
                            <span>MACD: ${stock.macd_signal || '--'}</span>
                        </div>
                        <div class="signal-row">
                            <span>正: +${(stock.weighted_positive || 0).toFixed(1)}</span>
                            <span>负: -${(stock.weighted_negative || 0).toFixed(1)}</span>
                        </div>
                        ${stock.direction ? `<div class="direction-tag">${stock.direction}</div>` : ''}
                        <div class="recommendation-text">${getRecommendation(stock)}</div>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

// 显示股票详情
async function showDetail(symbol) {
    const stock = currentData.stocks.find(s => s.symbol === symbol);
    if (!stock) {
        // 如果没有缓存，从后端获取
        try {
            const history = await getStockHistory(symbol, 1);
            if (history && history.length > 0) {
                showDetailFromData(history[0]);
                return;
            }
        } catch (e) {
            console.error('获取详情失败:', e);
        }
        return;
    }
    showDetailFromData(stock);
}

function showDetailFromData(stock) {
    const modal = document.getElementById('detail-modal');
    const content = document.getElementById('detail-content');

    // 解析 JSON 数据获取完整信息
    let fullData = null;
    if (stock.json_data) {
        try {
            fullData = typeof stock.json_data === 'string' ? JSON.parse(stock.json_data) : stock.json_data;
        } catch (e) {}
    }

    const signals = fullData?.signals || [];
    const news = fullData?.news || [];

    content.innerHTML = `
        <h2>${stock.symbol} - ${stock.name || ''}</h2>
        
        <div class="detail-section">
            <h3>价格信息</h3>
            <p>当前价: <strong>$${stock.price?.toFixed(2) || '--'}</strong></p>
            <p>今日涨跌: <span class="${stock.daily_change >= 0 ? 'up' : stock.daily_change < 0 ? 'down' : ''}">${stock.daily_change >= 0 ? '+' : ''}${stock.daily_change != null ? stock.daily_change.toFixed(2) : '--'}%</span></p>
            <p>10天趋势: ${stock.ten_day_trend ? (stock.ten_day_trend >= 0 ? '+' : '') + stock.ten_day_trend.toFixed(2) + '%' : '--'}</p>
        </div>
        
        <div class="detail-section">
            <h3>技术指标</h3>
            <p>PE: ${stock.pe_ratio?.toFixed(1) || '--'}</p>
            <p>RSI(14): ${stock.rsi_14?.toFixed(1) || '--'}</p>
            <p>MACD: ${stock.macd_signal || '--'}</p>
            ${fullData?.sma5 ? `<p>SMA5: ${fullData.sma5.toFixed(2)}</p>` : ''}
            ${fullData?.sma10 ? `<p>SMA10: ${fullData.sma10.toFixed(2)}</p>` : ''}
        </div>
        
        <div class="detail-section">
            <h3>分析师评级</h3>
            <p>看涨比例: ${stock.analyst_bull_pct?.toFixed(0) || '--'}%</p>
            <p>新闻数量: ${stock.news_count || 0} 条</p>
        </div>
        
        <div class="detail-section">
            <h3>分析信号 (${signals.length}条)</h3>
            ${signals.map(s => `<p>${s[0]} ${s[1]}</p>`).join('')}
        </div>
        
        ${news.length > 0 ? `
        <div class="detail-section">
            <h3>相关新闻</h3>
            ${news.map(n => `<p>• ${n.headline || n.title || '无标题'}</p>`).join('')}
        </div>
        ` : ''}
        
        <div class="detail-section">
            <h3>综合判断</h3>
            <p class="verdict-large ${getVerdictClass(stock.verdict)}">${stock.verdict || '中性'}</p>
            <p class="recommendation-detail">${getRecommendation(stock)}</p>
            <p>正面: +${(stock.weighted_positive || 0).toFixed(1)} | 负面: -${(stock.weighted_negative || 0).toFixed(1)}</p>
            <p>更新时间: ${new Date(stock.timestamp).toLocaleString('zh-CN')}</p>
        </div>
        
        ${stock.direction ? `<div class="detail-section"><h3>推文方向</h3><p>${stock.direction}</p></div>` : ''}
    `;

    modal.style.display = 'flex';
}

// 关闭弹窗
function closeModal() {
    document.getElementById('detail-modal').style.display = 'none';
}

// 显示加载状态
function showLoading(section) {
    const container = document.getElementById(section);
    if (container) {
        container.innerHTML = '<div class="loading">⏳ 加载中...</div>';
    }
}

// 显示错误
function showError(section, message) {
    const container = document.getElementById(section);
    if (container) {
        container.innerHTML = `<div class="error">❌ ${message}</div>`;
    }
}

// 更新更新时间
function updateUpdateTime() {
    const settingsTime = document.getElementById('settings-time');
    if (settingsTime && currentData.lastUpdate) {
        settingsTime.textContent = new Date(currentData.lastUpdate).toLocaleString('zh-CN');
    }
}

// 获取判断类别样式
function getVerdictClass(verdict) {
    switch (verdict) {
        case '看涨': return 'verdict-bull';
        case '看跌': return 'verdict-bear';
        default: return 'verdict-neutral';
    }
}

function getRecommendation(stock) {
    if (stock.recommendation) return stock.recommendation;
    // 从后端 JSON 解析
    if (stock.json_data) {
        try {
            const data = typeof stock.json_data === 'string' ? JSON.parse(stock.json_data) : stock.json_data;
            if (data.recommendation) return data.recommendation;
        } catch (e) {}
    }
    // 根据 verdict 生成
    switch (stock.verdict) {
        case '看涨': return '可关注买入机会';
        case '看跌': return '建议观望，可考虑减仓';
        default: return '多空信号相当，建议观望';
    }
}

// 显示提示
function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 100);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

// 切换标签页
function showTab(tab, btn) {
    document.getElementById('page-history').style.display = 'none';
    document.getElementById('page-settings').style.display = 'none';
    document.getElementById('indices').style.display = '';
    document.getElementById('stocks').style.display = '';

    if (tab === 'history') {
        document.getElementById('page-history').style.display = 'block';
        document.getElementById('indices').style.display = 'none';
        document.getElementById('stocks').style.display = 'none';
        loadHistory();
    } else if (tab === 'settings') {
        document.getElementById('page-settings').style.display = 'block';
        document.getElementById('indices').style.display = 'none';
        document.getElementById('stocks').style.display = 'none';
        loadSettings();
    }

    document.querySelectorAll('.tab-item').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
}

// 加载历史
async function loadHistory() {
    const container = document.getElementById('history-content');
    container.innerHTML = '<div class="loading">⏳ 加载中...</div>';

    try {
        const data = await getLatestAnalysis();
        if (data.length === 0) {
            container.innerHTML = '<p class="empty">暂无历史记录</p>';
            return;
        }

        container.innerHTML = `
            <div class="history-list">
                ${data.map(item => `
                    <div class="history-card" onclick="showDetail('${item.symbol}')">
                        <span>${item.symbol}</span>
                        <span>$${item.price?.toFixed(2)}</span>
                        <span class="${item.verdict === '看涨' ? 'up' : item.verdict === '看跌' ? 'down' : ''}">${item.verdict}</span>
                        <span>${new Date(item.timestamp).toLocaleDateString()}</span>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (e) {
        container.innerHTML = '<p class="error">加载失败</p>';
    }
}

// 加载设置
async function loadSettings() {
    try {
        const watchList = await getWatchList();
        document.getElementById('settings-count').textContent = watchList.length + ' 只';
        document.getElementById('settings-list').innerHTML = watchList.map(s =>
            `<p>${s.symbol} - ${s.name}</p>`
        ).join('');
    } catch (e) {
        console.error('设置加载失败:', e);
    }
}