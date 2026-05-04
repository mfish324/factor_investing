# Factor Investing

A backtesting and paper trading system for factor-based stock selection strategies. Evaluates multiple factor models against S&P 500 universe and supports ML-based ensemble approaches.

## Tech Stack

**Language:** Python 3.13
**Data:** Polygon.io API (financials, prices, market caps, insider/institutional data)
**ML:** XGBoost, LightGBM, scikit-learn, Optuna (hyperparameter tuning)
**Trading:** Alpaca API (paper trading)
**Viz:** Plotly (interactive HTML charts)
**CLI:** Click

## Project Structure

```
factor_investing/
├── main.py                  # CLI entry point (click commands)
├── config.py                # All configuration (API keys, dates, weights, etc.)
├── data/
│   ├── polygon_client.py    # Polygon API wrapper (financials, prices, market caps)
│   ├── cache.py             # SQLite cache for API responses
│   └── universe.py          # S&P 500 universe management
├── factors/
│   ├── base.py              # BaseFactor ABC (calculate, composite_score, zscore)
│   ├── value.py             # P/E, P/B, P/S, EV/EBITDA, earnings yield
│   ├── quality.py           # ROE, ROA, ROIC, margins, Piotroski F-Score
│   ├── growth.py            # Revenue/earnings CAGR, YoY growth
│   ├── momentum.py          # MomentumFactors + VolatilityFactors classes
│   └── sentiment.py         # Insider activity, institutional holdings
├── models/
│   ├── base.py              # FactorModel ABC (score, rank, select_portfolio)
│   ├── magic_formula.py     # Greenblatt earnings yield + ROIC
│   ├── piotroski.py         # Piotroski F-Score
│   ├── garp.py              # Growth at reasonable price
│   ├── quality_value.py     # Quality + value composite
│   ├── three_factor.py      # Fama-French three factor
│   ├── six_factor.py        # Six factor composite (value/quality/growth/momentum/sentiment/vol)
│   ├── low_volatility.py    # Low vol + quality filter (defensive)
│   ├── shareholder_yield.py # Dividend + buyback + debt paydown yield
│   ├── ml_ensemble.py       # XGBoost ranker trained on all factors
│   ├── rotation.py          # Strategy rotation meta-model
│   └── saved/               # Serialized ML models (.joblib)
├── ml/
│   ├── features.py          # FeatureEngineer (matrix creation, scaling, imputation)
│   ├── models.py            # ML model wrappers (XGBoostRanker, etc.)
│   └── training.py          # Training pipeline (CV, Optuna tuning)
├── backtesting/
│   ├── engine.py            # BacktestEngine (walk-forward simulation)
│   ├── metrics.py           # PerformanceMetrics, Sharpe, drawdown, alpha/beta
│   ├── export.py            # Strategy curve export (parquet/csv)
│   └── rotation_backtest.py # Rotation strategy backtester
├── analysis/
│   ├── comparison.py        # ModelComparison (correlations, drawdowns, stats)
│   ├── visualization.py     # Plotly chart generation
│   └── equity_ta.py         # TA signals on equity curves (MACD, RSI, SMA)
├── trading/                 # Alpaca paper trading integration
└── results/                 # Output reports, charts, exported curves
```

## Running

```bash
# Backtests
python main.py run --all                    # Run all 9 models
python main.py run --model low_volatility   # Run specific model
python main.py run --all --start-date 2019-01-01 --end-date 2026-03-12

# ML
python main.py train-ml                     # Train ML ensemble (needs long history)
python main.py train-ml --no-tune           # Skip Optuna tuning

# Other
python main.py list-models                  # List available models
python main.py current-picks --model six_factor
python main.py cache-stats
python main.py update-data

# Strategy rotation
python main.py rotation export-curves
python main.py rotation signals
python main.py rotation backtest

# Paper trading
python main.py trade status
python main.py trade picks --all
python main.py trade rebalance --model six_factor --dry-run
```

## Key Architecture

- **Factor calculators** (`factors/`) compute raw metrics per stock. Each has `calculate()` for single stock, `calculate_universe()` for batch, and a `*_composite_score()` method.
- **Models** (`models/`) implement `score()` returning a Series (higher = better). Base class provides `rank()` and `select_portfolio()`.
- **BacktestEngine** does walk-forward simulation: on each rebalance date, calls `model.select_portfolio()`, then tracks daily P&L.
- **ML pipeline** uses `FeatureEngineer` to build feature matrix from all factor categories, trains XGBoost with Optuna, saves to joblib. The fitted scaler/imputer are serialized with the model.
- Data is cached in SQLite (`data/cache.db`) to avoid redundant API calls.

## Environment Variables

- `POLYGON_API_KEY` - Required for all data operations
- `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` - Required for paper trading only

## Available Models

`magic_formula`, `piotroski`, `garp`, `quality_value`, `three_factor`, `six_factor`, `low_volatility`, `shareholder_yield`, `ml_ensemble`

## User Preferences

- Do NOT use Docker. Prefer native/local installations.
