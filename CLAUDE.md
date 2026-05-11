# Factor Investing

A backtesting and paper trading system for factor-based stock selection strategies. Evaluates multiple factor models against S&P 500 universe and supports ML-based ensemble approaches.

## Tech Stack

**Language:** Python 3.13
**Data:** Polygon.io API (financials, prices, market caps, insider/institutional data)
**ML:** XGBoost, LightGBM, scikit-learn, Optuna (hyperparameter tuning)
**Trading:** Alpaca API (paper trading)
**Viz:** Plotly (interactive HTML charts), Streamlit (live dashboard)
**CLI:** Click
**Storage:** SQLite (`data/cache.db` for Polygon responses, `data/shadow.db` for tracker)

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
│   ├── point_in_time.py     # PointInTimeView: structural look-ahead protection
│   ├── export.py            # Strategy curve export (parquet/csv)
│   └── rotation_backtest.py # Rotation strategy backtester
├── analysis/
│   ├── comparison.py        # ModelComparison (correlations, drawdowns, stats)
│   ├── visualization.py     # Plotly chart generation
│   └── equity_ta.py         # TA signals on equity curves (MACD, RSI, SMA)
├── tracking/                # Phase 1: shadow tracker for parallel-strategy monitoring
│   ├── shadow_db.py         # SQLite store: equity, holdings, picks, meta
│   └── snapshot.py          # backfill_strategy() + update_strategy_daily()
├── dashboard/               # Phase 2: Streamlit dashboard
│   └── app.py               # Reads shadow.db, renders curves/regimes/picks/correlations
├── trading/                 # Alpaca paper trading integration
├── scripts/                 # One-off analysis scripts (margin, blends, determinism)
├── tests/                   # pytest unit tests (currently: PointInTimeView)
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

# Shadow tracker + dashboard
python main.py shadow init                  # one-time DB init
python main.py shadow build-membership      # fetch S&P 500 historical membership from Wikipedia
python main.py shadow backfill               # populate from BacktestEngine
python main.py shadow update                 # incremental daily refresh
python main.py shadow status                 # one-line summary per strategy
python main.py shadow dashboard              # launch Streamlit dashboard

# Reality checks
python scripts/etf_cross_check.py            # compare strategies vs real ETFs (SYLD, VLUE, etc.)
python scripts/determinism_test.py           # verify same-process reproducibility

# Tests
pytest tests/ -v
```

## Key Architecture

- **Factor calculators** (`factors/`) compute raw metrics per stock. Each has `calculate()` for single stock, `calculate_universe()` for batch, and a `*_composite_score()` method.
- **Models** (`models/`) implement `score()` returning a Series (higher = better). Base class provides `rank()` and `select_portfolio()`.
- **BacktestEngine** does walk-forward simulation: on each rebalance date, restricts the universe to point-in-time S&P 500 members (when `membership_db` is wired), builds a `PointInTimeView` of prices and financials so the model only sees data dated `<= rebalance_date`, calls `model.select_portfolio()`, then tracks daily P&L. Market caps are recomputed at each rebalance from `shares_outstanding × price[as_of_date]` (constant-shares approximation). A more accurate splits-aware path exists (`_market_caps_with_splits` using `NI/EPS_diluted × cumulative_split_factor × asof_price`) but is not yet validated — see `memory/project_splits_work.md` for the resume point.
- **PointInTimeView** (`backtesting/point_in_time.py`) is the architectural look-ahead guard. Models receive a read-only dict-like view that physically drops rows after `as_of`. The bug class behind the May 2026 look-ahead incident cannot recur. Locked in by `tests/test_point_in_time.py`.
- **PIT S&P 500 membership** (`data/sp500_membership.py`) — sourced from Wikipedia, replayed backward from today's snapshot to answer `members_on(date)`. 112 tickers were members on 2019-01-01 but are not today (AAL, BBWI, FRC, GPS, HBI, SIVB, TWTR, etc.) — without this, the backtest never has to face the value traps real factor ETFs paid for. Build with `python main.py shadow build-membership`.
- **ML pipeline** uses `FeatureEngineer` to build feature matrix from all factor categories, trains XGBoost with Optuna, saves to joblib. The fitted scaler/imputer are serialized with the model. **The current `models/saved/ml_ensemble.joblib` was trained pre-fix and underperforms on honest data — needs retraining.**
- **Shadow tracker** (`tracking/`) maintains a parallel SQLite DB (`data/shadow.db`) with daily equity curves, holdings, and picks for every strategy. Decoupled from the real Alpaca account: only one strategy (or a blend) actually executes; the rest are tracked for the dashboard and rotation engine.
- **Dashboard** (`dashboard/app.py`) is a Streamlit app that reads `shadow.db` and renders performance summary, cumulative return / drawdown charts, regime signals (20/50 SMA + RSI), correlation heatmap, and current picks.
- Data is cached in SQLite (`data/cache.db`) to avoid redundant API calls.

### Look-ahead bias history (May 2026)

The pre-`b68bd5a` engine passed the full prices dict (through the cache tip = today's intraday quote on market days) to `model.select_portfolio()` at every rebalance. Models using latest price (market cap, P/E, momentum) silently consumed future data, and results varied across runs at different times of day because Polygon's intraday quote changed.

The fix is in three layers:
1. `main.py load_data` truncates prices and benchmark to `<= end_date` at load.
2. `BacktestEngine.run` constructs `PointInTimeView` per rebalance for prices and financials; recomputes market caps from `shares × asof_price`.
3. `tests/test_point_in_time.py` locks the as-of guarantee architecturally.

Reports and shadow-DB data generated from commit `b68bd5a` onward are honest. Anything before that has bias on absolute returns; relative model rankings are still informative but not authoritative.

### Survivorship and shares (May 2026, ongoing)

After the look-ahead fix, an ETF cross-check (`scripts/etf_cross_check.py`) showed our `shareholder_yield` model at +26.55% annualized while the real Cambria SYLD ETF returned 3.83% over the same window — a +22.7pt gap that screamed methodology bias. Two further fixes landed:

1. **PIT S&P 500 membership** (commit `e2ee5ed`): universe expanded from ~470 (today's list) to ~604 (union of historical members). Shareholder Yield dropped to ~+167% / 21.85% annualized; SYLD gap shrank to +17.2pts.

2. **Splits-aware market cap** (commit `c94bf71` and later, **not yet validated**): per-filing implied shares (`NI/EPS_diluted`) scaled by cumulative split factor since the filing date. This corrects both the constant-shares buyback under-statement AND the split inconsistency that breaks naive implied-shares. Code is committed; backfill stalled on first try; needs re-run + ETF cross-check in next session.

Current trustworthy strategies (per cross-check vs real ETFs): low_volatility (~0pt gap), ml_ensemble (~0pt), quality_value (+2.3pts), magic_formula (matches real-world underperformance). Mildly inflated: three_factor, six_factor (+7pts each, partly real concentration premium). Still suspect: shareholder_yield (+17pts).

## Environment Variables

- `POLYGON_API_KEY` - Required for all data operations
- `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` - Required for paper trading only

## Available Models

`magic_formula`, `piotroski`, `garp`, `quality_value`, `three_factor`, `six_factor`, `low_volatility`, `shareholder_yield`, `ml_ensemble`

## User Preferences

- Do NOT use Docker. Prefer native/local installations.
