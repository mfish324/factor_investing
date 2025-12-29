"""
Piotroski F-Score model.
Reference: Joseph Piotroski's "Value Investing: The Use of Historical Financial Statement Information"
"""

from typing import Dict
import pandas as pd
import numpy as np
import logging

from .base import FactorModel
from factors.quality import QualityFactors
from factors.value import ValueFactors

logger = logging.getLogger(__name__)


class PiotroskiModel(FactorModel):
    """
    Piotroski F-Score Model

    Strategy:
    1. Calculate F-Score (0-9) for each stock
    2. Optionally filter for low P/B stocks
    3. Select stocks with F-Score >= threshold (typically 7+)
    """

    name = "Piotroski F-Score"
    description = "9-point financial strength score, often combined with low P/B"

    def __init__(
        self,
        min_f_score: int = 7,
        require_low_pb: bool = True,
        pb_percentile: float = 0.33
    ):
        """
        Args:
            min_f_score: Minimum F-Score to include (0-9)
            require_low_pb: Whether to filter for low P/B stocks
            pb_percentile: If require_low_pb, only include stocks below this P/B percentile
        """
        super().__init__()
        self.min_f_score = min_f_score
        self.require_low_pb = require_low_pb
        self.pb_percentile = pb_percentile
        self.quality_factors = QualityFactors()
        self.value_factors = ValueFactors()

    def score(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        **kwargs
    ) -> pd.Series:
        """
        Score stocks using Piotroski F-Score.

        Score is the F-Score (0-9), with optional P/B filtering.
        """
        if not financials:
            return pd.Series(dtype=float)

        f_scores = {}
        pb_ratios = {}

        for ticker, fin_df in financials.items():
            if fin_df.empty or len(fin_df) < 2:
                continue

            market_cap = market_caps.get(ticker) if market_caps else None

            # Calculate F-Score
            quality_factors = self.quality_factors.calculate(
                fin_df, prices.get(ticker), market_cap
            )
            f_score = quality_factors.get('f_score')

            if f_score is not None:
                f_scores[ticker] = f_score

                # Calculate P/B if we need it for filtering
                if self.require_low_pb and market_cap:
                    value_factors = self.value_factors.calculate(
                        fin_df, prices.get(ticker), market_cap
                    )
                    pb = value_factors.get('pb_ratio')
                    if pb is not None:
                        pb_ratios[ticker] = pb

        if not f_scores:
            return pd.Series(dtype=float)

        f_score_series = pd.Series(f_scores)

        # Apply P/B filter if required
        if self.require_low_pb and pb_ratios:
            pb_series = pd.Series(pb_ratios)
            pb_threshold = pb_series.quantile(self.pb_percentile)

            # Filter for low P/B stocks
            low_pb_tickers = pb_series[pb_series <= pb_threshold].index
            f_score_series = f_score_series.loc[
                f_score_series.index.intersection(low_pb_tickers)
            ]

        # Filter for minimum F-Score
        f_score_series = f_score_series[f_score_series >= self.min_f_score]

        return f_score_series

    def get_factor_exposures(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Get F-Score and P/B for all stocks.
        """
        records = []

        for ticker, fin_df in financials.items():
            if fin_df.empty or len(fin_df) < 2:
                continue

            market_cap = market_caps.get(ticker) if market_caps else None

            quality_factors = self.quality_factors.calculate(
                fin_df, prices.get(ticker), market_cap
            )
            value_factors = self.value_factors.calculate(
                fin_df, prices.get(ticker), market_cap
            )

            records.append({
                'ticker': ticker,
                'f_score': quality_factors.get('f_score'),
                'pb_ratio': value_factors.get('pb_ratio'),
                'roe': quality_factors.get('roe'),
                'roa': quality_factors.get('roa'),
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
        Select stocks passing F-Score threshold.

        Note: May return fewer than n stocks if not enough qualify.
        """
        scores = self.score(financials, prices, market_caps, **kwargs)

        if len(scores) == 0:
            return []

        # Sort by F-Score (descending), then by some tie-breaker if needed
        sorted_scores = scores.sort_values(ascending=False)

        # Take top n
        return sorted_scores.head(n).index.tolist()
