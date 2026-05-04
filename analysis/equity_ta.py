"""
Technical analysis on strategy equity curves for rotation signals.
"""

from typing import Dict, Optional, Tuple
import pandas as pd
import numpy as np
import logging

try:
    import pandas_ta as ta
    _PANDAS_TA_AVAILABLE = True
except ImportError:
    _PANDAS_TA_AVAILABLE = False

from config import (
    TA_MACD_FAST, TA_MACD_SLOW, TA_MACD_SIGNAL,
    TA_RSI_PERIOD,
    TA_SMA_FAST, TA_SMA_SLOW,
)

logger = logging.getLogger(__name__)


class EquityCurveAnalyzer:
    """
    Apply technical analysis indicators to equity curves for strategy rotation signals.
    """

    def __init__(
        self,
        macd_fast: int = None,
        macd_slow: int = None,
        macd_signal: int = None,
        rsi_period: int = None,
        sma_fast: int = None,
        sma_slow: int = None,
        ema_fast: int = None,
        ema_slow: int = None,
        bb_period: int = 20,
        bb_std: float = 2.0,
    ):
        """
        Initialize the analyzer with TA parameters.

        Args:
            macd_fast: MACD fast period (default from config)
            macd_slow: MACD slow period (default from config)
            macd_signal: MACD signal period (default from config)
            rsi_period: RSI period (default from config)
            sma_fast: SMA fast period (default from config)
            sma_slow: SMA slow period (default from config)
            ema_fast: EMA fast period (default: 12)
            ema_slow: EMA slow period (default: 26)
            bb_period: Bollinger Bands period (default: 20)
            bb_std: Bollinger Bands standard deviations (default: 2.0)
        """
        if not _PANDAS_TA_AVAILABLE:
            raise ImportError("pandas-ta is required. Install with: pip install pandas-ta")

        self.macd_fast = macd_fast or TA_MACD_FAST
        self.macd_slow = macd_slow or TA_MACD_SLOW
        self.macd_signal = macd_signal or TA_MACD_SIGNAL
        self.rsi_period = rsi_period or TA_RSI_PERIOD
        self.sma_fast = sma_fast or TA_SMA_FAST
        self.sma_slow = sma_slow or TA_SMA_SLOW
        self.ema_fast = ema_fast or 12
        self.ema_slow = ema_slow or 26
        self.bb_period = bb_period
        self.bb_std = bb_std

    def analyze(
        self,
        equity_curve: pd.Series,
        strategy_name: str = "strategy"
    ) -> pd.DataFrame:
        """
        Apply all TA indicators to an equity curve.

        Args:
            equity_curve: Series of portfolio values indexed by date
            strategy_name: Name of the strategy for column prefixing

        Returns:
            DataFrame with all TA indicators and signals
        """
        if equity_curve.empty:
            raise ValueError("Equity curve is empty")

        df = pd.DataFrame(index=equity_curve.index)
        df['value'] = equity_curve.values

        # Calculate all indicators
        macd_df = self.calculate_macd(equity_curve)
        rsi_df = self.calculate_rsi(equity_curve)
        sma_df = self.calculate_sma_crossover(equity_curve)
        ema_df = self.calculate_ema_crossover(equity_curve)
        bb_df = self.calculate_bollinger_bands(equity_curve)

        # Merge all indicators
        for indicator_df in [macd_df, rsi_df, sma_df, ema_df, bb_df]:
            df = df.join(indicator_df, how='left')

        # Generate composite signal
        df['composite_signal'] = self.generate_composite_signal(df)

        return df

    def calculate_macd(
        self,
        series: pd.Series,
        fast: int = None,
        slow: int = None,
        signal: int = None
    ) -> pd.DataFrame:
        """
        Calculate MACD indicator.

        Args:
            series: Price/value series
            fast: Fast period
            slow: Slow period
            signal: Signal period

        Returns:
            DataFrame with MACD, signal, histogram, and signal columns
        """
        fast = fast or self.macd_fast
        slow = slow or self.macd_slow
        signal = signal or self.macd_signal

        macd = ta.macd(series, fast=fast, slow=slow, signal=signal)

        if macd is None or macd.empty:
            return pd.DataFrame(index=series.index)

        # Rename columns for clarity
        macd.columns = ['macd', 'macd_histogram', 'macd_signal']

        # Generate signals
        # Bullish: MACD crosses above signal line
        # Bearish: MACD crosses below signal line
        macd['macd_cross_up'] = (
            (macd['macd'] > macd['macd_signal']) &
            (macd['macd'].shift(1) <= macd['macd_signal'].shift(1))
        ).astype(int)
        macd['macd_cross_down'] = (
            (macd['macd'] < macd['macd_signal']) &
            (macd['macd'].shift(1) >= macd['macd_signal'].shift(1))
        ).astype(int)

        # Running signal: 1 if MACD > signal, -1 if MACD < signal
        macd['macd_trend'] = np.where(
            macd['macd'] > macd['macd_signal'], 1,
            np.where(macd['macd'] < macd['macd_signal'], -1, 0)
        )

        return macd

    def calculate_rsi(
        self,
        series: pd.Series,
        period: int = None
    ) -> pd.DataFrame:
        """
        Calculate RSI indicator.

        Args:
            series: Price/value series
            period: RSI period

        Returns:
            DataFrame with RSI value and signal columns
        """
        period = period or self.rsi_period

        rsi = ta.rsi(series, length=period)

        if rsi is None:
            return pd.DataFrame(index=series.index)

        df = pd.DataFrame(index=series.index)
        df['rsi'] = rsi

        # Signal interpretation
        # Oversold exit: RSI crosses above 30 (bullish)
        # Overbought exit: RSI crosses below 70 (bearish)
        df['rsi_oversold_exit'] = (
            (df['rsi'] > 30) & (df['rsi'].shift(1) <= 30)
        ).astype(int)
        df['rsi_overbought_exit'] = (
            (df['rsi'] < 70) & (df['rsi'].shift(1) >= 70)
        ).astype(int)

        # Running signal based on RSI zones
        df['rsi_zone'] = np.where(
            df['rsi'] < 30, -1,  # Oversold (wait for exit)
            np.where(df['rsi'] > 70, -1, 1)  # Overbought (cautious) or neutral (bullish)
        )

        # Momentum signal: positive if RSI trending up
        df['rsi_momentum'] = np.where(
            df['rsi'] > df['rsi'].shift(1), 1,
            np.where(df['rsi'] < df['rsi'].shift(1), -1, 0)
        )

        return df

    def calculate_sma_crossover(
        self,
        series: pd.Series,
        fast: int = None,
        slow: int = None
    ) -> pd.DataFrame:
        """
        Calculate SMA crossover signals.

        Args:
            series: Price/value series
            fast: Fast SMA period
            slow: Slow SMA period

        Returns:
            DataFrame with SMA values and crossover signals
        """
        fast = fast or self.sma_fast
        slow = slow or self.sma_slow

        sma_fast = ta.sma(series, length=fast)
        sma_slow = ta.sma(series, length=slow)

        if sma_fast is None or sma_slow is None:
            return pd.DataFrame(index=series.index)

        df = pd.DataFrame(index=series.index)
        df['sma_fast'] = sma_fast
        df['sma_slow'] = sma_slow

        # Golden cross: fast crosses above slow (bullish)
        # Death cross: fast crosses below slow (bearish)
        df['sma_golden_cross'] = (
            (df['sma_fast'] > df['sma_slow']) &
            (df['sma_fast'].shift(1) <= df['sma_slow'].shift(1))
        ).astype(int)
        df['sma_death_cross'] = (
            (df['sma_fast'] < df['sma_slow']) &
            (df['sma_fast'].shift(1) >= df['sma_slow'].shift(1))
        ).astype(int)

        # Running trend signal
        df['sma_trend'] = np.where(
            df['sma_fast'] > df['sma_slow'], 1,
            np.where(df['sma_fast'] < df['sma_slow'], -1, 0)
        )

        # Price above/below SMA
        df['price_above_sma_fast'] = (series > df['sma_fast']).astype(int)
        df['price_above_sma_slow'] = (series > df['sma_slow']).astype(int)

        return df

    def calculate_ema_crossover(
        self,
        series: pd.Series,
        fast: int = None,
        slow: int = None
    ) -> pd.DataFrame:
        """
        Calculate EMA crossover signals.

        Args:
            series: Price/value series
            fast: Fast EMA period
            slow: Slow EMA period

        Returns:
            DataFrame with EMA values and crossover signals
        """
        fast = fast or self.ema_fast
        slow = slow or self.ema_slow

        ema_fast = ta.ema(series, length=fast)
        ema_slow = ta.ema(series, length=slow)

        if ema_fast is None or ema_slow is None:
            return pd.DataFrame(index=series.index)

        df = pd.DataFrame(index=series.index)
        df['ema_fast'] = ema_fast
        df['ema_slow'] = ema_slow

        # Crossover signals
        df['ema_cross_up'] = (
            (df['ema_fast'] > df['ema_slow']) &
            (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1))
        ).astype(int)
        df['ema_cross_down'] = (
            (df['ema_fast'] < df['ema_slow']) &
            (df['ema_fast'].shift(1) >= df['ema_slow'].shift(1))
        ).astype(int)

        # Running trend signal
        df['ema_trend'] = np.where(
            df['ema_fast'] > df['ema_slow'], 1,
            np.where(df['ema_fast'] < df['ema_slow'], -1, 0)
        )

        return df

    def calculate_bollinger_bands(
        self,
        series: pd.Series,
        period: int = None,
        std: float = None
    ) -> pd.DataFrame:
        """
        Calculate Bollinger Bands.

        Args:
            series: Price/value series
            period: BB period
            std: Number of standard deviations

        Returns:
            DataFrame with BB values and signals
        """
        period = period or self.bb_period
        std = std or self.bb_std

        bbands = ta.bbands(series, length=period, std=std)

        if bbands is None or bbands.empty:
            return pd.DataFrame(index=series.index)

        df = pd.DataFrame(index=series.index)
        # BBands returns: BBL, BBM, BBU, BBB, BBP
        df['bb_lower'] = bbands.iloc[:, 0]
        df['bb_mid'] = bbands.iloc[:, 1]
        df['bb_upper'] = bbands.iloc[:, 2]
        df['bb_width'] = bbands.iloc[:, 3] if bbands.shape[1] > 3 else None
        df['bb_percent'] = bbands.iloc[:, 4] if bbands.shape[1] > 4 else None

        # Signals based on BB position
        df['bb_oversold'] = (series < df['bb_lower']).astype(int)
        df['bb_overbought'] = (series > df['bb_upper']).astype(int)

        # Mean reversion signal: price crossing mid band
        df['bb_cross_mid_up'] = (
            (series > df['bb_mid']) & (series.shift(1) <= df['bb_mid'].shift(1))
        ).astype(int)
        df['bb_cross_mid_down'] = (
            (series < df['bb_mid']) & (series.shift(1) >= df['bb_mid'].shift(1))
        ).astype(int)

        return df

    def generate_composite_signal(
        self,
        ta_df: pd.DataFrame,
        weights: Dict[str, float] = None
    ) -> pd.Series:
        """
        Generate a composite signal combining all indicators.

        Args:
            ta_df: DataFrame with all TA indicators
            weights: Optional custom weights for each indicator

        Returns:
            Series with composite signal values between -1 and 1
        """
        if weights is None:
            weights = {
                'macd_trend': 0.25,
                'rsi_zone': 0.15,
                'rsi_momentum': 0.10,
                'sma_trend': 0.20,
                'ema_trend': 0.15,
                'price_above_sma_slow': 0.15,
            }

        signal = pd.Series(0.0, index=ta_df.index)

        for indicator, weight in weights.items():
            if indicator in ta_df.columns:
                indicator_value = ta_df[indicator].fillna(0)
                signal += weight * indicator_value

        # Normalize to -1 to 1 range
        signal = signal.clip(-1, 1)

        return signal

    def analyze_all_strategies(
        self,
        strategy_values: pd.DataFrame
    ) -> Dict[str, pd.DataFrame]:
        """
        Analyze all strategies and return TA data for each.

        Args:
            strategy_values: DataFrame with date index and strategy columns

        Returns:
            Dictionary of strategy name -> TA DataFrame
        """
        results = {}

        for strategy in strategy_values.columns:
            try:
                equity_curve = strategy_values[strategy].dropna()
                if len(equity_curve) > self.macd_slow:  # Need enough data
                    results[strategy] = self.analyze(equity_curve, strategy)
                else:
                    logger.warning(f"Not enough data for {strategy}, skipping")
            except Exception as e:
                logger.error(f"Error analyzing {strategy}: {e}")

        return results

    def get_current_signals(
        self,
        strategy_ta: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """
        Get the current (latest) signal for each strategy.

        Args:
            strategy_ta: Dictionary of strategy name -> TA DataFrame

        Returns:
            DataFrame with current signals for each strategy
        """
        signals = []

        for strategy, ta_df in strategy_ta.items():
            if ta_df.empty:
                continue

            latest = ta_df.iloc[-1]
            signals.append({
                'strategy': strategy,
                'date': ta_df.index[-1],
                'composite_signal': latest.get('composite_signal', 0),
                'macd_trend': latest.get('macd_trend', 0),
                'rsi': latest.get('rsi', 50),
                'rsi_zone': latest.get('rsi_zone', 0),
                'sma_trend': latest.get('sma_trend', 0),
                'ema_trend': latest.get('ema_trend', 0),
                'price_above_sma_slow': latest.get('price_above_sma_slow', 0),
            })

        return pd.DataFrame(signals).set_index('strategy')

    def get_signal_history(
        self,
        strategy_ta: Dict[str, pd.DataFrame],
        lookback_days: int = 63
    ) -> pd.DataFrame:
        """
        Get composite signal history for all strategies.

        Args:
            strategy_ta: Dictionary of strategy name -> TA DataFrame
            lookback_days: Number of days to include

        Returns:
            DataFrame with date index and strategy signal columns
        """
        signals = {}

        for strategy, ta_df in strategy_ta.items():
            if 'composite_signal' in ta_df.columns:
                signals[strategy] = ta_df['composite_signal'].tail(lookback_days)

        if not signals:
            return pd.DataFrame()

        return pd.DataFrame(signals)
