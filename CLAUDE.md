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
- **BacktestEngine** does walk-forward simulation: on each rebalance date, restricts the universe to point-in-time S&P 500 members (when `membership_db` is wired), builds a `PointInTimeView` of prices and financials so the model only sees data dated `<= rebalance_date`, calls `model.select_portfolio()`, then tracks daily P&L. Market caps are recomputed at each rebalance via the splits-aware path (`_market_caps_with_splits`: per-filing implied shares `NI/EPS_diluted` × cumulative split factor since the filing × asof price), falling back to constant-shares (`shares_outstanding × price[as_of_date]`) when a ticker lacks usable EPS data. Validated in the 2026-07-18/07-23 cross-check work — see [[splits-marketcap-validation]] and [[epoch-date-cache-lookahead]].
- **PointInTimeView** (`backtesting/point_in_time.py`) is the architectural look-ahead guard. Models receive a read-only dict-like view that physically drops rows after `as_of`. The bug class behind the May 2026 look-ahead incident cannot recur. Locked in by `tests/test_point_in_time.py`. A second, subtler variant of the same bug class — cached financials never actually getting truncated because of an epoch-int datetime misparse — was found and fixed 2026-07-18/23; see "Look-ahead bias history" below and `tests/test_epoch_dates.py`.
- **PIT S&P 500 membership** (`data/sp500_membership.py`) — sourced from Wikipedia, replayed backward from today's snapshot to answer `members_on(date)`. 112 tickers were members on 2019-01-01 but are not today (AAL, BBWI, FRC, GPS, HBI, SIVB, TWTR, etc.) — without this, the backtest never has to face the value traps real factor ETFs paid for. Build with `python main.py shadow build-membership`.
- **ML pipeline** uses `FeatureEngineer` to build feature matrix from all factor categories, trains XGBoost with Optuna, saves to joblib. The fitted scaler/imputer are serialized with the model. Training builds **one cross-sectional snapshot** (features as of the window end, labeled with each ticker's forward return over the trailing `holding_period` days) and fits a single static ranker on it — it is not a walk-forward panel, so the training window's end date must fall *before* any backtest window the model will be evaluated on, or the one labeled snapshot leaks real future returns. Our Polygon plan's ~5-year rolling price history means there's no historical era free of overlap with the full 2021-08–2026-07 backtest window, so `models/saved/ml_ensemble.joblib` (retrained 2026-07-23 via `scripts/train_ml_oos.py`, redone same day after the NaN-default fix below since `FeatureEngineer` uses the same calculators) is trained on 2021-08-01–2023-06-30 only and must be evaluated only on 2023-07-01 onward — see `results/ml_ensemble_oos_2023-07_2026-07/` for its honest numbers (31.97% annualized, Sharpe 1.13, alpha +11.82%, vs SPY's 18.60%/0.96 over the same window). Because of this shorter, disjoint window, ml_ensemble is **deliberately excluded** from `results/comprehensive_2026-07-18/` and `scripts/etf_cross_check.py`'s uniform comparison (both cover the other 8 models only, full 2021-08–2026-07 window) — do not re-add it there by running it on the full window with the OOS-trained model, since that would reintroduce partial in-sample contamination on the front half.
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

### Survivorship, shares, and the epoch-date cache bug (May–July 2026)

After the look-ahead fix, an ETF cross-check (`scripts/etf_cross_check.py`) showed our `shareholder_yield` model at +26.55% annualized while the real Cambria SYLD ETF returned 3.83% over the same window — a +22.7pt gap that screamed methodology bias. Two further fixes landed:

1. **PIT S&P 500 membership** (commit `e2ee5ed`): universe expanded from ~470 (today's list) to ~604 (union of historical members). Shareholder Yield dropped to ~+167% / 21.85% annualized; SYLD gap shrank to +17.2pts.

2. **Splits-aware market cap** (commit `c94bf71`): per-filing implied shares (`NI/EPS_diluted`) scaled by cumulative split factor since the filing date. Validated 2026-07-18 across all 9 models — did **not** move the shareholder_yield gap (still +17.6pt), which turned out to be the tell that the real bug was elsewhere.

3. **Epoch-date cache bug** (found/fixed 2026-07-18 evening, committed `0726004`/`7bad526` on 2026-07-23 after a mid-session interruption): `cache.get_financials` decoded epoch-second `filing_date` ints as nanoseconds → ~1970 dates, so `PointInTimeView`'s truncation mask was always `True` and cached financials were **never actually truncated** — every cache-fed backtest (i.e. nearly all of them) leaked years of future filings into every rebalance. This was the real driver: after the fix, shareholder_yield's gap vs SYLD collapsed from +17.6pt to **+0.4pt**. See [[epoch-date-cache-lookahead]] for the full timeline, including a red-herring cross-process "non-determinism" scare that turned out to just be the code still being edited between reruns.

A fourth, distinct bug (also 2026-07-23, commit `704fd0f`) was found while investigating why several of these gaps looked off: `row.get(field, 0) or 0` and `row.get(a) or row.get(b)` both silently fail to catch a field that is *present but NaN* (common in Polygon's financials — Python's `or` treats NaN as truthy, so `nan or 0` returns `nan`, not `0`). `magic_formula`'s simple two-factor formula (EY + ROIC, no fallback to other metrics) had zero cushion against this and was silently running 12-14 stock portfolios instead of the requested 30 at every rebalance. Fixed via `BaseFactor.field_or_default`/`field_or_fallback` (`factors/base.py`), applied in `factors/quality.py`, `factors/value.py`, `factors/sentiment.py`, `models/shareholder_yield.py`.

Current cross-check state (`results/comprehensive_2026-07-18/etf_cross_check/`, regenerated 2026-07-23 post-NaN-fix, 8 non-ML models only — see ML pipeline note above for why ml_ensemble is excluded): shareholder_yield +1.0pt (SYLD), six_factor +2.0pt (MTUM), low_volatility -0.1/+0.9pt (USMV/SPLV) — all plausible. quality_value -4.5/-6.0pt (QUAL/SPHQ), three_factor -4.0/-7.5pt (IUSV/VLUE), piotroski -6.1pt (SPHQ), magic_formula -7.1pt (SPY) run *behind* their ETF analogs — a new and much less alarming direction than the pre-fix inflation (concentrated 30-stock bets vs. diversified ETFs, no dividend reinvestment).

**quality_value/three_factor negative-gap investigation (2026-07-23, closed, no bug found):** checked portfolio diversification (clean 30/30 every rebalance), filing staleness (median ~6mo, expected for annual-only financials), and transaction costs (already modeled, 10bps/trade). Quantified ROIC's post-NaN-fix impact directly: with ROIC neutralized (simulating its pre-fix near-total-NaN state) vs. active at its real weight (1.2, the highest in the quality composite), only 24/30 quality_value picks overlap — confirms ROIC's fix is a real, partial driver of the composite's changed behavior, not a symptom of a residual bug. Sector-concentration couldn't be checked cleanly (`data/universe.py`'s `SECTOR_MAP` is sparse — mostly "Unknown" for held tickers). No further action planned; a proper sector classification would be the next step if this is revisited.

## Environment Variables

- `POLYGON_API_KEY` - Required for all data operations
- `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` - Required for paper trading only

## Available Models

`magic_formula`, `piotroski`, `garp`, `quality_value`, `three_factor`, `six_factor`, `low_volatility`, `shareholder_yield`, `ml_ensemble`

## User Preferences

- Do NOT use Docker. Prefer native/local installations.
