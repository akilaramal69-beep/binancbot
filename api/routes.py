from fastapi import APIRouter
from core.config import settings
import logging
import os
import json
from execution.manager import RiskManager
from execution.executor import TradingExecutor

router = APIRouter()
logger = logging.getLogger("uvicorn")

@router.get("/balance")
async def get_balance():
    executor = TradingExecutor()
    try:
        balance = await executor.get_balance("USDT")
        return {"balance": balance}
    finally:
        await executor.close_connection()

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

@router.get("/analysis")
async def get_analysis():
    cache_file = "latest_analysis.json"
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return json.load(f)
    return {}

@router.get("/analysis_history")
async def get_analysis_history():
    history_file = "analysis_history.json"
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            return json.load(f)
    return []

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
