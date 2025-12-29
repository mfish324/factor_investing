"""
Value factor calculations.
"""

from typing import Dict, Optional
import pandas as pd
import numpy as np
import logging

from .base import BaseFactor

logger = logging.getLogger(__name__)


class ValueFactors(BaseFactor):
    """
    Value factor calculations including:
    - Earnings Yield
    - P/E, P/B, P/S, P/FCF
    - EV/EBITDA
    """

    name = "Value Factors"
    description = "Traditional value metrics for stock valuation"

    def calculate(
        self,
        financials: pd.DataFrame,
        prices: pd.DataFrame = None,
        market_cap: float = None
    ) -> Dict[str, float]:
        """
        Calculate all value factors for a stock.
        """
        if financials.empty:
            return {}

        # Get latest financial data
        latest = financials.iloc[0] if len(financials) > 0 else pd.Series()

        results = {
            'earnings_yield': self._earnings_yield(latest, market_cap),
            'pe_ratio': self._pe_ratio(latest, market_cap),
            'pb_ratio': self._pb_ratio(latest, market_cap),
            'ps_ratio': self._ps_ratio(latest, market_cap),
            'pcf_ratio': self._pcf_ratio(latest, market_cap),
            'ev_ebitda': self._ev_ebitda(latest, market_cap),
        }

        return results

    def _earnings_yield(
        self,
        financials: pd.Series,
        market_cap: float
    ) -> Optional[float]:
        """
        Earnings Yield = EBIT / Enterprise Value

        Enterprise Value = Market Cap + Total Debt - Cash
        """
        ebit = financials.get('ebit') or financials.get('operating_income')
        if pd.isna(ebit) or pd.isna(market_cap):
            return None

        total_debt = financials.get('total_debt', 0) or 0
        cash = financials.get('cash', 0) or 0

        enterprise_value = market_cap + total_debt - cash

        if enterprise_value <= 0:
            return None

        return ebit / enterprise_value

    def _pe_ratio(
        self,
        financials: pd.Series,
        market_cap: float
    ) -> Optional[float]:
        """
        Price-to-Earnings = Market Cap / Net Income
        Or Price / EPS
        """
        net_income = financials.get('net_income')
        if pd.isna(net_income) or pd.isna(market_cap):
            return None

        if net_income <= 0:
            return None  # Negative earnings = no P/E

        return market_cap / net_income

    def _pb_ratio(
        self,
        financials: pd.Series,
        market_cap: float
    ) -> Optional[float]:
        """
        Price-to-Book = Market Cap / Total Equity
        """
        book_value = financials.get('total_equity')
        if pd.isna(book_value) or pd.isna(market_cap):
            return None

        if book_value <= 0:
            return None

        return market_cap / book_value

    def _ps_ratio(
        self,
        financials: pd.Series,
        market_cap: float
    ) -> Optional[float]:
        """
        Price-to-Sales = Market Cap / Revenue
        """
        revenue = financials.get('revenue')
        if pd.isna(revenue) or pd.isna(market_cap):
            return None

        if revenue <= 0:
            return None

        return market_cap / revenue

    def _pcf_ratio(
        self,
        financials: pd.Series,
        market_cap: float
    ) -> Optional[float]:
        """
        Price-to-Free-Cash-Flow = Market Cap / FCF
        FCF = Operating Cash Flow - CapEx
        """
        fcf = financials.get('free_cash_flow')

        # Calculate if not directly available
        if pd.isna(fcf):
            ocf = financials.get('operating_cash_flow')
            capex = financials.get('capex', 0)
            if pd.notna(ocf):
                fcf = ocf - abs(capex or 0)

        if pd.isna(fcf) or pd.isna(market_cap):
            return None

        if fcf <= 0:
            return None

        return market_cap / fcf

    def _ev_ebitda(
        self,
        financials: pd.Series,
        market_cap: float
    ) -> Optional[float]:
        """
        EV/EBITDA = Enterprise Value / EBITDA
        """
        ebitda = financials.get('ebitda')

        # Estimate if not available
        if pd.isna(ebitda):
            ebit = financials.get('ebit') or financials.get('operating_income')
            # Rough approximation - in practice would need D&A
            ebitda = ebit  # This is a simplification

        if pd.isna(ebitda) or pd.isna(market_cap):
            return None

        if ebitda <= 0:
            return None

        total_debt = financials.get('total_debt', 0) or 0
        cash = financials.get('cash', 0) or 0

        enterprise_value = market_cap + total_debt - cash

        if enterprise_value <= 0:
            return None

        return enterprise_value / ebitda

    def value_composite_score(
        self,
        factor_df: pd.DataFrame
    ) -> pd.Series:
        """
        Calculate composite value score from all value factors.
        Lower valuation ratios = higher score.
        """
        # For value, lower is better (except earnings yield)
        higher_is_better = {
            'earnings_yield': True,  # Higher EY = cheaper
            'pe_ratio': False,       # Lower P/E = cheaper
            'pb_ratio': False,       # Lower P/B = cheaper
            'ps_ratio': False,       # Lower P/S = cheaper
            'pcf_ratio': False,      # Lower P/FCF = cheaper
            'ev_ebitda': False,      # Lower EV/EBITDA = cheaper
        }

        # Equal weights by default
        weights = {col: 1.0 for col in factor_df.columns if col in higher_is_better}

        return self.composite_score(factor_df, weights, higher_is_better)

    def calculate_universe_with_composite(
        self,
        financials_dict: Dict[str, pd.DataFrame],
        prices_dict: Dict[str, pd.DataFrame] = None,
        market_caps: Dict[str, float] = None
    ) -> pd.DataFrame:
        """
        Calculate value factors for universe with composite score.
        """
        df = self.calculate_universe(financials_dict, prices_dict, market_caps)

        if not df.empty:
            df['value_composite'] = self.value_composite_score(df)

        return df
