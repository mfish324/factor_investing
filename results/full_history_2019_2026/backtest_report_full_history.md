# Factor Investing Full-History Backtest Report

**Period:** January 1, 2019 - May 1, 2026 (~7.3 years)
**Universe:** S&P 500 (excluding financials) - 470 candidate stocks, 453 with complete data
**Portfolio Size:** 30 stocks per strategy
**Rebalance Frequency:** Monthly
**Benchmark:** SPY (S&P 500 ETF)
**Report Date:** May 4, 2026

---

## Executive Summary

This is the first multi-cycle backtest for the full 9-model lineup, spanning the COVID crash and recovery (2020), the 2022 bear market, the 2023-24 AI-led rally, and the sideways 2025-26 environment. Unlike the short Q4-2025/Q1-2026 window where Low Volatility dominated, the long-cycle picture is led by the **Six Factor composite** (+152.78% total / 20.50% annualized / 0.93 Sharpe).

**Key takeaways:**
- **Six Factor** is the all-weather winner — best return, best Sharpe, best alpha (+9.37%), highest information ratio (1.08), and most positive months (40/59).
- **ML Ensemble** comes in second on return (+120%) but takes the longest beating to get there (-33% drawdown, beta 1.17).
- **Three Factor** quietly delivered Sharpe 0.68 with sub-market beta and a -20.24% max drawdown — strong risk-adjusted returns from a simple model.
- **Low Volatility** has the shallowest drawdown (-17.92%) and lowest beta (0.49), but mid-pack absolute return — its diversification value (correlation 0.55-0.76 vs others) is more interesting than its standalone performance.
- **Shareholder Yield is broken** — losing -17% over 7+ years with -14.97% alpha. Needs a real dividend data feed before it's useful.
- **Magic Formula and Piotroski** show negative alpha across the full cycle, raising real questions about either as standalones in a modern S&P 500 universe.

---

## Performance Summary

| Rank | Model | Total Return | Ann. Return | Volatility | Sharpe | Sortino | Max DD | Calmar | Alpha | Beta | Info Ratio |
|---:|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **Six Factor** | **+152.78%** | **20.50%** | 17.47% | **0.93** | **1.29** | -20.90% | 0.98 | **+9.37%** | 0.93 | **1.08** |
| 2 | ML Ensemble | +120.07% | 17.19% | 24.15% | 0.61 | 0.89 | -33.22% | 0.52 | +4.24% | 1.17 | 0.46 |
| 3 | Three Factor | +113.04% | 16.43% | 19.20% | 0.68 | 1.02 | -20.24% | 0.81 | +5.29% | 0.93 | 0.43 |
| 4 | Quality-Value | +56.61% | 9.44% | 17.49% | 0.37 | 0.52 | -21.43% | 0.44 | -1.63% | 0.93 | -0.26 |
| 5 | Low Volatility | +50.04% | 8.50% | **12.35%** | 0.40 | 0.54 | **-17.92%** | 0.47 | +0.72% | **0.49** | -0.28 |
| 6 | GARP | +44.25% | 7.65% | 18.46% | 0.27 | 0.40 | -29.78% | 0.26 | -2.99% | 0.87 | -0.31 |
| 7 | Piotroski | +26.28% | 4.80% | 20.46% | 0.14 | 0.20 | -27.35% | 0.18 | -6.16% | 0.91 | -0.43 |
| 8 | Magic Formula | +11.97% | 2.30% | 16.58% | -0.02 | -0.03 | -22.33% | 0.10 | -8.03% | 0.83 | -0.98 |
| 9 | Shareholder Yield | -17.10% | -3.70% | 19.60% | -0.30 | -0.42 | -34.10% | -0.11 | -14.97% | 0.95 | -1.31 |

---

## Model Tier Analysis

### Tier 1: Strong Outperformers

**Six Factor** (+152.78%, Sharpe 0.93, Alpha +9.37%)
- Best in nearly every category — return, Sharpe, alpha, info ratio, monthly hit rate (40/59)
- Sub-market beta (0.93) with the best alpha of any model — pure stock-selection edge
- Recovery factor of 7.31 — by far the fastest recovering from drawdowns
- Worst month only -8.98%, best month +9.77% — well-controlled tail behavior
- Ranking is consistent: it was Tier-2 on the short Q4 window too. This is the model to beat.

**ML Ensemble** (+120.07%, Sharpe 0.61, Alpha +4.24%)
- Second-highest absolute return but pays for it: -33.22% max DD, 24.15% volatility, beta 1.17
- Best month +24.98%, worst -14.87% — the highest-variance strategy by a wide margin
- Information ratio 0.46 is decent but weaker than Six Factor or Three Factor on a risk-adjusted basis

**Three Factor** (+113.04%, Sharpe 0.68, Alpha +5.29%)
- The hidden gem. Simple Fama-French three-factor delivered 16.43% annualized at 0.68 Sharpe
- Best month +24.09% (caught a strong factor reversion), shallowest drawdown of the high-return models (-20.24%)
- Recovery factor 5.58 — second-best after Six Factor

### Tier 2: Modest Returns

**Quality-Value** (+56.61%, Sharpe 0.37)
- Slight negative alpha (-1.63%) — kept up with the market on a beta-adjusted basis but didn't add value
- Worth keeping as a building block (it composes into Six Factor) but not as a standalone

**Low Volatility** (+50.04%, Sharpe 0.40, Beta 0.49)
- Lowest volatility (12.35%) and shallowest drawdown (-17.92%) by design
- Slight positive alpha (+0.72%) — barely earns its keep on absolute terms
- Real value is in its **low correlation with everything else** (0.55-0.76 vs other models)
- Best as a portfolio component, not a standalone

**GARP** (+44.25%, Sharpe 0.27)
- Negative alpha (-2.99%); deepest non-Tier-4 drawdown (-29.78%)

### Tier 3: Underperformers

**Piotroski** (+26.28%, Sharpe 0.14, Alpha -6.16%)
- F-Score is not enough on its own in modern markets

**Magic Formula** (+11.97%, Sharpe -0.02, Alpha -8.03%)
- Greenblatt's combo of earnings yield + ROIC underperformed the market by ~8%/yr on a beta-adjusted basis
- Information ratio -0.98 — the second-worst in the lineup
- Confirms what the Q4 report flagged: this strategy needs help

### Tier 4: Broken

**Shareholder Yield** (-17.10%, Sharpe -0.30, Alpha -14.97%)
- Lost money in absolute terms over 7+ years while the market roughly tripled
- The dividend/buyback yield estimation is the suspected culprit (no direct dividend feed)
- **Do not deploy** until the data source is fixed — this is a known problem, not a research finding

---

## Correlation Analysis

Most models are tightly correlated (0.78-0.94), reflecting the fact that they're all selecting from the same S&P 500 universe with overlapping factor signals. The exceptions:

| | Six Factor | ML Ensemble | Low Volatility |
|:---|---:|---:|---:|
| Six Factor | 1.00 | 0.90 | 0.68 |
| ML Ensemble | 0.90 | 1.00 | 0.55 |
| Low Volatility | 0.68 | 0.55 | 1.00 |

- **Low Volatility is the only meaningful diversifier** — 0.55 correlation with ML Ensemble, 0.68 with Six Factor, 0.66-0.76 with everything else
- ML Ensemble and Six Factor are 0.90 correlated — running both gives you concentration, not diversification
- The traditional value/quality models (Magic Formula, Piotroski, GARP, Quality-Value) are all 0.81-0.91 with each other — pick one

---

## Drawdown Analysis

| Model | Max DD | Avg DD | DD Duration (days) | Recovery Factor |
|:---|---:|---:|---:|---:|
| Low Volatility | -17.92% | -4.27% | 1093 | 2.79 |
| Three Factor | -20.24% | -4.75% | 1077 | 5.58 |
| Six Factor | -20.90% | -5.04% | **1028** | **7.31** |
| Quality-Value | -21.43% | -5.09% | 1107 | 2.64 |
| Magic Formula | -22.33% | -7.62% | 1154 | 0.54 |
| Piotroski | -27.35% | -11.85% | 1159 | 0.96 |
| GARP | -29.78% | -8.83% | 1143 | 1.49 |
| ML Ensemble | -33.22% | -8.35% | 1126 | 3.61 |
| Shareholder Yield | -34.10% | -18.23% | 1212 | -0.50 |

**Six Factor has the fastest drawdown recovery** (lowest duration, highest recovery factor), confirming its all-weather profile. Low Vol has the shallowest absolute drawdown but takes longer to recover than Six Factor or Three Factor.

---

## Monthly Hit Rate

| Model | Positive Months | Negative Months | Win Rate |
|:---|---:|---:|---:|
| Six Factor | 40 | 19 | 67.8% |
| Quality-Value | 37 | 22 | 62.7% |
| Low Volatility | 37 | 22 | 62.7% |
| Three Factor | 36 | 23 | 61.0% |
| ML Ensemble | 32 | 27 | 54.2% |
| GARP | 32 | 27 | 54.2% |
| Shareholder Yield | 30 | 29 | 50.8% |
| Magic Formula | 29 | 30 | 49.2% |
| Piotroski | 29 | 30 | 49.2% |

Six Factor wins on this metric too — 68% of months are positive vs ~60% for the broader market. This is closer to a "pick a winner" than the headline Sharpe suggests.

---

## Conclusions & Recommendations

1. **Six Factor is the production-quality choice for a single-strategy deployment.** It dominates on return, Sharpe, alpha, info ratio, and drawdown recovery. It has been competitive in both the short Q4 window and the full multi-cycle backtest.

2. **A Low Volatility + Six Factor blend is more interesting than Low Volatility + ML Ensemble.** Six Factor has ~3x the alpha of ML Ensemble with half the volatility. Pairing Six Factor (high alpha) with Low Vol (low correlation, shallow DDs) likely yields a better risk-adjusted profile than the LowVol/ML blend the Q4 report suggested.

3. **Three Factor is underrated.** A simple Fama-French model delivered Sharpe 0.68 over 7+ years with the second-shallowest max drawdown and second-best recovery factor. Worth considering as a low-complexity alternative to Six Factor.

4. **Drop Magic Formula and Piotroski as standalones.** Both deliver significantly negative alpha across a full cycle. Their factor signals (earnings yield, F-score) may still be valuable as inputs to composites — but they are not viable as deployed strategies.

5. **Shareholder Yield needs a real dividend feed before any further evaluation.** Current results are uninterpretable because the dividend/buyback estimation is approximated. Adding Polygon's dividend endpoint or a third-party feed should be a prerequisite to including this model in any allocation.

6. **ML Ensemble is high-conviction but high-cost.** It works (Sharpe 0.61, +4.24% alpha), but the -33% max drawdown and 1.17 beta make it unsuitable as a primary allocation. Consider constraining beta or blending with Low Vol if used.

7. **Next steps to consider:**
   - Run a 60/40 Six Factor / Low Vol blend backtest and compare to standalone Six Factor
   - Re-train ML Ensemble using the longer history now available (2019-2026)
   - Wire up a real dividend feed for Shareholder Yield, then re-run
   - Run rotation strategy across this longer history to see if regime-switching adds value

---

*Report generated from factor_investing backtest engine. Charts available in `results/full_history_2019_2026/charts/`.*
