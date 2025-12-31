"""
Technical Indicators for Trading AI
Implements common technical analysis indicators used in quantitative trading
"""
import numpy as np
from typing import Optional


class TechnicalIndicators:
    """Collection of technical indicators for market analysis"""
    
    @staticmethod
    def sma(prices: np.ndarray, period: int) -> np.ndarray:
        """Simple Moving Average"""
        if len(prices) < period:
            return np.full(len(prices), np.nan)
        result = np.full(len(prices), np.nan)
        for i in range(period - 1, len(prices)):
            result[i] = np.mean(prices[i - period + 1:i + 1])
        return result
    
    @staticmethod
    def ema(prices: np.ndarray, period: int) -> np.ndarray:
        """Exponential Moving Average"""
        if len(prices) < period:
            return np.full(len(prices), np.nan)
        alpha = 2.0 / (period + 1.0)
        ema_values = np.zeros_like(prices)
        ema_values[0] = prices[0]
        for i in range(1, len(prices)):
            ema_values[i] = alpha * prices[i] + (1 - alpha) * ema_values[i-1]
        return ema_values
    
    @staticmethod
    def rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Relative Strength Index (0-100)"""
        if len(prices) < period + 1:
            return np.full(len(prices), 50.0)
        deltas = np.diff(prices, prepend=prices[0])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        rsi_values = np.full(len(prices), 50.0)
        avg_gain = np.mean(gains[:period+1])
        avg_loss = np.mean(losses[:period+1])
        if avg_loss == 0:
            rsi_values[period] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_values[period] = 100 - (100 / (1 + rs))
        for i in range(period + 1, len(prices)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss == 0:
                rsi_values[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi_values[i] = 100 - (100 / (1 + rs))
        return rsi_values
    
    @staticmethod
    def macd(prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """MACD: (macd_line, signal_line, histogram)"""
        fast_ema = TechnicalIndicators.ema(prices, fast)
        slow_ema = TechnicalIndicators.ema(prices, slow)
        macd_line = fast_ema - slow_ema
        signal_line = TechnicalIndicators.ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    @staticmethod
    def bollinger_bands(prices: np.ndarray, period: int = 20, num_std: float = 2.0) -> tuple:
        """Bollinger Bands: (upper, middle, lower)"""
        if len(prices) < period:
            return np.full(len(prices), np.nan), np.full(len(prices), np.nan), np.full(len(prices), np.nan)
        middle = TechnicalIndicators.sma(prices, period)
        std = np.array([np.std(prices[max(0, i-period+1):i+1]) if i >= period-1 else np.nan for i in range(len(prices))])
        upper = middle + (num_std * std)
        lower = middle - (num_std * std)
        return upper, middle, lower
    
    @staticmethod
    def calculate_all_indicators(prices: np.ndarray) -> dict:
        """Calculate all technical indicators"""
        indicators = {}
        indicators['sma_20'] = TechnicalIndicators.sma(prices, 20)
        indicators['sma_50'] = TechnicalIndicators.sma(prices, 50)
        indicators['ema_12'] = TechnicalIndicators.ema(prices, 12)
        indicators['ema_26'] = TechnicalIndicators.ema(prices, 26)
        indicators['rsi'] = TechnicalIndicators.rsi(prices, 14)
        macd_line, signal_line, histogram = TechnicalIndicators.macd(prices)
        indicators['macd'] = macd_line
        indicators['macd_signal'] = signal_line
        indicators['macd_histogram'] = histogram
        upper_bb, middle_bb, lower_bb = TechnicalIndicators.bollinger_bands(prices)
        indicators['bb_upper'] = upper_bb
        indicators['bb_middle'] = middle_bb
        indicators['bb_lower'] = lower_bb
        indicators['bb_width'] = np.where(middle_bb != 0, (upper_bb - lower_bb) / middle_bb, 0)
        indicators['price_change'] = np.diff(prices, prepend=prices[0])
        indicators['price_change_pct'] = np.where(prices[:-1] != 0, np.diff(prices, prepend=prices[0]) / prices[:-1], 0)
        if len(indicators['price_change_pct']) < len(prices):
            indicators['price_change_pct'] = np.append([0], indicators['price_change_pct'])
        return indicators
