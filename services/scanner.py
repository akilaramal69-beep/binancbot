import asyncio
import logging
import time
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
        self._executor = None
        self._last_position_check = 0
        self._consecutive_failures = 0

    async def _get_executor(self) -> TradingExecutor:
        if self._executor is None:
            self._executor = TradingExecutor()
        return self._executor

    async def run_forever(self):
        logger.info(f"Starting Independent Scanner: Watching {self.symbols} every {settings.SCAN_INTERVAL_MINUTES} mins")
        
        while True:
            scan_start = time.time()
            executor = await self._get_executor()
            
            try:
                # Check exits (every 30s minimum)
                current_time = time.time()
                if current_time - self._last_position_check > 30:
                    await self.check_existing_positions(executor)
                    self._last_position_check = current_time
                
                # Scan all symbols in parallel
                results = await asyncio.gather(*[
                    analyze_symbol(symbol) for symbol in self.symbols
                ], return_exceptions=True)
                
                # Track failures
                failures = sum(1 for r in results if isinstance(r, Exception))
                self._consecutive_failures = 0 if failures == 0 else self._consecutive_failures + 1
                
                elapsed = time.time() - scan_start
                logger.info(f"Scan complete in {elapsed:.2f}s. Sleeping for {settings.SCAN_INTERVAL_MINUTES} minutes...")
                await asyncio.sleep(self.interval)
                
            except Exception as e:
                self._consecutive_failures += 1
                logger.error(f"Error in scanner loop: {e}")
                
                # Circuit breaker: pause on consecutive failures
                if self._consecutive_failures >= 3:
                    logger.warning("Circuit breaker triggered - pausing scanner for 5 minutes")
                    await asyncio.sleep(300)
                else:
                    await asyncio.sleep(60) 

    async def check_existing_positions(self, executor: TradingExecutor):
        """
        Checks open positions for Take-Profit or Stop-Loss hits.
        """
        positions = RiskManager.load_positions()
        if not positions:
            return

        logger.info(f"Checking {len(positions)} open positions for EXITS...")
        
        symbols = list(positions.keys())
        prices = await asyncio.gather(*[executor.get_latest_price(s) for s in symbols], return_exceptions=True)
        
        # Debounce: don't exit same position within 60 seconds of last check
        import time
        now = time.time()
        
        for symbol, price_result in zip(symbols, prices):
            if not isinstance(price_result, (float, int)) or price_result is None:
                logger.error(f"Invalid price for {symbol}: {price_result}")
                continue
            
            current_price = float(price_result)
            pos = positions[symbol]
            
            # Skip if recently opened (prevent immediate stop-loss on fresh entries)
            opened_at = pos.get("opened_at", 0)
            if now - opened_at < 60:
                continue
            
            # Max holding time check
            max_hold_seconds = settings.MAX_HOLDING_HOURS * 3600
            time_based_exit = False
            time_reason = ""
            if now - opened_at > max_hold_seconds:
                logger.info(f"Max holding time reached for {symbol}. Closing position.")
                time_based_exit = True
                time_reason = f"Max Hold Time ({settings.MAX_HOLDING_HOURS}h) 🚪"
            
            await RiskManager.update_trailing_stop(symbol, current_price)
            
            updated_pos = RiskManager.load_positions().get(symbol, pos)
            sl_price = updated_pos["sl_price"]
            tp_price = updated_pos["tp_price"]
            entry_price = updated_pos["entry_price"]
            amount = updated_pos["amount"]

            target_distance = tp_price - entry_price
            level1 = entry_price + (target_distance * 0.5)
            level2 = entry_price + (target_distance * 0.9)

            if not time_based_exit:
                if target_distance > 0 and current_price >= level1 and not updated_pos.get("breakeven"):
                    new_sl = max(sl_price, entry_price * 1.002)
                    await RiskManager.update_position_data(symbol, {"breakeven": True, "sl_price": new_sl})
                    await TelegramService.send_message(f"🛡️ <b>True Breakeven Activated</b> for {symbol}\nPrice reached 50% of target. Stop Loss secured at ${new_sl:.2f} (Covers Fees).")

                if target_distance > 0 and current_price >= level2 and not updated_pos.get("scaled_out"):
                    half_amount = amount * 0.5
                    if half_amount * current_price >= 11:
                        logger.info(f"Selling 50% of {symbol} at Level 2...")
                        await executor.place_order(symbol, "sell", half_amount)
                        await RiskManager.update_position_data(symbol, {
                            "scaled_out": True, 
                            "amount": amount - half_amount,
                            "sl_price": current_price * 0.98
                        })
                        await TelegramService.send_message(f"🎯 <b>Level 2 Profit (50%)</b> for {symbol}\nSecured 50% profit, letting the rest run.")

                sl_price = RiskManager.load_positions().get(symbol, {}).get("sl_price", sl_price)

            should_exit = False
            reason = ""
            
            if time_based_exit:
                should_exit = True
                reason = time_reason
            elif current_price >= tp_price:
                should_exit = True
                reason = "Take Profit Hit 🎯"
            elif current_price <= sl_price:
                should_exit = True
                reason = "Stop Loss Hit 🛑"

            if should_exit:
                logger.info(f"EXIT TRIGGERED for {symbol}: {reason} at {current_price}")
                await executor.place_order(symbol, "sell", pos["amount"])
                await RiskManager.remove_position(symbol, exit_price=current_price, reason=reason)
                await TelegramService.send_message(
                    f"💰 <b>Position Closed</b> for {symbol}\n"
                    f"Reason: {reason}\n"
                    f"Exit Price: {current_price}\n"
                    f"Entry: {pos['entry_price']}"
                )
