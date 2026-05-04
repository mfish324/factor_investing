"""
Shareholder Yield factor model.
Combines dividend yield, net buyback yield, and debt paydown yield.
Companies returning capital to shareholders tend to outperform,
especially in sideways and down markets.
"""

from typing import Dict, Optional
import pandas as pd
import numpy as np
import logging

from .base import FactorModel
from factors.base import BaseFactor
from factors.quality import QualityFactors

logger = logging.getLogger(__name__)


class ShareholderYieldFactors(BaseFactor):
    """
    Shareholder yield factor calculations.
    Measures total capital returned to shareholders via dividends,
    buybacks, and debt reduction.
    """

    name = "Shareholder Yield Factors"
    description = "Dividend yield, buyback yield, and debt paydown metrics"

    def calculate(
        self,
        financials: pd.DataFrame,
        prices: pd.DataFrame = None,
        market_cap: float = None
    ) -> Dict[str, float]:
        """Calculate shareholder yield factors for a single stock."""
        if financials.empty or market_cap is None:
            return {}

        results = {
            'dividend_yield': self._dividend_yield(financials, market_cap),
            'buyback_yield': self._buyback_yield(financials, market_cap),
            'debt_paydown_yield': self._debt_paydown_yield(financials, market_cap),
            'fcf_yield': self._fcf_yield(financials, market_cap),
        }

        return results

    def _dividend_yield(
        self,
        financials: pd.DataFrame,
        market_cap: float
    ) -> Optional[float]:
        """
        Dividend yield estimated from financials.
        Uses net income payout approach when direct dividend data unavailable.
        """
        latest = financials.iloc[0] if len(financials) > 0 else pd.Series()

        # Try to get dividends paid from cash flow statement
        # (typically reported as negative in cash flow)
        dividends = latest.get('dividends_paid')
        if pd.notna(dividends) and market_cap > 0:
            return abs(dividends) / market_cap

        # Fallback: estimate from FCF and retained earnings change
        net_income = latest.get('net_income')
        if len(financials) >= 2 and pd.notna(net_income):
            prev = financials.iloc[1]
            retained_curr = latest.get('total_equity', 0) or 0
            retained_prev = prev.get('total_equity', 0) or 0
            # Rough estimate: dividends ~ net_income - change_in_equity
            # (ignoring share issuance/buybacks for this estimate)
            equity_change = retained_curr - retained_prev
            if pd.notna(equity_change) and net_income > 0:
                estimated_div = max(0, net_income - equity_change)
                if market_cap > 0:
                    return estimated_div / market_cap

        return 0.0  # No dividend detected

    def _buyback_yield(
        self,
        financials: pd.DataFrame,
        market_cap: float
    ) -> Optional[float]:
        """
        Net buyback yield from share count changes.
        Positive = company is buying back shares (shrinking float).
        """
        if len(financials) < 2 or market_cap <= 0:
            return None

        latest = financials.iloc[0]
        previous = financials.iloc[1]

        shares_curr = latest.get('shares_outstanding')
        shares_prev = previous.get('shares_outstanding')

        if pd.isna(shares_curr) or pd.isna(shares_prev) or shares_prev <= 0:
            return None

        # Negative change = buyback (good for shareholders)
        share_change_pct = (shares_prev - shares_curr) / shares_prev

        return share_change_pct

    def _debt_paydown_yield(
        self,
        financials: pd.DataFrame,
        market_cap: float
    ) -> Optional[float]:
        """
        Debt paydown yield: reduction in net debt as % of market cap.
        Positive = company is deleveraging (returning value to equity holders).
        """
        if len(financials) < 2 or market_cap <= 0:
            return None

        latest = financials.iloc[0]
        previous = financials.iloc[1]

        debt_curr = (latest.get('total_debt', 0) or 0) - (latest.get('cash', 0) or 0)
        debt_prev = (previous.get('total_debt', 0) or 0) - (previous.get('cash', 0) or 0)

        if pd.isna(debt_curr) or pd.isna(debt_prev):
            return None

        # Positive = net debt decreased (deleveraging)
        debt_reduction = debt_prev - debt_curr

        return debt_reduction / market_cap

    def _fcf_yield(
        self,
        financials: pd.DataFrame,
        market_cap: float
    ) -> Optional[float]:
        """
        Free cash flow yield = FCF / Market Cap.
        Measures capacity to return capital.
        """
        latest = financials.iloc[0] if len(financials) > 0 else pd.Series()

        fcf = latest.get('free_cash_flow')
        if pd.isna(fcf):
            ocf = latest.get('operating_cash_flow')
            capex = latest.get('capex', 0)
            if pd.notna(ocf):
                fcf = ocf - abs(capex or 0)

        if pd.isna(fcf) or market_cap <= 0:
            return None

        return fcf / market_cap

    def shareholder_yield_composite(
        self,
        factor_df: pd.DataFrame
    ) -> pd.Series:
        """
        Combined shareholder yield score.
        All components: higher = more capital returned to shareholders.
        """
        higher_is_better = {
            'dividend_yield': True,
            'buyback_yield': True,
            'debt_paydown_yield': True,
            'fcf_yield': True,
        }

        weights = {
            'dividend_yield': 1.0,
            'buyback_yield': 1.2,      # Buybacks slightly more predictive
            'debt_paydown_yield': 0.6,  # Debt paydown less direct
            'fcf_yield': 1.0,          # FCF capacity
        }

        return self.composite_score(factor_df, weights, higher_is_better)


class ShareholderYieldModel(FactorModel):
    """
    Shareholder Yield Model

    Strategy:
    1. Calculate shareholder yield (dividends + buybacks + debt paydown)
    2. Add quality filter to avoid yield traps
    3. Combine for defensive, income-oriented portfolio

    Rationale:
    Companies actively returning capital tend to be mature, profitable,
    and disciplined with capital allocation. This combination provides
    downside protection in weak markets while capturing steady returns.
    """

    name = "Shareholder Yield"
    description = "Dividend + buyback + debt paydown yield with quality filter"

    def __init__(
        self,
        yield_weight: float = 0.60,
        quality_weight: float = 0.40
    ):
        super().__init__()
        total = yield_weight + quality_weight
        self.yield_weight = yield_weight / total
        self.quality_weight = quality_weight / total

        self.sh_yield_factors = ShareholderYieldFactors()
        self.quality_factors = QualityFactors()

    def score(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        **kwargs
    ) -> pd.Series:
        """
        Score stocks using shareholder yield + quality composite.
        """
        if not financials or market_caps is None:
            return pd.Series(dtype=float)

        # Calculate shareholder yield factors
        yield_df = self.sh_yield_factors.calculate_universe(
            financials, prices, market_caps
        )

        if yield_df.empty:
            return pd.Series(dtype=float)

        yield_composite = self.sh_yield_factors.shareholder_yield_composite(yield_df)

        # Calculate quality factors
        quality_df = self.quality_factors.calculate_universe(
            financials, prices, market_caps
        )

        if not quality_df.empty:
            quality_composite = self.quality_factors.quality_composite_score(quality_df)

            # Align indices
            common = yield_composite.index.intersection(quality_composite.index)
            yield_composite = yield_composite.loc[common]
            quality_composite = quality_composite.loc[common]

            # Z-score normalize
            yield_z = self.zscore_normalize(yield_composite)
            quality_z = self.zscore_normalize(quality_composite)

            return (
                self.yield_weight * yield_z +
                self.quality_weight * quality_z
            )

        return yield_composite

    def get_factor_exposures(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        **kwargs
    ) -> pd.DataFrame:
        """Get underlying shareholder yield and quality factors."""
        yield_df = self.sh_yield_factors.calculate_universe(
            financials, prices, market_caps
        )
        quality_df = self.quality_factors.calculate_universe(
            financials, prices, market_caps
        )

        if yield_df.empty:
            return quality_df
        if quality_df.empty:
            return yield_df

        combined = yield_df.join(quality_df, how='outer', rsuffix='_quality')
        combined['yield_composite'] = self.sh_yield_factors.shareholder_yield_composite(yield_df)
        combined['quality_composite'] = self.quality_factors.quality_composite_score(quality_df)

        return combined
