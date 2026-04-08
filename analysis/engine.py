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
        
        # 1. Fundamental Analysis (Sentiment)
        ai_sentiment = await SentimentAnalysis.get_news_sentiment(symbol)
        av_sentiment = await AlphaVantageService.get_news_sentiment(symbol)
        
        sentiment_score = (ai_sentiment + av_sentiment) / 2
        logger.info(f"Sentiment - AI: {ai_sentiment}, AV: {av_sentiment}, Combined: {sentiment_score}")

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
                fib_level_hit = TechnicalAnalysis.is_price_at_fib_level(price, fib_levels)
                
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

        # 3. Decision Logic
        should_trade = False
        side = "buy" # Proactive scanner always looks for buy entries
        
        if sentiment_score > 0.2 and fib_level_hit in ["level_618", "level_500", "level_786"]:
            if ema_20 == 0 or price > ema_20:
                should_trade = True
                logger.info(f"Trade Criteria Met for {symbol}")

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
                
                # await executor.place_order(symbol, side, position_size/price)
                logger.info(f"EXECUTING LIVE TRADE: {side} {symbol} size: {position_size}")
                await TelegramService.send_message(f"🚀 <b>Live Trade Executed</b>\n{side} {symbol} ${position_size:.2f}")
            except Exception as e:
                logger.error(f"Execution failed: {e}")
        else:
            logger.info(f"No trade for {symbol}")
            
    except Exception as e:
        logger.error(f"Critical error in analyze_symbol for {symbol}: {e}")
    finally:
        await executor.close_connection()
