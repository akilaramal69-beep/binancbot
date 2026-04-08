import logging
import httpx
from core.config import settings
from execution.manager import RiskManager
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger("uvicorn")

class TelegramService:
    @staticmethod
    async def send_message(text: str):
        """
        Sends a simple push message (as before).
        """
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            return

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload)
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")

    @staticmethod
    async def start_interactive_bot():
        """
        Starts the Telegram command listener.
        """
        if not settings.TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram Bot Token missing. Interactive features disabled.")
            return

        application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

        # Add Command Handlers
        application.add_handler(CommandHandler("start", TelegramService.cmd_start))
        application.add_handler(CommandHandler("holdings", TelegramService.cmd_holdings))
        application.add_handler(CommandHandler("status", TelegramService.cmd_status))
        application.add_handler(CommandHandler("stats", TelegramService.cmd_status))

        logger.info("Starting Telegram Interactive Listener...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()

    @staticmethod
    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🚀 <b>AI Trading Bot Active!</b>\n\n"
            "Commands:\n"
            "/holdings - See what we are currently buying\n"
            "/status - General bot health\n"
            "/stats - Performance history",
            parse_mode="HTML"
        )

    @staticmethod
    async def cmd_holdings(update: Update, context: ContextTypes.DEFAULT_TYPE):
        positions = RiskManager.load_positions()
        if not positions:
            await update.message.reply_text("📭 No open positions at the moment.")
            return

        msg = "🎯 <b>Current Holdings:</b>\n\n"
        for symbol, pos in positions.items():
            msg += f"• <b>{symbol}</b>\n"
            msg += f"  Entry: ${pos['entry_price']}\n"
            msg += f"  Amount: {pos['amount']:.4f}\n"
            msg += f"  Target (TP): ${pos['tp_price']:.2f}\n"
            msg += f"  Stop (SL): ${pos['sl_price']:.2f}\n\n"
        
        await update.message.reply_text(msg, parse_mode="HTML")

    @staticmethod
    async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        positions = RiskManager.load_positions()
        import os, json
        history_count = 0
        if os.path.exists("history.json"):
            with open("history.json", "r") as f:
                history_count = len(json.load(f))

        msg = "🤖 <b>Bot Status:</b>\n\n"
        msg += f"✅ Scanner: Running\n"
        msg += f"📦 Open Positions: {len(positions)}\n"
        msg += f"📊 Completed Trades: {history_count}\n"
        msg += f"🎯 Watchlist: {settings.WATCH_SYMBOLS}\n"
        
        await update.message.reply_text(msg, parse_mode="HTML")
