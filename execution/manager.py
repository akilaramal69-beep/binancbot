import logging
import json
import os

logger = logging.getLogger("uvicorn")

POSITIONS_FILE = "positions.json"

class RiskManager:
    @staticmethod
    def calculate_position_size(balance: float, risk_percent: float = 0.02, min_order_usd: float = 10.0) -> float:
        """
        Calculates position size with Binance $10 minimum floor.
        """
        size = balance * risk_percent
        if balance >= min_order_usd and size < min_order_usd:
            return min_order_usd
        return size

    @staticmethod
    def save_position(symbol: str, entry_price: float, amount: float, side: str, tp_price: float = None):
        """
        Persists an open position with TP and Trailing SL.
        """
        positions = RiskManager.load_positions()
        
        # Default TP if not provided (5%)
        final_tp = tp_price if tp_price else entry_price * 1.05
        
        positions[symbol] = {
            "entry_price": entry_price,
            "amount": amount,
            "side": side,
            "highest_price": entry_price,
            "tp_price": final_tp,
            "sl_price": entry_price * 0.98
        }
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
    def remove_position(symbol: str):
        """
        Removes a closed position from the JSON file.
        """
        positions = RiskManager.load_positions()
        if symbol in positions:
            del positions[symbol]
            with open(POSITIONS_FILE, "w") as f:
                json.dump(positions, f, indent=4)
            logger.info(f"Position removed for {symbol}")

    @staticmethod
    def update_trailing_stop(symbol: str, current_price: float):
        """
        Updates the highest price seen to move the trailing stop-loss up.
        """
        positions = RiskManager.load_positions()
        if symbol in positions:
            pos = positions[symbol]
            if current_price > pos["highest_price"]:
                pos["highest_price"] = current_price
                # Keep SL 2% below highest price
                new_sl = current_price * 0.98
                if new_sl > pos["sl_price"]:
                    pos["sl_price"] = new_sl
                    logger.info(f"Trailing SL moved up for {symbol} to {new_sl}")
                
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
