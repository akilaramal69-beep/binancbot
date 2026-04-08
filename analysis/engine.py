from analysis.technical import TechnicalAnalysis
from analysis.sentiments import SentimentAnalysis
from execution.executor import TradingExecutor
from execution.manager import RiskManager
from services.telegram import TelegramService
from services.alpha_vantage import AlphaVantageService
from core.config import settings
import logging

logger = logging.getLogger("uvicorn")

async def analyze_symbol(symbol: str, is_demo: bool = None):
    """
    The 'Brain' of the bot. Proactively analyzes a symbol from Binance.
    """
    is_demo_context = settings.USE_TESTNET or False
    
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

        # 3. Decision Logic (Aggressive & Breakout)
        should_trade = False
        side = "buy" 
        
        # Standard Retracement Levels
        buy_levels = ["level_236", "level_382", "level_500", "level_618", "level_786"]
        
        # EMA Precision Check (Tolerance Band: 0.2%)
        ema_match = False
        if ema_20 > 0:
            if abs(price - ema_20) / ema_20 < 0.002: # 0.2% tolerance
                ema_match = True
                logger.info(f"EMA Trend Match (Within Tolerance) for {symbol}")

        # Check for Retracement
        if sentiment_score > 0.2 and (fib_level_hit in buy_levels or ema_match):
            if ema_20 == 0 or price >= ema_20 or ema_match:
                should_trade = True
                logger.info(f"Entry Match: {symbol} at {fib_level_hit or 'EMA'}")

        # Check for Breakout (Sentiment must be very high)
        if not should_trade and sentiment_score >= settings.SENTIMENT_BREAKOUT_THRESHOLD:
            if fib_level_hit == "level_0":
                should_trade = True
                logger.info(f"Breakout Triggered: {symbol} at level_0 with sentiment {sentiment_score}")

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
                
                # Calculate Fibonacci Extensions for Take-Profit
                extensions = TechnicalAnalysis.calculate_fibonacci_extensions(actual_high, actual_low)
                tp_price = extensions["level_1272"]
                
                # Save the position for tracking
                RiskManager.save_position(symbol, price, position_size/price, side, tp_price=tp_price)
                
                await TelegramService.send_message(f"🚀 <b>Live Trade Executed</b>\n{side} {symbol} ${position_size:.2f}")
            except Exception as e:
                logger.error(f"Execution failed: {e}")
        else:
            logger.info(f"No trade for {symbol}")
            
    except Exception as e:
        logger.error(f"Critical error in analyze_symbol for {symbol}: {e}")
    finally:
        await executor.close_connection()
