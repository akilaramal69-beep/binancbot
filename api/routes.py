from fastapi import APIRouter
from core.config import settings
import logging

router = APIRouter()
logger = logging.getLogger("uvicorn")

@router.get("/status")
async def get_status():
    return {
        "bot_name": "AI Trading Bot",
        "mode": "Independent Scanner",
        "symbols": settings.WATCH_SYMBOLS,
        "exchange": settings.EXCHANGE_ID,
        "testnet": settings.USE_TESTNET,
        "status": "active"
    }

@router.get("/")
async def root():
    return {"message": "AI Trading Bot Independent Scanner is running"}
