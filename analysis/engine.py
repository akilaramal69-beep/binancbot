from analysis.technical import TechnicalAnalysis
from analysis.sentiments import SentimentAnalysis
from execution.executor import TradingExecutor
from execution.manager import RiskManager
from services.telegram import TelegramService
from services.alpha_vantage import AlphaVantageService
from core.config import settings
import logging
import os
import json
import tempfile
import datetime
import asyncio

logger = logging.getLogger("uvicorn")

def atomic_write_json(filepath, data):
    """
    Safely writes to a JSON file atomically, preventing read collisions
    from concurrent processes (e.g., Telegram status requests).
    """
    dir_name = os.path.dirname(os.path.abspath(filepath))
    with tempfile.NamedTemporaryFile('w', dir=dir_name, delete=False, suffix='.json') as tf:
        json.dump(data, tf, indent=4)
        tempname = tf.name
    os.replace(tempname, filepath)

async def _get_weighted_sentiment(symbol: str) -> float:
    """ Fetches and weights sentiment from multiple sources. """
    try:
        ai_sentiment = await SentimentAnalysis.get_news_sentiment(symbol)
        av_sentiment = await AlphaVantageService.get_news_sentiment(symbol)
        
        if av_sentiment == 0:
            sentiment = ai_sentiment
        else:
            sentiment = (ai_sentiment * 0.8) + (av_sentiment * 0.2)
            
        logger.info(f"Sentiment for {symbol} - AI: {ai_sentiment}, AV: {av_sentiment}, Weighted: {sentiment:.2f}")
        return sentiment
    except Exception as e:
        logger.warning(f"Sentiment calculation failed for {symbol}: {e}")
        return 0.5 # Neutral fallback

def _calculate_institutional_score(symbol: str, price: float, ema_20: float, fib_level_hit: str, 
                                 sentiment_score: float, prev_sentiment: float, 
                                 volume_spike: bool, bos: bool, elliott_phase: str) -> int:
    """ Computes the 10-point institutional scoring matrix. """
    score = 0
    
    # 1. Trend & Structure (Max 3)
    if ema_20 > 0 and price > ema_20: score += 1
    if bos: score += 1
    if ema_20 > 0 and (price / ema_20) >= (1 + settings.MOMENTUM_EMA_GAP): score += 1

    # 2. Elliott Wave Bonus (Max 2)
    if elliott_phase in ["Wave 5 Breakout", "Wave 5 Ignition"]:
        score += 2
    elif elliott_phase == "Wave 4 Retracement":
        score += 1

    # 3. Fibonacci & EMA Confluence (Max 3)
    ema_match = False
    ema_tolerance = 0.005 if settings.FAST_TRADE_MODE else 0.002
    if ema_20 > 0 and abs(price - ema_20) / ema_20 < ema_tolerance: ema_match = True

    if fib_level_hit:
        score += 1
        if fib_level_hit in ["level_500", "level_618"]: score += 2
    elif ema_match:
        score += 2

    # 4. Sentiment (Max 3)
    if sentiment_score >= 0.70: score += 1
    if sentiment_score >= 0.85: score += 1
    if sentiment_score - prev_sentiment >= 0.10: score += 1

    # 5. Volume (Max 1)
    if volume_spike: score += 1
    
    return min(score, 10)

def _check_explosive_confirmation(ohlcv: list, highs: list, atr: float, price: float) -> bool:
    """ Validates candle quality to filter out fakeouts/wicks. """
    if not ohlcv or len(highs) < 10: return False
    
    current_candle = ohlcv[-1]
    c_open, c_high, c_low, c_close = current_candle[1:5]
    candle_size = c_high - c_low
    candle_body = abs(c_close - c_open)
    
    if candle_size <= 0: return False

    # 1. Body Quality (No long upper wicks)
    closes_near_high = (c_close - c_low) / candle_size >= 0.8
    body_ratio = candle_body / candle_size
    strong_candle = body_ratio >= 0.6
    
    # 2. Breakout Direction & FOMO Filter
    recent_range_high = max(highs[-6:-1])
    valid_direction = c_close > recent_range_high
    
    distance_from_range = (c_close - recent_range_high) / atr if atr > 0 else 0
    fomo_safe = distance_from_range <= 0.5
    
    # 3. Volatility Expansion
    volatility_expansion = candle_size > (1.5 * atr)
    
    return volatility_expansion and closes_near_high and strong_candle and valid_direction and fomo_safe

def _save_analysis_data(symbol: str, data: dict):
    """ Atomic save for WebUI cache and history. """
    try:
        cache_file = "latest_analysis.json"
        cache = {}
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                cache = json.load(f)
        
        cache[symbol] = data
        atomic_write_json(cache_file, cache)
        
        history_file = "analysis_history.json"
        history = []
        if os.path.exists(history_file):
            with open(history_file, "r") as f:
                history = json.load(f)
        
        entry = data.copy()
        entry["symbol"] = symbol
        history.append(entry)
        
        if len(history) > 100:
            history = history[-100:]
            
        atomic_write_json(history_file, history)
        
        # Update Total Scans
        total_scans_file = "total_scans.json"
        total_scans = 0
        if os.path.exists(total_scans_file):
            try:
                with open(total_scans_file, "r") as f:
                    total_scans = json.load(f).get("count", 0)
            except: pass
        with open(total_scans_file, "w") as f:
            json.dump({"count": total_scans + 1}, f)
            
    except Exception as e:
        logger.warning(f"Failed to save analysis for {symbol}: {e}")

async def analyze_symbol(symbol: str, is_demo: bool | None = None):
    """
    Main orchestration for symbol analysis and trade execution.
    """
    positions = RiskManager.load_positions()
    
    # Check position limit
    if len(positions) >= settings.MAX_CONCURRENT_POSITIONS:
        logger.info(f"Max positions ({settings.MAX_CONCURRENT_POSITIONS}) reached. Skipping {symbol}")
        return
    
    # Check existing position
    if symbol in positions:
        logger.info(f"Already holding {symbol}. Skipping scanner.")
        return

    executor = TradingExecutor()
    
    price = None
    sentiment_score = 0.5
    ohlcv = None
    
    try:
        price = await executor.get_latest_price(symbol)
        if not price:
            logger.warning(f"No price data for {symbol}")
            return
        logger.info(f"--- Analyzing {symbol} at {price} ---")
        
        # Fetch sentiment and OHLCV in parallel
        sentiment_task = _get_weighted_sentiment(symbol)
        ohlcv_task = executor.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        sentiment_score, ohlcv = await asyncio.gather(sentiment_task, ohlcv_task)
        
        if not ohlcv:
            logger.warning(f"No OHLCV for {symbol}")
            return
            
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        
        # Market regime filter - only trade in uptrends
        market_regime = TechnicalAnalysis.detect_market_regime(closes, settings.MARKET_REGIME_EMA_PERIOD)
        if market_regime == "downtrend":
            logger.info(f"Downtrend detected for {symbol}. Skipping trade.")
            return
        
        fib_levels = TechnicalAnalysis.calculate_fibonacci_levels(max(highs), min(lows))
        fib_level_hit = TechnicalAnalysis.is_price_at_fib_level(price, fib_levels, settings.FIB_TOLERANCE)
        ema_20 = TechnicalAnalysis.calculate_ema(highs, period=20, symbol=symbol)
        atr = TechnicalAnalysis.calculate_atr(highs, lows, closes, symbol=symbol)
        volume_spike = TechnicalAnalysis.is_volume_spike(volumes)
        bos = TechnicalAnalysis.detect_bos(highs, lows, price)
        elliott_phase = TechnicalAnalysis.identify_elliott_wave(closes, atr)

        # 3. Dynamic Acceleration Stats
        prev_sentiment = sentiment_score
        prev_score = 0
        if os.path.exists("latest_analysis.json"):
            try:
                with open("latest_analysis.json", "r") as f:
                    cache = json.load(f)
                    s_data = cache.get(symbol, {})
                    prev_sentiment = s_data.get("sentiment", sentiment_score)
                    prev_score = s_data.get("score", 0)
            except: pass

        # 4. Final Scoring
        fib_level = fib_level_hit if fib_level_hit else ""
        score = _calculate_institutional_score(
            symbol, price, ema_20, fib_level, sentiment_score, 
            prev_sentiment, volume_spike, bos, elliott_phase
        )
        score = min(score, 10)
        score_jump = score - prev_score
        logger.info(f"Institutional Score {symbol}: {score}/10 (Jump: {score_jump}) | EW: {elliott_phase}")

        # 5. Explosive Move Validation
        explosive_move = _check_explosive_confirmation(ohlcv, highs, atr, price)
        
        # 6. Trade Decision
        should_trade = False
        required_score = 5 if settings.FAST_TRADE_MODE else 7
        
        if score >= required_score:
            should_trade = True
        elif score >= 6 and score_jump >= 3 and explosive_move:
            should_trade = True
        elif score_jump >= 3 and volume_spike and not bos and explosive_move:
            should_trade = True

        # 7. Persistence & WebUI
        analysis_data = {
            "price": price,
            "sentiment": sentiment_score,
            "fib_level": fib_level_hit,
            "ema": ema_20,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "score": score,
            "elliott_phase": elliott_phase,
            "signal": f"BUY ({score}/10)" if should_trade else f"WATCH ({score}/10)"
        }
        _save_analysis_data(symbol, analysis_data)

        # 8. Execution
        if should_trade:
            await TelegramService.send_message(f"🚨 <b>Trade Entry: {symbol}</b>\nScore: {score}/10\nPrice: {price}")
            try:
                balance = await executor.get_balance("USDT")
                pos_size = RiskManager.calculate_position_size(balance)
                
                # Minimum notional check ($11)
                if pos_size < 11 and balance >= 11:
                    pos_size = 11.5
                
                if balance < pos_size:
                    logger.error(f"Insufficient balance for {symbol}")
                    return

                await executor.place_order(symbol, "buy", pos_size/price)
                tp_price = price + (3.0 * atr) if atr > 0 else price * 1.05
                sl_price = price - (1.5 * atr) if atr > 0 else price * 0.98
                
                await RiskManager.save_position(symbol, price, pos_size/price, "buy", tp_price, sl_price, entry_time=datetime.datetime.now().timestamp())
                logger.info(f"LIVE TRADE EXECUTED: Buy {symbol} at {price}")
            except Exception as e:
                logger.error(f"Order placement failed: {e}")
        else:
            logger.info(f"No trade for {symbol}")

    except Exception as e:
        logger.error(f"Critical error in analyze_symbol: {e}")
    finally:
        await executor.close_connection()
