"""
Base class for factor calculations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List
import pandas as pd
import numpy as np
from scipy import stats
import logging

logger = logging.getLogger(__name__)


class BaseFactor(ABC):
    """
    Abstract base class for factor calculations.
    Provides common utilities for normalization and scoring.
    """

    name: str = "Base Factor"
    description: str = "Abstract base factor"

    def __init__(self):
        self._cache = {}

    @abstractmethod
    def calculate(
        self,
        financials: pd.DataFrame,
        prices: pd.DataFrame = None,
        market_cap: float = None
    ) -> Dict[str, float]:
        """
        Calculate factor values for a single stock.

        Args:
            financials: DataFrame of financial statements
            prices: DataFrame of price data (optional)
            market_cap: Current market cap (optional)

        Returns:
            Dictionary of factor name -> value
        """
        pass

    def calculate_universe(
        self,
        financials_dict: Dict[str, pd.DataFrame],
        prices_dict: Dict[str, pd.DataFrame] = None,
        market_caps: Dict[str, float] = None
    ) -> pd.DataFrame:
        """
        Calculate factors for all stocks in universe.

        Args:
            financials_dict: Dictionary of ticker -> financials DataFrame
            prices_dict: Dictionary of ticker -> prices DataFrame
            market_caps: Dictionary of ticker -> market cap

        Returns:
            DataFrame with tickers as index and factors as columns
        """
        results = []
        prices_dict = prices_dict or {}
        market_caps = market_caps or {}

        for ticker, financials in financials_dict.items():
            try:
                factors = self.calculate(
                    financials,
                    prices_dict.get(ticker),
                    market_caps.get(ticker)
                )
                factors['ticker'] = ticker
                results.append(factors)
            except Exception as e:
                logger.warning(f"Failed to calculate factors for {ticker}: {e}")
                continue

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results).set_index('ticker')
        return df

    @staticmethod
    def zscore_normalize(series: pd.Series, winsorize_pct: float = 0.01) -> pd.Series:
        """
        Z-score normalize a series with optional winsorization.

        Args:
            series: Series to normalize
            winsorize_pct: Percentile for winsorization (0.01 = 1%)

        Returns:
            Normalized series
        """
        # Remove NaN for calculation
        valid = series.dropna()
        if len(valid) < 3:
            return pd.Series(np.nan, index=series.index)

        # Winsorize
        if winsorize_pct > 0:
            lower = valid.quantile(winsorize_pct)
            upper = valid.quantile(1 - winsorize_pct)
            valid = valid.clip(lower=lower, upper=upper)

        # Z-score
        mean = valid.mean()
        std = valid.std()
        if std == 0:
            return pd.Series(0, index=series.index)

        result = (series - mean) / std
        return result

    @staticmethod
    def rank_normalize(series: pd.Series) -> pd.Series:
        """
        Rank normalize a series to [0, 1] range.

        Args:
            series: Series to normalize

        Returns:
            Rank-normalized series
        """
        ranks = series.rank(pct=True)
        return ranks

    @staticmethod
    def safe_divide(
        numerator: float,
        denominator: float,
        default: float = np.nan
    ) -> float:
        """
        Safely divide two numbers, handling zeros and NaN.
        """
        if pd.isna(numerator) or pd.isna(denominator):
            return default
        if denominator == 0:
            return default
        return numerator / denominator

    @staticmethod
    def get_latest_value(
        df: pd.DataFrame,
        column: str,
        periods_back: int = 0
    ) -> Optional[float]:
        """
        Get value from financial statements.

        Args:
            df: Financial statements DataFrame (sorted by date desc)
            column: Column name to retrieve
            periods_back: Number of periods to go back (0 = most recent)

        Returns:
            Value or None if not available
        """
        if df.empty or column not in df.columns:
            return None

        if periods_back >= len(df):
            return None

        value = df.iloc[periods_back][column]
        return value if pd.notna(value) else None

    @staticmethod
    def calculate_growth_rate(
        current: float,
        previous: float
    ) -> Optional[float]:
        """
        Calculate period-over-period growth rate.
        """
        if pd.isna(current) or pd.isna(previous):
            return None
        if previous == 0:
            return None
        return (current - previous) / abs(previous)

    @staticmethod
    def calculate_cagr(
        start_value: float,
        end_value: float,
        years: int
    ) -> Optional[float]:
        """
        Calculate Compound Annual Growth Rate.
        """
        if pd.isna(start_value) or pd.isna(end_value):
            return None
        if start_value <= 0 or end_value <= 0:
            return None
        if years <= 0:
            return None

        return (end_value / start_value) ** (1 / years) - 1

    def composite_score(
        self,
        factor_df: pd.DataFrame,
        weights: Dict[str, float] = None,
        higher_is_better: Dict[str, bool] = None
    ) -> pd.Series:
        """
        Calculate weighted composite score from multiple factors.

        Args:
            factor_df: DataFrame of factor values
            weights: Optional weights for each factor (defaults to equal)
            higher_is_better: Dict indicating direction for each factor

        Returns:
            Series of composite scores
        """
        if factor_df.empty:
            return pd.Series(dtype=float)

        weights = weights or {col: 1.0 for col in factor_df.columns}
        higher_is_better = higher_is_better or {col: True for col in factor_df.columns}

        # Normalize weights
        total_weight = sum(weights.values())
        weights = {k: v / total_weight for k, v in weights.items()}

        composite = pd.Series(0.0, index=factor_df.index)

        for col in factor_df.columns:
            if col not in weights:
                continue

            # Z-score normalize
            normalized = self.zscore_normalize(factor_df[col])

            # Flip sign if lower is better
            if not higher_is_better.get(col, True):
                normalized = -normalized

            composite += weights[col] * normalized.fillna(0)

        return composite
