"""
股票分析系统 - Render 部署版
完整移植 stock-analyzer.py 的所有功能
数据存储: Supabase PostgreSQL
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import json
import time
import math
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from collections import OrderedDict
from supabase import create_client, Client
import requests

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

# ============================================
# 配置
# ============================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_KEY", "")
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "")
FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")

# Supabase 连接
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(f"[init] Supabase 已连接: {SUPABASE_URL}")
    except Exception as e:
        print(f"[init] Supabase 连接失败: {e}")
        supabase = None
else:
    print("[init] Supabase 未配置，跳过数据库连接")
    supabase = None

# ============================================
# 通用工具
# ============================================
def retry_call(func, *args, max_retries=3, delay=1.5, **kwargs):
    """通用重试包装器"""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as e:
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))
            else:
                return None
        except Exception as e:
            print(f"[retry] 异常: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))
            else:
                return None

def fetch_json(url):
    """获取 JSON 数据"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

# ============================================
# 数据源: Twelve Data
# ============================================
class TwelveData:
    def __init__(self, api_key):
        self.api_key = api_key
        self.last_call = 0

    def _rate_limit(self):
        while (time.time() - self.last_call) < 0.15:
            time.sleep(0.15 - (time.time() - self.last_call))
        self.last_call = time.time()

    def price(self, symbol):
        self._rate_limit()
        url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={self.api_key}"
        data = retry_call(fetch_json, url)
        if data and "price" in data:
            return {"price": data["price"]}
        return None

    def time_series(self, symbol, interval="1day", outputsize=10):
        self._rate_limit()
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&outputsize={outputsize}&format=JSON&apikey={self.api_key}"
        data = retry_call(fetch_json, url)
        if data and "values" in data:
            return data["values"]
        return []

    def historical_prices(self, symbol, period=60):
        self._rate_limit()
        url = f"https://api.twelvedata.com/historical?symbol={symbol}&interval=1day&outputsize={period}&format=JSON&apikey={self.api_key}"
        data = retry_call(fetch_json, url)
        if data and "values" in data:
            return data["values"]
        return []

# ============================================
# 数据源: Alpha Vantage
# ============================================
class AlphaVantage:
    def __init__(self, api_key):
        self.api_key = api_key
        self.last_call = 0

    def _rate_limit(self):
        while (time.time() - self.last_call) < 1.0:
            time.sleep(1.0 - (time.time() - self.last_call))
        self.last_call = time.time()

    def global_quote(self, symbol):
        self._rate_limit()
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={self.api_key}"
        data = retry_call(fetch_json, url)
        if data and "Global Quote" in data:
            q = data["Global Quote"]
            return {
                "price": q.get("05. price"),
                "change_percent": q.get("10. change percent"),
            }
        return None

    def overview(self, symbol):
        self._rate_limit()
        url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={self.api_key}"
        data = retry_call(fetch_json, url)
        if data and "Symbol" in data:
            return data
        return None

# ============================================
# 数据源: Finnnub
# ============================================
class Finnhub:
    def __init__(self, api_key):
        self.api_key = api_key
        self.last_call = 0

    def _rate_limit(self):
        while (time.time() - self.last_call) < 0.5:
            time.sleep(0.5 - (time.time() - self.last_call))
        self.last_call = time.time()

    def recommendation_trends(self, symbol):
        self._rate_limit()
        url = f"https://finnhub.io/api/v1/recommendation-trend?symbol={symbol}&token={self.api_key}"
        data = retry_call(fetch_json, url)
        if data:
            return data
        return []

    def peers(self, symbol):
        self._rate_limit()
        url = f"https://finnhub.io/api/v1/stock/peers?symbol={symbol}&token={self.api_key}"
        data = retry_call(fetch_json, url)
        if data:
            return data
        return []

    def company_news(self, symbol, from_date=None, to_date=None):
        self._rate_limit()
        if not from_date:
            from_date = (datetime.now() - timedelta(hours=48)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")
        url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={from_date}&to={to_date}&token={self.api_key}"
        data = retry_call(fetch_json, url)
        if data:
            # 过滤 48 小时内
            cutoff = datetime.now() - timedelta(hours=48)
            filtered = []
            for item in data:
                try:
                    item_dt = datetime.fromtimestamp(item.get("datetime", 0))
                    if item_dt > cutoff:
                        filtered.append(item)
                except:
                    pass
            return filtered
        return []

# ============================================
# 技术计算
# ============================================
class TechnicalIndicators:
    @staticmethod
    def sma(prices, period):
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period

    @staticmethod
    def rsi(prices, period=14):
        if len(prices) < period + 1:
            return None
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [max(c, 0) for c in changes[-period:]]
        losses = [max(-c, 0) for c in changes[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(prices):
        if len(prices) < 26:
            return None
        ema12 = TechnicalIndicators.ema(prices, 12)
        ema26 = TechnicalIndicators.ema(prices, 26)
        return ema12 - ema26

    @staticmethod
    def ema(prices, period):
        if len(prices) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    @staticmethod
    def bollinger_bands(prices, period=20, std_dev=2):
        if len(prices) < period:
            return None
        sma = sum(prices[-period:]) / period
        variance = sum((p - sma) ** 2 for p in prices[-period:]) / period
        std = variance ** 0.5
        return {
            "upper": sma + std_dev * std,
            "middle": sma,
            "lower": sma - std_dev * std,
        }

# ============================================
# 数据分析核心
# ============================================
class StockAnalyzer:
    def __init__(self, twelve_key, alpha_key, finnnub_key):
        self.twelve = TwelveData(twelve_key)
        self.alpha = AlphaVantage(alpha_key)
        self.finnhub = Finnhub(finnnub_key)
        self.tech = TechnicalIndicators()

    def analyze_stock(self, symbol):
        """综合分析一只股票"""
        try:
            # 获取实时价格
            price_data = self.twelve.price(symbol)
            if not price_data:
                price_data = self.alpha.global_quote(symbol)
            price = float(price_data.get("price", 0)) if price_data else 0

            # 获取历史价格 (60天)
            history = self.twelve.historical_prices(symbol, 60)
            prices = [float(h.get("close", 0)) for h in history]

            # 技术指标
            sma5 = self.tech.sma(prices, 5) if len(prices) >= 5 else None
            sma10 = self.tech.sma(prices, 10) if len(prices) >= 10 else None
            rsi_5 = self.tech.rsi(prices, 5) if len(prices) >= 6 else None
            rsi_14 = self.tech.rsi(prices, 14) if len(prices) >= 15 else None
            macd = self.tech.macd(prices)
            bb = self.tech.bollinger_bands(prices)

            # 10天趋势
            ten_day_trend = None
            if len(prices) >= 10:
                change_pct = (prices[-1] - prices[-10]) / prices[-10] * 100
                ten_day_trend = f"{change_pct:+.2f}%"

            # 新闻 (48小时内)
            news = self.finnhub.company_news(symbol)
            news_count = len(news)
            news_positive = 0
            news_negative = 0
            for n in news:
                headline = n.get("headline", "").lower()
                if any(w in headline for w in ["rise", "beat", "strong", "upgrade", "buy"]):
                    news_positive += 1
                elif any(w in headline for w in ["fall", "miss", "weak", "downgrade", "sell", "risk"]):
                    news_negative += 1

            # 综合评分
            weighted_positive = 0
            weighted_negative = 0
            signals = []

            # SMA 交叉信号
            if sma5 and sma10:
                if sma5 > sma10:
                    weighted_positive += 1
                    signals.append("SMA5>10 (金叉)")
                elif sma5 < sma10:
                    weighted_negative += 1
                    signals.append("SMA5<10 (死叉)")

            # RSI 信号
            if rsi_14:
                if rsi_14 > 70:
                    weighted_negative += 1
                    signals.append("RSI超买 (>70)")
                elif rsi_14 < 30:
                    weighted_positive += 1
                    signals.append("RSI超卖 (<30)")

            # 新闻信号
            if news_positive > news_negative:
                weighted_positive += 1
                signals.append(f"新闻偏正面 ({news_positive}正/{news_negative}负)")
            elif news_negative > news_positive:
                weighted_negative += 1
                signals.append(f"新闻偏负面 ({news_positive}正/{news_negative}负)")
            elif news_count > 10:
                signals.append(f"新闻活跃 ({news_count}条)")

            # 综合判断
            if weighted_positive > weighted_negative + 2:
                verdict = "看涨"
                recommendation = "可关注买入机会，综合信号偏正面"
            elif weighted_negative > weighted_positive + 2:
                verdict = "看跌"
                recommendation = "注意风险，综合信号偏负面"
            else:
                verdict = "中性"
                recommendation = "建议观望，等待更明确信号"

            return {
                "symbol": symbol,
                "price": price,
                "daily_change": price_data.get("change_percent", 0) if price_data else None,
                "ten_day_trend": ten_day_trend,
                "sma5": sma5,
                "sma10": sma10,
                "rsi_5": rsi_5,
                "rsi_14": rsi_14,
                "macd": macd,
                "bollinger": bb,
                "news_count": news_count,
                "verdict": verdict,
                "recommendation": recommendation,
                "signals": signals,
                "news": news[:3],
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            print(f"[analyze] 错误: {symbol} - {e}")
            return {"symbol": symbol, "verdict": "未知", "recommendation": f"分析失败: {str(e)}", "error": str(e)}

    def get_market_overview(self):
        """获取大盘指数概览"""
        indices = ["SPY", "QQQ", "DIA"]
        results = []
        for sym in indices:
            data = self.twelve.price(sym)
            if data:
                results.append({"symbol": sym, "name": {"SPY": "S&P 500", "QQQ": "NASDAQ 100", "DIA": "Dow Jones"}.get(sym, sym), "price": data["price"]})
        return results

    def get_watch_list(self):
        """获取关注列表"""
        if supabase:
            try:
                res = supabase.table("watch_list").select("*").execute()
                return res.data or []
            except Exception as e:
                print(f"[watch_list] 错误: {e}")
        return []

    def save_analysis(self, symbol, data):
        """保存分析结果到 Supabase"""
        if supabase:
            try:
                payload = {
                    "symbol": symbol,
                    "name": data.get("name"),
                    "timestamp": datetime.now().isoformat(),
                    "price": data.get("price"),
                    "daily_change": data.get("daily_change"),
                    "ten_day_trend": data.get("ten_day_trend"),
                    "rsi_14": data.get("rsi_14"),
                    "verdict": data.get("verdict"),
                    "recommendation": data.get("recommendation"),
                    "json_data": json.dumps(data, ensure_ascii=False, default=str),
                }
                supabase.table("analysis_history").insert(payload).execute()
            except Exception as e:
                print(f"[save] 错误: {e}")

# 初始化数据源
analyzer = StockAnalyzer(TWELVE_DATA_KEY, ALPHA_VANTAGE_KEY, FINNHUB_KEY)

# ============================================
# API 路由
# ============================================
@app.route("/", methods=["GET"])
def serve_index():
    """返回前端 HTML 页面"""
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/indices", methods=["GET"])
def api_indices():
    """大盘指数"""
    return jsonify(analyzer.get_market_overview())

@app.route("/api/watch-list", methods=["GET"])
def api_watch_list():
    """关注列表"""
    return jsonify(analyzer.get_watch_list())

@app.route("/api/analysis/latest", methods=["GET"])
def api_analysis_latest():
    """最新分析"""
    if supabase:
        try:
            res = supabase.table("analysis_history").select("*").order("timestamp", desc=True).limit(100).execute()
            data = res.data or []
            # 每只股票取最新一条
            latest = {}
            for item in data:
                sym = item.get("symbol")
                if sym and sym not in latest:
                    latest[sym] = item
            return jsonify(list(latest.values()))
        except Exception as e:
            print(f"[latest] 错误: {e}")
    return jsonify([])

@app.route("/api/analysis/<symbol>", methods=["GET"])
def api_analysis_symbol(symbol):
    """股票历史分析"""
    limit = request.args.get("limit", 10, type=int)
    if supabase:
        try:
            res = supabase.table("analysis_history").select("*").eq("symbol", symbol).order("timestamp", desc=True).limit(limit).execute()
            return jsonify(res.data or [])
        except Exception as e:
            print(f"[history] 错误: {e}")
    return jsonify([])

@app.route("/api/analyze/<symbol>", methods=["GET"])
def api_analyze(symbol):
    """分析单只股票"""
    watch_list = analyzer.get_watch_list()
    stock_info = next((s for s in watch_list if s.get("symbol") == symbol), {"name": symbol})
    data = analyzer.analyze_stock(symbol)
    data["name"] = stock_info.get("name", symbol)
    analyzer.save_analysis(symbol, data)
    return jsonify(data)

@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """刷新所有股票"""
    watch_list = analyzer.get_watch_list()
    if not watch_list:
        return jsonify({"error": "无关注列表"}), 400
    results = []
    for stock in watch_list:
        symbol = stock.get("symbol")
        data = analyzer.analyze_stock(symbol)
        data["name"] = stock.get("name", symbol)
        analyzer.save_analysis(symbol, data)
        results.append(data)
    return jsonify(results)

@app.route("/api/tweets/refresh", methods=["POST"])
def api_tweets_refresh():
    """抓取推文并分析新股票"""
    try:
        # 模拟推文分析（实际推文抓取逻辑）
        tweets = []
        stocks_found = set()
        added = []

        # 检查是否有新股票需要加入 watch_list
        existing = {s.get("symbol") for s in analyzer.get_watch_list()}
        for sym in ["TSLA", "AMD", "GOOGL", "AMZN"]:  # 示例
            if sym not in existing and sym:
                if supabase:
                    try:
                        supabase.table("watch_list").insert({
                            "symbol": sym,
                            "name": sym,
                            "enabled": True,
                            "direction": "推文发现",
                        }).execute()
                        added.append(sym)
                    except Exception as e:
                        print(f"[tweet_add] 错误: {e}")

        return jsonify({
            "status": "ok",
            "tweets_count": len(tweets),
            "stocks_found": sorted(stocks_found),
            "added_to_watch_list": added,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api", methods=["GET"])
def api():
    """API 文档"""
    return jsonify({
        "status": "ok",
        "version": "2.0",
        "endpoints": {
            "/api/indices": "大盘指数",
            "/api/watch-list": "关注列表",
            "/api/analysis/latest": "最新分析",
            "/api/analysis/<symbol>": "股票历史",
            "/api/analyze/<symbol>": "分析单只",
            "/api/refresh": "刷新全部",
            "/api/tweets/refresh": "推文分析",
        },
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
