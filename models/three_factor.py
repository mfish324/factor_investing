"""
Three-Factor Composite model.
Combines Value + Quality + Growth with configurable weights.
"""

from typing import Dict
import pandas as pd
import numpy as np
import logging

from .base import FactorModel
from factors.value import ValueFactors
from factors.quality import QualityFactors
from factors.growth import GrowthFactors

logger = logging.getLogger(__name__)


class ThreeFactorModel(FactorModel):
    """
    Three-Factor Composite Model: Value + Quality + Growth

    Strategy:
    1. Calculate composite scores for value, quality, and growth
    2. Z-score normalize each composite
    3. Combine with configurable weights
    """

    name = "Three-Factor"
    description = "Value + Quality + Growth composite with configurable weights"

    def __init__(
        self,
        value_weight: float = 0.34,
        quality_weight: float = 0.33,
        growth_weight: float = 0.33
    ):
        """
        Args:
            value_weight: Weight for value composite
            quality_weight: Weight for quality composite
            growth_weight: Weight for growth composite
        """
        super().__init__()
        # Normalize weights
        total = value_weight + quality_weight + growth_weight
        self.value_weight = value_weight / total
        self.quality_weight = quality_weight / total
        self.growth_weight = growth_weight / total

        self.value_factors = ValueFactors()
        self.quality_factors = QualityFactors()
        self.growth_factors = GrowthFactors()

    def score(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        **kwargs
    ) -> pd.Series:
        """
        Score stocks using three-factor composite.
        """
        if not financials or market_caps is None:
            return pd.Series(dtype=float)

        # Calculate all factors for universe
        value_df = self.value_factors.calculate_universe(
            financials, prices, market_caps
        )
        quality_df = self.quality_factors.calculate_universe(
            financials, prices, market_caps
        )
        growth_df = self.growth_factors.calculate_universe(
            financials, prices, market_caps
        )

        if value_df.empty and quality_df.empty and growth_df.empty:
            return pd.Series(dtype=float)

        # Calculate composite scores
        composites = {}

        if not value_df.empty:
            composites['value'] = self.value_factors.value_composite_score(value_df)
        if not quality_df.empty:
            composites['quality'] = self.quality_factors.quality_composite_score(quality_df)
        if not growth_df.empty:
            composites['growth'] = self.growth_factors.growth_composite_score(growth_df)

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
            return pd.Series(dtype=float)

        common_tickers = list(common_tickers)

        # Z-score normalize and combine
        combined_score = pd.Series(0.0, index=common_tickers)

        weights = {
            'value': self.value_weight,
            'quality': self.quality_weight,
            'growth': self.growth_weight
        }

        for factor_name, series in composites.items():
            z_score = self.zscore_normalize(series.loc[common_tickers])
            combined_score += weights[factor_name] * z_score.fillna(0)

        return combined_score

    def get_factor_exposures(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Get all factor exposures.
        """
        value_df = self.value_factors.calculate_universe(
            financials, prices, market_caps
        )
        quality_df = self.quality_factors.calculate_universe(
            financials, prices, market_caps
        )
        growth_df = self.growth_factors.calculate_universe(
            financials, prices, market_caps
        )

        # Start with value factors
        if value_df.empty:
            combined = pd.DataFrame()
        else:
            combined = value_df.copy()
            combined['value_composite'] = self.value_factors.value_composite_score(value_df)

        # Add quality factors
        if not quality_df.empty:
            quality_df['quality_composite'] = self.quality_factors.quality_composite_score(quality_df)
            if combined.empty:
                combined = quality_df
            else:
                combined = combined.join(quality_df, how='outer', rsuffix='_q')

        # Add growth factors
        if not growth_df.empty:
            growth_df['growth_composite'] = self.growth_factors.growth_composite_score(growth_df)
            if combined.empty:
                combined = growth_df
            else:
                combined = combined.join(growth_df, how='outer', rsuffix='_g')

        return combined
