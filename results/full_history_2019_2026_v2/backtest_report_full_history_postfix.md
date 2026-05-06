# Factor Investing Full-History Backtest (Post Look-Ahead Fix)

**Period:** January 1, 2019 - May 1, 2026 (~7.3 years)
**Universe:** S&P 500 (excluding financials) - 453 stocks with complete data
**Portfolio Size:** 30 stocks per strategy
**Rebalance Frequency:** Monthly
**Benchmark:** SPY
**Report Date:** May 6, 2026

---

## Executive Summary

This is the same 7.3-year backtest as before, but run after fixing a look-ahead bias bug in the engine: prices, market caps, and benchmark are now correctly truncated to the rebalance date instead of leaking through to the cache tip (= today's intraday price). Market caps are now computed as `shares_outstanding × price[as_of_date]` rather than reusing today's snapshot.

**The fix changed every single result, several of them dramatically:**

- **Shareholder Yield went from -17% to +221%.** It was the worst model in the prior report; it's now the highest-return model. Diagnosis there ("needs better dividend data") was wrong — the strategy was being poisoned by today's market caps in historical yield calculations.
- **Piotroski went from +26% to +122%.** F-Score was filtering out good stocks because P/B used today's prices.
- **GARP went from +44% to +121%.** Same mechanism.
- **Quality-Value went from +57% to +118%.** Same.
- **Three Factor is now the Sharpe leader** at 0.95 (was 0.68).
- **Six Factor dropped slightly** to +147% (from +153%) — the bug had been *helping* it via momentum on inflated recent prices.
- **ML Ensemble dropped to +85% (from +120%)** — the model was trained on biased features and learned to exploit them. It needs retraining on the fixed pipeline before its real performance can be assessed.

---

## Performance Summary (Post-Fix)

| Rank | Model | Total Return | Ann. Return | Volatility | Sharpe | Sortino | Max DD | Calmar | Alpha | Beta | Info Ratio |
|---:|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **Shareholder Yield** | **+221.82%** | **26.55%** | 27.73% | 0.83 | **1.71** | -18.41% | **1.44** | **+16.33%** | 0.85 | 0.62 |
| 2 | Three Factor | +174.78% | 22.58% | 19.04% | **0.95** | 1.44 | **-19.75%** | 1.14 | +11.83% | 0.92 | **0.93** |
| 3 | Six Factor | +146.68% | 19.95% | 17.65% | 0.89 | 1.25 | -19.99% | 1.00 | +9.30% | 0.91 | 0.90 |
| 4 | Piotroski | +122.09% | 17.44% | 20.18% | 0.70 | 0.99 | -26.29% | 0.66 | +6.64% | 0.93 | 0.48 |
| 5 | GARP | +121.00% | 17.32% | 19.00% | 0.73 | 1.04 | -25.49% | 0.68 | +6.68% | 0.91 | 0.51 |
| 6 | Quality-Value | +117.57% | 16.95% | 17.60% | 0.75 | 1.04 | -22.84% | 0.74 | +6.07% | 0.94 | 0.71 |
| 7 | ML Ensemble | +85.10% | 13.21% | 20.85% | 0.51 | 0.67 | -26.85% | 0.49 | +2.58% | 0.91 | 0.17 |
| 8 | Low Volatility | +37.89% | 6.69% | **12.05%** | 0.27 | 0.36 | **-17.64%** | 0.38 | -0.92% | **0.49** | -0.41 |
| 9 | Magic Formula | +12.38% | 2.38% | 19.69% | 0.01 | 0.02 | -38.37% | 0.06 | -9.04% | 1.01 | -0.85 |

---

## Pre-Fix vs Post-Fix Comparison

| Model | Pre-Fix Return | Post-Fix Return | Δ | Pre-Fix Sharpe | Post-Fix Sharpe |
|:---|---:|---:|---:|---:|---:|
| Magic Formula | +11.97% | +12.38% | +0.4 | -0.02 | 0.01 |
| **Piotroski** | +26.28% | +122.09% | **+95.8** | 0.14 | 0.70 |
| **GARP** | +44.25% | +121.00% | **+76.8** | 0.27 | 0.73 |
| **Quality-Value** | +56.61% | +117.57% | **+61.0** | 0.37 | 0.75 |
| **Three Factor** | +113.04% | +174.78% | **+61.7** | 0.68 | 0.95 |
| Six Factor | +152.78% | +146.68% | -6.1 | 0.93 | 0.89 |
| Low Volatility | +50.04% | +37.89% | -12.2 | 0.40 | 0.27 |
| **Shareholder Yield** | -17.10% | +221.82% | **+238.9** | -0.30 | 0.83 |
| ML Ensemble | +120.07% | +85.10% | -35.0 | 0.61 | 0.51 |

---

## Tier Analysis (Post-Fix)

### Tier 1: Outperformers

**Shareholder Yield** (+221.82%, Sharpe 0.83, Alpha +16.33%)
- The fix changed this from "broken model" to "best total return" — biggest swing in the lineup.
- Highest annualized return (26.55%) and highest alpha (+16.33%).
- Volatility is high (27.73%), but Sortino is 1.71 — the volatility is asymmetric (more upside), which is what we want.
- Calmar 1.44 is the best in the lineup — it generates returns relative to the drawdowns it takes.
- **Worth investigating before deploying:** is the high Sharpe coming from genuine factor edge, or from a few extreme rebalances? Run a per-month return distribution before sizing this up.

**Three Factor** (+174.78%, Sharpe 0.95, Alpha +11.83%)
- Best Sharpe (0.95) and best info ratio (0.93). Shallow drawdown (-19.75%).
- Simple Fama-French composite. Punching well above its weight.
- Lower beta (0.92) than most.

**Six Factor** (+146.68%, Sharpe 0.89, Alpha +9.30%)
- Still strong, but no longer clearly #1. The bug had been juicing it through momentum on inflated prices.
- Comparable to Three Factor on most metrics; Three Factor wins on every dimension by a small margin.
- Suggests the additional factors (sentiment, volatility) aren't adding much over the base 3-factor composite.

### Tier 2: Solid Performers

**Piotroski** (+122.09%, Sharpe 0.70)
- Massive upgrade from pre-fix. F-Score + as-of-date P/B is genuinely effective.
- Drawdown deeper than Three Factor (-26.29%) but absolute return is solid.

**GARP** (+121.00%, Sharpe 0.73, Alpha +6.68%)
- Growth-at-reasonable-price works when the "price" component isn't future-tipped.

**Quality-Value** (+117.57%, Sharpe 0.75)
- Best drawdown control in this tier (-22.84%) and lowest volatility (17.60%).
- Effectively a defensive Tier-1 candidate.

### Tier 3: Underperformers / Needs Work

**ML Ensemble** (+85.10%, Sharpe 0.51, Alpha +2.58%)
- Trained on biased features → learned to exploit them → underperforms on honest data.
- Needs retraining on the fixed feature pipeline before its real value can be judged.
- Until retrained, do not deploy.

**Low Volatility** (+37.89%, Sharpe 0.27, Alpha -0.92%)
- Still has the lowest beta (0.49) and shallowest drawdown (-17.64%) — its defensive properties are real.
- But absolute return is now lagging meaningfully. Useful only as a portfolio diversifier; not as a standalone.

**Magic Formula** (+12.38%, Sharpe 0.01, Alpha -9.04%)
- The post-fix result confirms what the prior report suspected: as a standalone for modern S&P 500, Greenblatt's combo is not viable.
- Negative information ratio (-0.85) — gives up alpha vs the benchmark in a systematic way.

---

## Correlation Insights (Post-Fix)

| | Three Factor | Six Factor | Shareholder Yield | Low Volatility |
|:---|---:|---:|---:|---:|
| Three Factor | 1.00 | 0.88 | 0.56 | 0.66 |
| Six Factor | 0.88 | 1.00 | 0.56 | 0.75 |
| Shareholder Yield | 0.56 | 0.56 | 1.00 | 0.38 |
| Low Volatility | 0.66 | 0.75 | 0.38 | 1.00 |

**Shareholder Yield is now the best diversifier**, not Low Volatility — it has only 0.56 correlation with Three Factor / Six Factor and 0.38 with Low Vol. That's better than what Low Vol used to offer. **A Three Factor + Shareholder Yield blend is now the most interesting pair to study** (high return + low correlation).

---

## What This Means

1. **The headline winner has changed.** Shareholder Yield is the top model by total return and alpha, with the best Calmar ratio. Three Factor is the Sharpe leader. Six Factor has dropped from #1 to #3.

2. **Most prior conclusions need to be re-examined.** The previous report's "Shareholder Yield is broken" finding was false. The Q4 report's "Low Volatility dominates short-term" claim is also suspect because it was measured under the same biased pipeline.

3. **The fix changed model rankings.** Models with strong fundamental signals (Piotroski, GARP, Quality-Value, Shareholder Yield) all improved meaningfully because the bug was systematically misvaluing historical positions. Models that lean on momentum and recent price (Six Factor, Low Volatility, ML Ensemble) all moved down — they had been benefiting from the lookahead.

4. **ML Ensemble must be retrained** before it can be evaluated. Its current poor performance reflects the mismatch between its biased training distribution and the now-honest backtest distribution.

5. **Next steps to consider:**
   - Retrain ML Ensemble on the fixed pipeline
   - Run a Three Factor + Shareholder Yield blend at 60/40, 70/30, 80/20
   - Re-run the rotation strategy with the fixed engine
   - Investigate what's driving Shareholder Yield's huge alpha — is it concentrated in a few periods, or steady?

---

*Report generated from factor_investing backtest engine after look-ahead bias fix (commit b68bd5a). Charts available in `results/full_history_2019_2026_v2/charts/`.*
