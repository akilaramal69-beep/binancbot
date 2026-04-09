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
                                  volume_spike: bool, bos: bool, elliott_phase: str,
                                  trend_strength: float = 0.5) -> int:
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
    
    # Bonus: Trend strength adds up to +2 points for strong trends
    if trend_strength >= 0.7:
        score += 2
    elif trend_strength >= 0.5:
        score += 1
    
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

async def analyze_symbol_full(symbol: str) -> dict:
    """
    Full analysis returning dict for trade ranking.
    Returns: {symbol, score, trend_strength, sentiment, price, atr, should_trade, reason}
    """
    result = {
        "symbol": symbol,
        "score": 0,
        "trend_strength": 0.0,
        "sentiment": 0.5,
        "price": None,
        "atr": 0.0,
        "ema_20": 0.0,
        "fib_level_hit": "",
        "bos": False,
        "elliott_phase": "None",
        "volume_spike": False,
        "explosive_move": False,
        "should_trade": False,
        "reason": "",
        "executor": None
    }
    
    positions = RiskManager.load_positions()
    
    if len(positions) >= settings.MAX_CONCURRENT_POSITIONS:
        result["reason"] = "max_positions_reached"
        return result
    
    if symbol in positions:
        result["reason"] = "already_holding"
        return result

    executor = TradingExecutor()
    result["executor"] = executor
    
    try:
        price = await executor.get_latest_price(symbol)
        if not price:
            result["reason"] = "no_price"
            return result
        
        result["price"] = price
        
        sentiment_task = _get_weighted_sentiment(symbol)
        ohlcv_task = executor.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        sentiment_score, ohlcv = await asyncio.gather(sentiment_task, ohlcv_task)
        
        result["sentiment"] = sentiment_score
        
        if not ohlcv:
            result["reason"] = "no_ohlcv"
            return result
            
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        
        market_regime = TechnicalAnalysis.detect_market_regime(closes, settings.MARKET_REGIME_EMA_PERIOD)
        if market_regime == "downtrend":
            result["reason"] = "downtrend"
            return result
        
        trend_strength = TechnicalAnalysis.calculate_trend_strength(closes, highs)
        result["trend_strength"] = trend_strength
        
        fib_level_hit = TechnicalAnalysis.is_price_at_fib_level(price, 
            TechnicalAnalysis.calculate_fibonacci_levels(max(highs), min(lows)), 
            settings.FIB_TOLERANCE)
        result["fib_level_hit"] = fib_level_hit if fib_level_hit else ""
        
        ema_20 = TechnicalAnalysis.calculate_ema(highs, period=20, symbol=symbol)
        result["ema_20"] = ema_20
        
        atr = TechnicalAnalysis.calculate_atr(highs, lows, closes, symbol=symbol)
        result["atr"] = atr
        
        volume_spike = TechnicalAnalysis.is_volume_spike(volumes)
        result["volume_spike"] = volume_spike
        
        bos = TechnicalAnalysis.detect_bos(highs, lows, price)
        result["bos"] = bos
        
        elliott_phase = TechnicalAnalysis.identify_elliott_wave(closes, atr)
        result["elliott_phase"] = elliott_phase
        
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

        score = _calculate_institutional_score(
            symbol, price, ema_20, result["fib_level_hit"], sentiment_score, 
            prev_sentiment, volume_spike, bos, elliott_phase, trend_strength
        )
        result["score"] = min(score, 10)
        score_jump = result["score"] - prev_score
        
        explosive_move = _check_explosive_confirmation(ohlcv, highs, atr, price)
        result["explosive_move"] = explosive_move
        
        required_score = 5 if settings.FAST_TRADE_MODE else 7
        trend_gate_passed = trend_strength >= settings.MIN_TREND_STRENGTH
        
        if result["score"] >= required_score and trend_gate_passed:
            result["should_trade"] = True
            result["reason"] = "score_passed"
        elif result["score"] >= 6 and score_jump >= 3 and explosive_move and trend_gate_passed:
            result["should_trade"] = True
            result["reason"] = "momentum_explosive"
        elif score_jump >= 3 and volume_spike and not bos and explosive_move and trend_gate_passed:
            result["should_trade"] = True
            result["reason"] = "volume_explosive"
        
        if not result["should_trade"]:
            if not trend_gate_passed:
                result["reason"] = "weak_trend"
            elif result["score"] < required_score:
                result["reason"] = "low_score"
        
        # Save analysis data
        analysis_data = {
            "price": price,
            "sentiment": sentiment_score,
            "fib_level": result["fib_level_hit"],
            "ema": ema_20,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "score": result["score"],
            "elliott_phase": elliott_phase,
            "signal": f"BUY ({result['score']}/10)" if result["should_trade"] else f"WATCH ({result['score']}/10)"
        }
        _save_analysis_data(symbol, analysis_data)
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        result["reason"] = f"error: {str(e)}"
        return result
    finally:
        await executor.close_connection()


async def execute_trade(result: dict):
    """Execute a trade from analysis result."""
    symbol = result["symbol"]
    price = result["price"]
    atr = result["atr"]
    trend_strength = result["trend_strength"]
    reduction = result.get("position_reduction", 1.0)  # Default full size
    
    executor = TradingExecutor()
    try:
        balance = await executor.get_balance("USDT")
        
        pos_size_usd, stop_distance = RiskManager.calculate_position_size(
            balance, price, atr, 
            risk_percent=settings.RISK_PER_TRADE_PERCENT
        )
        
        if pos_size_usd < 11.5:
            pos_size_usd = 11.5
        
        # Apply position reduction (0.5 for correlated clusters)
        pos_size_usd = pos_size_usd * reduction
        
        if balance < pos_size_usd:
            logger.error(f"Insufficient balance for {symbol}")
            return False

        amount = pos_size_usd / price
        await executor.place_order(symbol, "buy", amount)
        
        tp_price, sl_price = RiskManager.calculate_tp_sl(price, atr, settings.TRADING_MODE, trend_strength)
        
        await RiskManager.save_position(symbol, price, amount, "buy", tp_price, sl_price, 
            entry_time=datetime.datetime.now().timestamp())
        
        size_msg = f"Size: ${pos_size_usd:.2f}" if reduction == 1.0 else f"Size: ${pos_size_usd:.2f} (50% reduced)"
        logger.info(f"LIVE TRADE EXECUTED: Buy {symbol} at {price} | {size_msg} | SL: {sl_price:.2f} | TP: {tp_price:.2f}")
        await TelegramService.send_message(f"🚨 <b>Trade Entry: {symbol}</b>\nScore: {result['score']}/10\nPrice: {price}\nReason: {result['reason']}\n{size_msg}")
        return True
        
    except Exception as e:
        logger.error(f"Order placement failed for {symbol}: {e}")
        return False
    finally:
        await executor.close_connection()


# Keep legacy function for backward compatibility
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
        
        # Calculate trend strength for scoring adjustment
        trend_strength = TechnicalAnalysis.calculate_trend_strength(closes, highs)
        
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
            prev_sentiment, volume_spike, bos, elliott_phase, trend_strength
        )
        score = min(score, 10)
        score_jump = score - prev_score
        logger.info(f"Institutional Score {symbol}: {score}/10 (Jump: {score_jump}) | EW: {elliott_phase}")

        # 5. Explosive Move Validation
        explosive_move = _check_explosive_confirmation(ohlcv, highs, atr, price)
        
        # 6. Trade Decision
        should_trade = False
        required_score = 5 if settings.FAST_TRADE_MODE else 7
        
        # Trade quality gate - trend must be strong enough
        trend_gate_passed = trend_strength >= settings.MIN_TREND_STRENGTH
        
        if score >= required_score and trend_gate_passed:
            should_trade = True
        elif score >= 6 and score_jump >= 3 and explosive_move and trend_gate_passed:
            should_trade = True
        elif score_jump >= 3 and volume_spike and not bos and explosive_move and trend_gate_passed:
            should_trade = True
        
        # Log why trade was rejected if trend is weak
        if not should_trade and score >= required_score and not trend_gate_passed:
            logger.info(f"Trade rejected: Weak trend strength ({trend_strength:.2f} < {settings.MIN_TREND_STRENGTH})")

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
                
                # Risk-based position sizing
                pos_size_usd, stop_distance = RiskManager.calculate_position_size(
                    balance, price, atr, 
                    risk_percent=settings.RISK_PER_TRADE_PERCENT
                )
                
                # Enforce minimum notional
                if pos_size_usd < 11.5:
                    pos_size_usd = 11.5
                
                if balance < pos_size_usd:
                    logger.error(f"Insufficient balance for {symbol}")
                    return

                amount = pos_size_usd / price
                await executor.place_order(symbol, "buy", amount)
                
                # Get TP/SL based on trading mode AND trend strength
                tp_price, sl_price = RiskManager.calculate_tp_sl(price, atr, settings.TRADING_MODE, trend_strength)
                
                await RiskManager.save_position(symbol, price, amount, "buy", tp_price, sl_price, entry_time=datetime.datetime.now().timestamp())
                logger.info(f"LIVE TRADE EXECUTED: Buy {symbol} at {price} | Size: ${pos_size_usd:.2f} | SL: {sl_price:.2f} | TP: {tp_price:.2f}")
            except Exception as e:
                logger.error(f"Order placement failed: {e}")
        else:
            logger.info(f"No trade for {symbol}")

    except Exception as e:
        logger.error(f"Critical error in analyze_symbol: {e}")
    finally:
        await executor.close_connection()
