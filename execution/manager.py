import logging

logger = logging.getLogger("uvicorn")

class RiskManager:
    @staticmethod
    def calculate_position_size(balance: float, risk_percent: float = 0.02, min_order_usd: float = 10.0) -> float:
        """
        Calculates position size. For small budgets (like $10), it ensures 
        the minimum order size required by Binance is met.
        """
        size = balance * risk_percent
        
        # If the account is small, we must use the minimum order size
        # otherwise Binance will reject the trade.
        if balance >= min_order_usd and size < min_order_usd:
            logger.info(f"Budget constraint: Adjusting position size to Binance minimum ${min_order_usd}")
            return min_order_usd
            
        return size

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
