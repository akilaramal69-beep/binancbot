import pandas as pd
import numpy as np

class TechnicalAnalysis:
    @staticmethod
    def calculate_fibonacci_levels(high: float, low: float) -> dict:
        """
        Calculates Fibonacci retracement levels based on high and low price.
        """
        diff = high - low
        levels = {
            "level_0": high,
            "level_236": high - 0.236 * diff,
            "level_382": high - 0.382 * diff,
            "level_500": high - 0.5 * diff,
            "level_618": high - 0.618 * diff,
            "level_786": high - 0.786 * diff,
            "level_100": low
        }
        return levels

    @staticmethod
    def is_price_at_fib_level(price: float, levels: dict, tolerance: float = 0.005) -> str:
        """
        Checks if the current price is near any Fibonacci level within a tolerance percentage.
        """
        for level_name, level_price in levels.items():
            if abs(price - level_price) / level_price <= tolerance:
                return level_name
        return None

    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
        """
        Calculates Relative Strength Index (RSI).
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
