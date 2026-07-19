// ============================================
// 前端应用逻辑
// ============================================

// 当前分析数据
let currentData = {
    indices: [],
    stocks: [],
    lastUpdate: null,
};

// 初始化应用
document.addEventListener('DOMContentLoaded', async () => {
    // 初始化 Supabase
    await initSupabase();
    
    // 加载数据
    await loadIndices();
    await loadStocks();
    
    // 设置刷新按钮
    document.getElementById('refresh-btn')?.addEventListener('click', async () => {
        await refreshAll();
    });
});

// 加载大盘指数
async function loadIndices() {
    showLoading('indices');
    
    try {
        const indices = await getIndices();
        currentData.indices = indices;
        renderIndices(indices);
        console.log('大盘指数加载成功:', indices);
    } catch (e) {
        console.error('大盘指数加载失败:', e);
        showError('indices', '大盘指数加载失败: ' + (e.message || '未知错误'));
    }
}

// 加载股票列表
async function loadStocks() {
    showLoading('stocks');
    
    try {
        const stocks = await analyzeAllStocks();
        currentData.stocks = stocks;
        currentData.lastUpdate = new Date().toISOString();
        renderStocks(stocks);
        updateUpdateTime();
        console.log('股票数据加载成功:', stocks.length, '只');
    } catch (e) {
        console.error('股票数据加载失败:', e);
        showError('stocks', '股票数据加载失败: ' + (e.message || '未知错误'));
    }
}

// 刷新全部数据
async function refreshAll() {
    showLoading('indices');
    showLoading('stocks');
    
    try {
        await Promise.all([loadIndices(), loadStocks()]);
        showToast('✅ 数据已刷新');
    } catch (e) {
        showToast('❌ 刷新失败');
    }
}

// 渲染大盘指数
function renderIndices(indices) {
    const container = document.getElementById('indices');
    if (!container) return;
    
    container.innerHTML = `
        <h2>🏛️ 大盘指数</h2>
        <div class="indices-grid">
            ${indices.map(idx => `
                <div class="index-card">
                    <span class="index-name">${idx.name}</span>
                    <span class="index-price">
                        $${idx.price?.toFixed(2) || '--'}
                    </span>
                </div>
            `).join('')}
        </div>
    `;
}

// 渲染股票列表
function renderStocks(stocks) {
    const container = document.getElementById('stocks');
    if (!container) return;
    
    container.innerHTML = `
        <h2>📊 关注股票</h2>
        <div class="stocks-list">
            ${stocks.map(stock => `
                <div class="stock-card" onclick="showDetail('${stock.symbol}')">
                    <div class="stock-header">
                        <span class="stock-symbol">${stock.symbol}</span>
                        <span class="stock-name">${stock.name}</span>
                        <span class="verdict-badge ${getVerdictClass(stock.verdict)}">${stock.verdict}</span>
                    </div>
                    <div class="stock-body">
                        <div class="price-row">
                            <span class="stock-price">$${stock.price?.toFixed(2) || '--'}</span>
                            <span class="daily-change ${stock.daily_change >= 0 ? 'up' : 'down'}">
                                ${stock.daily_change >= 0 ? '▲' : '▼'} ${Math.abs(stock.daily_change).toFixed(2)}%
                            </span>
                        </div>
                        <div class="stats-row">
                            <span>10天: ${stock.ten_day_trend ? (stock.ten_day_trend >= 0 ? '+' : '') + stock.ten_day_trend.toFixed(1) + '%' : '--'}</span>
                            <span>RSI: ${stock.rsi_14?.toFixed(1) || '--'}</span>
                            <span>MACD: ${stock.macd_signal}</span>
                        </div>
                        <div class="signal-row">
                            <span>正: +${stock.weighted_positive.toFixed(1)}</span>
                            <span>负: -${stock.weighted_negative.toFixed(1)}</span>
                        </div>
                        ${stock.direction ? `<div class="direction-tag">${stock.direction}</div>` : ''}
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

// 显示股票详情
function showDetail(symbol) {
    const stock = currentData.stocks.find(s => s.symbol === symbol);
    if (!stock) return;
    
    const modal = document.getElementById('detail-modal');
    const content = document.getElementById('detail-content');
    
    content.innerHTML = `
        <h2>${stock.symbol} - ${stock.name}</h2>
        
        <div class="detail-section">
            <h3>价格信息</h3>
            <p>当前价: <strong>$${stock.price?.toFixed(2) || '--'}</strong></p>
            <p>今日涨跌: <span class="${stock.daily_change >= 0 ? 'up' : 'down'}">${stock.daily_change >= 0 ? '+' : ''}${stock.daily_change?.toFixed(2) || '--'}%</span></p>
            <p>10天趋势: ${stock.ten_day_trend ? (stock.ten_day_trend >= 0 ? '+' : '') + stock.ten_day_trend.toFixed(2) + '%' : '--'}</p>
        </div>
        
        <div class="detail-section">
            <h3>技术指标</h3>
            <p>PE: ${stock.pe_ratio?.toFixed(1) || '--'}</p>
            <p>RSI(14): ${stock.rsi_14?.toFixed(1) || '--'}</p>
            <p>MACD: ${stock.macd_signal}</p>
        </div>
        
        <div class="detail-section">
            <h3>分析师评级</h3>
            <p>看涨比例: ${stock.analyst_bull_pct?.toFixed(0) || '--'}%</p>
            <p>新闻数量: ${stock.news_count} 条</p>
        </div>
        
        <div class="detail-section">
            <h3>综合判断</h3>
            <p class="verdict-large ${getVerdictClass(stock.verdict)}">${stock.verdict}</p>
            <p>正面: +${stock.weighted_positive.toFixed(1)} | 负面: -${stock.weighted_negative.toFixed(1)}</p>
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
    const el = document.getElementById('update-time');
    if (el && currentData.lastUpdate) {
        el.textContent = new Date(currentData.lastUpdate).toLocaleString('zh-CN');
    }
    
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

// 显示提示
function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

// 切换标签页
function showTab(tab, btn) {
    // 隐藏所有页面
    document.getElementById('page-history').style.display = 'none';
    document.getElementById('page-settings').style.display = 'none';
    document.getElementById('indices').style.display = '';
    document.getElementById('stocks').style.display = '';
    
    // 显示选中页面
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
    
    // 更新标签状态
    document.querySelectorAll('.tab-item').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
}

// 加载历史
async function loadHistory() {
    const container = document.getElementById('history-content');
    container.innerHTML = '<div class="loading">⏳ 加载中...</div>';
    
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
}

// 加载设置
function loadSettings() {
    document.getElementById('settings-count').textContent = CONFIG.watchList.length;
}
