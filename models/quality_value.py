"""
Quality-Value composite model.
Combines quality metrics (ROE, ROIC, margins) with value metrics (P/E, P/B, etc.).
"""

from typing import Dict
import pandas as pd
import numpy as np
import logging

from .base import FactorModel
from factors.value import ValueFactors
from factors.quality import QualityFactors

logger = logging.getLogger(__name__)


class QualityValueModel(FactorModel):
    """
    Quality-Value Composite Model

    Strategy:
    1. Calculate quality composite score (ROE, ROIC, margins)
    2. Calculate value composite score (P/E, P/B, EV/EBITDA)
    3. Z-score normalize each
    4. Combine with configurable weights
    """

    name = "Quality-Value"
    description = "Composite of quality and value factors"

    def __init__(
        self,
        quality_weight: float = 0.5,
        value_weight: float = 0.5
    ):
        """
        Args:
            quality_weight: Weight for quality composite
            value_weight: Weight for value composite
        """
        super().__init__()
        # Normalize weights
        total = quality_weight + value_weight
        self.quality_weight = quality_weight / total
        self.value_weight = value_weight / total

        self.value_factors = ValueFactors()
        self.quality_factors = QualityFactors()

    def score(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        **kwargs
    ) -> pd.Series:
        """
        Score stocks using quality-value composite.
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

        if value_df.empty or quality_df.empty:
            return pd.Series(dtype=float)

        # Calculate composite scores
        value_composite = self.value_factors.value_composite_score(value_df)
        quality_composite = self.quality_factors.quality_composite_score(quality_df)

        # Align indices
        common_tickers = value_composite.index.intersection(quality_composite.index)
        value_composite = value_composite.loc[common_tickers]
        quality_composite = quality_composite.loc[common_tickers]

        # Z-score normalize
        value_z = self.zscore_normalize(value_composite)
        quality_z = self.zscore_normalize(quality_composite)

        # Combine with weights
        combined_score = (
            self.quality_weight * quality_z +
            self.value_weight * value_z
        )

        return combined_score

    def get_factor_exposures(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Get all quality and value factors for stocks.
        """
        value_df = self.value_factors.calculate_universe(
            financials, prices, market_caps
        )
        quality_df = self.quality_factors.calculate_universe(
            financials, prices, market_caps
        )

        # Merge on ticker
        if value_df.empty:
            return quality_df
        if quality_df.empty:
            return value_df

        # Combine
        combined = value_df.join(quality_df, how='outer', rsuffix='_quality')

        # Add composite scores
        combined['value_composite'] = self.value_factors.value_composite_score(value_df)
        combined['quality_composite'] = self.quality_factors.quality_composite_score(quality_df)

        return combined
