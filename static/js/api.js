// ============================================
// ============================================
// API 调用模块 - Render 部署版
// ============================================

// API_BASE 已在 config.js 中定义，这里不再重复声明
// Flask 后端 API（主要数据源）
// ============================================

// 获取大盘指数
async function getIndices() {
    try {
        const resp = await fetch(`${API_BASE}/indices`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (e) {
        console.error('获取大盘指数失败:', e);
        return [];
    }
}

// 获取关注列表
async function getWatchList() {
    try {
        const resp = await fetch(`${API_BASE}/watch-list`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (e) {
        console.error('获取关注列表失败:', e);
        return [];
    }
}

// 获取最新分析（从数据库）
async function getLatestAnalysis() {
    try {
        const resp = await fetch(`${API_BASE}/analysis/latest`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (e) {
        console.error('获取最新分析失败:', e);
        return [];
    }
}

// 获取单个股票历史
async function getStockHistory(symbol, limit = 10) {
    try {
        const resp = await fetch(`${API_BASE}/analysis/${symbol}?limit=${limit}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (e) {
        console.error('获取历史失败:', e);
        return [];
    }
}

// 分析单只股票（Flask 后端调外部 API）
async function analyzeStock(symbol) {
    try {
        const resp = await fetch(`${API_BASE}/analyze/${symbol}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (e) {
        console.error('分析股票失败:', e);
        return null;
    }
}

// 刷新所有股票（逐个GET调用，避免POST超时）
async function refreshAll() {
    try {
        const watchList = await getWatchList();
        if (!watchList || watchList.length === 0) {
            return [];
        }
        // 逐个分析，并行请求
        const symbols = watchList.map(s => s.symbol);
        const promises = symbols.map(symbol => analyzeStock(symbol));
        const results = await Promise.all(promises);
        return results.filter(r => r !== null);
    } catch (e) {
        console.error('刷新失败:', e);
        return [];
    }
}

// 抓取推文并分析
async function refreshTweets() {
    try {
        const resp = await fetch(`${API_BASE}/tweets/refresh`, { method: 'POST' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (e) {
        console.error('推文分析失败:', e);
        return null;
    }
}

// 移除股票（从关注列表移除，不删历史）
async function removeStock(symbol) {
    try {
        const resp = await fetch(`${API_BASE}/watch-list/${symbol}/remove`, { method: 'POST' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        await loadStocks();
        showToast(`✅ 已移除 ${symbol}`);
    } catch (e) {
        console.error('移除失败:', e);
        showToast('❌ 移除失败');
    }
}

// ============================================
// 等待
// ============================================
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
