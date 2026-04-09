import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from typing import Optional

class TechnicalAnalysis:
    @staticmethod
    def calculate_fibonacci_levels(high: float, low: float) -> dict:
        """
        Calculates Fibonacci retracement levels based on high and low price.
        """
        if high <= low or high <= 0 or low <= 0:
            return {}
        
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
        if high <= low or high <= 0 or low <= 0:
            return {}
        
        diff = high - low
        extensions = {
            "level_1272": high + 0.272 * diff,
            "level_1618": high + 0.618 * diff
        }
        return extensions

    @staticmethod
    def is_price_at_fib_level(price: float, levels: dict, tolerance: float = 0.005) -> Optional[str]:
        """
        Checks if the current price is near any Fibonacci level within a tolerance percentage.
        """
        if not levels:
            return None
        for level_name, level_price in levels.items():
            if level_price > 0 and abs(price - level_price) / level_price <= tolerance:
                return level_name
        return None

    @staticmethod
    def calculate_rsi(prices, period: int = 14) -> float:
        """
        Calculates Relative Strength Index (RSI) using Wilder's smoothing (EMA with alpha=1/period).
        """
        if not isinstance(prices, pd.Series):
            prices = pd.Series(prices)
        
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        
        alpha = 1.0 / period
        avg_gain = gain.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
        
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

    @staticmethod
    def calculate_ema(prices, period: int = 20) -> float:
        """
        Calculates Exponential Moving Average (EMA).
        """
        if len(prices) < period:
            return 0.0
        
        return float(pd.Series(prices).ewm(span=period, adjust=False).mean().iloc[-1])

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
        result = atr.iloc[-1]
        return float(result) if not pd.isna(result) else 0.0

    @staticmethod
    def is_volume_spike(volumes: list, period: int = 20, multiplier: float = 1.5) -> bool:
        """ Confirms if current volume is significantly higher than moving average. """
        if len(volumes) < period: return False
        series = pd.Series(volumes)
        sma = series.rolling(window=period-1).mean().iloc[-2]
        if pd.isna(sma) or sma <= 0:
            return False
        current_vol = series.iloc[-1]
        return current_vol > (sma * multiplier)

    @staticmethod
    def detect_bos(highs: list, lows: list, current_price: float) -> bool:
        """
        Detects Break of Structure (BOS) - both bullish and bearish.
        Bullish BOS: price breaks above recent high
        Bearish BOS: price breaks below recent low
        """
        if len(highs) < 10 or len(lows) < 10: return False
        recent_high = max(highs[-10:-1])
        recent_low = min(lows[-10:-1])
        if current_price > recent_high:
            return True
        if current_price < recent_low:
            return True
        return False
        
    @staticmethod
    def identify_elliott_wave(closes: list) -> str:
        """
        Uses Scipy argrelextrema to identify local peaks and troughs 
        to validate short-term 5-wave motive sequences.
        """
        if len(closes) < 30: return "None"
        
        data = np.array(closes)
        smoothed = pd.Series(data).rolling(window=3).mean().dropna()
        
        peaks = argrelextrema(smoothed.values, np.greater, order=2)[0]
        troughs = argrelextrema(smoothed.values, np.less, order=2)[0]
        
        if len(peaks) < 2 or len(troughs) < 2:
            return "None"
            
        all_extrema = sorted(np.concatenate((peaks, troughs)))
        recent = all_extrema[-6:] 
        
        points = [smoothed.iloc[i] for i in recent]
        
        if len(points) >= 5:
            start, w1_high, w2_low, w3_high, w4_low = points[-5:]
            
            wave_1_movement = w1_high - start
            wave_2_movement = w1_high - w2_low
            wave_3_movement = w3_high - w2_low
            
            if w2_low < start: return "None"
            if w3_high <= w1_high: return "None"
            if w4_low <= w1_high: return "None"
            
            current_price = closes[-1]
            wave_5_movement = current_price - w4_low
            
            if wave_3_movement < wave_1_movement and wave_3_movement < wave_5_movement:
                return "None"
            
            if current_price > w3_high:
                return "Wave 5 Breakout"
            elif current_price > w4_low and current_price <= w3_high:
                return "Wave 5 Ignition"
                
        if len(points) >= 4:
            start, w1_high, w2_low, w3_high = points[-4:]
            if w2_low >= start and w3_high > w1_high:
                current_price = closes[-1]
                if current_price > w1_high and current_price < w3_high:
                    return "Wave 4 Retracement"
        
        return "None"
    
    @staticmethod
    def calculate_fibonacci_bearish(high: float, low: float) -> dict:
        """Calculates Fibonacci retracement for bearish trends."""
        if high <= low or high <= 0 or low <= 0:
            return {}
        
        diff = high - low
        return {
            "level_0": low,
            "level_236": low + 0.236 * diff,
            "level_382": low + 0.382 * diff,
            "level_500": low + 0.5 * diff,
            "level_618": low + 0.618 * diff,
            "level_786": low + 0.786 * diff,
            "level_100": high
        }
