import httpx
from core.config import settings
import logging

logger = logging.getLogger("uvicorn")

_http_client = None

async def get_http_client():
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client

class AlphaVantageService:
    @staticmethod
    async def get_news_sentiment(symbol: str) -> float:
        """
        Fetches news sentiment for a symbol from Alpha Vantage.
        Returns a score between -1 and 1.
        """
        if not settings.ALPHA_VANTAGE_API_KEY:
            logger.warning("Alpha Vantage API key missing. Skipping AV sentiment.")
            return 0.0

        url = "https://www.alphavantage.co/query"
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": symbol.replace("/", ""), # Convert BTC/USDT to BTC
            "apikey": settings.ALPHA_VANTAGE_API_KEY
        }

        try:
            client = await get_http_client()
            response = await client.get(url, params=params)
            data = response.json()
            
            if "feed" in data and len(data["feed"]) > 0:
                scores = [item.get("overall_sentiment_score", 0) for item in data["feed"]]
                avg_score = sum(scores) / len(scores)
                return avg_score
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching Alpha Vantage sentiment: {e}")
            return 0.0

    @staticmethod
    async def get_ema(symbol: str, interval: str = '60min', time_period: int = 20) -> float:
        """
        Fetches EMA (Exponential Moving Average) from Alpha Vantage.
        """
        if not settings.ALPHA_VANTAGE_API_KEY:
            return 0.0

        url = "https://www.alphavantage.co/query"
        params = {
            "function": "EMA",
            "symbol": symbol.replace("/", ""),
            "interval": interval,
            "time_period": time_period,
            "series_type": "close",
            "apikey": settings.ALPHA_VANTAGE_API_KEY
        }

        try:
            client = await get_http_client()
            response = await client.get(url, params=params)
            data = response.json()
            
            if "Technical Analysis: EMA" in data:
                latest_timestamp = next(iter(data["Technical Analysis: EMA"]))
                return float(data["Technical Analysis: EMA"][latest_timestamp]["EMA"])
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching Alpha Vantage EMA: {e}")
            return 0.0
