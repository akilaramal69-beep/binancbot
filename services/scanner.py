import asyncio
import logging
from core.config import settings
from analysis.engine import analyze_symbol

logger = logging.getLogger("uvicorn")

class MarketScanner:
    def __init__(self):
        self.symbols = [s.strip() for s in settings.WATCH_SYMBOLS.split(",") if s.strip()]
        self.interval = settings.SCAN_INTERVAL_MINUTES * 60

    async def run_forever(self):
        logger.info(f"Starting Independent Scanner: Watching {self.symbols} every {settings.SCAN_INTERVAL_MINUTES} mins")
        
        while True:
            try:
                for symbol in self.symbols:
                    logger.info(f"--- Scanning Market for {symbol} ---")
                    # We pass a minimal dict to analyze_symbol to maintain compatibility
                    # or better: refactor analyze_symbol to handle this
                    await analyze_symbol(symbol)
                    
                logger.info(f"Scan complete. Sleeping for {settings.SCAN_INTERVAL_MINUTES} minutes...")
                await asyncio.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"Error in scanner loop: {e}")
                await asyncio.sleep(60) # Wait a bit before retrying on error
