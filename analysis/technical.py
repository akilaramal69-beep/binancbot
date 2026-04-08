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

    @staticmethod
    def calculate_atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
        """ Calculates Average True Range (ATR) for volatility measurement. """
        if len(highs) < period: return 0.0
        df = pd.DataFrame({'high': highs, 'low': lows, 'close': closes})
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift())
        df['tr3'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        atr = df['tr'].rolling(window=period).mean()
        return float(atr.iloc[-1])

    @staticmethod
    def is_volume_spike(volumes: list, period: int = 20, multiplier: float = 1.5) -> bool:
        """ Confirms if current volume is significantly higher than moving average. """
        if len(volumes) < period: return False
        df = pd.DataFrame({'volume': volumes})
        # Use period-1 for SMA so current spike doesn't heavily distort average
        sma = df['volume'].rolling(window=period-1).mean().iloc[-2] 
        current_vol = df['volume'].iloc[-1]
        return current_vol > (sma * multiplier)

    @staticmethod
    def detect_bos(highs: list, lows: list, current_price: float) -> bool:
        """ Detects basic short-term Bullish Break of Structure. """
        if len(highs) < 10: return False
        recent_high = max(highs[-10:-1]) # Exclude current forming candle
        if current_price > recent_high:
            return True
        return False
