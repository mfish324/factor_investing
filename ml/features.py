"""
Feature engineering for ML-based factor models.
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler
from sklearn.impute import SimpleImputer, KNNImputer
import logging

from factors.value import ValueFactors
from factors.quality import QualityFactors
from factors.growth import GrowthFactors
from factors.momentum import MomentumFactors, VolatilityFactors
from factors.sentiment import SentimentFactors
from config import WINSORIZE_LIMITS, SECTOR_NEUTRALIZE

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Transform raw factor data into ML-ready features.
    """

    def __init__(
        self,
        scaler_type: str = 'robust',
        imputer_type: str = 'median',
        winsorize_limits: Tuple[float, float] = None
    ):
        """
        Args:
            scaler_type: 'standard', 'robust', or 'minmax'
            imputer_type: 'mean', 'median', or 'knn'
            winsorize_limits: Tuple of (lower, upper) percentiles for winsorization
        """
        self.scaler_type = scaler_type
        self.imputer_type = imputer_type
        self.winsorize_limits = winsorize_limits or WINSORIZE_LIMITS

        self.scaler = self._get_scaler(scaler_type)
        self.imputer = self._get_imputer(imputer_type)

        # Factor calculators
        self.value_factors = ValueFactors()
        self.quality_factors = QualityFactors()
        self.growth_factors = GrowthFactors()
        self.momentum_factors = MomentumFactors()
        self.volatility_factors = VolatilityFactors()
        self.sentiment_factors = SentimentFactors()

        # Feature names after fitting
        self.feature_names_: List[str] = []
        self._fitted = False

    def _get_scaler(self, scaler_type: str):
        """Get scaler instance."""
        scalers = {
            'standard': StandardScaler(),
            'robust': RobustScaler(),
            'minmax': MinMaxScaler()
        }
        return scalers.get(scaler_type, RobustScaler())

    def _get_imputer(self, imputer_type: str):
        """Get imputer instance."""
        if imputer_type == 'knn':
            return KNNImputer(n_neighbors=5)
        elif imputer_type == 'mean':
            return SimpleImputer(strategy='mean')
        else:
            return SimpleImputer(strategy='median')

    def create_feature_matrix(
        self,
        financials_dict: Dict[str, pd.DataFrame],
        prices_dict: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float],
        benchmark_prices: pd.DataFrame = None,
        insider_transactions: Dict[str, pd.DataFrame] = None,
        institutional_holdings: Dict[str, pd.DataFrame] = None,
        shares_outstanding: Dict[str, float] = None
    ) -> pd.DataFrame:
        """
        Create feature matrix from all factor data.

        Args:
            financials_dict: Ticker -> financials DataFrame
            prices_dict: Ticker -> prices DataFrame
            market_caps: Ticker -> market cap
            benchmark_prices: Benchmark price DataFrame
            insider_transactions: Optional insider transaction data
            institutional_holdings: Optional institutional holdings data
            shares_outstanding: Optional shares outstanding data

        Returns:
            DataFrame with tickers as index and features as columns
        """
        # Calculate all factor categories
        dfs_to_join = []

        # Value factors
        value_df = self.value_factors.calculate_universe(
            financials_dict, prices_dict, market_caps
        )
        if not value_df.empty:
            value_df = value_df.add_prefix('value_')
            dfs_to_join.append(value_df)

        # Quality factors
        quality_df = self.quality_factors.calculate_universe(
            financials_dict, prices_dict, market_caps
        )
        if not quality_df.empty:
            quality_df = quality_df.add_prefix('quality_')
            dfs_to_join.append(quality_df)

        # Growth factors
        growth_df = self.growth_factors.calculate_universe(
            financials_dict, prices_dict, market_caps
        )
        if not growth_df.empty:
            growth_df = growth_df.add_prefix('growth_')
            dfs_to_join.append(growth_df)

        # Momentum factors
        momentum_df = self.momentum_factors.calculate_universe(
            prices_dict, benchmark_prices
        )
        if not momentum_df.empty:
            momentum_df = momentum_df.add_prefix('momentum_')
            dfs_to_join.append(momentum_df)

        # Volatility factors
        vol_df = self.volatility_factors.calculate_universe(
            prices_dict, benchmark_prices
        )
        if not vol_df.empty:
            vol_df = vol_df.add_prefix('vol_')
            dfs_to_join.append(vol_df)

        if not dfs_to_join:
            return pd.DataFrame()

        # Combine all factors
        combined = dfs_to_join[0]
        for df in dfs_to_join[1:]:
            combined = combined.join(df, how='outer')

        # Only set feature_names_ if not already fitted (avoid clobbering during inference)
        if not self._fitted:
            self.feature_names_ = combined.columns.tolist()

        return combined

    def add_interaction_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Create interaction terms between factors.
        """
        X = X.copy()

        # Value × Quality interaction
        if 'value_value_composite' in X.columns and 'quality_quality_composite' in X.columns:
            X['value_x_quality'] = X['value_value_composite'] * X['quality_quality_composite']

        # Momentum × Value
        if 'momentum_momentum_composite' in X.columns and 'value_value_composite' in X.columns:
            X['momentum_x_value'] = X['momentum_momentum_composite'] * X['value_value_composite']

        # Quality × Growth
        if 'quality_quality_composite' in X.columns and 'growth_growth_composite' in X.columns:
            X['quality_x_growth'] = X['quality_quality_composite'] * X['growth_growth_composite']

        # Momentum × Quality (quality momentum)
        if 'momentum_momentum_composite' in X.columns and 'quality_quality_composite' in X.columns:
            X['momentum_x_quality'] = X['momentum_momentum_composite'] * X['quality_quality_composite']

        return X

    def add_sector_features(
        self,
        X: pd.DataFrame,
        sector_map: Dict[str, str]
    ) -> pd.DataFrame:
        """
        Add sector dummy variables.
        """
        X = X.copy()

        sectors = pd.Series({ticker: sector_map.get(ticker, 'Unknown')
                           for ticker in X.index})

        # Create dummies
        sector_dummies = pd.get_dummies(sectors, prefix='sector')
        sector_dummies.index = X.index

        return X.join(sector_dummies)

    def winsorize(
        self,
        X: pd.DataFrame,
        limits: Tuple[float, float] = None
    ) -> pd.DataFrame:
        """
        Clip extreme values to reduce outlier impact.
        """
        limits = limits or self.winsorize_limits
        X = X.copy()

        for col in X.columns:
            lower = X[col].quantile(limits[0])
            upper = X[col].quantile(limits[1])
            X[col] = X[col].clip(lower=lower, upper=upper)

        return X

    def sector_neutralize(
        self,
        X: pd.DataFrame,
        sector_map: Dict[str, str]
    ) -> pd.DataFrame:
        """
        Subtract sector mean from each factor.
        Makes factors comparable across sectors.
        """
        X = X.copy()

        sectors = pd.Series({ticker: sector_map.get(ticker, 'Unknown')
                           for ticker in X.index})

        for col in X.columns:
            if col.startswith('sector_'):
                continue
            sector_means = X.groupby(sectors)[col].transform('mean')
            X[col] = X[col] - sector_means

        return X

    def fit_transform(
        self,
        X: pd.DataFrame,
        winsorize: bool = True,
        add_interactions: bool = True
    ) -> pd.DataFrame:
        """
        Fit preprocessing and transform features.
        """
        X = X.copy()

        # Winsorize
        if winsorize:
            X = self.winsorize(X)

        # Add interactions
        if add_interactions:
            X = self.add_interaction_features(X)

        # Store feature names before imputation
        self.feature_names_ = X.columns.tolist()

        # Drop columns that are entirely NaN (imputer can't handle them)
        all_nan_cols = X.columns[X.isna().all()]
        if len(all_nan_cols) > 0:
            logger.warning(f"Dropping all-NaN columns: {all_nan_cols.tolist()}")
            X = X.drop(columns=all_nan_cols)
            self.feature_names_ = X.columns.tolist()

        # Impute missing values
        X_imputed = self.imputer.fit_transform(X)

        # Scale
        X_scaled = self.scaler.fit_transform(X_imputed)

        self._fitted = True

        return pd.DataFrame(X_scaled, index=X.index, columns=X.columns)

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transform features using fitted preprocessing.
        """
        if not self._fitted:
            raise ValueError("FeatureEngineer must be fitted first")

        X = X.copy()

        # Add interactions if missing
        X = self.add_interaction_features(X)

        # Ensure same columns
        for col in self.feature_names_:
            if col not in X.columns:
                X[col] = np.nan

        X = X[self.feature_names_]

        # Impute and scale
        X_imputed = self.imputer.transform(X)
        X_scaled = self.scaler.transform(X_imputed)

        return pd.DataFrame(X_scaled, index=X.index, columns=X.columns)

    def create_target_variable(
        self,
        prices_dict: Dict[str, pd.DataFrame],
        holding_period: int = 63,
        target_type: str = 'return',
        as_of_date: str = None
    ) -> pd.Series:
        """
        Create forward return target for supervised learning.

        Args:
            prices_dict: Ticker -> prices DataFrame
            holding_period: Number of trading days to look ahead
            target_type: 'return', 'excess_return', 'binary', 'tercile'
            as_of_date: Date to calculate forward returns from

        Returns:
            Series of target values indexed by ticker
        """
        forward_returns = {}

        for ticker, prices in prices_dict.items():
            if prices.empty or 'close' not in prices.columns:
                continue

            close = prices['close'].values

            if as_of_date:
                # Find index for as_of_date
                if 'date' in prices.columns:
                    dates = pd.to_datetime(prices['date'])
                    mask = dates <= pd.Timestamp(as_of_date)
                    if not mask.any():
                        continue
                    start_idx = mask.sum() - 1
                else:
                    start_idx = -1
            else:
                if len(close) > holding_period + 1:
                    start_idx = len(close) - holding_period - 1
                else:
                    start_idx = 0

            end_idx = start_idx + holding_period

            if end_idx >= len(close) or start_idx < 0:
                continue

            start_price = close[start_idx]
            end_price = close[end_idx]

            if start_price > 0:
                forward_returns[ticker] = (end_price - start_price) / start_price

        if not forward_returns:
            return pd.Series(dtype=float)

        returns = pd.Series(forward_returns)

        if target_type == 'return':
            return returns
        elif target_type == 'binary':
            median = returns.median()
            return (returns > median).astype(int)
        elif target_type == 'tercile':
            return pd.qcut(returns, 3, labels=[0, 1, 2]).astype(int)
        else:
            return returns

    def prepare_training_data(
        self,
        financials_dict: Dict[str, pd.DataFrame],
        prices_dict: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float],
        benchmark_prices: pd.DataFrame = None,
        holding_period: int = 63,
        target_type: str = 'return'
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare features and target for training.
        """
        # Create features
        X = self.create_feature_matrix(
            financials_dict, prices_dict, market_caps, benchmark_prices
        )

        if X.empty:
            return pd.DataFrame(), pd.Series(dtype=float)

        # Create target
        y = self.create_target_variable(
            prices_dict, holding_period, target_type
        )

        # Align
        common_tickers = X.index.intersection(y.index)
        X = X.loc[common_tickers]
        y = y.loc[common_tickers]

        # Remove rows with all NaN features
        valid_mask = ~X.isna().all(axis=1)
        X = X[valid_mask]
        y = y[valid_mask]

        return X, y
