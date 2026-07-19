// ============================================
// API 调用模块 - Render 部署版
// ============================================

const API_BASE = '/api';

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

// 获取最新分析
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

// 获取历史
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

// 分析股票
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

// 刷新全部
async function refreshAll() {
    try {
        const resp = await fetch(`${API_BASE}/refresh`, { method: 'POST' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (e) {
        console.error('刷新失败:', e);
        return [];
    }
}

// 推文分析
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

// 等待
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
