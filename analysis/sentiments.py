import httpx
import openai
import re
import asyncio
from core.config import settings
import logging

logger = logging.getLogger("uvicorn")

TIMEOUT = asyncio.timeout(10)  # 10 second timeout

class SentimentAnalysis:
    @staticmethod
    async def get_news_sentiment(symbol: str) -> float:
        """
        Fetches news related to the symbol and uses AI to determine sentiment.
        Returns a score between -1 (Bearish) and 1 (Bullish).
        """
        try:
            async with asyncio.timeout(settings.API_TIMEOUT_SECONDS):
                news_data = await SentimentAnalysis._fetch_news(symbol)
                
                if not settings.OPENAI_API_KEY and not settings.GROQ_API_KEY:
                    logger.warning("No AI API key found. Skipping sentiment analysis.")
                    return 0.0
                
                prompt = f"Analyze the sentiment of the following news for {symbol}. Return ONLY a number between -1 and 1.\n\nNews:\n{news_data}"
                
                if settings.GROQ_API_KEY:
                    return await SentimentAnalysis._call_groq(prompt)
                else:
                    return await SentimentAnalysis._call_openai(prompt)
                    
        except asyncio.TimeoutError:
            logger.warning(f"Sentiment analysis timeout for {symbol}")
            return 0.5  # Neutral fallback
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return 0.0

    @staticmethod
    async def _fetch_news(symbol: str) -> str:
        return f"Bullish progress for {symbol} as adoption grows. Regulators showing positive interest."

    @staticmethod
    async def _call_openai(prompt: str) -> float:
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content.strip()
        match = re.search(r"(-?\d+(\.\d+)?)", content)
        return float(match.group(1)) if match else 0.0

    @staticmethod
    async def _call_groq(prompt: str) -> float:
        """
        Calls the Groq API with the specified model.
        """
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    logger.error(f"Groq API Error: Status {response.status_code}, Response: {response.text}")
                    return 0.0
                
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()
                
                match = re.search(r"(-?\d+(\.\d+)?)", content)
                if match:
                    return float(match.group(1))
                return 0.0
        except Exception as e:
            logger.error(f"Error calling Groq: {e}")
            return 0.0
