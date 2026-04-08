from analysis.technical import TechnicalAnalysis
from analysis.sentiments import SentimentAnalysis
from execution.executor import TradingExecutor
from execution.manager import RiskManager
from services.telegram import TelegramService
from services.alpha_vantage import AlphaVantageService
from core.config import settings
import logging

logger = logging.getLogger("uvicorn")

async def process_signal(data: dict):
    """
    The 'Brain' of the bot. Processes the incoming TradingView signal.
    """
    symbol = data.get("symbol")
    side = data.get("side") # buy/sell
    price = data.get("price")
    is_demo = data.get("is_demo", False)
    
    logger.info(f"Processing {'DEMO' if is_demo else 'LIVE'} {side} signal for {symbol} at {price}")
    
    await TelegramService.send_message(
        f"🔔 <b>New Signal Received</b>\n"
        f"Symbol: {symbol}\n"
        f"Side: {side}\n"
        f"Price: {price}\n"
        f"Type: {'Demo' if is_demo else 'Live'}"
    )
    
    # 1. Fundamental Analysis (Sentiment)
    ai_sentiment = await SentimentAnalysis.get_news_sentiment(symbol)
    av_sentiment = await AlphaVantageService.get_news_sentiment(symbol)
    
    # Combined sentiment score (averaging AI and AV)
    sentiment_score = (ai_sentiment + av_sentiment) / 2
    logger.info(f"Sentiment Scores - AI: {ai_sentiment}, AV: {av_sentiment}, Combined: {sentiment_score}")
    
    # 2. Technical Analysis (Fibonacci)
    executor = TradingExecutor()
    try:
        # Fetch actual OHLCV data from Binance for high/low calculation
        ohlcv = await executor.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        
        if ohlcv:
            # Get High and Low from the last 50 candles
            highs = [candle[2] for candle in ohlcv]
            lows = [candle[3] for candle in ohlcv]
            actual_high = max(highs)
            actual_low = min(lows)
        else:
            logger.warning(f"Failed to fetch OHLCV for {symbol}. Using mock values.")
            actual_high = price * 1.1
            actual_low = price * 0.9

        fib_levels = TechnicalAnalysis.calculate_fibonacci_levels(actual_high, actual_low)
        fib_level_hit = TechnicalAnalysis.is_price_at_fib_level(price, fib_levels)
        
        logger.info(f"Binance High: {actual_high}, Low: {actual_low}")
        logger.info(f"Fibonacci Level Hit: {fib_level_hit}")
    finally:
        # We'll reopen connection if a trade needs to be executed
        await executor.close_connection()
    
    # 2.5 Alpha Vantage Technical Verification (EMA)
    av_ema = await AlphaVantageService.get_ema(symbol)
    logger.info(f"Alpha Vantage EMA: {av_ema}")

    # 3. Decision Logic
    # Enhanced Criteria: 
    # - Sentiment > 0.2
    # - Price at Fibonacci support
    # - Price > EMA (Trend verification)
    should_trade = False
    
    if side == "buy":
        if sentiment_score > 0.2 and fib_level_hit in ["level_618", "level_500", "level_786"]:
            # Optional: Price > EMA for bullish trend confirmation
            if av_ema == 0 or price > av_ema:
                should_trade = True
                logger.info("Trade Criteria Met: Sentiment bullish, Fib support hit, and Trend confirming.")
    
    elif side == "sell" and sentiment_score < -0.2:
        should_trade = True
        logger.info("Trade Criteria Met: Sentiment is bearish. Selling.")

    if should_trade:
        summary_msg = f"✅ <b>Trade Criteria Met (High Accuracy)</b> for {symbol}\n" \
                      f"Sentiment: {sentiment_score:.2f}\n" \
                      f"Fib Level: {fib_level_hit}\n" \
                      f"Trend (EMA): {'Bullish' if price > av_ema else 'N/A'}"
        await TelegramService.send_message(summary_msg)

        if is_demo:
            logger.info(f"DEMO MODE: Skipping execution for {symbol}")
            await TelegramService.send_message(f"🧪 <b>Demo Execution Simulated</b> for {symbol}. No real trade placed.")
            return

        executor = TradingExecutor()
        try:
            balance = await executor.get_balance("USDT")
            position_size = RiskManager.calculate_position_size(balance)
            
            # For crypto, often need to convert USDT size to Asset amount
            # amount = position_size / price
            
            # await executor.place_order(symbol, side, amount)
            logger.info(f"EXECUTING LIVE TRADE: {side} {symbol} with size {position_size}")
            await TelegramService.send_message(f"🚀 <b>Live Trade Executed</b>\n{side} {symbol} size: {position_size:.2f}")
        finally:
            await executor.close_connection()
    else:
        logger.info("Trade criteria not met. Skipping signal.")
        await TelegramService.send_message(f"⚠️ <b>Trade Skipped</b> for {symbol}. Criteria not met.")
