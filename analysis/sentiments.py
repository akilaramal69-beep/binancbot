import httpx
from core.config import settings
import logging

logger = logging.getLogger("uvicorn")

class SentimentAnalysis:
    @staticmethod
    async def get_news_sentiment(symbol: str) -> float:
        """
        Fetches news related to the symbol and uses AI to determine sentiment.
        Returns a score between -1 (Bearish) and 1 (Bullish).
        """
        try:
            # For demonstration, we'll fetch mock news or 
            # actually call CryptoPanic if an API key is provided
            news_data = await SentimentAnalysis._fetch_news(symbol)
            
            if not settings.OPENAI_API_KEY and not settings.GROQ_API_KEY:
                logger.warning("No AI API key found. Skipping sentiment analysis.")
                return 0.0
            
            # Combine news into a prompt
            prompt = f"Analyze the sentiment of the following news for {symbol}. Return ONLY a number between -1 and 1.\n\nNews:\n{news_data}"
            
            # Use Groq if available, else OpenAI
            if settings.GROQ_API_KEY:
                return await SentimentAnalysis._call_groq(prompt)
            else:
                return await SentimentAnalysis._call_openai(prompt)
                
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return 0.0

    @staticmethod
    async def _fetch_news(symbol: str) -> str:
        # Placeholder for real news fetching logic
        # Could use NewsAPI or CryptoPanic
        return f"Bullish progress for {symbol} as adoption grows. Regulators showing positive interest."

    @staticmethod
    async def _call_openai(prompt: str) -> float:
        # Simple OpenAI integration
        import openai
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return float(response.choices[0].message.content.strip())

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
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()
                
                # Extract the numeric sentiment value
                import re
                match = re.search(r"(-?\d+(\.\d+)?)", content)
                if match:
                    return float(match.group(1))
                return 0.0
        except Exception as e:
            logger.error(f"Error calling Groq: {e}")
            return 0.0
