"""
Quality factor calculations.
"""

from typing import Dict, Optional
import pandas as pd
import numpy as np
import logging

from .base import BaseFactor

logger = logging.getLogger(__name__)


class QualityFactors(BaseFactor):
    """
    Quality factor calculations including:
    - ROE, ROA, ROIC
    - Margin metrics
    - Leverage ratios
    - Piotroski F-Score
    """

    name = "Quality Factors"
    description = "Quality and profitability metrics"

    def calculate(
        self,
        financials: pd.DataFrame,
        prices: pd.DataFrame = None,
        market_cap: float = None
    ) -> Dict[str, float]:
        """
        Calculate all quality factors for a stock.
        """
        if financials.empty:
            return {}

        results = {
            'roe': self._roe(financials),
            'roa': self._roa(financials),
            'roic': self._roic(financials),
            'gross_margin': self._gross_margin(financials),
            'operating_margin': self._operating_margin(financials),
            'net_margin': self._net_margin(financials),
            'debt_to_equity': self._debt_to_equity(financials),
            'current_ratio': self._current_ratio(financials),
            'interest_coverage': self._interest_coverage(financials),
            'f_score': self._piotroski_f_score(financials),
        }

        return results

    def _roe(self, financials: pd.DataFrame) -> Optional[float]:
        """
        Return on Equity = Net Income / Shareholders Equity
        """
        if len(financials) < 1:
            return None

        latest = financials.iloc[0]
        net_income = latest.get('net_income')
        equity = latest.get('total_equity')

        return self.safe_divide(net_income, equity)

    def _roa(self, financials: pd.DataFrame) -> Optional[float]:
        """
        Return on Assets = Net Income / Total Assets
        """
        if len(financials) < 1:
            return None

        latest = financials.iloc[0]
        net_income = latest.get('net_income')
        assets = latest.get('total_assets')

        return self.safe_divide(net_income, assets)

    def _roic(self, financials: pd.DataFrame) -> Optional[float]:
        """
        Return on Invested Capital = NOPAT / Invested Capital

        NOPAT = Operating Income × (1 - Tax Rate)
        Invested Capital = Total Equity + Total Debt - Cash
        """
        if len(financials) < 1:
            return None

        latest = financials.iloc[0]

        operating_income = latest.get('operating_income') or latest.get('ebit')
        if pd.isna(operating_income):
            return None

        # Estimate tax rate from net income / pretax income, or use 25% default
        net_income = latest.get('net_income')
        if pd.notna(net_income) and pd.notna(operating_income) and operating_income != 0:
            # Rough approximation - operating income as proxy for pretax
            tax_rate = 1 - (net_income / operating_income) if operating_income > 0 else 0.25
            tax_rate = min(max(tax_rate, 0), 0.5)  # Bound between 0-50%
        else:
            tax_rate = 0.25

        nopat = operating_income * (1 - tax_rate)

        # Invested capital
        equity = latest.get('total_equity', 0) or 0
        debt = latest.get('total_debt', 0) or 0
        cash = latest.get('cash', 0) or 0

        invested_capital = equity + debt - cash

        return self.safe_divide(nopat, invested_capital)

    def _gross_margin(self, financials: pd.DataFrame) -> Optional[float]:
        """
        Gross Margin = Gross Profit / Revenue
        """
        if len(financials) < 1:
            return None

        latest = financials.iloc[0]
        gross_profit = latest.get('gross_profit')
        revenue = latest.get('revenue')

        return self.safe_divide(gross_profit, revenue)

    def _operating_margin(self, financials: pd.DataFrame) -> Optional[float]:
        """
        Operating Margin = Operating Income / Revenue
        """
        if len(financials) < 1:
            return None

        latest = financials.iloc[0]
        operating_income = latest.get('operating_income') or latest.get('ebit')
        revenue = latest.get('revenue')

        return self.safe_divide(operating_income, revenue)

    def _net_margin(self, financials: pd.DataFrame) -> Optional[float]:
        """
        Net Margin = Net Income / Revenue
        """
        if len(financials) < 1:
            return None

        latest = financials.iloc[0]
        net_income = latest.get('net_income')
        revenue = latest.get('revenue')

        return self.safe_divide(net_income, revenue)

    def _debt_to_equity(self, financials: pd.DataFrame) -> Optional[float]:
        """
        Debt-to-Equity = Total Debt / Shareholders Equity
        """
        if len(financials) < 1:
            return None

        latest = financials.iloc[0]
        debt = latest.get('total_debt', 0) or 0
        equity = latest.get('total_equity')

        return self.safe_divide(debt, equity)

    def _current_ratio(self, financials: pd.DataFrame) -> Optional[float]:
        """
        Current Ratio = Current Assets / Current Liabilities
        """
        if len(financials) < 1:
            return None

        latest = financials.iloc[0]
        current_assets = latest.get('current_assets')
        current_liabilities = latest.get('current_liabilities')

        return self.safe_divide(current_assets, current_liabilities)

    def _interest_coverage(self, financials: pd.DataFrame) -> Optional[float]:
        """
        Interest Coverage = EBIT / Interest Expense
        """
        if len(financials) < 1:
            return None

        latest = financials.iloc[0]
        ebit = latest.get('ebit') or latest.get('operating_income')
        interest = latest.get('interest_expense')

        if pd.isna(interest) or interest == 0:
            return None  # No debt or no interest expense

        return self.safe_divide(ebit, abs(interest))

    def _piotroski_f_score(self, financials: pd.DataFrame) -> Optional[int]:
        """
        Piotroski F-Score: 9 binary criteria scoring financial strength.

        Profitability (4 points):
        1. ROA > 0
        2. Operating Cash Flow > 0
        3. ROA increased vs prior year
        4. Cash Flow from Operations > Net Income (accruals)

        Leverage/Liquidity (3 points):
        5. Decrease in long-term debt ratio
        6. Increase in current ratio
        7. No new shares issued

        Operating Efficiency (2 points):
        8. Increase in gross margin
        9. Increase in asset turnover
        """
        if len(financials) < 2:
            return None  # Need at least 2 periods for comparison

        current = financials.iloc[0]
        prior = financials.iloc[1]

        score = 0

        # 1. ROA > 0
        net_income = current.get('net_income')
        assets = current.get('total_assets')
        if pd.notna(net_income) and pd.notna(assets) and assets > 0:
            roa = net_income / assets
            if roa > 0:
                score += 1

        # 2. Operating Cash Flow > 0
        ocf = current.get('operating_cash_flow')
        if pd.notna(ocf) and ocf > 0:
            score += 1

        # 3. ROA increased
        prior_roa = self.safe_divide(
            prior.get('net_income'),
            prior.get('total_assets')
        )
        current_roa = self.safe_divide(net_income, assets)
        if pd.notna(current_roa) and pd.notna(prior_roa):
            if current_roa > prior_roa:
                score += 1

        # 4. Cash Flow > Net Income (quality of earnings)
        if pd.notna(ocf) and pd.notna(net_income):
            if ocf > net_income:
                score += 1

        # 5. Decrease in long-term debt ratio
        current_debt_ratio = self.safe_divide(
            current.get('total_debt'),
            current.get('total_assets')
        )
        prior_debt_ratio = self.safe_divide(
            prior.get('total_debt'),
            prior.get('total_assets')
        )
        if pd.notna(current_debt_ratio) and pd.notna(prior_debt_ratio):
            if current_debt_ratio < prior_debt_ratio:
                score += 1

        # 6. Increase in current ratio
        current_cr = self.safe_divide(
            current.get('current_assets'),
            current.get('current_liabilities')
        )
        prior_cr = self.safe_divide(
            prior.get('current_assets'),
            prior.get('current_liabilities')
        )
        if pd.notna(current_cr) and pd.notna(prior_cr):
            if current_cr > prior_cr:
                score += 1

        # 7. No new shares issued
        current_shares = current.get('shares_outstanding')
        prior_shares = prior.get('shares_outstanding')
        if pd.notna(current_shares) and pd.notna(prior_shares):
            if current_shares <= prior_shares:
                score += 1

        # 8. Increase in gross margin
        current_gm = self.safe_divide(
            current.get('gross_profit'),
            current.get('revenue')
        )
        prior_gm = self.safe_divide(
            prior.get('gross_profit'),
            prior.get('revenue')
        )
        if pd.notna(current_gm) and pd.notna(prior_gm):
            if current_gm > prior_gm:
                score += 1

        # 9. Increase in asset turnover
        current_at = self.safe_divide(
            current.get('revenue'),
            current.get('total_assets')
        )
        prior_at = self.safe_divide(
            prior.get('revenue'),
            prior.get('total_assets')
        )
        if pd.notna(current_at) and pd.notna(prior_at):
            if current_at > prior_at:
                score += 1

        return score

    def quality_composite_score(
        self,
        factor_df: pd.DataFrame
    ) -> pd.Series:
        """
        Calculate composite quality score.
        Higher profitability/coverage = higher score.
        Lower leverage = higher score.
        """
        higher_is_better = {
            'roe': True,
            'roa': True,
            'roic': True,
            'gross_margin': True,
            'operating_margin': True,
            'net_margin': True,
            'debt_to_equity': False,  # Lower is better
            'current_ratio': True,
            'interest_coverage': True,
            'f_score': True,
        }

        weights = {
            'roe': 1.0,
            'roa': 0.8,
            'roic': 1.2,  # ROIC is key quality metric
            'gross_margin': 0.8,
            'operating_margin': 1.0,
            'net_margin': 0.6,
            'debt_to_equity': 0.8,
            'current_ratio': 0.4,
            'interest_coverage': 0.6,
            'f_score': 1.5,  # F-Score is comprehensive
        }

        return self.composite_score(factor_df, weights, higher_is_better)

    def calculate_universe_with_composite(
        self,
        financials_dict: Dict[str, pd.DataFrame],
        prices_dict: Dict[str, pd.DataFrame] = None,
        market_caps: Dict[str, float] = None
    ) -> pd.DataFrame:
        """
        Calculate quality factors for universe with composite score.
        """
        df = self.calculate_universe(financials_dict, prices_dict, market_caps)

        if not df.empty:
            df['quality_composite'] = self.quality_composite_score(df)

        return df
