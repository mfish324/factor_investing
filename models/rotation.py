"""
Strategy rotation model for meta-strategy allocation.
"""

from enum import Enum
from typing import Dict, Optional, List
from dataclasses import dataclass
import pandas as pd
import numpy as np
import logging

from analysis.equity_ta import EquityCurveAnalyzer
from config import (
    ROTATION_DEFAULT_METHOD,
    ROTATION_LOOKBACK_DAYS,
    ROTATION_REBALANCE_FREQ,
    ROTATION_MIN_HOLDING_DAYS,
)

logger = logging.getLogger(__name__)


class AllocationMethod(Enum):
    """Strategy allocation methods."""
    BINARY = "binary"       # 100% to best strategy
    WEIGHTED = "weighted"   # Proportional to signal strength
    MOMENTUM = "momentum"   # Weight by recent performance
    TOP_N = "top_n"         # Equal weight top N strategies


@dataclass
class AllocationResult:
    """Result of an allocation calculation."""
    date: pd.Timestamp
    allocations: Dict[str, float]
    signals: Dict[str, float]
    method: AllocationMethod
    selected_strategies: List[str]


class StrategyRotationModel:
    """
    Meta-strategy decision engine that rotates between factor strategies
    based on technical analysis signals on their equity curves.
    """

    def __init__(
        self,
        method: str = None,
        lookback_days: int = None,
        rebalance_freq: str = None,
        min_holding_days: int = None,
        top_n: int = 2,
        signal_threshold: float = 0.0,
    ):
        """
        Initialize the rotation model.

        Args:
            method: Allocation method ('binary', 'weighted', 'momentum', 'top_n')
            lookback_days: Days of history for momentum calculation
            rebalance_freq: Rebalance frequency ('daily', 'weekly', 'monthly')
            min_holding_days: Minimum days before switching strategies
            top_n: Number of strategies for top_n method
            signal_threshold: Minimum signal strength to allocate
        """
        self.method = AllocationMethod(method or ROTATION_DEFAULT_METHOD)
        self.lookback_days = lookback_days or ROTATION_LOOKBACK_DAYS
        self.rebalance_freq = rebalance_freq or ROTATION_REBALANCE_FREQ
        self.min_holding_days = min_holding_days or ROTATION_MIN_HOLDING_DAYS
        self.top_n = top_n
        self.signal_threshold = signal_threshold

        self.ta_analyzer = EquityCurveAnalyzer()
        self._last_switch_date: Optional[pd.Timestamp] = None
        self._current_allocation: Optional[Dict[str, float]] = None

    def calculate_allocations(
        self,
        strategy_values: pd.DataFrame,
        as_of_date: pd.Timestamp = None,
        strategy_ta: Dict[str, pd.DataFrame] = None,
    ) -> AllocationResult:
        """
        Calculate strategy allocations for a given date.

        Args:
            strategy_values: DataFrame with date index and strategy columns
            as_of_date: Date to calculate allocation for (default: latest)
            strategy_ta: Pre-computed TA data (optional, will calculate if not provided)

        Returns:
            AllocationResult with allocations and metadata
        """
        if as_of_date is None:
            as_of_date = strategy_values.index.max()

        # Ensure we only use data up to as_of_date
        values_to_date = strategy_values.loc[:as_of_date]

        # Calculate TA signals if not provided
        if strategy_ta is None:
            strategy_ta = self.ta_analyzer.analyze_all_strategies(values_to_date)

        # Get current signals for each strategy
        signals = self._get_signals_at_date(strategy_ta, as_of_date)

        if not signals:
            # Fall back to equal weight if no signals
            n_strategies = len(strategy_values.columns)
            allocations = {s: 1.0 / n_strategies for s in strategy_values.columns}
            return AllocationResult(
                date=as_of_date,
                allocations=allocations,
                signals={},
                method=self.method,
                selected_strategies=list(strategy_values.columns)
            )

        # Calculate allocations based on method
        if self.method == AllocationMethod.BINARY:
            allocations = self._binary_allocation(signals)
        elif self.method == AllocationMethod.WEIGHTED:
            allocations = self._weighted_allocation(signals)
        elif self.method == AllocationMethod.MOMENTUM:
            allocations = self._momentum_allocation(values_to_date, signals)
        elif self.method == AllocationMethod.TOP_N:
            allocations = self._top_n_allocation(signals)
        else:
            raise ValueError(f"Unknown method: {self.method}")

        # Apply signal threshold
        allocations = self._apply_threshold(allocations, signals)

        # Normalize to sum to 1
        allocations = self._normalize_allocations(allocations)

        selected = [s for s, w in allocations.items() if w > 0]

        return AllocationResult(
            date=as_of_date,
            allocations=allocations,
            signals=signals,
            method=self.method,
            selected_strategies=selected
        )

    def generate_rotation_history(
        self,
        strategy_values: pd.DataFrame,
        rebalance_freq: str = None
    ) -> pd.DataFrame:
        """
        Generate full allocation history over the strategy data period.

        Args:
            strategy_values: DataFrame with date index and strategy columns
            rebalance_freq: Override rebalance frequency

        Returns:
            DataFrame with date index and allocation columns for each strategy
        """
        freq = rebalance_freq or self.rebalance_freq

        # Get rebalance dates
        rebalance_dates = self._get_rebalance_dates(strategy_values.index, freq)

        logger.info(f"Generating rotation history with {len(rebalance_dates)} rebalance dates")

        # Pre-compute TA for all strategies (more efficient)
        strategy_ta = self.ta_analyzer.analyze_all_strategies(strategy_values)

        # Track allocations
        allocation_history = []
        signal_history = []

        for date in rebalance_dates:
            # Skip if we don't have enough history
            if date < strategy_values.index[self.lookback_days]:
                continue

            result = self.calculate_allocations(
                strategy_values,
                as_of_date=date,
                strategy_ta=strategy_ta
            )

            allocation_row = {'date': date}
            allocation_row.update(result.allocations)
            allocation_history.append(allocation_row)

            signal_row = {'date': date}
            signal_row.update(result.signals)
            signal_history.append(signal_row)

        if not allocation_history:
            return pd.DataFrame()

        alloc_df = pd.DataFrame(allocation_history).set_index('date')
        return alloc_df

    def _get_signals_at_date(
        self,
        strategy_ta: Dict[str, pd.DataFrame],
        as_of_date: pd.Timestamp
    ) -> Dict[str, float]:
        """Extract composite signals at a specific date."""
        signals = {}

        for strategy, ta_df in strategy_ta.items():
            if ta_df.empty or 'composite_signal' not in ta_df.columns:
                continue

            # Get the latest data on or before as_of_date
            valid_dates = ta_df.index[ta_df.index <= as_of_date]
            if len(valid_dates) == 0:
                continue

            latest_date = valid_dates[-1]
            signals[strategy] = ta_df.loc[latest_date, 'composite_signal']

        return signals

    def _binary_allocation(self, signals: Dict[str, float]) -> Dict[str, float]:
        """100% to the best strategy."""
        if not signals:
            return {}

        best_strategy = max(signals.items(), key=lambda x: x[1])[0]
        return {s: 1.0 if s == best_strategy else 0.0 for s in signals}

    def _weighted_allocation(self, signals: Dict[str, float]) -> Dict[str, float]:
        """Weight proportional to signal strength."""
        if not signals:
            return {}

        # Shift signals to be positive (add 1, so -1 becomes 0, 0 becomes 1, 1 becomes 2)
        shifted = {s: max(0, sig + 1) for s, sig in signals.items()}

        total = sum(shifted.values())
        if total == 0:
            # Equal weight if all signals are very negative
            n = len(signals)
            return {s: 1.0 / n for s in signals}

        return {s: w / total for s, w in shifted.items()}

    def _momentum_allocation(
        self,
        strategy_values: pd.DataFrame,
        signals: Dict[str, float]
    ) -> Dict[str, float]:
        """Weight by recent performance combined with signals."""
        if strategy_values.empty:
            return self._weighted_allocation(signals)

        # Calculate recent returns
        lookback_values = strategy_values.tail(self.lookback_days)
        recent_returns = (
            lookback_values.iloc[-1] / lookback_values.iloc[0] - 1
        )

        # Combine momentum with TA signals
        combined_score = {}
        for strategy in signals:
            if strategy in recent_returns.index:
                momentum_score = recent_returns[strategy]
                ta_signal = signals[strategy]
                # 50% momentum, 50% TA signal
                combined_score[strategy] = 0.5 * momentum_score + 0.5 * (ta_signal + 1) / 2
            else:
                combined_score[strategy] = signals[strategy]

        # Shift to positive and normalize
        min_score = min(combined_score.values()) if combined_score else 0
        shifted = {s: score - min_score + 0.01 for s, score in combined_score.items()}

        total = sum(shifted.values())
        return {s: w / total for s, w in shifted.items()}

    def _top_n_allocation(self, signals: Dict[str, float]) -> Dict[str, float]:
        """Equal weight top N strategies by signal."""
        if not signals:
            return {}

        # Sort by signal strength
        sorted_strategies = sorted(signals.items(), key=lambda x: x[1], reverse=True)

        # Take top N
        top_strategies = [s for s, _ in sorted_strategies[:self.top_n]]

        # Equal weight
        weight = 1.0 / len(top_strategies) if top_strategies else 0
        return {s: weight if s in top_strategies else 0.0 for s in signals}

    def _apply_threshold(
        self,
        allocations: Dict[str, float],
        signals: Dict[str, float]
    ) -> Dict[str, float]:
        """Zero out allocations for strategies below signal threshold."""
        return {
            s: w if signals.get(s, 0) >= self.signal_threshold else 0.0
            for s, w in allocations.items()
        }

    def _normalize_allocations(
        self,
        allocations: Dict[str, float]
    ) -> Dict[str, float]:
        """Normalize allocations to sum to 1."""
        total = sum(allocations.values())
        if total == 0:
            # Equal weight fallback
            n = len(allocations)
            return {s: 1.0 / n for s in allocations}
        return {s: w / total for s, w in allocations.items()}

    def _get_rebalance_dates(
        self,
        date_index: pd.DatetimeIndex,
        freq: str
    ) -> List[pd.Timestamp]:
        """Generate rebalance dates based on frequency."""
        if freq == 'daily':
            return list(date_index)
        elif freq == 'weekly':
            # Get last trading day of each week
            return list(date_index.to_series().groupby(
                pd.Grouper(freq='W')
            ).last().dropna().values)
        elif freq == 'monthly':
            return list(date_index.to_series().groupby(
                pd.Grouper(freq='M')
            ).last().dropna().values)
        else:
            # Default to weekly
            return list(date_index.to_series().groupby(
                pd.Grouper(freq='W')
            ).last().dropna().values)

    def get_current_recommendation(
        self,
        strategy_values: pd.DataFrame
    ) -> AllocationResult:
        """
        Get the current allocation recommendation.

        Args:
            strategy_values: DataFrame with date index and strategy columns

        Returns:
            AllocationResult for today
        """
        return self.calculate_allocations(strategy_values)
