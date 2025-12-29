"""
Six-Factor Composite model.
Combines Value + Quality + Growth + Sentiment + Momentum + Volatility.
"""

from typing import Dict
import pandas as pd
import numpy as np
import logging

from .base import FactorModel
from factors.value import ValueFactors
from factors.quality import QualityFactors
from factors.growth import GrowthFactors
from factors.sentiment import SentimentFactors
from factors.momentum import MomentumFactors, VolatilityFactors
from config import DEFAULT_FACTOR_WEIGHTS

logger = logging.getLogger(__name__)


class SixFactorModel(FactorModel):
    """
    Six-Factor Composite Model

    Combines:
    - Value (P/E, P/B, EV/EBITDA, etc.)
    - Quality (ROE, ROIC, margins, F-Score)
    - Growth (Revenue, Earnings growth)
    - Sentiment (Insider buying, institutional ownership)
    - Momentum (12-1 momentum, relative strength)
    - Volatility (Low vol factor)
    """

    name = "Six-Factor"
    description = "Comprehensive factor model: Value + Quality + Growth + Sentiment + Momentum + Vol"

    def __init__(
        self,
        weights: Dict[str, float] = None,
        polygon_client=None
    ):
        """
        Args:
            weights: Factor weights dict (defaults to config.DEFAULT_FACTOR_WEIGHTS)
            polygon_client: Optional Polygon client for sentiment data
        """
        super().__init__()

        # Set weights
        self.weights = weights or DEFAULT_FACTOR_WEIGHTS.copy()

        # Normalize weights
        total = sum(self.weights.values())
        self.weights = {k: v / total for k, v in self.weights.items()}

        # Initialize factor calculators
        self.value_factors = ValueFactors()
        self.quality_factors = QualityFactors()
        self.growth_factors = GrowthFactors()
        self.sentiment_factors = SentimentFactors(polygon_client)
        self.momentum_factors = MomentumFactors()
        self.volatility_factors = VolatilityFactors()

    def score(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        insider_transactions: Dict[str, pd.DataFrame] = None,
        institutional_holdings: Dict[str, pd.DataFrame] = None,
        shares_outstanding: Dict[str, float] = None,
        benchmark_prices: pd.DataFrame = None,
        **kwargs
    ) -> pd.Series:
        """
        Score stocks using six-factor composite.
        """
        if not financials or market_caps is None:
            return pd.Series(dtype=float)

        composites = {}

        # Value composite
        if self.weights.get('value', 0) > 0:
            value_df = self.value_factors.calculate_universe(
                financials, prices, market_caps
            )
            if not value_df.empty:
                composites['value'] = self.value_factors.value_composite_score(value_df)

        # Quality composite
        if self.weights.get('quality', 0) > 0:
            quality_df = self.quality_factors.calculate_universe(
                financials, prices, market_caps
            )
            if not quality_df.empty:
                composites['quality'] = self.quality_factors.quality_composite_score(quality_df)

        # Growth composite
        if self.weights.get('growth', 0) > 0:
            growth_df = self.growth_factors.calculate_universe(
                financials, prices, market_caps
            )
            if not growth_df.empty:
                composites['growth'] = self.growth_factors.growth_composite_score(growth_df)

        # Momentum composite
        if self.weights.get('momentum', 0) > 0:
            momentum_df = self.momentum_factors.calculate_universe(
                prices, benchmark_prices
            )
            if not momentum_df.empty:
                composites['momentum'] = self.momentum_factors.momentum_composite_score(momentum_df)

        # Volatility composite
        if self.weights.get('volatility', 0) > 0:
            vol_df = self.volatility_factors.calculate_universe(
                prices, benchmark_prices
            )
            if not vol_df.empty:
                composites['volatility'] = self.volatility_factors.volatility_composite_score(vol_df)

        # Sentiment composite (if data available)
        if self.weights.get('sentiment', 0) > 0 and insider_transactions:
            sentiment_data = self._calculate_sentiment_universe(
                financials, prices, market_caps,
                insider_transactions, institutional_holdings, shares_outstanding
            )
            if not sentiment_data.empty:
                composites['sentiment'] = self.sentiment_factors.sentiment_composite_score(sentiment_data)

        if not composites:
            return pd.Series(dtype=float)

        # Find common tickers
        common_tickers = None
        for series in composites.values():
            if common_tickers is None:
                common_tickers = set(series.index)
            else:
                common_tickers = common_tickers.intersection(series.index)

        if not common_tickers:
            # Fall back to union if intersection is empty
            all_tickers = set()
            for series in composites.values():
                all_tickers.update(series.index)
            common_tickers = all_tickers

        common_tickers = list(common_tickers)

        # Z-score normalize and combine
        combined_score = pd.Series(0.0, index=common_tickers)

        for factor_name, series in composites.items():
            weight = self.weights.get(factor_name, 0)
            if weight > 0:
                # Reindex to common tickers
                aligned = series.reindex(common_tickers)
                z_score = self.zscore_normalize(aligned)
                combined_score += weight * z_score.fillna(0)

        return combined_score

    def _calculate_sentiment_universe(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float],
        insider_transactions: Dict[str, pd.DataFrame],
        institutional_holdings: Dict[str, pd.DataFrame] = None,
        shares_outstanding: Dict[str, float] = None
    ) -> pd.DataFrame:
        """
        Calculate sentiment factors for all stocks.
        """
        records = []
        institutional_holdings = institutional_holdings or {}
        shares_outstanding = shares_outstanding or {}

        for ticker in financials.keys():
            try:
                factors = self.sentiment_factors.calculate(
                    financials.get(ticker, pd.DataFrame()),
                    prices.get(ticker),
                    market_caps.get(ticker),
                    insider_transactions.get(ticker),
                    institutional_holdings.get(ticker),
                    shares_outstanding.get(ticker)
                )
                if factors:
                    factors['ticker'] = ticker
                    records.append(factors)
            except Exception as e:
                logger.warning(f"Failed to calculate sentiment for {ticker}: {e}")
                continue

        if not records:
            return pd.DataFrame()

        return pd.DataFrame(records).set_index('ticker')

    def get_factor_exposures(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        benchmark_prices: pd.DataFrame = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Get all six factor exposures.
        """
        # Collect all factor DataFrames
        dfs = []

        # Value
        value_df = self.value_factors.calculate_universe(financials, prices, market_caps)
        if not value_df.empty:
            value_df['value_composite'] = self.value_factors.value_composite_score(value_df)
            dfs.append(value_df)

        # Quality
        quality_df = self.quality_factors.calculate_universe(financials, prices, market_caps)
        if not quality_df.empty:
            quality_df['quality_composite'] = self.quality_factors.quality_composite_score(quality_df)
            # Rename overlapping columns
            quality_df = quality_df.add_suffix('_q')
            quality_df = quality_df.rename(columns={'quality_composite_q': 'quality_composite'})
            dfs.append(quality_df)

        # Growth
        growth_df = self.growth_factors.calculate_universe(financials, prices, market_caps)
        if not growth_df.empty:
            growth_df['growth_composite'] = self.growth_factors.growth_composite_score(growth_df)
            dfs.append(growth_df)

        # Momentum
        momentum_df = self.momentum_factors.calculate_universe(prices, benchmark_prices)
        if not momentum_df.empty:
            momentum_df['momentum_composite'] = self.momentum_factors.momentum_composite_score(momentum_df)
            dfs.append(momentum_df)

        # Volatility
        vol_df = self.volatility_factors.calculate_universe(prices, benchmark_prices)
        if not vol_df.empty:
            vol_df['volatility_composite'] = self.volatility_factors.volatility_composite_score(vol_df)
            dfs.append(vol_df)

        # Combine all
        if not dfs:
            return pd.DataFrame()

        combined = dfs[0]
        for df in dfs[1:]:
            combined = combined.join(df, how='outer')

        return combined
