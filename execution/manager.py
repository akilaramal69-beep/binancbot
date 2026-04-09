import logging
import json
import os
import asyncio
import datetime

logger = logging.getLogger("uvicorn")

POSITIONS_FILE = "positions.json"
HISTORY_FILE = "history.json"
_file_lock = asyncio.Lock()

class RiskManager:
    @staticmethod
    def calculate_position_size(balance: float, risk_percent: float = 0.02, min_order_usd: float = 11.5) -> float:
        """
        Calculates position size with a safe $11.5 minimum floor for fees.
        """
        size = balance * risk_percent
        if balance >= min_order_usd and size < min_order_usd:
            return min_order_usd
        return size

    @staticmethod
    async def save_position(symbol: str, entry_price: float, amount: float, side: str, tp_price: float = 0.0, sl_price: float = 0.0, entry_time: float = 0.0):
        """
        Persists an open position with TP and Trailing SL.
        """
        positions = RiskManager.load_positions()
        
        final_tp = tp_price if tp_price is not None and tp_price > 0 else entry_price * 1.05
        final_sl = sl_price if sl_price is not None and sl_price > 0 else entry_price * 0.98
        
        positions[symbol] = {
            "entry_price": entry_price,
            "amount": amount,
            "side": side,
            "highest_price": entry_price,
            "tp_price": final_tp,
            "sl_price": final_sl,
            "original_sl": final_sl,
            "breakeven": False,
            "scaled_out": False,
            "opened_at": entry_time
        }
        async with _file_lock:
            with open(POSITIONS_FILE, "w") as f:
                json.dump(positions, f, indent=4)
        logger.info(f"Position saved for {symbol} at {entry_price}")

    @staticmethod
    def load_positions() -> dict:
        """
        Loads open positions from the JSON file.
        """
        if not os.path.exists(POSITIONS_FILE):
            return {}
        try:
            with open(POSITIONS_FILE, "r") as f:
                return json.load(f)
        except:
            return {}

    @staticmethod
    async def remove_position(symbol: str, exit_price: float = 0, reason: str = "Unknown"):
        """
        Removes a closed position and archives it to the history file.
        """
        positions = RiskManager.load_positions()
        if symbol in positions:
            closed_pos = positions[symbol]
            closed_pos["symbol"] = symbol
            closed_pos["exit_price"] = exit_price
            closed_pos["exit_reason"] = reason
            closed_pos["closed_at"] = datetime.datetime.now().isoformat()
            
            pnl = (exit_price - closed_pos["entry_price"]) * closed_pos["amount"]
            if closed_pos["side"] == "sell":
                pnl = -pnl
            closed_pos["pnl"] = pnl
            
            await RiskManager.archive_to_history(closed_pos)
            
            del positions[symbol]
            async with _file_lock:
                with open(POSITIONS_FILE, "w") as f:
                    json.dump(positions, f, indent=4)
            logger.info(f"Position removed and archived for {symbol}")

    @staticmethod
    async def archive_to_history(data: dict):
        """
        Appends historical trade data to history.json.
        """
        history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    history = json.load(f)
            except:
                history = []
        
        history.append(data)
        async with _file_lock:
            with open(HISTORY_FILE, "w") as f:
                json.dump(history, f, indent=4)

    @staticmethod
    async def update_trailing_stop(symbol: str, current_price: float):
        """
        Updates the highest price seen to move the trailing stop-loss up.
        """
        positions = RiskManager.load_positions()
        if symbol in positions:
            pos = positions[symbol]
            if current_price > pos["highest_price"]:
                pos["highest_price"] = current_price
                new_sl = current_price * 0.98
                if new_sl > pos["sl_price"]:
                    pos["sl_price"] = new_sl
                    logger.info(f"Trailing SL moved up for {symbol} to {new_sl}")
                
            async with _file_lock:
                with open(POSITIONS_FILE, "w") as f:
                    json.dump(positions, f, indent=4)

    @staticmethod
    async def update_position_data(symbol: str, data: dict):
        """
        Updates arbitrary keys for a given position.
        """
        positions = RiskManager.load_positions()
        if symbol in positions:
            positions[symbol].update(data)
            async with _file_lock:
                with open(POSITIONS_FILE, "w") as f:
                    json.dump(positions, f, indent=4)

    @staticmethod
    def get_stop_loss_price(entry_price: float, side: str, stop_loss_percent: float = 0.02) -> float:
        if side == "buy":
            return entry_price * (1 - stop_loss_percent)
        else:
            return entry_price * (1 + stop_loss_percent)

    @staticmethod
    def get_take_profit_price(entry_price: float, side: str, take_profit_percent: float = 0.05) -> float:
        if side == "buy":
            return entry_price * (1 + take_profit_percent)
        else:
            return entry_price * (1 - take_profit_percent)
