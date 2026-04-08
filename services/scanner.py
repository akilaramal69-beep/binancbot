import asyncio
import logging
from core.config import settings
from analysis.engine import analyze_symbol
from execution.manager import RiskManager
from execution.executor import TradingExecutor
from services.telegram import TelegramService

logger = logging.getLogger("uvicorn")

class MarketScanner:
    def __init__(self):
        self.symbols = [s.strip() for s in settings.WATCH_SYMBOLS.split(",") if s.strip()]
        self.interval = settings.SCAN_INTERVAL_MINUTES * 60

    async def run_forever(self):
        logger.info(f"Starting Independent Scanner: Watching {self.symbols} every {settings.SCAN_INTERVAL_MINUTES} mins")
        
        executor = TradingExecutor()
        while True:
            try:
                # 1. First, check exits for all open positions
                await self.check_existing_positions(executor)

                # 2. Then, scan for new opportunities
                for symbol in self.symbols:
                    logger.info(f"--- Scanning Market for {symbol} ---")
                    await analyze_symbol(symbol)
                    
                logger.info(f"Scan complete. Sleeping for {settings.SCAN_INTERVAL_MINUTES} minutes...")
                await asyncio.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"Error in scanner loop: {e}")
                await asyncio.sleep(60) 

    async def check_existing_positions(self, executor: TradingExecutor):
        """
        Checks open positions for Take-Profit or Stop-Loss hits.
        """
        positions = RiskManager.load_positions()
        if not positions:
            return

        logger.info(f"Checking {len(positions)} open positions for EXITS...")
        for symbol, pos in list(positions.items()):
            try:
                current_price = await executor.get_latest_price(symbol)
                
                # Update Trailing Stop
                RiskManager.update_trailing_stop(symbol, current_price)
                
                # Fetch updated data to check TP/SL
                updated_pos = RiskManager.load_positions().get(symbol)
                sl_price = updated_pos["sl_price"]
                tp_price = updated_pos["tp_price"]

                # Check Exit
                should_exit = False
                reason = ""
                
                if current_price >= tp_price:
                    should_exit = True
                    reason = "Take Profit Hit 🎯"
                elif current_price <= sl_price:
                    should_exit = True
                    reason = "Stop Loss Hit 🛑"

                if should_exit:
                    logger.info(f"EXIT TRIGGERED for {symbol}: {reason} at {current_price}")
                    
                    # Execute the Sell Order to close position
                    await executor.place_order(symbol, "sell", pos["amount"])
                    
                    RiskManager.remove_position(symbol)
                    await TelegramService.send_message(
                        f"💰 <b>Position Closed</b> for {symbol}\n"
                        f"Reason: {reason}\n"
                        f"Exit Price: {current_price}\n"
                        f"Entry: {pos['entry_price']}"
                    )
            except Exception as e:
                logger.error(f"Error checking position for {symbol}: {e}")
