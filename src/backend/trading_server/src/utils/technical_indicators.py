"""
Technical Indicators for Trading AI
Implements common technical analysis indicators used in quantitative trading
"""

from typing import Optional

import numpy as np


class TechnicalIndicators:
    """Collection of technical indicators for market analysis"""

    @staticmethod
    def sma(prices: np.ndarray, period: int) -> np.ndarray:
        """Simple Moving Average"""
        if len(prices) < period:
            return np.full(len(prices), np.nan)
        result = np.full(len(prices), np.nan)
        for i in range(period - 1, len(prices)):
            result[i] = np.mean(prices[i - period + 1 : i + 1])
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
            ema_values[i] = alpha * prices[i] + (1 - alpha) * ema_values[i - 1]
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
        avg_gain = np.mean(gains[: period + 1])
        avg_loss = np.mean(losses[: period + 1])
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
    def macd(
        prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple:
        """MACD: (macd_line, signal_line, histogram)"""
        fast_ema = TechnicalIndicators.ema(prices, fast)
        slow_ema = TechnicalIndicators.ema(prices, slow)
        macd_line = fast_ema - slow_ema
        signal_line = TechnicalIndicators.ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def bollinger_bands(
        prices: np.ndarray, period: int = 20, num_std: float = 2.0
    ) -> tuple:
        """Bollinger Bands: (upper, middle, lower)"""
        if len(prices) < period:
            return (
                np.full(len(prices), np.nan),
                np.full(len(prices), np.nan),
                np.full(len(prices), np.nan),
            )
        middle = TechnicalIndicators.sma(prices, period)
        std = np.array(
            [
                (
                    np.std(prices[max(0, i - period + 1) : i + 1])
                    if i >= period - 1
                    else np.nan
                )
                for i in range(len(prices))
            ]
        )
        upper = middle + (num_std * std)
        lower = middle - (num_std * std)
        return upper, middle, lower

    @staticmethod
    def atr(
        high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
    ) -> np.ndarray:
        """Average True Range"""
        if len(high) < period + 1:
            return np.full(len(high), np.nan)
        tr = np.zeros(len(high))
        tr[0] = high[0] - low[0]
        for i in range(1, len(high)):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )
        atr_values = np.full(len(high), np.nan)
        atr_values[period] = np.mean(tr[1 : period + 1])
        for i in range(period + 1, len(high)):
            atr_values[i] = (atr_values[i - 1] * (period - 1) + tr[i]) / period
        return atr_values

    @staticmethod
    def stochastic(
        high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
    ) -> tuple:
        """Stochastic Oscillator: (%K, %D)"""
        if len(high) < period:
            return np.full(len(high), np.nan), np.full(len(high), np.nan)
        k_values = np.full(len(high), np.nan)
        for i in range(period - 1, len(high)):
            highest = np.max(high[i - period + 1 : i + 1])
            lowest = np.min(low[i - period + 1 : i + 1])
            if highest != lowest:
                k_values[i] = 100 * (close[i] - lowest) / (highest - lowest)
            else:
                k_values[i] = 50.0
        d_values = TechnicalIndicators.sma(k_values, 3)
        return k_values, d_values

    @staticmethod
    def williams_r(
        high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
    ) -> np.ndarray:
        """Williams %R"""
        if len(high) < period:
            return np.full(len(high), np.nan)
        wr_values = np.full(len(high), np.nan)
        for i in range(period - 1, len(high)):
            highest = np.max(high[i - period + 1 : i + 1])
            lowest = np.min(low[i - period + 1 : i + 1])
            if highest != lowest:
                wr_values[i] = -100 * (highest - close[i]) / (highest - lowest)
            else:
                wr_values[i] = -50.0
        return wr_values

    @staticmethod
    def cci(
        high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 20
    ) -> np.ndarray:
        """Commodity Channel Index"""
        if len(high) < period:
            return np.full(len(high), np.nan)
        tp = (high + low + close) / 3.0  # Typical Price
        sma_tp = TechnicalIndicators.sma(tp, period)
        mad = np.full(len(high), np.nan)  # Mean Absolute Deviation
        for i in range(period - 1, len(high)):
            mad[i] = np.mean(np.abs(tp[i - period + 1 : i + 1] - sma_tp[i]))
        cci_values = np.full(len(high), np.nan)
        for i in range(period - 1, len(high)):
            if mad[i] != 0:
                cci_values[i] = (tp[i] - sma_tp[i]) / (0.015 * mad[i])
            else:
                cci_values[i] = 0.0
        return cci_values

    @staticmethod
    def adx(
        high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
    ) -> np.ndarray:
        """Average Directional Index"""
        if len(high) < period * 2:
            return np.full(len(high), np.nan)
        # Calculate +DM and -DM
        plus_dm = np.zeros(len(high))
        minus_dm = np.zeros(len(high))
        for i in range(1, len(high)):
            up_move = high[i] - high[i - 1]
            down_move = low[i - 1] - low[i]
            if up_move > down_move and up_move > 0:
                plus_dm[i] = up_move
            if down_move > up_move and down_move > 0:
                minus_dm[i] = down_move
        # Smooth +DM and -DM
        atr_values = TechnicalIndicators.atr(high, low, close, period)
        plus_di = np.full(len(high), np.nan)
        minus_di = np.full(len(high), np.nan)
        for i in range(period, len(high)):
            if atr_values[i] != 0:
                plus_di[i] = 100 * (
                    np.mean(plus_dm[i - period + 1 : i + 1]) / atr_values[i]
                )
                minus_di[i] = 100 * (
                    np.mean(minus_dm[i - period + 1 : i + 1]) / atr_values[i]
                )
        # Calculate DX and ADX
        dx = np.full(len(high), np.nan)
        for i in range(period, len(high)):
            di_sum = plus_di[i] + minus_di[i]
            if di_sum != 0:
                dx[i] = 100 * abs(plus_di[i] - minus_di[i]) / di_sum
        adx_values = TechnicalIndicators.ema(dx, period)
        return adx_values

    @staticmethod
    def obv(close: np.ndarray, volume: Optional[np.ndarray] = None) -> np.ndarray:
        """On-Balance Volume (requires volume data)"""
        if volume is None:
            return np.full(len(close), np.nan)
        obv_values = np.zeros(len(close))
        obv_values[0] = volume[0]
        for i in range(1, len(close)):
            if close[i] > close[i - 1]:
                obv_values[i] = obv_values[i - 1] + volume[i]
            elif close[i] < close[i - 1]:
                obv_values[i] = obv_values[i - 1] - volume[i]
            else:
                obv_values[i] = obv_values[i - 1]
        return obv_values

    @staticmethod
    def calculate_all_indicators(
        prices: np.ndarray,
        high: Optional[np.ndarray] = None,
        low: Optional[np.ndarray] = None,
        volume: Optional[np.ndarray] = None,
    ) -> dict:
        """
        Calculate all technical indicators

        :param prices: Close prices (or mid prices if high/low not available)
        :param high: High prices (optional, uses prices if not provided)
        :param low: Low prices (optional, uses prices if not provided)
        :param volume: Volume data (optional)
        :return: Dictionary of indicators
        """
        indicators = {}

        # Use prices as high/low if not provided (for tick data)
        if high is None:
            high = prices
        if low is None:
            low = prices

        # Moving Averages
        indicators["sma_5"] = TechnicalIndicators.sma(prices, 5)
        indicators["sma_10"] = TechnicalIndicators.sma(prices, 10)
        indicators["sma_20"] = TechnicalIndicators.sma(prices, 20)
        indicators["sma_50"] = TechnicalIndicators.sma(prices, 50)
        indicators["sma_100"] = TechnicalIndicators.sma(prices, 100)
        indicators["sma_200"] = TechnicalIndicators.sma(prices, 200)

        indicators["ema_8"] = TechnicalIndicators.ema(prices, 8)
        indicators["ema_12"] = TechnicalIndicators.ema(prices, 12)
        indicators["ema_21"] = TechnicalIndicators.ema(prices, 21)
        indicators["ema_26"] = TechnicalIndicators.ema(prices, 26)
        indicators["ema_50"] = TechnicalIndicators.ema(prices, 50)
        indicators["ema_200"] = TechnicalIndicators.ema(prices, 200)

        # Momentum Indicators
        indicators["rsi"] = TechnicalIndicators.rsi(prices, 14)
        indicators["rsi_7"] = TechnicalIndicators.rsi(prices, 7)
        indicators["rsi_21"] = TechnicalIndicators.rsi(prices, 21)

        macd_line, signal_line, histogram = TechnicalIndicators.macd(prices)
        indicators["macd"] = macd_line
        indicators["macd_signal"] = signal_line
        indicators["macd_histogram"] = histogram

        # Bollinger Bands
        upper_bb, middle_bb, lower_bb = TechnicalIndicators.bollinger_bands(prices)
        indicators["bb_upper"] = upper_bb
        indicators["bb_middle"] = middle_bb
        indicators["bb_lower"] = lower_bb
        indicators["bb_width"] = np.where(
            middle_bb != 0, (upper_bb - lower_bb) / middle_bb, 0
        )
        indicators["bb_percent"] = np.where(
            upper_bb != lower_bb, (prices - lower_bb) / (upper_bb - lower_bb), 0.5
        )

        # Volatility Indicators
        if np.array_equal(high, prices) and np.array_equal(low, prices):
            # For tick data, estimate high/low from prices
            atr_values = np.full(len(prices), np.nan)
        else:
            atr_values = TechnicalIndicators.atr(high, low, prices, 14)
        indicators["atr"] = atr_values
        indicators["atr_7"] = (
            TechnicalIndicators.atr(high, low, prices, 7)
            if not (np.array_equal(high, prices) and np.array_equal(low, prices))
            else np.full(len(prices), np.nan)
        )

        # Oscillators
        if not (np.array_equal(high, prices) and np.array_equal(low, prices)):
            stoch_k, stoch_d = TechnicalIndicators.stochastic(high, low, prices, 14)
            indicators["stoch_k"] = stoch_k
            indicators["stoch_d"] = stoch_d
            indicators["williams_r"] = TechnicalIndicators.williams_r(
                high, low, prices, 14
            )
            indicators["cci"] = TechnicalIndicators.cci(high, low, prices, 20)
            adx_values = TechnicalIndicators.adx(high, low, prices, 14)
            indicators["adx"] = adx_values
        else:
            indicators["stoch_k"] = np.full(len(prices), np.nan)
            indicators["stoch_d"] = np.full(len(prices), np.nan)
            indicators["williams_r"] = np.full(len(prices), np.nan)
            indicators["cci"] = np.full(len(prices), np.nan)
            indicators["adx"] = np.full(len(prices), np.nan)

        # Volume Indicators
        if volume is not None:
            indicators["obv"] = TechnicalIndicators.obv(prices, volume)
            indicators["volume_sma"] = TechnicalIndicators.sma(volume, 20)
        else:
            indicators["obv"] = np.full(len(prices), np.nan)
            indicators["volume_sma"] = np.full(len(prices), np.nan)

        # Price Changes
        indicators["price_change"] = np.diff(prices, prepend=prices[0])
        price_change_pct = np.zeros_like(prices)
        if len(prices) > 1:
            price_change_pct[1:] = np.where(
                prices[:-1] != 0, (prices[1:] - prices[:-1]) / prices[:-1], 0
            )
        indicators["price_change_pct"] = price_change_pct

        # Additional Price Features
        indicators["price_high_low_ratio"] = (
            np.where(low != 0, high / low, 1.0)
            if not (np.array_equal(high, prices) and np.array_equal(low, prices))
            else np.ones(len(prices))
        )

        # Moving Average Crossovers
        indicators["sma_cross_20_50"] = indicators["sma_20"] - indicators["sma_50"]
        indicators["ema_cross_12_26"] = indicators["ema_12"] - indicators["ema_26"]

        # Price Position
        indicators["price_position_sma20"] = np.where(
            indicators["sma_20"] != 0,
            (prices - indicators["sma_20"]) / indicators["sma_20"],
            0,
        )
        indicators["price_position_bb"] = indicators["bb_percent"]

        return indicators
