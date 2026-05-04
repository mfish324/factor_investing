"""
Low Volatility factor model.
Exploits the low-volatility anomaly: stocks with lower historical volatility
tend to deliver better risk-adjusted returns, especially in down/sideways markets.
"""

from typing import Dict
import pandas as pd
import numpy as np
import logging

from .base import FactorModel
from factors.momentum import VolatilityFactors
from factors.quality import QualityFactors

logger = logging.getLogger(__name__)


class LowVolatilityModel(FactorModel):
    """
    Low Volatility Model

    Strategy:
    1. Calculate volatility metrics (historical vol, beta, downside vol)
    2. Calculate quality metrics as a stability filter (profitable, low leverage)
    3. Favor stocks with lowest volatility among quality names
    4. Combine with configurable weights

    Rationale:
    The low-volatility anomaly shows that low-vol stocks earn higher
    risk-adjusted returns than high-vol stocks. Adding a quality filter
    avoids "cheap for a reason" low-vol traps (e.g., declining businesses).
    """

    name = "Low Volatility"
    description = "Low volatility stocks with quality filter for defensive positioning"

    def __init__(
        self,
        volatility_weight: float = 0.65,
        quality_weight: float = 0.35
    ):
        super().__init__()
        total = volatility_weight + quality_weight
        self.volatility_weight = volatility_weight / total
        self.quality_weight = quality_weight / total

        self.volatility_factors = VolatilityFactors()
        self.quality_factors = QualityFactors()

    def score(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        benchmark_prices: pd.DataFrame = None,
        **kwargs
    ) -> pd.Series:
        """
        Score stocks using low-volatility composite with quality filter.
        """
        if not prices:
            return pd.Series(dtype=float)

        # Calculate volatility factors for universe
        vol_df = self.volatility_factors.calculate_universe(
            prices, benchmark_prices
        )

        if vol_df.empty:
            return pd.Series(dtype=float)

        # Low volatility composite (already inverted: higher = lower vol)
        vol_composite = self.volatility_factors.volatility_composite_score(vol_df)

        # Calculate quality factors if financials available
        if financials and market_caps:
            quality_df = self.quality_factors.calculate_universe(
                financials, prices, market_caps
            )

            if not quality_df.empty:
                quality_composite = self.quality_factors.quality_composite_score(quality_df)

                # Align indices
                common = vol_composite.index.intersection(quality_composite.index)
                vol_composite = vol_composite.loc[common]
                quality_composite = quality_composite.loc[common]

                # Z-score normalize
                vol_z = self.zscore_normalize(vol_composite)
                quality_z = self.zscore_normalize(quality_composite)

                return (
                    self.volatility_weight * vol_z +
                    self.quality_weight * quality_z
                )

        # Fallback: volatility only
        return vol_composite

    def get_factor_exposures(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        benchmark_prices: pd.DataFrame = None,
        **kwargs
    ) -> pd.DataFrame:
        """Get underlying volatility and quality factors."""
        vol_df = self.volatility_factors.calculate_universe(
            prices, benchmark_prices
        )
        quality_df = self.quality_factors.calculate_universe(
            financials, prices, market_caps
        )

        if vol_df.empty:
            return quality_df
        if quality_df.empty:
            return vol_df

        combined = vol_df.join(quality_df, how='outer', rsuffix='_quality')
        combined['vol_composite'] = self.volatility_factors.volatility_composite_score(vol_df)
        combined['quality_composite'] = self.quality_factors.quality_composite_score(quality_df)

        return combined
