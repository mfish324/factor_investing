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
from data.corporate_actions import cumulative_split_factor, flexible_to_datetime

logger = logging.getLogger(__name__)


class ShareholderYieldFactors(BaseFactor):
    """
    Shareholder yield factor calculations.
    Measures total capital returned to shareholders via dividends,
    buybacks, and debt reduction.

    Dividends come from Polygon's dividends endpoint (real per-share cash
    amounts); buybacks from per-filing average share counts. Both are
    as-reported values, so they are converted to today's split-adjusted
    basis (via `cumulative_split_factor`) before being combined with
    Polygon's split-adjusted prices.
    """

    name = "Shareholder Yield Factors"
    description = "Dividend yield, buyback yield, and debt paydown metrics"

    def calculate(
        self,
        financials: pd.DataFrame,
        prices: pd.DataFrame = None,
        market_cap: float = None,
        splits: list = None,
        dividends: list = None,
        as_of=None,
    ) -> Dict[str, float]:
        """Calculate shareholder yield factors for a single stock."""
        if financials.empty or market_cap is None:
            return {}

        results = {
            'dividend_yield': self._dividend_yield(prices, splits, dividends, as_of),
            'buyback_yield': self._buyback_yield(financials, market_cap, splits),
            'debt_paydown_yield': self._debt_paydown_yield(financials, market_cap),
            'fcf_yield': self._fcf_yield(financials, market_cap),
        }

        return results

    @staticmethod
    def _asof_and_price(prices: pd.DataFrame, as_of=None):
        """Return (as_of_ts, last_close) from a price DataFrame."""
        if prices is None or prices.empty or 'close' not in prices.columns:
            return None, None
        last = prices.iloc[-1]
        price = last['close']
        if pd.isna(price) or price <= 0:
            return None, None
        if as_of is not None:
            ts = pd.Timestamp(as_of)
        elif 'date' in prices.columns:
            ts = pd.to_datetime(last['date'], errors='coerce')
        else:
            ts = pd.to_datetime(prices.index[-1], errors='coerce')
        if pd.isna(ts):
            return None, None
        return ts, float(price)

    def _dividend_yield(
        self,
        prices: pd.DataFrame,
        splits: list,
        dividends: list,
        as_of=None,
    ) -> Optional[float]:
        """
        Trailing-12-month cash dividends per share divided by the as-of price.

        Dividend amounts are as-declared per share; each is divided by the
        cumulative split factor since its ex-date to put it on today's
        split-adjusted basis (matching the price). Only dividends with
        ex_dividend_date <= as_of are visible (point-in-time).

        Returns None when no dividend data was provided (missing data,
        scored neutral), 0.0 when the company paid nothing in the window.
        """
        if dividends is None:
            return None
        asof_ts, price = self._asof_and_price(prices, as_of)
        if asof_ts is None:
            return None

        window_start = asof_ts - pd.Timedelta(days=365)
        # Parse all ex-dates in one vectorized call (per-record
        # pd.to_datetime dominated backtest runtime)
        ex_dates = pd.to_datetime(
            [d.get('ex_dividend_date') for d in dividends], errors='coerce'
        )
        total = 0.0
        for d, ex_ts in zip(dividends, ex_dates):
            amount = d.get('cash_amount')
            if pd.isna(ex_ts) or amount is None:
                continue
            if not (window_start < ex_ts <= asof_ts):
                continue
            factor = cumulative_split_factor(splits or [], ex_ts)
            try:
                total += float(amount) / factor
            except (TypeError, ValueError, ZeroDivisionError):
                continue

        return total / price

    def _buyback_yield(
        self,
        financials: pd.DataFrame,
        market_cap: float,
        splits: list = None,
    ) -> Optional[float]:
        """
        Net buyback yield from year-over-year change in average share count.
        Positive = company is buying back shares (shrinking float).

        Per-filing share counts are as-reported, so each is scaled by the
        cumulative split factor since its own filing date. Without this, a
        4:1 split reads as a -300% "buyback" and a reverse split as a
        massive one.
        """
        if len(financials) < 2 or market_cap <= 0:
            return None

        latest = financials.iloc[0]
        previous = financials.iloc[1]

        shares_curr = latest.get('shares_outstanding')
        shares_prev = previous.get('shares_outstanding')

        if pd.isna(shares_curr) or pd.isna(shares_prev) or not shares_prev or shares_prev <= 0:
            return None

        if splits:
            parsed = flexible_to_datetime(pd.Series([latest.get('filing_date'), previous.get('filing_date')]))
            curr_fd, prev_fd = parsed.iloc[0], parsed.iloc[1]
            if pd.isna(curr_fd) or pd.isna(prev_fd):
                return None
            shares_curr = shares_curr * cumulative_split_factor(splits, curr_fd)
            shares_prev = shares_prev * cumulative_split_factor(splits, prev_fd)

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

        NOTE: Polygon's financials serve neither free_cash_flow nor capex,
        so in practice this is operating-cash-flow yield. Kept as-is
        (honest labeling pending a capex source).
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

    def calculate_universe(
        self,
        financials_dict: Dict[str, pd.DataFrame],
        prices_dict: Dict[str, pd.DataFrame] = None,
        market_caps: Dict[str, float] = None,
        splits_by_ticker: Dict[str, list] = None,
        dividends_by_ticker: Dict[str, list] = None,
        as_of=None,
    ) -> pd.DataFrame:
        """
        Calculate shareholder yield factors for all stocks, passing each
        ticker's splits and dividends into the per-stock calculation.
        """
        results = []
        prices_dict = prices_dict or {}
        market_caps = market_caps or {}
        splits_by_ticker = splits_by_ticker or {}
        dividends_by_ticker = dividends_by_ticker or {}

        for ticker, financials in financials_dict.items():
            try:
                factors = self.calculate(
                    financials,
                    prices_dict.get(ticker),
                    market_caps.get(ticker),
                    splits=splits_by_ticker.get(ticker),
                    dividends=dividends_by_ticker.get(ticker),
                    as_of=as_of,
                )
                factors['ticker'] = ticker
                results.append(factors)
            except Exception as e:
                logger.warning(f"Failed to calculate shareholder yield for {ticker}: {e}")
                continue

        if not results:
            return pd.DataFrame()

        return pd.DataFrame(results).set_index('ticker')

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

        # Corporate actions, when the caller (engine / load_data) provides
        # them. `as_of` comes from the PointInTimeView during backtests so
        # dividend visibility is point-in-time.
        splits_by_ticker = kwargs.get('splits_by_ticker')
        dividends_by_ticker = kwargs.get('dividends_by_ticker')
        as_of = getattr(prices, 'as_of', None)

        # Calculate shareholder yield factors
        yield_df = self.sh_yield_factors.calculate_universe(
            financials, prices, market_caps,
            splits_by_ticker=splits_by_ticker,
            dividends_by_ticker=dividends_by_ticker,
            as_of=as_of,
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
