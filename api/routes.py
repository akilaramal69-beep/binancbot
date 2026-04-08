from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from core.config import settings
from analysis.engine import process_signal
import logging

router = APIRouter()
logger = logging.getLogger("uvicorn")

@router.post("/webhook")
async def tradingview_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives alerts from TradingView.
    Expected JSON: {"passphrase": "...", "symbol": "BTC/USDT", "side": "buy", "type": "long_entry", "price": 45000}
    """
    data = await request.json()
    
    if "passphrase" not in data or data["passphrase"] != settings.WEBHOOK_PASSPHRASE:
        logger.warning(f"Unauthorized webhook attempt from {request.client.host}")
        raise HTTPException(status_code=401, detail="Invalid passphrase")

    # Queue the signal for background processing (AI analysis + execution)
    background_tasks.add_task(process_signal, data)
    
    return {"status": "success", "message": "Signal queued for analysis and execution"}

@router.get("/status")
async def get_status():
    return {
        "bot_name": "AI Trading Bot",
        "exchange": settings.EXCHANGE_ID,
        "testnet": settings.USE_TESTNET,
        "status": "active"
    }

@router.get("/")
async def root():
    return {"message": "AI Trading Bot is running"}
