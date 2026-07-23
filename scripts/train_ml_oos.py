"""
Retrain ml_ensemble with a training window that ends before the backtest
evaluation window, so the saved model is genuinely out-of-sample when
backtested/cross-checked.

Background: MLEnsembleModel.train() builds ONE cross-sectional snapshot
(features as of the window end, labeled with each ticker's forward return
over the trailing `holding_period` days) and fits a single static ranker on
it -- it is not a walk-forward panel. The previous joblib was trained with a
snapshot dated inside the 2021-08 to 2026-07-17 backtest window (a snapshot
around 2026-03-12, per config.BACKTEST_END_DATE), so its one labeled
snapshot leaked real forward returns from inside the test period.

Our Polygon plan only serves ~5 years of rolling daily price history, so
there is no separate historical era to train on without overlapping the only
backtest window we can construct. Split it instead: train on 2021-08-01 to
2023-06-30, then backtest/cross-check only 2023-07-01 onward (see
scripts/etf_cross_check.py's OOS carve-out for ml_ensemble).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

from data.universe import UniverseManager
from models.ml_ensemble import MLEnsembleModel
from ml.features import FeatureEngineer
from main import load_data, get_polygon_client

TRAIN_START = "2021-08-01"
TRAIN_END = "2023-06-30"


def main():
    polygon_client = get_polygon_client()
    universe = UniverseManager().get_universe('sp500', exclude_financials=True)

    financials, prices, market_caps, benchmark_prices, _, _, _ = load_data(
        polygon_client, universe, TRAIN_START, TRAIN_END
    )

    feature_engineer = FeatureEngineer()
    ml_model = MLEnsembleModel(feature_engineer=feature_engineer)
    ml_model.train(
        financials=financials,
        prices=prices,
        market_caps=market_caps,
        benchmark_prices=benchmark_prices,
        tune_hyperparams=True,
        n_trials=50,
    )
    ml_model.save()
    print(f"Saved ml_ensemble model trained on {TRAIN_START} -> {TRAIN_END}")

    importance = ml_model.get_feature_importance()
    if importance is not None and not importance.empty:
        print("\nTop 10 Most Important Features:")
        print(importance.head(10).to_string())


if __name__ == "__main__":
    main()
