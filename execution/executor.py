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
        self.markets = None

    async def _ensure_markets(self):
        if self.markets is None:
            self.markets = await self.exchange.load_markets()

    def amount_to_precision(self, symbol: str, amount: float) -> str:
        """
        Truncates quantity to match LOT_SIZE requirements.
        """
        return self.exchange.amount_to_precision(symbol, amount)

    def price_to_precision(self, symbol: str, price: float) -> str:
        """
        Truncates price to match PRICE_FILTER requirements.
        """
        return self.exchange.price_to_precision(symbol, price)

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
        Places a market or limit order with correct precision.
        """
        try:
            await self._ensure_markets()
            
            # Truncate amount to match exchange precision (LOT_SIZE)
            formatted_amount = self.amount_to_precision(symbol, amount)
            
            if price:
                formatted_price = self.price_to_precision(symbol, price)
                order = await self.exchange.create_order(symbol, 'limit', side, formatted_amount, formatted_price)
            else:
                order = await self.exchange.create_order(symbol, 'market', side, formatted_amount)
            
            logger.info(f"Order placed successfully: {order['id']}")
            return order
        except Exception as e:
            logger.error(f"Error placing order for {symbol}: {e}")
            return None

    async def close_connection(self):
        await self.exchange.close()
