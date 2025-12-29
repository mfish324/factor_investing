"""
Joel Greenblatt's Magic Formula model.
Reference: "The Little Book That Beats the Market"
"""

from typing import Dict
import pandas as pd
import numpy as np
import logging

from .base import FactorModel
from factors.value import ValueFactors
from factors.quality import QualityFactors

logger = logging.getLogger(__name__)


class MagicFormulaModel(FactorModel):
    """
    Magic Formula: Earnings Yield + ROIC

    Strategy:
    1. Rank stocks by Earnings Yield (higher = better)
    2. Rank stocks by ROIC (higher = better)
    3. Combine ranks (sum of ranks)
    4. Select stocks with lowest combined rank
    """

    name = "Magic Formula"
    description = "Greenblatt's Magic Formula: high earnings yield + high ROIC"

    def __init__(self):
        super().__init__()
        self.value_factors = ValueFactors()
        self.quality_factors = QualityFactors()

    def score(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        **kwargs
    ) -> pd.Series:
        """
        Score stocks using Magic Formula methodology.

        Higher score = better (combines high EY and high ROIC).
        """
        if not financials or market_caps is None:
            return pd.Series(dtype=float)

        earnings_yields = {}
        roics = {}

        for ticker, fin_df in financials.items():
            if fin_df.empty:
                continue

            market_cap = market_caps.get(ticker)
            if market_cap is None or market_cap <= 0:
                continue

            # Calculate earnings yield
            value_factors = self.value_factors.calculate(
                fin_df, prices.get(ticker), market_cap
            )
            ey = value_factors.get('earnings_yield')

            # Calculate ROIC
            quality_factors = self.quality_factors.calculate(
                fin_df, prices.get(ticker), market_cap
            )
            roic = quality_factors.get('roic')

            if ey is not None and roic is not None:
                earnings_yields[ticker] = ey
                roics[ticker] = roic

        if not earnings_yields or not roics:
            return pd.Series(dtype=float)

        # Create series
        ey_series = pd.Series(earnings_yields)
        roic_series = pd.Series(roics)

        # Rank each factor (higher = better, so ascending=False for percentile rank)
        ey_rank = ey_series.rank(ascending=False, method='average')
        roic_rank = roic_series.rank(ascending=False, method='average')

        # Align indices
        common_tickers = ey_rank.index.intersection(roic_rank.index)
        ey_rank = ey_rank.loc[common_tickers]
        roic_rank = roic_rank.loc[common_tickers]

        # Combined rank (lower is better)
        combined_rank = ey_rank + roic_rank

        # Convert to score (higher is better)
        # Max rank - combined rank gives us higher score for better stocks
        max_rank = combined_rank.max()
        score = max_rank - combined_rank + 1

        return score

    def get_factor_exposures(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Get earnings yield and ROIC for all stocks.
        """
        records = []

        for ticker, fin_df in financials.items():
            if fin_df.empty:
                continue

            market_cap = market_caps.get(ticker) if market_caps else None
            if market_cap is None or market_cap <= 0:
                continue

            value_factors = self.value_factors.calculate(
                fin_df, prices.get(ticker), market_cap
            )
            quality_factors = self.quality_factors.calculate(
                fin_df, prices.get(ticker), market_cap
            )

            records.append({
                'ticker': ticker,
                'earnings_yield': value_factors.get('earnings_yield'),
                'roic': quality_factors.get('roic'),
            })

        if not records:
            return pd.DataFrame()

        return pd.DataFrame(records).set_index('ticker')
