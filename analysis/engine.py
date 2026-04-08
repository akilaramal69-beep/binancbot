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

logger = logging.getLogger("uvicorn")

async def analyze_symbol(symbol: str, is_demo: bool = None):
    """
    The 'Brain' of the bot. Proactively analyzes a symbol from Binance.
    """
    is_demo_context = settings.USE_TESTNET or False
    
    # NEW: Check if we already have an open position for this symbol
    positions = RiskManager.load_positions()
    if symbol in positions:
        logger.info(f"Already holding a position for {symbol}. Skipping scanner for new entries.")
        return

    executor = TradingExecutor()
    try:
        # 0. Fetch latest price
        price = await executor.get_latest_price(symbol)
        
        logger.info(f"Proactive Analysis for {symbol} at {price}")
        
        await TelegramService.send_message(
            f"🔍 <b>Market Scan Started</b>\n"
            f"Symbol: {symbol}\n"
            f"Price: {price}"
        )
        
        # 1. Fundamental Analysis (Weighted Sentiment)
        ai_sentiment = await SentimentAnalysis.get_news_sentiment(symbol)
        av_sentiment = await AlphaVantageService.get_news_sentiment(symbol)
        
        # Weighted Logic: 80% AI, 20% Alpha Vantage. 
        # If AV is missing/0, use 100% AI.
        if av_sentiment == 0:
            sentiment_score = ai_sentiment
        else:
            sentiment_score = (ai_sentiment * 0.8) + (av_sentiment * 0.2)
            
        logger.info(f"Sentiment - AI: {ai_sentiment}, AV: {av_sentiment}, Weighted: {sentiment_score:.2f}")

        # 2. Technical Analysis (Fibonacci)
        # Handle exceptions internally to not break the main loop
        fib_level_hit = None
        try:
            ohlcv = await executor.fetch_ohlcv(symbol, timeframe='1h', limit=50)
            
            if ohlcv:
                highs = [candle[2] for candle in ohlcv]
                lows = [candle[3] for candle in ohlcv]
                actual_high = max(highs)
                actual_low = min(lows)
                fib_levels = TechnicalAnalysis.calculate_fibonacci_levels(actual_high, actual_low)
                
                # Use configurable tolerance for better sensitivity
                fib_level_hit = TechnicalAnalysis.is_price_at_fib_level(
                    price, fib_levels, tolerance=settings.FIB_TOLERANCE
                )
                
                # Calculate EMA locally from Binance highs/lows or close prices
                # For simplicity, we'll use the 'high' prices we already have
                ema_20 = TechnicalAnalysis.calculate_ema(highs, period=20)
                
                logger.info(f"Fib Level Hit: {fib_level_hit}, Local EMA: {ema_20}")
            else:
                logger.warning(f"Failed to fetch OHLCV for {symbol}")
        except Exception as e:
            logger.error(f"Error in Fibonacci analysis: {e}")

        # 2.5 Alpha Vantage Technical Verification (REMOVED to save credits)
        # We now use the local ema_20 calculated above
        pass

        # 2.75 Market Regime Check (Optional but recommended)
        # Check if 24h volume change is healthy
        try:
            ticker = await executor.exchange.fetch_ticker(symbol)
            vol_change = ticker.get('percentage', 0)
            logger.info(f"24h Price Change: {vol_change}%")
            # We avoid "falling knives" or completely dead markets
            if vol_change < -15: # Extreme crash
                 logger.warning(f"Market Regime: {symbol} is crashing too hard. Skipping.")
                 return
        except Exception as e:
            logger.warning(f"Market Regime check failed for {symbol}: {e}")

        # 3. Decision Logic - Institutional Scoring Matrix (0-10 Points)
        score = 0
        should_trade = False
        side = "buy" 
        
        # Pull historical sentiment and score for dynamic acceleration
        prev_sentiment = 0
        prev_score = score
        cache_file = "latest_analysis.json"
        
        try:
            if os.path.exists(cache_file):
                with open(cache_file, "r") as f:
                    cache_data = json.load(f)
                    symbol_data = cache_data.get(symbol, {})
                    prev_sentiment = symbol_data.get("sentiment", sentiment_score)
                    # Support parsing from the new schema
                    prev_score = symbol_data.get("score", score)
        except:
            pass

        # Calculate Advanced Indicators
        atr = 0.0
        volume_spike = False
        bos = False
        if ohlcv:
            closes = [candle[4] for candle in ohlcv]
            volumes = [candle[5] for candle in ohlcv]
            atr = TechnicalAnalysis.calculate_atr(highs, lows, closes)
            volume_spike = TechnicalAnalysis.is_volume_spike(volumes)
            bos = TechnicalAnalysis.detect_bos(highs, lows, price)
            
        ema_match = False
        ema_tolerance = 0.005 if settings.FAST_TRADE_MODE else 0.002
        if ema_20 > 0 and abs(price - ema_20) / ema_20 < ema_tolerance: ema_match = True

        # SCORING - TREND & STRUCTURE (Max 3)
        if ema_20 > 0 and price > ema_20: score += 1
        if bos: score += 1
        if ema_20 > 0 and (price / ema_20) >= (1 + settings.MOMENTUM_EMA_GAP): score += 1

        # SCORING - FIBONACCI (Max 3)
        if fib_level_hit:
            score += 1
            if fib_level_hit in ["level_500", "level_618"]: score += 2 # Golden Zone
        elif ema_match:
            score += 2 # High confluence standard

        # SCORING - SENTIMENT (Max 3)
        if sentiment_score >= 0.70: score += 1
        if sentiment_score >= 0.85: score += 1
        if sentiment_score - prev_sentiment >= 0.10: score += 1 # Acceleration

        # SCORING - VOLUME (Max 1)
        if volume_spike: score += 1
        
        score_jump = score - prev_score
        logger.info(f"Institutional Trade Score {symbol}: {score}/10 (Jump: {score_jump}) | ATR: {atr:.4f} | Vol-Spike: {volume_spike} | BOS: {bos}")

        # Candle Structure Confirmation (Filter Fakeouts/Long Wicks)
        explosive_move = False
        if ohlcv:
            current_candle = ohlcv[-1]
            c_open, c_high, c_low, c_close = current_candle[1:5]
            
            candle_size = c_high - c_low
            candle_body = abs(c_close - c_open)
            
            # Strict Quality Filters
            closes_near_high = False
            strong_candle = False
            valid_break_direction = False
            
            if candle_size > 0:
                # 1. Close must be near the high to prevent massive upper wicks
                closes_near_high = (c_close - c_low) / candle_size >= 0.8
                # 2. Buyers must control the candle heavily (Big Body)
                body_ratio = candle_body / candle_size
                strong_candle = body_ratio >= 0.6
                
            # 3. Ensure we aren't just bouncing inside market noise (Breakout Direction)
            if len(highs) > 5:
                recent_range_high = max(highs[-6:-1]) # Exclude current candle
                if c_close > recent_range_high:
                    # FOMO Filter: Prevent chasing candles that have already run too far
                    distance_from_range = (c_close - recent_range_high) / atr if atr > 0 else 0
                    if distance_from_range <= 0.5:
                        valid_break_direction = True
                
            # Combine Volatility (ATR) and Structure
            if candle_size > (1.5 * atr) and closes_near_high and strong_candle and valid_break_direction:
                explosive_move = True

        # Core Entry Triggers
        required_score = 5 if settings.FAST_TRADE_MODE else 7
        if score >= required_score:
            should_trade = True
            logger.info(f"🔥 SCORE ENTRY TRIGGERED: {symbol} at Score {score} (Jump: {score_jump})!")
        elif score >= 6 and score_jump >= 3:
            if explosive_move:
                should_trade = True
                logger.info(f"🚀 EXPLOSIVE ACCELERATION TRIGGERED: {symbol} Score {score} (Jump: {score_jump}) + Solid Strong Candle!")
            else:
                logger.info(f"⚠️ Acceleration Detected but weak candle structure/wicking for {symbol}. Waiting for confirmation.")
        elif score_jump >= 3 and volume_spike and not bos:
            # Pre-BOS Expansion (Early Ignition)
            if explosive_move:
                should_trade = True
                logger.info(f"💥 PRE-BOS IGNITION TRIGGERED: {symbol} Score {score} (Jump: {score_jump}) + Vol Spike + ATR Expansion!")
            else:
                logger.info(f"⏱️ Early expansion probed for {symbol}, but candle structure insufficient.")

        # 4. Cache Analysis for WebUI
        try:
            cache_file = "latest_analysis.json"
            cache = {}
            if os.path.exists(cache_file):
                with open(cache_file, "r") as f:
                    cache = json.load(f)
            
            timestamp_str = str(logging.Formatter().formatTime(logging.LogRecord("", 0, "", 0, "", (), None)))
            
            cache_data = {
                "price": price,
                "sentiment": sentiment_score,
                "fib_level": fib_level_hit,
                "ema": ema_20,
                "timestamp": timestamp_str,
                "score": score,
                "signal": f"BUY ({score}/10)" if should_trade else f"WATCH ({score}/10)"
            }
            cache[symbol] = cache_data
            with open(cache_file, "w") as f:
                json.dump(cache, f, indent=4)
                
            # Keep a rolling history of the last 50 scans
            history_file = "analysis_history.json"
            history_list = []
            if os.path.exists(history_file):
                with open(history_file, "r") as f:
                    history_list = json.load(f)
            
            history_entry = cache_data.copy()
            history_entry["symbol"] = symbol
            history_list.append(history_entry)
            
            if len(history_list) > 50:
                history_list = history_list[-50:]
                
            with open(history_file, "w") as f:
                json.dump(history_list, f, indent=4)
                
            # Update Total Scans Counter
            total_scans_file = "total_scans.json"
            total_scans = 0
            if os.path.exists(total_scans_file):
                try:
                    with open(total_scans_file, "r") as f:
                        total_scans = json.load(f).get("count", 0)
                except:
                    pass
            with open(total_scans_file, "w") as f:
                json.dump({"count": total_scans + 1}, f)
                
        except Exception as e:
            logger.warning(f"Failed to cache analysis for {symbol}: {e}")

        if should_trade:
            summary_msg = f"✅ <b>Independent Trade Triggered</b> for {symbol}\n" \
                        f"Sentiment: {sentiment_score:.2f}\n" \
                        f"Fib Level: {fib_level_hit}"
            await TelegramService.send_message(summary_msg)

            if settings.USE_TESTNET:
                logger.info(f"TESTNET EXECUTION for {symbol}")
            
            try:
                balance = await executor.get_balance("USDT")
                position_size = RiskManager.calculate_position_size(balance)
                
                # Place actual Buy Order
                await executor.place_order(symbol, side, position_size/price)
                logger.info(f"EXECUTING LIVE TRADE: {side} {symbol} size: {position_size}")
                
                # Calculate ATR-Based TP/SL if available
                if atr > 0:
                    tp_price = price + (3.0 * atr)
                    sl_price = price - (1.5 * atr)
                    logger.info(f"Risk Params using ATR Volatility -> SL: {sl_price:.2f}, TP: {tp_price:.2f}")
                else:
                    extensions = TechnicalAnalysis.calculate_fibonacci_extensions(actual_high, actual_low)
                    tp_price = extensions.get("level_1272", price * 1.05)
                    sl_price = price * 0.98

                # Save the position for tracking
                RiskManager.save_position(symbol, price, position_size/price, side, tp_price=tp_price, sl_price=sl_price)
                
                await TelegramService.send_message(f"🚀 <b>Live Trade Executed</b>\n{side} {symbol} ${position_size:.2f}")
            except Exception as e:
                logger.error(f"Execution failed: {e}")
        else:
            logger.info(f"No trade for {symbol}")
            
    except Exception as e:
        logger.error(f"Critical error in analyze_symbol for {symbol}: {e}")
    finally:
        await executor.close_connection()
