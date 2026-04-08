import httpx
from core.config import settings
import logging

logger = logging.getLogger("uvicorn")

class TelegramService:
    @staticmethod
    async def send_message(message: str):
        if not settings.ENABLE_TELEGRAM or not settings.TELEGRAM_BOT_TOKEN:
            logger.debug("Telegram notifications are disabled or token is missing.")
            return

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                logger.debug(f"Telegram message sent: {message[:50]}...")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
