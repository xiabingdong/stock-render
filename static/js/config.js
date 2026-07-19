// ============================================
// 股票分析系统配置
// ============================================
const CONFIG = {
    // Supabase 配置
    supabaseUrl: 'https://ztximeqaoetfqojfwoda.supabase.co',
    supabaseKey: 'sb_secret_tiV8_7PzqbDOpeIbUJW9xw_E4yBY35P',
    
    // 外部API Keys
    twelveDataKey: '***',
    alphaVantageKey: '***',
    finnnubKey: 'd9cp54hr01qh8vpj12igd9cp54hr01qh8vpj12j0',
    
    // 关注股票列表
    watchList: [
        { symbol: 'AAPL', name: 'Apple', direction: 'AI芯片收购预期' },
        { symbol: 'MSFT', name: 'Microsoft', direction: 'AI capex' },
        { symbol: 'INTC', name: 'Intel', direction: '底部信号' },
        { symbol: 'NVDA', name: 'NVIDIA', direction: '' },
        { symbol: 'LITE', name: 'Lumentum', direction: '底部信号' },
        { symbol: 'META', name: 'Meta', direction: 'AI capex' },
    ],
    
    // 大盘指数
    indices: [
        { symbol: 'SPY', name: 'S&P 500' },
        { symbol: 'QQQ', name: 'NASDAQ 100' },
        { symbol: 'DIA', name: 'Dow Jones' },
    ],
};
