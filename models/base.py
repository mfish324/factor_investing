"""
Base class for factor models.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class FactorModel(ABC):
    """
    Abstract base class for factor-based stock selection models.
    """

    name: str = "Base Model"
    description: str = "Abstract base factor model"

    def __init__(self):
        self._scores_cache: Optional[pd.Series] = None

    @abstractmethod
    def score(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        **kwargs
    ) -> pd.Series:
        """
        Score all stocks in the universe.

        Args:
            financials: Dictionary of ticker -> financials DataFrame
            prices: Dictionary of ticker -> prices DataFrame
            market_caps: Dictionary of ticker -> market cap
            **kwargs: Additional data (insider transactions, etc.)

        Returns:
            Series of scores indexed by ticker, higher = better
        """
        pass

    def rank(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        ascending: bool = False,
        **kwargs
    ) -> pd.Series:
        """
        Rank stocks based on model scores.

        Args:
            financials: Dictionary of ticker -> financials DataFrame
            prices: Dictionary of ticker -> prices DataFrame
            market_caps: Dictionary of ticker -> market cap
            ascending: If True, lower score = higher rank

        Returns:
            Series of ranks (1 = best) indexed by ticker
        """
        scores = self.score(financials, prices, market_caps, **kwargs)
        return scores.rank(ascending=ascending, method='min')

    def select_portfolio(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        n: int = 30,
        **kwargs
    ) -> List[str]:
        """
        Select top N stocks for the portfolio.

        Args:
            financials: Dictionary of ticker -> financials DataFrame
            prices: Dictionary of ticker -> prices DataFrame
            market_caps: Dictionary of ticker -> market cap
            n: Number of stocks to select

        Returns:
            List of selected ticker symbols
        """
        scores = self.score(financials, prices, market_caps, **kwargs)

        # Remove NaN scores
        valid_scores = scores.dropna()

        if len(valid_scores) == 0:
            logger.warning(f"{self.name}: No valid scores available")
            return []

        # Select top N
        top_n = valid_scores.nlargest(n)
        return top_n.index.tolist()

    def get_factor_exposures(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Get the underlying factor exposures for all stocks.

        Returns:
            DataFrame with factor values for each stock
        """
        # Default implementation - subclasses should override
        return pd.DataFrame()

    @staticmethod
    def combine_ranks(
        *rank_series: pd.Series,
        weights: List[float] = None
    ) -> pd.Series:
        """
        Combine multiple rank series into a single combined rank.

        Args:
            *rank_series: Multiple series of ranks
            weights: Optional weights for each rank series

        Returns:
            Combined rank series (lower = better)
        """
        if not rank_series:
            return pd.Series(dtype=float)

        # Convert to DataFrame for alignment
        df = pd.concat(rank_series, axis=1)

        if weights is None:
            weights = [1.0] * len(rank_series)

        # Normalize weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        # Weighted average of ranks
        combined = pd.Series(0.0, index=df.index)
        for i, col in enumerate(df.columns):
            combined += weights[i] * df[col].fillna(df[col].max())

        # Re-rank the combined scores
        return combined.rank(method='min')

    @staticmethod
    def zscore_normalize(series: pd.Series) -> pd.Series:
        """Z-score normalize a series."""
        mean = series.mean()
        std = series.std()
        if std == 0:
            return pd.Series(0, index=series.index)
        return (series - mean) / std

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
