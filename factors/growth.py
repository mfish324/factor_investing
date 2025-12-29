"""
Growth factor calculations.
"""

from typing import Dict, Optional
import pandas as pd
import numpy as np
import logging

from .base import BaseFactor

logger = logging.getLogger(__name__)


class GrowthFactors(BaseFactor):
    """
    Growth factor calculations including:
    - Revenue growth (YoY and CAGR)
    - Earnings growth
    - Asset growth
    - Operating income growth
    """

    name = "Growth Factors"
    description = "Revenue, earnings, and asset growth metrics"

    def calculate(
        self,
        financials: pd.DataFrame,
        prices: pd.DataFrame = None,
        market_cap: float = None
    ) -> Dict[str, float]:
        """
        Calculate all growth factors for a stock.
        """
        if financials.empty or len(financials) < 2:
            return {}

        results = {
            'revenue_growth_yoy': self._revenue_growth_yoy(financials),
            'earnings_growth_yoy': self._earnings_growth_yoy(financials),
            'revenue_cagr_3y': self._revenue_cagr_3y(financials),
            'earnings_cagr_3y': self._earnings_cagr_3y(financials),
            'asset_growth_yoy': self._asset_growth_yoy(financials),
            'operating_income_growth_yoy': self._operating_income_growth_yoy(financials),
        }

        return results

    def _revenue_growth_yoy(self, financials: pd.DataFrame) -> Optional[float]:
        """
        Year-over-year revenue growth.
        """
        if len(financials) < 2:
            return None

        current_rev = self.get_latest_value(financials, 'revenue', 0)
        prior_rev = self.get_latest_value(financials, 'revenue', 1)

        return self.calculate_growth_rate(current_rev, prior_rev)

    def _earnings_growth_yoy(self, financials: pd.DataFrame) -> Optional[float]:
        """
        Year-over-year earnings (EPS) growth.
        """
        if len(financials) < 2:
            return None

        # Try EPS first, fall back to net income
        current_eps = self.get_latest_value(financials, 'eps_diluted', 0)
        prior_eps = self.get_latest_value(financials, 'eps_diluted', 1)

        if current_eps is None or prior_eps is None:
            current_eps = self.get_latest_value(financials, 'net_income', 0)
            prior_eps = self.get_latest_value(financials, 'net_income', 1)

        if prior_eps is None or prior_eps <= 0:
            return None  # Can't calculate meaningful growth from negative base

        return self.calculate_growth_rate(current_eps, prior_eps)

    def _revenue_cagr_3y(self, financials: pd.DataFrame) -> Optional[float]:
        """
        3-year compound annual growth rate for revenue.
        """
        if len(financials) < 4:  # Need 4 periods for 3-year CAGR
            return None

        start_rev = self.get_latest_value(financials, 'revenue', 3)
        end_rev = self.get_latest_value(financials, 'revenue', 0)

        return self.calculate_cagr(start_rev, end_rev, 3)

    def _earnings_cagr_3y(self, financials: pd.DataFrame) -> Optional[float]:
        """
        3-year compound annual growth rate for earnings.
        """
        if len(financials) < 4:
            return None

        # Try EPS first
        start_eps = self.get_latest_value(financials, 'eps_diluted', 3)
        end_eps = self.get_latest_value(financials, 'eps_diluted', 0)

        if start_eps is None or end_eps is None:
            start_eps = self.get_latest_value(financials, 'net_income', 3)
            end_eps = self.get_latest_value(financials, 'net_income', 0)

        return self.calculate_cagr(start_eps, end_eps, 3)

    def _asset_growth_yoy(self, financials: pd.DataFrame) -> Optional[float]:
        """
        Year-over-year asset growth.

        Note: Low asset growth is typically bullish (efficient capital use).
        """
        if len(financials) < 2:
            return None

        current_assets = self.get_latest_value(financials, 'total_assets', 0)
        prior_assets = self.get_latest_value(financials, 'total_assets', 1)

        return self.calculate_growth_rate(current_assets, prior_assets)

    def _operating_income_growth_yoy(self, financials: pd.DataFrame) -> Optional[float]:
        """
        Year-over-year operating income growth.
        """
        if len(financials) < 2:
            return None

        current_oi = self.get_latest_value(financials, 'operating_income', 0)
        prior_oi = self.get_latest_value(financials, 'operating_income', 1)

        if current_oi is None:
            current_oi = self.get_latest_value(financials, 'ebit', 0)
        if prior_oi is None:
            prior_oi = self.get_latest_value(financials, 'ebit', 1)

        if prior_oi is None or prior_oi <= 0:
            return None

        return self.calculate_growth_rate(current_oi, prior_oi)

    def growth_composite_score(
        self,
        factor_df: pd.DataFrame
    ) -> pd.Series:
        """
        Calculate composite growth score.
        Higher growth = higher score (except asset growth).
        """
        higher_is_better = {
            'revenue_growth_yoy': True,
            'earnings_growth_yoy': True,
            'revenue_cagr_3y': True,
            'earnings_cagr_3y': True,
            'asset_growth_yoy': False,  # Low asset growth is typically good
            'operating_income_growth_yoy': True,
        }

        weights = {
            'revenue_growth_yoy': 1.0,
            'earnings_growth_yoy': 1.2,  # Earnings growth is key
            'revenue_cagr_3y': 0.8,
            'earnings_cagr_3y': 1.0,
            'asset_growth_yoy': 0.5,
            'operating_income_growth_yoy': 0.8,
        }

        return self.composite_score(factor_df, weights, higher_is_better)

    def calculate_universe_with_composite(
        self,
        financials_dict: Dict[str, pd.DataFrame],
        prices_dict: Dict[str, pd.DataFrame] = None,
        market_caps: Dict[str, float] = None
    ) -> pd.DataFrame:
        """
        Calculate growth factors for universe with composite score.
        """
        df = self.calculate_universe(financials_dict, prices_dict, market_caps)

        if not df.empty:
            df['growth_composite'] = self.growth_composite_score(df)

        return df

    def calculate_peg_ratio(
        self,
        financials: pd.DataFrame,
        market_cap: float
    ) -> Optional[float]:
        """
        PEG Ratio = P/E / Expected Earnings Growth Rate

        Uses historical earnings growth as proxy for expected growth.
        """
        if len(financials) < 2:
            return None

        # Get P/E
        net_income = self.get_latest_value(financials, 'net_income', 0)
        if net_income is None or net_income <= 0 or market_cap is None:
            return None

        pe = market_cap / net_income

        # Get earnings growth rate (use 3-year CAGR if available, else YoY)
        growth = self._earnings_cagr_3y(financials)
        if growth is None:
            growth = self._earnings_growth_yoy(financials)

        if growth is None or growth <= 0:
            return None

        # Convert growth to percentage for PEG (growth = 0.15 -> 15)
        growth_pct = growth * 100

        if growth_pct == 0:
            return None

        return pe / growth_pct
