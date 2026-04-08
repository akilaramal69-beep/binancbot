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
    def calculate_fibonacci_extensions(high: float, low: float) -> dict:
        """
        Calculates Fibonacci extension levels for Take-Profit targets.
        """
        diff = high - low
        extensions = {
            "level_1272": high + 0.272 * diff,
            "level_1618": high + 0.618 * diff
        }
        return extensions

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

    @staticmethod
    def calculate_ema(prices: list, period: int = 20) -> float:
        """
        Calculates Exponential Moving Average (EMA).
        """
        if len(prices) < period:
            return 0.0
        
        df = pd.DataFrame(prices, columns=['price'])
        ema = df['price'].ewm(span=period, adjust=False).mean()
        return float(ema.iloc[-1])
