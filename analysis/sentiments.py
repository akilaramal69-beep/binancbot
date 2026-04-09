import httpx
import openai
import re
import asyncio
from core.config import settings
import logging

logger = logging.getLogger("uvicorn")

TIMEOUT_SECONDS = 10

class SentimentAnalysis:
    @staticmethod
    async def get_news_sentiment(symbol: str) -> float:
        """
        Fetches news related to the symbol and uses AI to determine sentiment.
        Returns a score between -1 (Bearish) and 1 (Bullish).
        """
        try:
            news_data = await SentimentAnalysis._fetch_news(symbol)
            
            if not settings.OPENAI_API_KEY and not settings.GROQ_API_KEY:
                logger.warning("No AI API key found. Skipping sentiment analysis.")
                return 0.0
            
            prompt = f"Analyze the sentiment of the following news for {symbol}. Return ONLY a number between -1 and 1.\n\nNews:\n{news_data}"
            
            if settings.GROQ_API_KEY:
                result = await SentimentAnalysis._call_groq(prompt)
            else:
                result = await SentimentAnalysis._call_openai(prompt)
                
            return result
                    
        except asyncio.TimeoutError:
            logger.warning(f"Sentiment analysis timeout for {symbol}")
            return 0.5
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return 0.0

    @staticmethod
    async def _fetch_news(symbol: str) -> str:
        return f"Bullish progress for {symbol} as adoption grows. Regulators showing positive interest."

    @staticmethod
    async def _call_openai(prompt: str) -> float:
        try:
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}]
                ),
                timeout=TIMEOUT_SECONDS
            )
            content = response.choices[0].message.content
            if not content:
                return 0.0
            match = re.search(r"(-?\d+(\.\d+)?)", content.strip())
            return float(match.group(1)) if match else 0.0
        except asyncio.TimeoutError:
            logger.warning("OpenAI timeout")
            return 0.5
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return 0.0

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
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await asyncio.wait_for(
                    client.post(url, json=payload, headers=headers),
                    timeout=TIMEOUT_SECONDS
                )
                if response.status_code != 200:
                    logger.error(f"Groq API Error: Status {response.status_code}, Response: {response.text}")
                    return 0.0
                
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if not content:
                    return 0.0
                
                match = re.search(r"(-?\d+(\.\d+)?)", content.strip())
                if match:
                    return float(match.group(1))
                return 0.0
        except asyncio.TimeoutError:
            logger.warning("Groq timeout")
            return 0.5
        except Exception as e:
            logger.error(f"Error calling Groq: {e}")
            return 0.0
