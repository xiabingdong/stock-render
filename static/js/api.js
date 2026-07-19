// ============================================
// 外部API调用 - 完整数据获取
// ============================================

// Worker 代理地址
const WORKER_URL = 'https://stock-api-proxy.xia-bd.workers.dev';

async function apiGet(path, params = '') {
    try {
        const url = `${WORKER_URL}/${path}?${params}`;
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const data = await response.json();
        return data;
    } catch (e) {
        console.error('API请求失败:', path, e);
        return null;
    }
}

// Twelve Data - 实时价格
async function getTwelveDataPrice(symbol) {
    return apiGet('twelve-data/price', `symbol=${symbol}`);
}

// Twelve Data - 历史数据 (60天)
async function getTwelveDataHistory(symbol, outputsize = 60) {
    const data = await apiGet('twelve-data/history', `symbol=${symbol}&outputsize=${outputsize}`);
    if (data && data.status === 'ok') {
        return data.values || [];
    }
    return [];
}

// Alpha Vantage - 涨跌幅
async function getAlphaVantageQuote(symbol) {
    const data = await apiGet('alpha-vantage/quote', `symbol=${symbol}`);
    if (data && data['Global Quote']) {
        return data['Global Quote'];
    }
    return null;
}

// Alpha Vantage - PE等基本面
async function getAlphaVantageOverview(symbol) {
    const data = await apiGet('alpha-vantage/overview', `symbol=${symbol}`);
    if (data && data.PERatio) {
        return data;
    }
    return null;
}

// Finnhub - 分析师评级
async function getFinnhubRecommendation(symbol) {
    const data = await apiGet('finnhub/recommendation', `symbol=${symbol}`);
    if (data && Array.isArray(data) && data.length > 0) {
        const last = data[data.length - 1];
        if (last) {
            const total = last.strong_buy + last.buy + last.hold + last.sell + last.strong_sell;
            const bull = last.strong_buy + last.buy;
            return {
                bull_pct: total > 0 ? (bull / total * 100) : null,
                total,
                strong_buy: last.strong_buy,
                buy: last.buy,
                hold: last.hold,
                sell: last.sell,
                strong_sell: last.strong_sell,
            };
        }
    }
    return null;
}

// Finnhub - 公司新闻
async function getFinnhubNews(symbol) {
    const today = new Date().toISOString().split('T')[0];
    const yesterday = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    const data = await apiGet('finnhub/news', `symbol=${symbol}&from=${yesterday}&to=${today}`);
    if (data && Array.isArray(data)) {
        return data;
    }
    return [];
}

// 计算RSI
function calculateRSI(closes, period = 14) {
    if (closes.length < period + 1) return null;
    
    const gains = [];
    const losses = [];
    
    for (let i = 1; i <= period; i++) {
        const change = closes[i-1] - closes[i];
        gains.push(Math.max(change, 0));
        losses.push(Math.max(-change, 0));
    }
    
    const avgGain = gains.reduce((a, b) => a + b, 0) / period;
    const avgLoss = losses.reduce((a, b) => a + b, 0) / period;
    
    if (avgLoss === 0) return 100;
    const rs = avgGain / avgLoss;
    return 100 - (100 / (1 + rs));
}

// 等待指定毫秒数（限流）
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// 分析单只股票 - 完整数据
async function analyzeStock(symbol, name, direction) {
    console.log('分析:', symbol);
    
    // 获取实时价格和历史数据 (Twelve Data)
    const [price, history] = await Promise.all([
        getTwelveDataPrice(symbol),
        getTwelveDataHistory(symbol, 60),
    ]);
    
    const priceVal = price ? parseFloat(price.price) : null;
    
    // 从历史数据计算技术指标
    const dailyChange = history.length >= 2 ? 
        ((parseFloat(history[0].close) - parseFloat(history[1].close)) / parseFloat(history[1].close)) * 100 : null;
    
    let tenDayTrend = null;
    let closes = [];
    if (history.length >= 10) {
        closes = history.slice(0, 10).map(h => parseFloat(h.close));
        tenDayTrend = ((closes[0] - closes[9]) / closes[9]) * 100;
    }
    
    const rsi14 = history.length >= 14 ? 
        calculateRSI(history.slice(0, 15).map(h => parseFloat(h.close))) : null;
    
    // MACD信号 (简化)
    let macdSignal = '中性';
    if (closes.length >= 12) {
        const avg5 = closes.slice(0, 5).reduce((a, b) => a + b, 0) / 5;
        const avg12 = closes.slice(0, 12).reduce((a, b) => a + b, 0) / 12;
        if (avg5 > avg12 * 1.01) macdSignal = '金叉';
        else if (avg5 < avg12 * 0.99) macdSignal = '死叉';
    }
    
    // 限流：Alpha Vantage 1次/秒
    await sleep(1100);
    const overview = await getAlphaVantageOverview(symbol);
    const pe = overview ? parseFloat(overview.PERatio) : null;
    
    // 限流
    await sleep(1100);
    const quote = await getAlphaVantageQuote(symbol);
    
    // 限流
    await sleep(200);
    const rec = await getFinnhubRecommendation(symbol);
    const bullPct = rec ? rec.bull_pct : null;
    
    // 限流
    await sleep(200);
    const news = await getFinnhubNews(symbol);
    const newsCount = news.length;
    
    // 计算加权分数
    let vp = 0, vn = 0;
    
    if (tenDayTrend) {
        if (tenDayTrend > 5) vp += 1.5;
        else if (tenDayTrend < -5) vn += 1.5;
    }
    
    if (dailyChange) {
        if (dailyChange > 0.5) vp += 1.0;
        else if (dailyChange < -0.5) vn += 1.0;
    }
    
    if (pe) {
        if (pe < 15) vp += 1.2;
        else if (pe > 50) vn += 1.2;
    }
    
    if (bullPct) {
        if (bullPct >= 60) vp += 1.5;
        else if (bullPct < 30) vn += 1.5;
    }
    
    if (rsi14) {
        if (rsi14 < 30) vp += 1.0;
        else if (rsi14 > 70) vn += 1.0;
    }
    
    if (macdSignal === '金叉') vp += 1.0;
    else if (macdSignal === '死叉') vn += 1.0;
    
    // 判断结论
    let verdict = '中性';
    if (vp > vn + 2) verdict = '看涨';
    else if (vn > vp + 2) verdict = '看跌';
    
    return {
        symbol,
        name,
        direction,
        price: priceVal,
        daily_change: dailyChange,
        ten_day_trend: tenDayTrend,
        weighted_positive: vp,
        weighted_negative: vn,
        verdict,
        pe_ratio: pe,
        rsi_14: rsi14,
        macd_signal: macdSignal,
        analyst_bull_pct: bullPct,
        news_count: newsCount,
        timestamp: new Date().toISOString(),
    };
}

// 获取大盘指数
async function getIndices() {
    const results = [];
    for (const idx of CONFIG.indices) {
        const price = await getTwelveDataPrice(idx.symbol);
        results.push({
            symbol: idx.symbol,
            name: idx.name,
            price: price ? parseFloat(price.price) : null,
        });
    }
    return results;
}

// 分析所有股票（串行，避免限流）
async function analyzeAllStocks() {
    const results = [];
    
    for (const stock of CONFIG.watchList) {
        const result = await analyzeStock(stock.symbol, stock.name, stock.direction);
        results.push(result);
        // 保存到数据库
        await saveAnalysis(
            result.symbol, result.name, result.price, result.daily_change,
            result.ten_day_trend, result.weighted_positive, result.weighted_negative,
            result.verdict, result.pe_ratio, result.rsi_14, result.macd_signal,
            result.analyst_bull_pct, result.news_count, JSON.stringify(result)
        );
    }
    
    // 清理旧数据
    await cleanupOldData();
    
    return results;
}
