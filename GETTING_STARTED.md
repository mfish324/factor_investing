# Getting Started

This is a practical, "what do I run today" guide. For project structure and architecture see `CLAUDE.md`.

## 1. One-time setup

### Python and dependencies

```bash
# Project requires Python 3.13. Verify:
python --version

# Install dependencies into your active environment:
pip install -r requirements.txt
```

### API keys

Create a `.env` file in the project root (it's gitignored). Minimum keys:

```
POLYGON_API_KEY=your_polygon_key
ALPACA_API_KEY=PK_your_alpaca_paper_key
ALPACA_SECRET_KEY=your_alpaca_paper_secret
```

- **Polygon** is required for all data operations. Sign up at <https://polygon.io>; a paid tier (~$30/mo) is needed for the rate limits the code expects.
- **Alpaca** is only needed for paper trading. Sign up at <https://alpaca.markets> and use the paper trading dashboard to generate keys. `config.py` defaults `ALPACA_PAPER = True`, so paper mode is on unless flipped.

### Verify the connection

```bash
python main.py cache-stats        # confirms Polygon side
python main.py trade account      # confirms Alpaca side (skip if not paper-trading yet)
```

### One-time shadow-tracker bootstrap

The shadow tracker maintains a separate SQLite DB (`data/shadow.db`) with daily equity curves and holdings for all 9 strategies in parallel. The dashboard and the (future) rotation engine both read from it. Bootstrap it once:

```bash
python main.py shadow init
python main.py shadow backfill --start-date 2019-01-01
```

Backfill runs the BacktestEngine for each of the 9 strategies and dumps results into the DB. Takes ~30-45 minutes on a warm cache. After it finishes:

```bash
python main.py shadow status
```

Should print one line per strategy with last-equity and total return.

## 2. Daily workflow (during paper trading / monitoring)

### Refresh the shadow DB

Once a day, after market close:

```bash
python main.py shadow update
```

This re-runs the engine for the last ~60 days through today and appends new rows for any strategy whose latest data is older than today. Should take 2-3 minutes with a warm Polygon cache.

If you're scripting it (Task Scheduler / cron), wrap it in a small batch file and schedule it for a few minutes after market close (4:30 PM ET).

### Open the dashboard

```bash
python main.py shadow dashboard
```

Opens at <http://localhost:8501>. Sections:

- **Performance summary** — total return / annualized / Sharpe / max DD / final equity per strategy, re-anchored to the selected window.
- **Cumulative return** — multi-line plot of all strategies + optional SPY benchmark.
- **Drawdown** — same set, multi-line.
- **Regime signals** — per-strategy 20/50 SMA trend tag (bull / bear / neutral) and RSI on the equity curve. Green = bull, red = bear, gray = neutral.
- **Correlation heatmap** — daily-return correlations within the selected window. Look for low cross-correlations when picking blends.
- **Current picks** — expandable card per strategy showing the latest 30 picks plus added/dropped vs prior rebalance.

The Streamlit cache is 5 minutes. After running `shadow update`, click "Rerun" in the top-right menu to refresh, or wait.

## 3. Paper trading workflow

### See what the strategy would buy today

```bash
python main.py trade picks --model three_factor
# Or all models:
python main.py trade picks --all
```

### Dry-run a rebalance

```bash
python main.py trade rebalance --model three_factor --dry-run
```

Shows the trades it *would* execute without sending anything to Alpaca. Read the output carefully.

### Actually execute (paper)

```bash
python main.py trade rebalance --model three_factor
```

### Monitor

```bash
python main.py trade positions
python main.py trade status --model three_factor
python main.py trade account
```

## 4. Re-running backtests

If you want to refresh the underlying performance reports (after data changes or model tweaks):

```bash
mkdir results/$(date +%Y%m%d)
python main.py run --all --start-date 2019-01-01 --end-date 2026-05-01 --output results/$(date +%Y%m%d)
```

Outputs:
- `comparison_report.md` — performance + correlation + drawdown tables
- `charts/full_report.html` — interactive Plotly tearsheet
- `run.log` — full execution log

After this, you may also want to re-run `shadow backfill` if the dashboard should reflect the updated numbers.

## 5. Specialty analyses (one-off scripts)

These live under `scripts/` and are runnable as `python scripts/<name>.py`:

- **`scripts/margin_analysis.py`** — sweep leverage (1x-3x) and margin rate (0-10%) for the top strategies. Output: `results/.../margin/margin_analysis.md`.
- **`scripts/blend_six_factor_low_vol.py`** — daily-rebalanced blend backtests across multiple weight combinations.
- **`scripts/determinism_test.py`** — sanity check that results are bit-identical across same-process re-runs (useful when debugging cache or look-ahead issues).

## 6. Common gotchas

### "Polygon 404 errors during loading"

Some delisted tickers (PARA, PXD, FI, etc.) 404 on `/v3/reference/tickers/{symbol}`. The loader logs the error and skips them. Universe size drops from 470 to ~453. This is normal.

### Dashboard shows stale data

Streamlit caches data 5 minutes. After `shadow update`, click Rerun (top-right menu) or wait.

### "Sharpe didn't change after fix"

Some models (Piotroski, GARP, Low Volatility) were always close to honest because they don't lean on latest-price market caps. Magic Formula similarly. The big movers from the look-ahead fix were Shareholder Yield (-17% → +221%), Three Factor, Quality-Value, Six Factor, ML Ensemble.

### "ml_ensemble underperforms"

The current `models/saved/ml_ensemble.joblib` was trained on data with the look-ahead bug present. The model learned features that no longer work post-fix. **Retrain before relying on it:**

```bash
python main.py train-ml
```

This takes a long time (Optuna hyperparameter search). Use `--no-tune` to skip Optuna and use defaults.

### "Cache TTL on prices is 24h, slowing things down"

`config.py` defines `CACHE_EXPIRY_PRICES_HOURS = 24` and `CACHE_EXPIRY_FINANCIALS_DAYS = 7`. If you're iterating on something that doesn't need fresh prices, you can bump this temporarily (don't commit the change).

### "Two backtests run at different times produce different numbers"

Should not happen post-fix (commit `b68bd5a` onward). If it does, run `python scripts/determinism_test.py`. Three back-to-back same-process runs should be bit-identical. If they aren't, file a bug.

## 7. What the strategies actually look like (post look-ahead fix, 2019-01-01 → 2026-05-01)

Final equity from $100k start, sorted by return:

| Rank | Strategy | Total Return | Sharpe | Max DD |
|---:|:---|---:|---:|---:|
| 1 | Shareholder Yield | +221.82% | 0.83 | -18.41% |
| 2 | Three Factor | +174.78% | **0.95** | -19.75% |
| 3 | Six Factor | +146.68% | 0.89 | -19.99% |
| 4 | Piotroski | +122.09% | 0.70 | -26.29% |
| 5 | GARP | +121.00% | 0.73 | -25.49% |
| 6 | Quality-Value | +117.57% | 0.75 | -22.84% |
| 7 | ML Ensemble | +85.10% | 0.51 | -26.85% |
| 8 | Low Volatility | +37.89% | 0.27 | -17.64% |
| 9 | Magic Formula | +12.38% | 0.01 | -38.37% |

Detail in `results/full_history_2019_2026_v3/backtest_report_full_history_postfix.md` (note: that report is in `_v2/`; `_v3` re-ran with the structural PointInTimeView protection and produced identical numbers).

## 8. If you're going to start paper-trading

The recommended on-ramp:

1. **Pick one strategy first.** Three Factor has the best Sharpe; Shareholder Yield has the best return; Six Factor is a solid middle. Three Factor is the safest place to start.
2. **Dry-run weekly for 2-3 weeks.** Confirm picks are stable, not churning.
3. **Paper-trade for 2-3 months at 1x leverage.** Compare actual paper P&L vs backtest expectations on the same period.
4. **Don't add leverage until step 3 looks healthy.** The margin analysis showed 1.5x-2x at 5-7% rates is the sweet spot, but only after the unlevered version is performing as expected.
5. **Use the dashboard during this period** to watch all 9 strategies in parallel. If your one chosen strategy starts diverging from the cohort, that's a regime signal worth investigating.

## 9. What's next

Phase 3 (planned): rotation/allocation engine that consumes the regime signals from the dashboard and produces target weights across strategies. The executor diffs the target against current Alpaca positions and submits the minimum trades. Not started yet — the user is going to use the Phase 2 dashboard for a few days/weeks first to see what's missing before designing Phase 3.

## 10. Useful files to check when something is off

- `results/full_history_2019_2026/discrepancy_investigation.md` — root-cause writeup of the May 2026 look-ahead bug; useful template for investigating future divergences.
- `results/full_history_2019_2026_v2/backtest_report_full_history_postfix.md` — narrative report on the post-fix results.
- `tests/test_point_in_time.py` — the architectural guard. If you're worried about look-ahead, run pytest first.
- `data/shadow.db` — the live tracker. Inspect with sqlite3 / DBeaver / `python main.py shadow status`.
- `data/cache.db` — Polygon response cache. `python main.py cache-stats` summarizes; `python main.py clear-cache` nukes it (rebuilds on next run).
