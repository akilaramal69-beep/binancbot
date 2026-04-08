from fastapi import APIRouter
from core.config import settings
import logging
import os
import json
from execution.manager import RiskManager

router = APIRouter()
logger = logging.getLogger("uvicorn")

@router.get("/status")
async def get_status():
    positions = RiskManager.load_positions()
    return {
        "bot_name": "AI Trading Bot",
        "mode": "Independent Scanner",
        "symbols": settings.WATCH_SYMBOLS,
        "exchange": settings.EXCHANGE_ID,
        "testnet": settings.USE_TESTNET,
        "status": "active",
        "open_positions": len(positions)
    }

@router.get("/stats")
async def get_stats():
    positions = RiskManager.load_positions()
    history = []
    if os.path.exists("history.json"):
        try:
            with open("history.json", "r") as f:
                history = json.load(f)
        except:
            history = []
            
    return {
        "open_positions": positions,
        "total_completed_trades": len(history),
        "history": history[-10:] # Show last 10 for the UI
    }
