"""
ML Ensemble model for stock selection.
"""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import logging
import joblib
from pathlib import Path

from .base import FactorModel
from ml.features import FeatureEngineer
from ml.models import XGBoostRanker, EnsembleFactorModel, FactorMLModel
from ml.training import MLTrainingPipeline
from config import ML_MODELS_DIR

logger = logging.getLogger(__name__)


class MLEnsembleModel(FactorModel):
    """
    ML-based stock selection using gradient boosting on all factors.
    """

    name = "ML Ensemble"
    description = "XGBoost/LightGBM ranker trained on all factor categories"

    def __init__(
        self,
        feature_engineer: FeatureEngineer = None,
        model_path: str = None,
        model_type: str = 'xgboost'
    ):
        super().__init__()
        self.feature_engineer = feature_engineer or FeatureEngineer()
        self.model_type = model_type

        try:
            self.model = XGBoostRanker()
        except ImportError:
            self.model = FactorMLModel('random_forest')

        self.is_trained = False

        if model_path:
            self.load(model_path)

    def train(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float],
        benchmark_prices: pd.DataFrame = None,
        holding_period: int = 63,
        tune_hyperparams: bool = True,
        n_trials: int = 50
    ) -> 'MLEnsembleModel':
        """
        Train the model on historical data.
        """
        logger.info("Training ML Ensemble model...")

        pipeline = MLTrainingPipeline(
            feature_engineer=self.feature_engineer,
            model_class=type(self.model),
            n_splits=5
        )

        self.model = pipeline.full_pipeline(
            financials_dict=financials,
            prices_dict=prices,
            market_caps=market_caps,
            benchmark_prices=benchmark_prices,
            holding_period=holding_period,
            tune_hyperparams=tune_hyperparams,
            n_trials=n_trials
        )

        self.is_trained = True
        logger.info("ML Ensemble model training complete")

        return self

    def score(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        benchmark_prices: pd.DataFrame = None,
        **kwargs
    ) -> pd.Series:
        """
        Score stocks using trained ML model.
        """
        if not self.is_trained:
            raise ValueError("Model must be trained first. Call train() or load()")

        # Create feature matrix
        X = self.feature_engineer.create_feature_matrix(
            financials, prices, market_caps, benchmark_prices
        )

        if X.empty:
            return pd.Series(dtype=float)

        # Transform features
        X_transformed = self.feature_engineer.transform(X)

        # Predict
        return self.model.predict(X_transformed)

    def select_portfolio(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        n: int = 30,
        benchmark_prices: pd.DataFrame = None,
        **kwargs
    ) -> List[str]:
        """
        Select top N stocks.
        """
        scores = self.score(financials, prices, market_caps, benchmark_prices)

        if scores.empty:
            return []

        return scores.nlargest(n).index.tolist()

    def get_factor_exposures(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        benchmark_prices: pd.DataFrame = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Get feature matrix used for predictions.
        """
        return self.feature_engineer.create_feature_matrix(
            financials, prices, market_caps, benchmark_prices
        )

    def get_feature_importance(self) -> pd.Series:
        """
        Get feature importance from trained model.
        """
        if not self.is_trained:
            return pd.Series(dtype=float)

        return self.model.feature_importance_

    def save(self, path: str = None):
        """
        Save trained model to disk.
        """
        if not self.is_trained:
            raise ValueError("Cannot save untrained model")

        path = path or str(ML_MODELS_DIR / f"{self.name.lower().replace(' ', '_')}.joblib")
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        save_dict = {
            'model': self.model,
            'feature_engineer': self.feature_engineer,
            'model_type': self.model_type
        }
        joblib.dump(save_dict, path)
        logger.info(f"Model saved to {path}")

    def load(self, path: str):
        """
        Load trained model from disk.
        """
        save_dict = joblib.load(path)
        self.model = save_dict['model']
        self.feature_engineer = save_dict['feature_engineer']
        self.model_type = save_dict.get('model_type', 'xgboost')
        self.is_trained = True
        logger.info(f"Model loaded from {path}")


class MultiModelEnsemble(FactorModel):
    """
    Ensemble combining multiple ML model types.
    """

    name = "Multi-Model Ensemble"
    description = "Ensemble of Random Forest, XGBoost, and LightGBM"

    def __init__(self, feature_engineer: FeatureEngineer = None):
        super().__init__()
        self.feature_engineer = feature_engineer or FeatureEngineer()
        self.ensemble = EnsembleFactorModel()
        self.is_trained = False

    def train(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float],
        benchmark_prices: pd.DataFrame = None,
        holding_period: int = 63
    ) -> 'MultiModelEnsemble':
        """
        Train the ensemble on historical data.
        """
        logger.info("Training Multi-Model Ensemble...")

        X, y = self.feature_engineer.prepare_training_data(
            financials, prices, market_caps, benchmark_prices, holding_period
        )

        if X.empty:
            raise ValueError("No training data available")

        X_transformed = self.feature_engineer.fit_transform(X)
        self.ensemble.fit(X_transformed, y)
        self.is_trained = True

        logger.info("Multi-Model Ensemble training complete")
        return self

    def score(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        benchmark_prices: pd.DataFrame = None,
        **kwargs
    ) -> pd.Series:
        """
        Score stocks using ensemble predictions.
        """
        if not self.is_trained:
            raise ValueError("Model must be trained first")

        X = self.feature_engineer.create_feature_matrix(
            financials, prices, market_caps, benchmark_prices
        )

        if X.empty:
            return pd.Series(dtype=float)

        X_transformed = self.feature_engineer.transform(X)
        return self.ensemble.predict(X_transformed)
