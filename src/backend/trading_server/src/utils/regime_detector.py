"""
Regime Detection Module

Detects market regimes (volatility, trend, market state) for feature engineering.
"""

import numpy as np
from typing import Dict, Optional
from enum import Enum


class VolatilityRegime(str, Enum):
    """Volatility regime classification"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class TrendRegime(str, Enum):
    """Trend regime classification"""

    STRONG_UP = "strong_up"
    WEAK_UP = "weak_up"
    SIDEWAYS = "sideways"
    WEAK_DOWN = "weak_down"
    STRONG_DOWN = "strong_down"


class MarketState(str, Enum):
    """Overall market state classification"""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    VOLATILE = "volatile"
    CALM = "calm"


class RegimeDetector:
    """
    Detects market regimes from price data
    """

    @staticmethod
    def detect_volatility_regime(
        prices: np.ndarray, period: int = 20, lookback: int = 100
    ) -> np.ndarray:
        """
        Detect volatility regime based on price volatility

        :param prices: Price array
        :param period: Period for volatility calculation
        :param lookback: Lookback period for regime classification
        :return: Array of VolatilityRegime values
        """
        if len(prices) < period + lookback:
            return np.full(len(prices), VolatilityRegime.MEDIUM.value)

        # Calculate rolling volatility (standard deviation of returns)
        returns = np.diff(prices, prepend=prices[0]) / prices
        volatility = np.full(len(prices), np.nan)

        for i in range(period - 1, len(prices)):
            volatility[i] = np.std(returns[i - period + 1 : i + 1])

        # Classify based on percentile of historical volatility
        regimes = np.full(len(prices), VolatilityRegime.MEDIUM.value)

        for i in range(lookback, len(prices)):
            if np.isnan(volatility[i]):
                continue

            # Get historical volatility for percentile calculation
            hist_vol = volatility[i - lookback + 1 : i + 1]
            hist_vol = hist_vol[~np.isnan(hist_vol)]

            if len(hist_vol) == 0:
                continue

            current_vol = volatility[i]
            p25 = np.percentile(hist_vol, 25)
            # p50 = np.percentile(hist_vol, 50)  # Not used currently
            p75 = np.percentile(hist_vol, 75)
            p95 = np.percentile(hist_vol, 95)

            if current_vol >= p95:
                regimes[i] = VolatilityRegime.EXTREME.value
            elif current_vol >= p75:
                regimes[i] = VolatilityRegime.HIGH.value
            elif current_vol <= p25:
                regimes[i] = VolatilityRegime.LOW.value
            else:
                regimes[i] = VolatilityRegime.MEDIUM.value

        return regimes

    @staticmethod
    def detect_trend_regime(
        prices: np.ndarray,
        short_period: int = 20,
        long_period: int = 50,
        strength_threshold: float = 0.5,
    ) -> np.ndarray:
        """
        Detect trend regime based on moving average crossovers and slope

        :param prices: Price array
        :param short_period: Short moving average period
        :param long_period: Long moving average period
        :param strength_threshold: Threshold for strong vs weak trend
        :return: Array of TrendRegime values
        """
        if len(prices) < long_period:
            return np.full(len(prices), TrendRegime.SIDEWAYS.value)

        # Calculate moving averages
        from utils.technical_indicators import TechnicalIndicators

        sma_short = TechnicalIndicators.sma(prices, short_period)
        sma_long = TechnicalIndicators.sma(prices, long_period)

        # Calculate price slope (rate of change)
        price_slope = np.full(len(prices), 0.0)
        for i in range(1, len(prices)):
            if prices[i - 1] != 0:
                price_slope[i] = (
                    (prices[i] - prices[i - short_period])
                    / (prices[i - short_period] * short_period)
                    if i >= short_period
                    else 0.0
                )

        regimes = np.full(len(prices), TrendRegime.SIDEWAYS.value)

        for i in range(long_period, len(prices)):
            if np.isnan(sma_short[i]) or np.isnan(sma_long[i]):
                continue

            # Determine trend direction
            ma_diff = sma_short[i] - sma_long[i]
            slope = price_slope[i]

            # Classify trend
            if ma_diff > 0 and abs(slope) > strength_threshold:
                regimes[i] = TrendRegime.STRONG_UP.value
            elif ma_diff > 0 and abs(slope) <= strength_threshold:
                regimes[i] = TrendRegime.WEAK_UP.value
            elif ma_diff < 0 and abs(slope) > strength_threshold:
                regimes[i] = TrendRegime.STRONG_DOWN.value
            elif ma_diff < 0 and abs(slope) <= strength_threshold:
                regimes[i] = TrendRegime.WEAK_DOWN.value
            else:
                regimes[i] = TrendRegime.SIDEWAYS.value

        return regimes

    @staticmethod
    def detect_market_state(
        prices: np.ndarray,
        volatility_regime: Optional[np.ndarray] = None,
        trend_regime: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Detect overall market state from volatility and trend regimes

        :param prices: Price array
        :param volatility_regime: Optional pre-computed volatility regime
        :param trend_regime: Optional pre-computed trend regime
        :return: Array of MarketState values
        """
        if volatility_regime is None:
            volatility_regime = RegimeDetector.detect_volatility_regime(prices)

        if trend_regime is None:
            trend_regime = RegimeDetector.detect_trend_regime(prices)

        states = np.full(len(prices), MarketState.NEUTRAL.value)

        for i in range(len(prices)):
            vol_regime = volatility_regime[i]
            trend_reg = trend_regime[i]

            # Combine volatility and trend to determine market state
            if vol_regime in [
                VolatilityRegime.HIGH.value,
                VolatilityRegime.EXTREME.value,
            ]:
                states[i] = MarketState.VOLATILE.value
            elif vol_regime == VolatilityRegime.LOW.value:
                states[i] = MarketState.CALM.value
            elif trend_reg in [TrendRegime.STRONG_UP.value, TrendRegime.WEAK_UP.value]:
                states[i] = MarketState.BULLISH.value
            elif trend_reg in [
                TrendRegime.STRONG_DOWN.value,
                TrendRegime.WEAK_DOWN.value,
            ]:
                states[i] = MarketState.BEARISH.value
            else:
                states[i] = MarketState.NEUTRAL.value

        return states

    @staticmethod
    def extract_regime_features(
        prices: np.ndarray,
    ) -> Dict[str, np.ndarray]:
        """
        Extract all regime features as numeric values for feature engineering

        :param prices: Price array
        :return: Dictionary of regime features
        """
        volatility_regime = RegimeDetector.detect_volatility_regime(prices)
        trend_regime = RegimeDetector.detect_trend_regime(prices)
        market_state = RegimeDetector.detect_market_state(
            prices, volatility_regime, trend_regime
        )

        # Convert to numeric features
        features = {}

        # Volatility regime (one-hot encoded)
        features["volatility_low"] = (
            volatility_regime == VolatilityRegime.LOW.value
        ).astype(float)
        features["volatility_medium"] = (
            volatility_regime == VolatilityRegime.MEDIUM.value
        ).astype(float)
        features["volatility_high"] = (
            volatility_regime == VolatilityRegime.HIGH.value
        ).astype(float)
        features["volatility_extreme"] = (
            volatility_regime == VolatilityRegime.EXTREME.value
        ).astype(float)

        # Trend regime (one-hot encoded)
        features["trend_strong_up"] = (
            trend_regime == TrendRegime.STRONG_UP.value
        ).astype(float)
        features["trend_weak_up"] = (trend_regime == TrendRegime.WEAK_UP.value).astype(
            float
        )
        features["trend_sideways"] = (
            trend_regime == TrendRegime.SIDEWAYS.value
        ).astype(float)
        features["trend_weak_down"] = (
            trend_regime == TrendRegime.WEAK_DOWN.value
        ).astype(float)
        features["trend_strong_down"] = (
            trend_regime == TrendRegime.STRONG_DOWN.value
        ).astype(float)

        # Market state (one-hot encoded)
        features["market_bullish"] = (market_state == MarketState.BULLISH.value).astype(
            float
        )
        features["market_bearish"] = (market_state == MarketState.BEARISH.value).astype(
            float
        )
        features["market_neutral"] = (market_state == MarketState.NEUTRAL.value).astype(
            float
        )
        features["market_volatile"] = (
            market_state == MarketState.VOLATILE.value
        ).astype(float)
        features["market_calm"] = (market_state == MarketState.CALM.value).astype(float)

        return features
