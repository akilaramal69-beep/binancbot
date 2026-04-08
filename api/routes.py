from fastapi import APIRouter
from core.config import settings
import logging
import os
import json
import time
from execution.manager import RiskManager

START_TIME = time.time()
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
    last_scan_time = 0
    if os.path.exists("latest_analysis.json"):
        last_scan_time = os.path.getmtime("latest_analysis.json")
        
    total_scans = 0
    if os.path.exists("total_scans.json"):
        try:
            with open("total_scans.json", "r") as f:
                total_scans = json.load(f).get("count", 0)
        except:
            pass
        
    return {
        "bot_name": "AI Trading Bot",
        "mode": "Independent Scanner",
        "symbols": settings.WATCH_SYMBOLS,
        "exchange": settings.EXCHANGE_ID,
        "testnet": settings.USE_TESTNET,
        "status": "active",
        "open_positions": len(positions),
        "scan_interval": settings.SCAN_INTERVAL_MINUTES,
        "last_scan_time": last_scan_time,
        "total_scans": total_scans,
        "bot_start_time": START_TIME
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
