import ccxt.async_support as ccxt
from core.config import settings
import logging

logger = logging.getLogger("uvicorn")

class TradingExecutor:
    def __init__(self):
        self.exchange_class = getattr(ccxt, settings.EXCHANGE_ID)
        self.exchange = self.exchange_class({
            'apiKey': settings.EXCHANGE_API_KEY,
            'secret': settings.EXCHANGE_SECRET,
            'enableRateLimit': True,
        })
        self.exchange.set_sandbox_mode(settings.USE_TESTNET)

    async def get_balance(self, coin: str = "USDT"):
        balance = await self.exchange.fetch_balance()
        return balance['free'].get(coin, 0.0)

    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100):
        """
        Fetches OHLCV data from Binance.
        """
        try:
            return await self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            return None

    async def get_latest_price(self, symbol: str):
        ticker = await self.exchange.fetch_ticker(symbol)
        return ticker['last']

    async def place_order(self, symbol: str, side: str, amount: float, price: float = None):
        """
        Places a market or limit order.
        """
        try:
            if price:
                order = await self.exchange.create_order(symbol, 'limit', side, amount, price)
            else:
                order = await self.exchange.create_order(symbol, 'market', side, amount)
            
            logger.info(f"Order placed successfully: {order['id']}")
            return order
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    async def close_connection(self):
        await self.exchange.close()
