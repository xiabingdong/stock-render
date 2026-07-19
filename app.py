"""
股票分析系统 - Render 部署版
完整移植 stock-analyzer.py 的所有功能
数据存储: Supabase PostgreSQL
"""

from flask import Flask, jsonify, request
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

app = Flask(__name__)
CORS(app)

# ============================================
# 配置
# ============================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_KEY", "")
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "")
FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# ============================================
# 初始化 Supabase
# ============================================
if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None

# ============================================
# 通用工具
# ============================================
def retry_call(func, max_retries=3, delay=1.5, *args, **kwargs):
    """通用重试包装器"""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as e:
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))
            else:
                return None
        except Exception:
            return None
    return None

def fetch_json(url, headers=None, timeout=15):
    """获取 JSON 数据"""
    if headers is None:
        headers = HEADERS
    try:
        req = urllib.request.Request(url, headers=headers)
        data = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        return data
    except Exception:
        return None

# ============================================
# 技术指标计算类
# ============================================
class TechnicalIndicators:
    @staticmethod
    def sma(closes, period):
        if len(closes) < period:
            return None
        return sum(closes[:period]) / period
    
    @staticmethod
    def rsi(closes, period=14):
        if len(closes) < period + 1:
            return None
        gains = []
        losses = []
        for i in range(1, period + 1):
            change = closes[i-1] - closes[i]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def macd(closes, fast=12, slow=26, signal=9):
        if len(closes) < slow:
            return None
        rev = closes[::-1]
        def ema(data, period):
            multiplier = 2 / (period + 1)
            ema_val = sum(data[:period]) / period
            for i in range(period, len(data)):
                ema_val = data[i] * multiplier + ema_val * (1 - multiplier)
            return ema_val
        
        ema_fast = ema(rev, fast)
        ema_slow = ema(rev, slow)
        macd_line = ema_fast - ema_slow
        
        macd_history = []
        for i in range(slow, len(rev) + 1):
            chunk = rev[:i]
            ef = ema(chunk, fast)
            es = ema(chunk, slow)
            macd_history.append(ef - es)
        
        if len(macd_history) >= signal:
            signal_line = ema(macd_history, signal)
            histogram = macd_line - signal_line
            return {"macd": round(macd_line, 4), "signal": round(signal_line, 4), 
                    "histogram": round(histogram, 4)}
        return {"macd": round(macd_line, 4), "signal": None, "histogram": None}
    
    @staticmethod
    def bollinger_bands(closes, period=20, std_dev=2):
        if len(closes) < period:
            return None
        middle = sum(closes[:period]) / period
        variance = sum((x - middle) ** 2 for x in closes[:period]) / period
        std = math.sqrt(variance)
        return {"upper": round(middle + std_dev * std, 2), "middle": round(middle, 2), 
                "lower": round(middle - std_dev * std, 2)}
    
    @staticmethod
    def volume_avg(history, period=5):
        volumes = []
        for h in history[:period]:
            try:
                v = h.get("volume", 0)
                if v and isinstance(v, (int, float)):
                    volumes.append(int(v))
                elif v and isinstance(v, str):
                    volumes.append(int(v))
            except:
                pass
        return sum(volumes) / len(volumes) if volumes else None

# ============================================
# API 数据获取类
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
        if data and data.get("status") == "ok":
            return data.get("values", [])
        return []
    
    def quote(self, symbol):
        self._rate_limit()
        url = f"https://api.twelvedata.com/quote?symbol={symbol}&apikey={self.api_key}"
        return retry_call(fetch_json, url)

class AlphaVantage:
    def __init__(self, api_key):
        self.api_key = api_key
    
    def global_quote(self, symbol):
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={self.api_key}"
        data = retry_call(fetch_json, url)
        if data and "Global Quote" in data:
            return data["Global Quote"]
        return None
    
    def time_series_daily(self, symbol):
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={self.api_key}"
        data = retry_call(fetch_json, url)
        if data and "Time Series (Daily)" in data:
            return data["Time Series (Daily)"]
        return None
    
    def overview(self, symbol):
        url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={self.api_key}"
        return retry_call(fetch_json, url)
    
    def sector(self, symbol):
        url = f"https://www.alphavantage.co/query?function=SECTOR&symbol={symbol}&apikey={self.api_key}"
        return retry_call(fetch_json, url)
    
    def currency_exchange_rate(self, from_currency="USD", to_currency="CNY"):
        url = f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency={from_currency}&to_currency={to_currency}&apikey={self.api_key}"
        data = retry_call(fetch_json, url)
        if data and "Realtime Currency Exchange Rate" in data:
            return data["Realtime Currency Exchange Rate"]
        return None
    
    def income_statement(self, symbol):
        url = f"https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={symbol}&apikey={self.api_key}"
        return retry_call(fetch_json, url)
    
    def balance_sheet(self, symbol):
        url = f"https://www.alphavantage.co/query?function=BALANCE_SHEET&symbol={symbol}&apikey={self.api_key}"
        return retry_call(fetch_json, url)
    
    def cash_flow(self, symbol):
        url = f"https://www.alphavantage.co/query?function=CASH_FLOW&symbol={symbol}&apikey={self.api_key}"
        return retry_call(fetch_json, url)

class Finnhub:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://finnhub.io/api/v1"
    
    def quote(self, symbol):
        url = f"{self.base_url}/quote?symbol={symbol}&token={self.api_key}"
        return retry_call(fetch_json, url)
    
    def company_news(self, symbol, from_date=None, to_date=None):
        if not from_date:
            # 只获取48小时内的新闻
            from_date = (datetime.now() - timedelta(hours=48)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")
        url = f"{self.base_url}/company-news?symbol={symbol}&from={from_date}&to={to_date}&token={self.api_key}"
        data = retry_call(fetch_json, url)
        if data and isinstance(data, list):
            # 再过滤一次：只保留48小时内的新闻
            cutoff = datetime.now() - timedelta(hours=48)
            fresh_news = []
            for item in data:
                try:
                    pub_time = datetime.fromtimestamp(item.get("datetime", 0))
                    if pub_time >= cutoff:
                        fresh_news.append(item)
                except (TypeError, ValueError):
                    pass
            return fresh_news
        return []
    
    def recommendation(self, symbol, from_date=None, to_date=None):
        if not from_date:
            from_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")
        url = f"{self.base_url}/stock/recommendation?symbol={symbol}&from={from_date}&to={to_date}&token={self.api_key}"
        data = retry_call(fetch_json, url)
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return None
    
    def peers(self, symbol):
        url = f"{self.base_url}/stock/peers?symbol={symbol}&token={self.api_key}"
        data = retry_call(fetch_json, url)
        return data if isinstance(data, list) else []
    
    def eps_surprises(self, symbol):
        url = f"{self.base_url}/stock/eps-surprises?symbol={symbol}&token={self.api_key}"
        return retry_call(fetch_json, url)

# ============================================
# 综合股票分析器
# ============================================
class StockAnalyzer:
    def __init__(self):
        self.twelve = TwelveData(TWELVE_DATA_KEY)
        self.alpha = AlphaVantage(ALPHA_VANTAGE_KEY)
        self.finnhub = Finnhub(FINNHUB_KEY)
        self.indicators = TechnicalIndicators()
    
    def get_market_overview(self):
        """获取大盘指数概况"""
        indices = [
            ("SPY", "S&P 500"),
            ("QQQ", "NASDAQ 100"),
            ("DIA", "Dow Jones"),
        ]
        results = []
        for symbol, name in indices:
            price_data = self.twelve.price(symbol)
            price = price_data.get("price", "N/A") if price_data else None
            results.append({"symbol": symbol, "name": name, "price": price})
            self.twelve._rate_limit()
        return results
    
    def _analyze_stock(self, symbol, tweet_direction, twelve_quote, alpha_quote,
                        history, overview, rec, news, twelve_quote_detail):
        """综合分析逻辑"""
        WEIGHTS = {
            "trend": 1.5, "daily_change": 1.0, "analyst": 1.5, "tweet": 0.5,
            "news": 0.8, "pe": 1.2, "peer": 0.5, "rsi5": 1.0, "rsi14": 1.2,
            "macd": 1.2, "ma": 1.0, "volume": 0.5, "bollinger": 0.8,
        }
        signals = []
        
        if history:
            closes = [float(r.get("close", 0)) for r in history if r.get("close")]
            if len(closes) >= 2:
                latest = closes[0]
                earliest = closes[-1]
                pct_change = (latest - earliest) / earliest * 100
                if pct_change > 10:
                    signals.append(("📈", f"10天涨幅超10%", "正", WEIGHTS["trend"]))
                elif pct_change > 5:
                    signals.append(("📈", f"10天上涨{pct_change:.1f}%", "正", WEIGHTS["trend"]))
                elif pct_change < -10:
                    signals.append(("📉", f"10天跌幅超10% ({pct_change:.1f}%)", "负", WEIGHTS["trend"]))
                elif pct_change < -5:
                    signals.append(("📉", f"10天下跌{abs(pct_change):.1f}%", "负", WEIGHTS["trend"]))
                
                sma5 = self.indicators.sma(closes, 5)
                sma10 = self.indicators.sma(closes, 10)
                if sma5 and sma10:
                    if sma5 > sma10 * 1.02:
                        signals.append(("⚡", f"5日均线金叉10日均线 (SMA5={sma5:.1f}, SMA10={sma10:.1f})", "正", WEIGHTS["ma"]))
                    elif sma5 < sma10 * 0.98:
                        signals.append(("⚡", f"5日均线死叉10日均线 (SMA5={sma5:.1f}, SMA10={sma10:.1f})", "负", WEIGHTS["ma"]))
                
                if len(closes) >= 6:
                    rsi5 = self.indicators.rsi(closes, 5)
                    if rsi5:
                        if rsi5 > 80:
                            signals.append(("🔴", f"RSI(5)={rsi5:.1f} 超买", "负", WEIGHTS["rsi5"]))
                        elif rsi5 > 70:
                            signals.append(("🟡", f"RSI(5)={rsi5:.1f} 偏高", "负", WEIGHTS["rsi5"]))
                        elif rsi5 < 20:
                            signals.append(("🟢", f"RSI(5)={rsi5:.1f} 超卖", "正", WEIGHTS["rsi5"]))
                        elif rsi5 < 30:
                            signals.append(("🔵", f"RSI(5)={rsi5:.1f} 偏低", "正", WEIGHTS["rsi5"]))
                
                if len(closes) >= 15:
                    rsi14 = self.indicators.rsi(closes, 14)
                    if rsi14:
                        if rsi14 > 70:
                            signals.append(("🔴", f"RSI(14)={rsi14:.1f} 超买", "负", WEIGHTS["rsi14"]))
                        elif rsi14 < 30:
                            signals.append(("🟢", f"RSI(14)={rsi14:.1f} 超卖", "正", WEIGHTS["rsi14"]))
                
                if len(closes) >= 26:
                    macd_result = self.indicators.macd(closes, 12, 26, 9)
                    if macd_result and macd_result.get("signal") is not None:
                        if macd_result['macd'] > macd_result['signal'] and macd_result['histogram'] > 0:
                            signals.append(("📈", f"MACD金叉 ({macd_result['macd']:.2f}/{macd_result['signal']:.2f})", "正", WEIGHTS["macd"]))
                        elif macd_result['macd'] < macd_result['signal'] and macd_result['histogram'] < 0:
                            signals.append(("📉", f"MACD死叉 ({macd_result['macd']:.2f}/{macd_result['signal']:.2f})", "负", WEIGHTS["macd"]))
                        elif macd_result['macd'] > 0:
                            signals.append(("🟢", "MACD在零轴上方，中期偏多", "正", WEIGHTS["macd"]))
                        else:
                            signals.append(("🔴", "MACD在零轴下方，中期偏空", "负", WEIGHTS["macd"]))
                
                avg_volume = self.indicators.volume_avg(history, 5)
                if avg_volume:
                    latest_volume = history[0].get("volume", 0)
                    try:
                        lv = int(latest_volume)
                        av = int(avg_volume)
                        if lv > av * 2:
                            signals.append(("📊", f"成交量暴增 (是平均的{lv/av:.1f}倍)", "提示", WEIGHTS["volume"]))
                    except:
                        pass
                
                if len(closes) >= 20:
                    bb = self.indicators.bollinger_bands(closes, 20, 2)
                    if bb:
                        current = closes[0]
                        if current > bb['upper']:
                            signals.append(("🔴", f"布林带上轨突破 (当前${current:.1f} > 上轨${bb['upper']:.1f})", "负", WEIGHTS["bollinger"]))
                        elif current < bb['lower']:
                            signals.append(("🟢", f"布林带下轨突破 (当前${current:.1f} < 下轨${bb['lower']:.1f})", "正", WEIGHTS["bollinger"]))
                        elif bb['middle'] < current < bb['upper']:
                            signals.append(("🟡", f"布林带偏强 (上轨${bb['upper']:.1f})", "正", WEIGHTS["bollinger"]))
                        elif bb['lower'] < current < bb['middle']:
                            signals.append(("🔵", f"布林带偏弱 (下轨${bb['lower']:.1f})", "负", WEIGHTS["bollinger"]))
        
        today_change = None
        if alpha_quote:
            try:
                today_change = float(alpha_quote.get("10. change percent", "0").replace("%", ""))
            except:
                pass
        if today_change is not None:
            if today_change > 2:
                signals.append(("📈", f"今日大涨{today_change:.1f}%", "正", WEIGHTS["daily_change"]))
            elif today_change > 0.5:
                signals.append(("✅", f"今日上涨{today_change:.1f}%", "正", WEIGHTS["daily_change"]))
            elif today_change < -2:
                signals.append(("📉", f"今日大跌{abs(today_change):.1f}%", "负", WEIGHTS["daily_change"]))
            elif today_change < -0.5:
                signals.append(("⚠️", f"今日下跌{abs(today_change):.1f}%", "负", WEIGHTS["daily_change"]))
        
        if rec:
            sb = rec.get("strong_buy", 0)
            b = rec.get("buy", 0)
            h = rec.get("hold", 0)
            s = rec.get("sell", 0)
            ss = rec.get("strong_sell", 0)
            total = sb + b + h + s + ss
            if total > 0:
                bull_pct = (sb + b) / total * 100
                bear_pct = (s + ss) / total * 100
                if bull_pct >= 70:
                    signals.append(("👍", f"分析师强烈看涨 ({bull_pct:.0f}%)", "正", WEIGHTS["analyst"]))
                elif bull_pct >= 50:
                    signals.append(("👍", f"分析师偏看涨 ({bull_pct:.0f}%)", "正", WEIGHTS["analyst"]))
                elif bear_pct >= 30:
                    signals.append(("👎", f"分析师看跌 ({bear_pct:.0f}%)", "负", WEIGHTS["analyst"]))
                else:
                    signals.append(("➡️", "分析师中性", "中", WEIGHTS["analyst"]))
        
        if tweet_direction:
            if "底部" in tweet_direction:
                signals.append(("💡", f"推文判断: {tweet_direction}", "提示", WEIGHTS["tweet"]))
            elif "涨价" in tweet_direction or "上涨" in tweet_direction:
                signals.append(("💡", f"推文看多: {tweet_direction}", "正", WEIGHTS["tweet"]))
            elif "估值" in tweet_direction or "跌" in tweet_direction:
                signals.append(("💡", f"推文看空: {tweet_direction}", "负", WEIGHTS["tweet"]))
            else:
                signals.append(("💡", f"推文提及: {tweet_direction}", "中", WEIGHTS["tweet"]))
        
        if news and len(news) > 0:
            recent_headlines = [n.get("headline", "").lower() for n in news[:5]]
            positive_words = ["rally", "upgrade", "beat", "surge", "outperform", "record", "bullish"]
            negative_words = ["crash", "plunge", "downgrade", "miss", "fall", "risk", "concern"]
            pos_count = sum(1 for h in recent_headlines for w in positive_words if w in h)
            neg_count = sum(1 for h in recent_headlines for w in negative_words if w in h)
            if pos_count > neg_count + 1:
                signals.append(("📰", f"新闻偏正面 ({pos_count}+/{neg_count}-)", "正", WEIGHTS["news"]))
            elif neg_count > pos_count + 1:
                signals.append(("📰", f"新闻偏负面 ({neg_count}+/{pos_count}-)", "负", WEIGHTS["news"]))
            elif len(news) > 10:
                signals.append(("📰", f"新闻活跃 ({len(news)}条)", "中", WEIGHTS["news"]))
        
        if overview:
            pe = overview.get("PERatio")
            try:
                pe_val = float(pe)
                if pe_val > 50:
                    signals.append(("💰", f"PE较高 ({pe_val})，注意估值风险", "负", WEIGHTS["pe"]))
                elif pe_val > 30:
                    signals.append(("💰", f"PE中等 ({pe_val})", "中", WEIGHTS["pe"]))
                elif pe_val > 15:
                    signals.append(("💰", f"PE合理 ({pe_val})", "正", WEIGHTS["pe"]))
                elif pe_val > 0:
                    signals.append(("💰", f"PE较低 ({pe_val})，可能被低估", "正", WEIGHTS["pe"]))
                else:
                    signals.append(("💰", "PE为负（亏损），需谨慎", "负", WEIGHTS["pe"]))
            except:
                pass
        
        peers = self.finnhub.peers(symbol)
        if peers and len(peers) > 1:
            peer_prices = []
            for peer in peers[:5]:
                p = self.twelve.price(peer)
                if p:
                    try:
                        peer_prices.append(float(p.get("price", 0)))
                    except:
                        pass
            if peer_prices:
                self.twelve._rate_limit()
                own_price = None
                if twelve_quote:
                    try:
                        own_price = float(twelve_quote.get("price", 0))
                    except:
                        pass
                if own_price and peer_prices:
                    avg_peer = sum(peer_prices) / len(peer_prices)
                    if own_price > avg_peer * 1.3:
                        signals.append(("🔄", f"相对同类偏高", "负", WEIGHTS["peer"]))
                    elif own_price < avg_peer * 0.7:
                        signals.append(("🔄", f"相对同类偏低", "正", WEIGHTS["peer"]))
        
        weighted_positive = 0
        weighted_negative = 0
        weighted_neutral = 0
        info_signals = []
        
        for emoji, desc, strength, weight in signals:
            if strength == "正":
                weighted_positive += weight
            elif strength == "负":
                weighted_negative += weight
            elif strength == "中":
                weighted_neutral += weight
            else:
                info_signals.append((emoji, desc))
        
        if weighted_positive > weighted_negative + 2:
            verdict = "看涨"
            recommendation = "可关注买入机会，综合信号偏正面"
        elif weighted_negative > weighted_positive + 2:
            verdict = "看跌"
            recommendation = "建议观望，综合信号偏负面，可考虑减仓"
        else:
            verdict = "中性"
            recommendation = "多空信号相当，建议观望"

        # 如果只有1-2个信号，降低确定性
        if len(signals) <= 2:
            recommendation = "数据不足，仅供参考"

        return {
            "verdict": verdict,
            "recommendation": recommendation,
            "weighted_positive": weighted_positive,
            "weighted_negative": weighted_negative,
            "weighted_neutral": weighted_neutral,
            "signals": signals,
            "info_signals": info_signals,
        }
    
    def analyze(self, symbol, tweet_direction=None):
        """综合分析"""
        print(f"📊 综合分析: {symbol}")
        
        twelve_quote = self.twelve.price(symbol)
        alpha_quote = self.alpha.global_quote(symbol)
        finnhub_quote = self.finnhub.quote(symbol)
        
        history = self.twelve.time_series(symbol, "1day", 60)
        
        time.sleep(1.1)
        overview = self.alpha.overview(symbol)
        time.sleep(1.1)
        sector = self.alpha.sector(symbol)
        time.sleep(0.2)
        rec = self.finnhub.recommendation(symbol)
        time.sleep(0.2)
        news = self.finnhub.company_news(symbol)
        time.sleep(0.2)
        peers = self.finnhub.peers(symbol)
        time.sleep(0.2)
        eps_surprises = self.finnhub.eps_surprises(symbol)
        
        if history:
            closes = [float(r.get("close", 0)) for r in history if r.get("close")]
        else:
            closes = []
        
        # 技术指标
        sma5 = self.indicators.sma(closes, 5) if len(closes) >= 5 else None
        sma10 = self.indicators.sma(closes, 10) if len(closes) >= 10 else None
        rsi5 = self.indicators.rsi(closes, 5) if len(closes) >= 6 else None
        rsi14 = self.indicators.rsi(closes, 14) if len(closes) >= 15 else None
        macd = self.indicators.macd(closes, 12, 26, 9) if len(closes) >= 26 else None
        bb = self.indicators.bollinger_bands(closes, 20, 2) if len(closes) >= 20 else None
        avg_volume = self.indicators.volume_avg(history, 5) if history else None
        
        # 今日涨跌
        today_change = None
        if alpha_quote:
            try:
                today_change = float(alpha_quote.get("10. change percent", "0").replace("%", ""))
            except:
                pass
        
        # 10天趋势
        ten_day_trend = None
        if len(closes) >= 10:
            ten_day_trend = ((closes[0] - closes[9]) / closes[9]) * 100
        
        # 分析师评级
        analyst_bull_pct = None
        if rec:
            total = rec.get("strong_buy", 0) + rec.get("buy", 0) + rec.get("hold", 0) + rec.get("sell", 0) + rec.get("strong_sell", 0)
            bull = rec.get("strong_buy", 0) + rec.get("buy", 0)
            if total > 0:
                analyst_bull_pct = bull / total * 100
        
        # PE
        pe_ratio = None
        if overview:
            try:
                pe_ratio = float(overview.get("PERatio", 0))
            except:
                pass
        
        # 综合分析
        result = self._analyze_stock(symbol, tweet_direction, twelve_quote, alpha_quote,
                                      history, overview, rec, news, None)
        
        return {
            "symbol": symbol,
            "price": float(twelve_quote.get("price", 0)) if twelve_quote else None,
            "finnhub_price": finnhub_quote.get("c") if finnhub_quote else None,
            "finnhub_change_pct": finnhub_quote.get("dp") if finnhub_quote else None,
            "daily_change": today_change,
            "ten_day_trend": ten_day_trend,
            "sma5": sma5,
            "sma10": sma10,
            "rsi5": rsi5,
            "rsi14": rsi14,
            "macd": macd,
            "bollinger": bb,
            "avg_volume_5d": avg_volume,
            "latest_volume": int(history[0].get("volume", 0)) if history else None,
            "pe_ratio": pe_ratio,
            "analyst_bull_pct": analyst_bull_pct,
            "analyst_rating": rec,
            "sector": sector,
            "peers": peers,
            "eps_surprises": eps_surprises,
            "news_count": len(news) if news else 0,
            "news": news[:3] if news else [],
            "verdict": result["verdict"],
            "weighted_positive": result["weighted_positive"],
            "weighted_negative": result["weighted_negative"],
            "signals": result["signals"],
            "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "history_60d": len(history),
        }

# ============================================
# 数据库操作
# ============================================
def save_analysis(symbol, analysis_result):
    """保存分析数据到 Supabase"""
    if not supabase:
        return
    try:
        supabase.table("analysis_history").insert({
            "symbol": symbol,
            "name": analysis_result.get("name", ""),
            "timestamp": analysis_result["timestamp"],
            "price": analysis_result.get("price"),
            "daily_change": analysis_result.get("daily_change"),
            "ten_day_trend": analysis_result.get("ten_day_trend"),
            "weighted_positive": analysis_result.get("weighted_positive", 0),
            "weighted_negative": analysis_result.get("weighted_negative", 0),
            "verdict": analysis_result.get("verdict"),
            "pe_ratio": analysis_result.get("pe_ratio"),
            "rsi_14": analysis_result.get("rsi14"),
            "macd_signal": "金叉" if analysis_result.get("macd") and analysis_result["macd"].get("histogram", 0) > 0 else "死叉" if analysis_result.get("macd") and analysis_result["macd"].get("histogram", 0) < 0 else "中性",
            "analyst_bull_pct": analysis_result.get("analyst_bull_pct"),
            "news_count": analysis_result.get("news_count", 0),
            "json_data": json.dumps(analysis_result, ensure_ascii=False, default=str),
        }).execute()
    except Exception as e:
        print(f"保存失败: {e}")

def get_latest_analysis():
    """获取所有股票的最新分析"""
    if not supabase:
        return []
    try:
        result = supabase.table("analysis_history").select("*").order("timestamp", desc=True).limit(100).execute()
        data = result.data if hasattr(result, 'data') else result
        if not data or len(data) == 0:
            return []
        latest = {}
        for item in data:
            sym = item.get("symbol")
            if sym and (sym not in latest or datetime.fromisoformat(item.get("timestamp", "")) > datetime.fromisoformat(latest[sym].get("timestamp", ""))):
                latest[sym] = item
        return list(latest.values())
    except Exception as e:
        print(f"获取失败: {e}")
        return []

def get_history(symbol, limit=10):
    """获取单个股票历史"""
    if not supabase:
        return []
    try:
        result = supabase.table("analysis_history").select("*").eq("symbol", symbol).order("timestamp", desc=True).limit(limit).execute()
        return result.data if hasattr(result, 'data') else result
    except Exception as e:
        print(f"获取历史失败: {e}")
        return []

def get_watch_list():
    """获取关注列表"""
    if not supabase:
        return []
    try:
        result = supabase.table("watch_list").select("*").eq("enabled", True).order("symbol").execute()
        return result.data if hasattr(result, 'data') else result
    except Exception as e:
        print(f"获取关注列表失败: {e}")
        return []

# ============================================
# 初始化分析器
# ============================================
analyzer = StockAnalyzer()

# ============================================
# API 端点
# ============================================
@app.route("/api/indices", methods=["GET"])
def api_indices():
    """大盘指数"""
    return jsonify(analyzer.get_market_overview())

@app.route("/api/watch-list", methods=["GET"])
def api_watch_list():
    """获取关注列表"""
    return jsonify(get_watch_list())

@app.route("/api/analysis/latest", methods=["GET"])
def api_analysis_latest():
    """获取最新分析"""
    return jsonify(get_latest_analysis())

@app.route("/api/analysis/<symbol>", methods=["GET"])
def api_analysis_history(symbol):
    """获取股票历史"""
    limit = request.args.get("limit", 10, type=int)
    return jsonify(get_history(symbol, limit))

@app.route("/api/analyze/<symbol>", methods=["GET"])
def api_analyze_single(symbol):
    """分析单只股票"""
    tweet_direction = request.args.get("tweet_direction", "")
    result = analyzer.analyze(symbol, tweet_direction)
    # 从 watch_list 获取名称
    watch_list = get_watch_list()
    for stock in watch_list:
        if stock.get("symbol") == symbol:
            result["name"] = stock.get("name", "")
            result["direction"] = stock.get("direction", "")
            break
    save_analysis(symbol, result)
    return jsonify(result)

@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """刷新所有股票数据"""
    watch_list = get_watch_list()
    if not watch_list:
        return jsonify({"error": "无关注列表"}), 400

    results = []
    for stock in watch_list:
        symbol = stock["symbol"]
        result = analyzer.analyze(symbol, stock.get("direction", ""))
        result["name"] = stock.get("name", symbol)
        result["direction"] = stock.get("direction", "")
        save_analysis(symbol, result)
        results.append(result)
        time.sleep(0.5)

    return jsonify(results)

@app.route("/api/watch-list/<symbol>/remove", methods=["POST"])
def api_remove_stock(symbol):
    """移除股票（从 watch_list 禁用，保留分析历史）"""
    if not supabase:
        return jsonify({"error": "数据库未配置"}), 500
    try:
        supabase.table("watch_list").update({"enabled": False}).eq("symbol", symbol.upper()).execute()
        return jsonify({"status": "ok", "symbol": symbol.upper()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tweets/refresh", methods=["POST"])
def api_tweet_refresh():
    """抓取推文并分析；自动把新股票加入 watch_list"""
    from tweet_fetcher import fetch_twitter_data, extract_stock_info
    try:
        tweets = fetch_twitter_data()
        if not tweets:
            return jsonify({"error": "无推文数据"}), 400

        stocks = set()
        tweet_info = {}
        for tweet in tweets:
            info = extract_stock_info(tweet)
            if info.get("symbols"):
                stocks.update(info["symbols"])
                tweet_info.update({s: info.get("ai_direction", "") for s in info["symbols"]})

        added = []
        for symbol in stocks:
            if supabase:
                try:
                    supabase.table("watch_list").upsert({
                        "symbol": symbol.upper(),
                        "name": symbol.upper(),
                        "direction": tweet_info.get(symbol.upper(), ""),
                        "enabled": True,
                    }).execute()
                    added.append(symbol.upper())
                except Exception as e:
                    print(f"自动添加 watch_list 失败 {symbol}: {e}")

        results = []
        for symbol in stocks:
            direction = tweet_info.get(symbol.upper(), "")
            result = analyzer.analyze(symbol, direction)
            result["name"] = symbol.upper()
            result["direction"] = direction
            save_analysis(symbol, result)
            results.append(result)
            time.sleep(0.5)

        return jsonify({
            "tweets_count": len(tweets),
            "stocks_found": sorted(stocks),
            "added_to_watch_list": added,
            "analysis": results,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def index():
    """首页"""
    return jsonify({
        "status": "ok",
        "version": "2.0",
        "endpoints": {
            "/api/indices": "大盘指数 (SPY, QQQ, DIA)",
            "/api/watch-list": "关注列表",
            "/api/analysis/latest": "最新分析",
            "/api/analysis/<symbol>": "股票历史",
            "/api/analyze/<symbol>": "分析单只股票",
            "/api/refresh": "刷新所有股票",
            "/api/tweets/refresh": "抓取推文分析",
        },
        "features": [
            "实时价格 (Twelve Data + Alpha Vantage + Finnnub)",
            "历史走势 (Twelve Data 60天)",
            "技术指标 (SMA, RSI(5/14), MACD, 布林带)",
            "分析师评级 (Finnnub)",
            "PE估值 (Alpha Vantage)",
            "同类对比 (Finnnub Peers)",
            "新闻情绪 (Finnnub)",
            "推文信号集成",
        ],
    })

# ============================================
# 启动
# ============================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
