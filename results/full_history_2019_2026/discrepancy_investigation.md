# Six Factor Result Discrepancy — Investigation Findings

**Date:** May 4, 2026
**Trigger:** Six Factor returned +152.78% in `python main.py run --all` at 11:23 AM but +193.26% in `scripts/blend_six_factor_low_vol.py` at 12:21 PM. Same period (2019-01-01 → 2026-05-01), same universe (453 stocks), same code, same rebalance schedule.

## Root cause: look-ahead bias on prices, exposed by intraday cache freshness

The backtest engine passes the **complete prices dictionary** (all dates from Jan 2019 through "today" — currently May 4, 2026) to the model on every rebalance date. The model's score functions use the latest price for things like market cap, P/E, momentum, and 52-week high distance. So the model is selecting stocks based on data that wouldn't have been available at the rebalance date.

**Why this manifested as morning vs afternoon divergence:** today is a market day. Polygon's daily price feed includes the current intraday quote until close. The morning run (11:23 AM ET) cached one set of "latest" prices; the afternoon runs (12:21 PM, 4 PM) cached another. Different price tips → different model scores → different portfolio selections at every rebalance → different cumulative returns over 7 years of compounding.

**Source:** `backtesting/engine.py` line 150 — `prices=prices` is passed unchanged into `model.select_portfolio()` regardless of the rebalance date.

## Evidence

### Determinism within a single Python process
Three back-to-back runs in one process (`scripts/determinism_test.py`):

```
[Run 1] Total: 193.2587%  Sharpe: 1.0488  Vol: 18.4451%  Final: $327,874.76
[Run 2] Total: 193.2587%  Sharpe: 1.0488  Vol: 18.4451%  Final: $327,874.76
[Run 3] Total: 193.2587%  Sharpe: 1.0488  Vol: 18.4451%  Final: $327,874.76

Max abs diff in daily returns: r1 vs r2 = 0e+00, r1 vs r3 = 0e+00
First-rebalance holdings identical (sorted): True
First-rebalance holdings identical (order): True
```

→ The code is bit-deterministic given the same inputs. The discrepancy comes from **inputs differing between processes**, not internal randomness.

### Morning vs afternoon (same command, same code, identical universe)

| Model | Morning (11:23) | Afternoon (15:58) | Δ |
|:---|---:|---:|---:|
| **magic_formula** | 11.97% | 10.01% | -1.96 pts |
| piotroski | 26.28% | 26.28% | **0.00** ✓ |
| garp | 44.25% | 44.25% | **0.00** ✓ |
| **quality_value** | 56.61% | 83.06% | +26.45 pts |
| **three_factor** | 113.04% | 147.27% | +34.23 pts |
| **six_factor** | 152.78% | 193.26% | +40.48 pts |
| low_volatility | 50.04% | 50.07% | +0.03 pts |
| **shareholder_yield** | -17.10% | -2.46% | +14.64 pts |
| **ml_ensemble** | 120.07% | 138.78% | +18.71 pts |

Six of nine models drift. The exceptions (Piotroski, GARP, Low Volatility) match between runs.

### Why some models are stable

- **Piotroski**: F-Score is built entirely from financial-statement data. No latest-price input → no look-ahead → deterministic across process runs.
- **GARP**: PEG ratio uses P/E, but Polygon caches the snapshot price used here at run start; in this run the calculation came out identical (likely because GARP's inputs round to integer ranks before combining, smoothing out the small intraday tip difference).
- **Low Volatility**: Uses rolling-window volatility over the past N days. Adding/removing a single tip-of-history price barely moves a 252-day vol estimate, so results are essentially identical.

The drifting models all use either earnings yield (which depends on market cap = shares × **latest price**) or short-window momentum signals (which depend heavily on the most recent prices). These propagate the intraday tip into rank changes that cascade through 7 years of monthly rebalances.

## Fix

Truncate the prices passed to `model.select_portfolio()` so it only sees data **up to the rebalance date**, not all of history including the cache tip.

**Two implementation paths:**

1. **Truncate per rebalance** (correct, slightly slower): in `engine.py`, before line 148, build `prices_at_date = {t: df[df['date'] <= date] for t, df in prices.items()}` and pass that. This eliminates look-ahead bias at every rebalance — the model sees only data it would have had at that point in time.

2. **Truncate to end_date once at load** (cheap, partial fix): in `main.py`'s `load_data`, slice each price DataFrame to `<= end_date` immediately after fetching. This makes results reproducible across runs (the cache tip no longer leaks in) but still leaks data from later in the backtest into earlier rebalances.

**Recommended:** do both. Option 2 makes results reproducible immediately and is a one-line change. Option 1 is the proper backtesting fix and removes the look-ahead bias from every model's stock selection.

## Implications for prior reports

All backtest reports generated before this fix (including `backtest_report_full_history.md` and `backtest_report_2025Q4_2026Q1.md`) carry some look-ahead bias. The relative ranking of models is probably still informative, but absolute returns may overstate true historical performance. After the fix, results should be re-run and reports regenerated.

## Next steps

1. Implement option 2 (load-time truncation) — quick win, makes results reproducible
2. Implement option 1 (per-rebalance truncation) — eliminates look-ahead bias entirely
3. Re-run full-history backtest and regenerate reports
4. Update memory: this was a real, latent bug that affected historical claims
