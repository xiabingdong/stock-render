// ============================================
// Supabase 数据库操作
// ============================================
let supabaseClient = null;

function initSupabase() {
    return new Promise((resolve, reject) => {
        if (window.supabase) {
            const client = window.supabase.createClient(CONFIG.supabaseUrl, CONFIG.supabaseKey);
            supabaseClient = client;
            resolve(client);
        } else {
            setTimeout(() => {
                if (window.supabase) {
                    const client = window.supabase.createClient(CONFIG.supabaseUrl, CONFIG.supabaseKey);
                    supabaseClient = client;
                    resolve(client);
                } else {
                    reject(new Error('Supabase SDK 加载失败'));
                }
            }, 1000);
        }
    });
}

// 保存分析记录
async function saveAnalysis(symbol, name, price, daily_change, ten_day_trend,
                            weighted_positive, weighted_negative, verdict,
                            pe_ratio, rsi_14, macd_signal, analyst_bull_pct, news_count, json_data) {
    if (!supabaseClient) return;
    
    const { error } = await supabaseClient
        .from('analysis_history')
        .insert([{
            symbol, name, price, daily_change, ten_day_trend,
            weighted_positive, weighted_negative, verdict,
            pe_ratio, rsi_14, macd_signal, analyst_bull_pct, news_count, json_data
        }]);
    
    if (error) console.error('保存失败:', error);
}

// 获取所有股票的最新分析记录（每张表取最新一条）
async function getLatestAnalysis() {
    if (!supabaseClient) return [];
    
    const { data, error } = await supabaseClient
        .from('analysis_history')
        .select('*')
        .order('timestamp', { ascending: false })
        .limit(100);
    
    if (error) console.error('获取失败:', error);
    
    if (!data || data.length === 0) return [];
    
    // 按symbol分组，取每个symbol的最新一条
    const latest = {};
    for (const item of data) {
        if (!latest[item.symbol] || new Date(item.timestamp) > new Date(latest[item.symbol].timestamp)) {
            latest[item.symbol] = item;
        }
    }
    
    return Object.values(latest);
}

// 获取单个股票的历史分析
async function getHistory(symbol, limit = 10) {
    if (!supabaseClient) return [];
    
    const { data, error } = await supabaseClient
        .from('analysis_history')
        .select('*')
        .eq('symbol', symbol)
        .order('timestamp', { ascending: false })
        .limit(limit);
    
    if (error) console.error('获取历史失败:', error);
    return data || [];
}

// 获取关注列表
async function getWatchList() {
    if (!supabaseClient) return CONFIG.watchList;
    
    const { data, error } = await supabaseClient
        .from('watch_list')
        .select('*')
        .eq('enabled', true)
        .order('symbol');
    
    if (error) console.error('获取关注列表失败:', error);
    return data || CONFIG.watchList;
}

// 添加关注股票
async function addWatch(symbol, name, direction) {
    if (!supabaseClient) return;
    
    const { error } = await supabaseClient
        .from('watch_list')
        .upsert([{ symbol, name, direction, enabled: true }]);
    
    if (error) console.error('添加失败:', error);
}

// 删除关注股票
async function removeWatch(symbol) {
    if (!supabaseClient) return;
    
    const { error } = await supabaseClient
        .from('watch_list')
        .update({ enabled: false })
        .eq('symbol', symbol);
    
    if (error) console.error('删除失败:', error);
}

// 删除旧的分析记录（保留最近100条）
async function cleanupOldData() {
    if (!supabaseClient) return;
    
    const { error } = await supabaseClient
        .from('analysis_history')
        .delete()
        .not('id', 'in', (await supabaseClient
            .from('analysis_history')
            .select('id')
            .order('timestamp', { ascending: false })
            .limit(100)
            .then(r => r.data || [])
        ).map(i => i.id));
    
    if (error) console.error('清理失败:', error);
}
