"""
Growth at Reasonable Price (GARP) model.
Made famous by Peter Lynch.
"""

from typing import Dict
import pandas as pd
import numpy as np
import logging

from .base import FactorModel
from factors.growth import GrowthFactors
from factors.value import ValueFactors

logger = logging.getLogger(__name__)


class GARPModel(FactorModel):
    """
    Growth at Reasonable Price (GARP) Model

    Strategy:
    1. Calculate PEG ratio (P/E / Earnings Growth Rate)
    2. Select stocks with PEG < threshold (typically 1.0)
    3. Filter for positive earnings and growth
    """

    name = "GARP"
    description = "Growth at Reasonable Price using PEG ratio"

    def __init__(
        self,
        max_peg: float = 1.0,
        min_growth: float = 0.05,
        max_pe: float = 40.0
    ):
        """
        Args:
            max_peg: Maximum PEG ratio to include
            min_growth: Minimum earnings growth rate (e.g., 0.05 = 5%)
            max_pe: Maximum P/E ratio (avoid negative earnings stocks)
        """
        super().__init__()
        self.max_peg = max_peg
        self.min_growth = min_growth
        self.max_pe = max_pe
        self.growth_factors = GrowthFactors()
        self.value_factors = ValueFactors()

    def score(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        **kwargs
    ) -> pd.Series:
        """
        Score stocks using GARP methodology.

        Lower PEG = higher score (inverted for consistency).
        """
        if not financials or market_caps is None:
            return pd.Series(dtype=float)

        peg_ratios = {}
        earnings_growth = {}
        pe_ratios = {}

        for ticker, fin_df in financials.items():
            if fin_df.empty or len(fin_df) < 2:
                continue

            market_cap = market_caps.get(ticker)
            if market_cap is None or market_cap <= 0:
                continue

            # Calculate PEG ratio
            peg = self.growth_factors.calculate_peg_ratio(fin_df, market_cap)

            # Get earnings growth
            growth_factors = self.growth_factors.calculate(
                fin_df, prices.get(ticker), market_cap
            )
            eg = growth_factors.get('earnings_growth_yoy')

            # Get P/E
            value_factors = self.value_factors.calculate(
                fin_df, prices.get(ticker), market_cap
            )
            pe = value_factors.get('pe_ratio')

            # Apply filters
            if peg is None or eg is None or pe is None:
                continue

            if eg < self.min_growth:
                continue  # Need positive growth

            if pe <= 0 or pe > self.max_pe:
                continue  # Need reasonable P/E

            if peg <= 0 or peg > self.max_peg * 2:  # Allow some buffer
                continue

            peg_ratios[ticker] = peg
            earnings_growth[ticker] = eg
            pe_ratios[ticker] = pe

        if not peg_ratios:
            return pd.Series(dtype=float)

        peg_series = pd.Series(peg_ratios)

        # Filter for max PEG
        valid_peg = peg_series[peg_series <= self.max_peg]

        # Convert PEG to score (lower PEG = higher score)
        # Use 1/PEG so higher is better
        scores = 1 / valid_peg

        return scores

    def get_factor_exposures(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Get PEG, P/E, and growth metrics for all stocks.
        """
        records = []

        for ticker, fin_df in financials.items():
            if fin_df.empty or len(fin_df) < 2:
                continue

            market_cap = market_caps.get(ticker) if market_caps else None
            if market_cap is None:
                continue

            peg = self.growth_factors.calculate_peg_ratio(fin_df, market_cap)

            growth_factors = self.growth_factors.calculate(
                fin_df, prices.get(ticker), market_cap
            )
            value_factors = self.value_factors.calculate(
                fin_df, prices.get(ticker), market_cap
            )

            records.append({
                'ticker': ticker,
                'peg_ratio': peg,
                'pe_ratio': value_factors.get('pe_ratio'),
                'earnings_growth_yoy': growth_factors.get('earnings_growth_yoy'),
                'revenue_growth_yoy': growth_factors.get('revenue_growth_yoy'),
            })

        if not records:
            return pd.DataFrame()

        return pd.DataFrame(records).set_index('ticker')

    def select_portfolio(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        n: int = 30,
        **kwargs
    ) -> list:
        """
        Select top N stocks by lowest PEG ratio.
        """
        scores = self.score(financials, prices, market_caps, **kwargs)

        if len(scores) == 0:
            return []

        # Higher score = lower PEG = better
        sorted_scores = scores.sort_values(ascending=False)

        return sorted_scores.head(n).index.tolist()
