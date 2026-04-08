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
                sl_price = updated_pos["sl_price"]
                tp_price = updated_pos["tp_price"]
                entry_price = updated_pos["entry_price"]
                amount = updated_pos["amount"]

                target_distance = tp_price - entry_price
                level1 = entry_price + (target_distance * 0.5)
                level2 = entry_price + (target_distance * 0.9)

                # Level 1: Breakeven (50% to target)
                if target_distance > 0 and current_price >= level1 and not updated_pos.get("breakeven"):
                    new_sl = max(sl_price, entry_price) # Move Stop Loss to Entry
                    RiskManager.update_position_data(symbol, {"breakeven": True, "sl_price": new_sl})
                    await TelegramService.send_message(f"🛡️ <b>Breakeven Activated</b> for {symbol}\nPrice reached 50% of target. Stop Loss secured at ${new_sl:.2f}.")

                # Level 2: Scale Out (90% to target)
                if target_distance > 0 and current_price >= level2 and not updated_pos.get("scaled_out"):
                    half_amount = amount * 0.5
                    # Binance strict MIN_NOTIONAL check (~$10, we use $11 to be safe)
                    if half_amount * current_price >= 11:
                        logger.info(f"Selling 50% of {symbol} at Level 2...")
                        await executor.place_order(symbol, "sell", half_amount)
                        RiskManager.update_position_data(symbol, {
                            "scaled_out": True, 
                            "amount": amount - half_amount,
                            "sl_price": current_price * 0.98 # Tighten SL
                        })
                        await TelegramService.send_message(f"🎯 <b>Level 2 Profit (50%)</b> for {symbol}\nSecured 50% profit, letting the rest run.")

                # Fetch updated SL after multi-step logic might have changed it
                sl_price = RiskManager.load_positions().get(symbol, {}).get("sl_price", sl_price)

                # Check Exit (Full closure)
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
                    
                    RiskManager.remove_position(symbol, exit_price=current_price, reason=reason)
                    await TelegramService.send_message(
                        f"💰 <b>Position Closed</b> for {symbol}\n"
                        f"Reason: {reason}\n"
                        f"Exit Price: {current_price}\n"
                        f"Entry: {pos['entry_price']}"
                    )
            except Exception as e:
                logger.error(f"Error checking position for {symbol}: {e}")
