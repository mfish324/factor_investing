"""
ML training pipeline with cross-validation and hyperparameter tuning.
"""

from typing import Dict, List, Tuple, Optional, Type
import pandas as pd
import numpy as np
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import mean_squared_error, ndcg_score
import logging

from .features import FeatureEngineer
from .models import FactorMLModel, XGBoostRanker
from config import ML_N_TRIALS

logger = logging.getLogger(__name__)

# Optional optuna import
try:
    import optuna
    HAS_OPTUNA = True
except ImportError:
    HAS_OPTUNA = False
    logger.warning("Optuna not installed. Hyperparameter tuning will be limited.")


class MLTrainingPipeline:
    """
    End-to-end training pipeline with cross-validation and hyperparameter tuning.
    """

    def __init__(
        self,
        feature_engineer: FeatureEngineer,
        model_class: Type[FactorMLModel] = None,
        n_splits: int = 5
    ):
        self.feature_engineer = feature_engineer
        self.model_class = model_class or FactorMLModel
        self.n_splits = n_splits
        self.best_model: Optional[FactorMLModel] = None
        self.best_params: Optional[Dict] = None

    def prepare_training_data(
        self,
        financials_dict: Dict[str, pd.DataFrame],
        prices_dict: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float],
        benchmark_prices: pd.DataFrame = None,
        holding_period: int = 63
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare feature matrix and target for training.
        """
        X, y = self.feature_engineer.prepare_training_data(
            financials_dict=financials_dict,
            prices_dict=prices_dict,
            market_caps=market_caps,
            benchmark_prices=benchmark_prices,
            holding_period=holding_period,
            target_type='return'
        )

        return X, y

    def time_series_cv(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        model_params: Dict = None
    ) -> Dict[str, float]:
        """
        Walk-forward cross-validation respecting time ordering.
        """
        model_params = model_params or {}
        tscv = TimeSeriesSplit(n_splits=self.n_splits)

        scores = {'mse': [], 'ic': [], 'top_quintile_return': []}

        for train_idx, test_idx in tscv.split(X):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

            # Train model
            model = self.model_class(**model_params)
            model.fit(X_train, y_train)

            # Predict
            y_pred = model.predict(X_test)

            # MSE
            mse = mean_squared_error(y_test, y_pred)
            scores['mse'].append(mse)

            # Information Coefficient (rank correlation)
            from scipy.stats import spearmanr
            ic, _ = spearmanr(y_test, y_pred)
            if not np.isnan(ic):
                scores['ic'].append(ic)

            # Top quintile return
            n_stocks = len(y_test)
            top_n = max(1, n_stocks // 5)
            top_tickers = y_pred.nlargest(top_n).index
            top_return = y_test.loc[top_tickers].mean()
            scores['top_quintile_return'].append(top_return)

        return {k: np.mean(v) for k, v in scores.items() if v}

    def hyperparameter_tuning(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_trials: int = None
    ) -> Dict:
        """
        Hyperparameter optimization.
        """
        n_trials = n_trials or ML_N_TRIALS

        if not HAS_OPTUNA:
            logger.warning("Optuna not available. Using default parameters.")
            return {}

        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
            }

            # Add model-specific parameters
            if hasattr(self.model_class, 'model_type'):
                if 'xgboost' in str(self.model_class):
                    params['subsample'] = trial.suggest_float('subsample', 0.6, 1.0)
                    params['colsample_bytree'] = trial.suggest_float('colsample_bytree', 0.6, 1.0)

            try:
                scores = self.time_series_cv(X, y, params)
                return scores.get('ic', 0)
            except Exception as e:
                logger.warning(f"Trial failed: {e}")
                return 0

        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

        self.best_params = study.best_params
        logger.info(f"Best parameters: {self.best_params}")
        logger.info(f"Best IC: {study.best_value:.4f}")

        return study.best_params

    def train_final_model(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        params: Dict = None
    ) -> FactorMLModel:
        """
        Train final model on all data with best parameters.
        """
        params = params or self.best_params or {}

        self.best_model = self.model_class(**params)
        self.best_model.fit(X, y)

        logger.info("Final model trained successfully")

        return self.best_model

    def full_pipeline(
        self,
        financials_dict: Dict[str, pd.DataFrame],
        prices_dict: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float],
        benchmark_prices: pd.DataFrame = None,
        holding_period: int = 63,
        tune_hyperparams: bool = True,
        n_trials: int = None
    ) -> FactorMLModel:
        """
        Run full training pipeline.
        """
        logger.info("Preparing training data...")
        X, y = self.prepare_training_data(
            financials_dict, prices_dict, market_caps,
            benchmark_prices, holding_period
        )

        if X.empty or y.empty:
            raise ValueError("No training data available")

        logger.info(f"Training data: {len(X)} samples, {X.shape[1]} features")

        # Fit feature engineering
        X_transformed = self.feature_engineer.fit_transform(X)

        # Cross-validation
        logger.info("Running cross-validation...")
        cv_scores = self.time_series_cv(X_transformed, y)
        logger.info(f"CV Scores: {cv_scores}")

        # Hyperparameter tuning
        if tune_hyperparams:
            logger.info("Tuning hyperparameters...")
            self.hyperparameter_tuning(X_transformed, y, n_trials)

        # Train final model
        logger.info("Training final model...")
        model = self.train_final_model(X_transformed, y)

        return model

    def analyze_feature_importance(self) -> pd.DataFrame:
        """
        Extract and analyze feature importance.
        """
        if self.best_model is None:
            raise ValueError("No trained model available")

        importance = self.best_model.feature_importance_
        if importance is None:
            return pd.DataFrame()

        # Group by factor category
        categories = {
            'value': [],
            'quality': [],
            'growth': [],
            'momentum': [],
            'volatility': [],
            'sentiment': [],
            'interaction': [],
            'other': []
        }

        for feature in importance.index:
            assigned = False
            for cat in ['value', 'quality', 'growth', 'momentum', 'vol', 'sentiment']:
                if feature.startswith(cat) or cat in feature.lower():
                    cat_key = 'volatility' if cat == 'vol' else cat
                    categories[cat_key].append(feature)
                    assigned = True
                    break

            if '_x_' in feature:
                categories['interaction'].append(feature)
                assigned = True

            if not assigned:
                categories['other'].append(feature)

        # Calculate category importance
        category_importance = {}
        for cat, features in categories.items():
            if features:
                cat_importance = importance[features].sum()
                category_importance[cat] = cat_importance

        return pd.DataFrame({
            'individual': importance.head(20),
            'category': pd.Series(category_importance)
        })
