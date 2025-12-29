"""
ML model definitions for factor-based stock selection.
"""

from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
from sklearn.ensemble import (
    RandomForestClassifier, RandomForestRegressor,
    GradientBoostingClassifier, GradientBoostingRegressor,
    VotingClassifier, StackingClassifier
)
from sklearn.linear_model import (
    Ridge, Lasso, ElasticNet,
    LogisticRegression, RidgeClassifier
)
from sklearn.neural_network import MLPClassifier, MLPRegressor
import logging

logger = logging.getLogger(__name__)

# Optional imports for XGBoost and LightGBM
try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    logger.warning("XGBoost not installed. Some models will be unavailable.")

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    logger.warning("LightGBM not installed. Some models will be unavailable.")


class FactorMLModel:
    """
    Base class for ML-based factor models.
    """

    def __init__(self, model_type: str = 'random_forest', **kwargs):
        self.model_type = model_type
        self.model = self._create_model(model_type, **kwargs)
        self.feature_importance_: Optional[pd.Series] = None
        self._fitted = False

    def _create_model(self, model_type: str, **kwargs):
        """Factory method for creating ML models."""
        models = {
            # Random Forest
            'random_forest': RandomForestRegressor(
                n_estimators=kwargs.get('n_estimators', 200),
                max_depth=kwargs.get('max_depth', 10),
                min_samples_leaf=kwargs.get('min_samples_leaf', 20),
                random_state=42,
                n_jobs=-1
            ),
            'random_forest_classifier': RandomForestClassifier(
                n_estimators=kwargs.get('n_estimators', 200),
                max_depth=kwargs.get('max_depth', 10),
                min_samples_leaf=kwargs.get('min_samples_leaf', 20),
                random_state=42,
                n_jobs=-1
            ),

            # Gradient Boosting
            'gradient_boosting': GradientBoostingRegressor(
                n_estimators=kwargs.get('n_estimators', 100),
                max_depth=kwargs.get('max_depth', 6),
                learning_rate=kwargs.get('learning_rate', 0.1),
                random_state=42
            ),
            'gradient_boosting_classifier': GradientBoostingClassifier(
                n_estimators=kwargs.get('n_estimators', 100),
                max_depth=kwargs.get('max_depth', 6),
                learning_rate=kwargs.get('learning_rate', 0.1),
                random_state=42
            ),

            # Linear models
            'ridge': Ridge(alpha=kwargs.get('alpha', 1.0)),
            'lasso': Lasso(alpha=kwargs.get('alpha', 0.1)),
            'elastic_net': ElasticNet(
                alpha=kwargs.get('alpha', 0.1),
                l1_ratio=kwargs.get('l1_ratio', 0.5)
            ),
            'logistic': LogisticRegression(
                C=kwargs.get('C', 1.0),
                penalty='l2',
                max_iter=1000,
                random_state=42
            ),

            # Neural Network
            'mlp': MLPRegressor(
                hidden_layer_sizes=kwargs.get('hidden_layers', (64, 32)),
                activation='relu',
                alpha=kwargs.get('alpha', 0.001),
                early_stopping=True,
                validation_fraction=0.2,
                random_state=42,
                max_iter=500
            ),
            'mlp_classifier': MLPClassifier(
                hidden_layer_sizes=kwargs.get('hidden_layers', (64, 32)),
                activation='relu',
                alpha=kwargs.get('alpha', 0.001),
                early_stopping=True,
                validation_fraction=0.2,
                random_state=42,
                max_iter=500
            ),
        }

        # Add XGBoost models if available
        if HAS_XGBOOST:
            models['xgboost'] = xgb.XGBRegressor(
                n_estimators=kwargs.get('n_estimators', 100),
                max_depth=kwargs.get('max_depth', 6),
                learning_rate=kwargs.get('learning_rate', 0.1),
                subsample=kwargs.get('subsample', 0.8),
                colsample_bytree=kwargs.get('colsample_bytree', 0.8),
                random_state=42
            )
            models['xgboost_classifier'] = xgb.XGBClassifier(
                n_estimators=kwargs.get('n_estimators', 100),
                max_depth=kwargs.get('max_depth', 6),
                learning_rate=kwargs.get('learning_rate', 0.1),
                random_state=42
            )

        # Add LightGBM models if available
        if HAS_LIGHTGBM:
            models['lightgbm'] = lgb.LGBMRegressor(
                n_estimators=kwargs.get('n_estimators', 100),
                num_leaves=kwargs.get('num_leaves', 31),
                learning_rate=kwargs.get('learning_rate', 0.1),
                random_state=42
            )
            models['lightgbm_classifier'] = lgb.LGBMClassifier(
                n_estimators=kwargs.get('n_estimators', 100),
                num_leaves=kwargs.get('num_leaves', 31),
                random_state=42
            )

        return models.get(model_type)

    def fit(self, X: pd.DataFrame, y: pd.Series) -> 'FactorMLModel':
        """Train the model."""
        if self.model is None:
            raise ValueError(f"Model type '{self.model_type}' not available")

        self.model.fit(X, y)
        self._fitted = True

        # Extract feature importance if available
        if hasattr(self.model, 'feature_importances_'):
            self.feature_importance_ = pd.Series(
                self.model.feature_importances_,
                index=X.columns
            ).sort_values(ascending=False)
        elif hasattr(self.model, 'coef_'):
            coef = self.model.coef_
            if len(coef.shape) > 1:
                coef = coef[0]
            self.feature_importance_ = pd.Series(
                np.abs(coef),
                index=X.columns
            ).sort_values(ascending=False)

        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        """Predict scores for stocks."""
        if not self._fitted:
            raise ValueError("Model must be fitted first")

        predictions = self.model.predict(X)
        return pd.Series(predictions, index=X.index)

    def select_portfolio(self, X: pd.DataFrame, n: int = 30) -> List[str]:
        """Select top N stocks based on predicted scores."""
        scores = self.predict(X)
        return scores.nlargest(n).index.tolist()


class XGBoostRanker(FactorMLModel):
    """
    XGBoost-based stock ranker.
    Uses regression objective for ranking stocks.
    """

    def __init__(self, **kwargs):
        if not HAS_XGBOOST:
            raise ImportError("XGBoost is required for XGBoostRanker")
        super().__init__(model_type='xgboost', **kwargs)

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        groups: np.ndarray = None
    ) -> 'XGBoostRanker':
        """
        Train the ranker.

        Args:
            X: Feature matrix
            y: Target (forward returns or ranks)
            groups: Optional group sizes for ranking
        """
        self.model.fit(X, y)
        self._fitted = True

        self.feature_importance_ = pd.Series(
            self.model.feature_importances_,
            index=X.columns
        ).sort_values(ascending=False)

        return self


class FactorTimingModel(FactorMLModel):
    """
    ML model to dynamically weight factors based on market regime.
    Predicts which factors will perform best in current environment.
    """

    def __init__(self, **kwargs):
        super().__init__(model_type='lightgbm_classifier' if HAS_LIGHTGBM else 'random_forest_classifier', **kwargs)
        self.factor_names: Optional[List[str]] = None

    def create_regime_features(self, date: str) -> pd.DataFrame:
        """
        Create features describing current market regime.

        This is a placeholder - in practice would include:
        - VIX level and trend
        - Yield curve slope
        - Market momentum
        - Credit spreads
        - Economic indicators
        """
        # Placeholder - would need external data
        return pd.DataFrame({
            'placeholder': [0]
        })

    def fit(
        self,
        regime_features: pd.DataFrame,
        best_factor: pd.Series
    ) -> 'FactorTimingModel':
        """
        Train model to predict which factor will work best.

        Args:
            regime_features: Macro/market features
            best_factor: Which factor had best returns
        """
        self.factor_names = best_factor.unique().tolist()

        if self.model is not None:
            self.model.fit(regime_features, best_factor)
            self._fitted = True

        return self

    def predict_factor_weights(
        self,
        current_regime: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Predict optimal factor weights for current regime.
        """
        if not self._fitted or self.factor_names is None:
            # Return equal weights
            return {}

        try:
            probas = self.model.predict_proba(current_regime)[0]
            weights = dict(zip(self.factor_names, probas))
            return weights
        except Exception:
            return {}


class NeuralFactorModel(FactorMLModel):
    """
    Neural network for non-linear factor combination.
    """

    def __init__(
        self,
        hidden_layers: tuple = (128, 64, 32),
        dropout: float = 0.3,
        **kwargs
    ):
        kwargs['hidden_layers'] = hidden_layers
        super().__init__(model_type='mlp', **kwargs)
        self.architecture = {
            'hidden_layers': hidden_layers,
            'dropout': dropout
        }


class EnsembleFactorModel:
    """
    Ensemble of multiple ML models for robust predictions.
    """

    def __init__(self, base_models: List[FactorMLModel] = None):
        if base_models is None:
            base_models = [
                FactorMLModel('random_forest'),
                FactorMLModel('gradient_boosting'),
            ]
            if HAS_XGBOOST:
                base_models.append(FactorMLModel('xgboost'))
            if HAS_LIGHTGBM:
                base_models.append(FactorMLModel('lightgbm'))

        self.base_models = base_models
        self._fitted = False

    def fit(self, X: pd.DataFrame, y: pd.Series) -> 'EnsembleFactorModel':
        """Train all base models."""
        for model in self.base_models:
            try:
                model.fit(X, y)
            except Exception as e:
                logger.warning(f"Failed to fit {model.model_type}: {e}")

        self._fitted = True
        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        """Average predictions from all models."""
        predictions = []

        for model in self.base_models:
            if model._fitted:
                try:
                    pred = model.predict(X)
                    predictions.append(pred)
                except Exception:
                    continue

        if not predictions:
            return pd.Series(dtype=float)

        # Average predictions
        combined = pd.concat(predictions, axis=1).mean(axis=1)
        return combined

    def select_portfolio(self, X: pd.DataFrame, n: int = 30) -> List[str]:
        """Select top N stocks based on ensemble prediction."""
        scores = self.predict(X)
        return scores.nlargest(n).index.tolist()
