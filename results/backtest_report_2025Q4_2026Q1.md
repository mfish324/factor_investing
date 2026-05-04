# Factor Investing Backtest Report

**Period:** October 31, 2025 - March 12, 2026
**Universe:** S&P 500 (excluding financials) - 470 stocks
**Portfolio Size:** 30 stocks per strategy
**Rebalance Frequency:** Monthly
**Benchmark:** SPY (S&P 500 ETF)
**Report Date:** March 17, 2026

---

## Executive Summary

This report evaluates 9 factor-based stock selection models over a challenging ~4.5 month period characterized by sideways-to-down market conditions. Two new defensive models (Low Volatility and Shareholder Yield) and an ML Ensemble model were introduced alongside the existing 6 factor strategies.

**Key Finding:** The **Low Volatility** model was the standout performer, delivering +9.50% with a 2.82 Sharpe ratio and only -3.19% max drawdown. It achieved this with a near-zero beta (0.08), demonstrating true market-independent returns. The **ML Ensemble** matched its return (+9.17%) but with significantly more risk.

---

## Performance Summary

| Rank | Model | Total Return | Ann. Return | Volatility | Sharpe | Sortino | Max Drawdown | Calmar | Alpha | Beta |
|---:|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **Low Volatility** | **+9.50%** | **29.31%** | **7.80%** | **2.82** | **5.36** | **-3.19%** | **9.19** | +25.85% | 0.08 |
| 2 | ML Ensemble | +9.17% | 28.21% | 25.09% | 0.96 | 1.30 | -10.24% | 2.75 | +34.72% | 1.65 |
| 3 | Six Factor | +1.66% | 4.76% | 10.34% | 0.11 | 0.19 | -3.77% | 1.26 | +5.10% | 0.68 |
| 4 | GARP | +1.33% | 3.80% | 13.28% | 0.05 | 0.09 | -6.87% | 0.55 | +3.91% | 0.65 |
| 5 | Piotroski | +0.79% | 2.25% | 14.04% | -0.06 | -0.10 | -6.26% | 0.36 | +3.22% | 0.78 |
| 6 | Quality-Value | +0.72% | 2.06% | 13.13% | -0.08 | -0.11 | -4.21% | 0.49 | +3.76% | 0.90 |
| 7 | Three Factor | +0.02% | 0.06% | 12.76% | -0.25 | -0.38 | -5.14% | 0.01 | +1.67% | 0.88 |
| 8 | Magic Formula | -1.73% | -4.83% | 14.32% | -0.55 | -0.70 | -8.57% | -0.56 | -3.20% | 0.88 |
| 9 | Shareholder Yield | -3.94% | -10.76% | 15.32% | -0.93 | -1.42 | -6.05% | -1.78 | -10.40% | 0.69 |

---

## Model Tier Analysis

### Tier 1: Strong Outperformers

**Low Volatility** (+9.50%, Sharpe 2.82)
- Best risk-adjusted returns by a wide margin
- Lowest volatility (7.80%) and shallowest drawdown (-3.19%)
- Near-zero beta (0.08) = effectively market-neutral performance
- Combines low-volatility stock selection with a quality filter (65/35 weighting)
- Recovery factor of 2.98 (highest among all models)

**ML Ensemble** (+9.17%, Sharpe 0.96)
- Comparable total return to Low Volatility, but with 3x the volatility
- Highest alpha (+34.72%) but also highest beta (1.65) -- amplifying market moves
- Highest win rate (53.93%) on daily returns
- Feature importance dominated by momentum and volatility signals
- Max drawdown of -10.24% is the worst of all models

### Tier 2: Modest Positive Returns

**Six Factor** (+1.66%, Sharpe 0.11)
- Best of the traditional multi-factor models
- Moderate volatility (10.34%) and controlled drawdown (-3.77%)
- Positive alpha (+5.10%) with sub-market beta (0.68)

**GARP** (+1.33%, Sharpe 0.05)
- Growth-at-reasonable-price approach held up reasonably
- Positive alpha (+3.91%) with lowest beta among traditional models (0.65)

### Tier 3: Near-Flat

**Piotroski** (+0.79%), **Quality-Value** (+0.72%), **Three Factor** (+0.02%)
- All essentially flat over the period
- Quality-Value had the best drawdown control (-4.21%) in this tier
- Three Factor showed no differentiation from the market

### Tier 4: Underperformers

**Magic Formula** (-1.73%)
- Classic Greenblatt approach struggled; high beta (0.88) with no compensating return
- Deepest drawdown among traditional models (-8.57%)

**Shareholder Yield** (-3.94%)
- Worst performer overall
- Dividend/buyback yield estimation limited by available data (no direct dividend feed)
- Results may improve with a dedicated dividend data source

---

## Correlation Analysis

Return correlations reveal important diversification insights:

| | Low Vol | ML Ensemble | Six Factor |
|:---|---:|---:|---:|
| Low Volatility | 1.00 | 0.17 | 0.40 |
| ML Ensemble | 0.17 | 1.00 | 0.76 |
| Six Factor | 0.40 | 0.76 | 1.00 |

- **Low Volatility is highly uncorrelated** with all other models (0.17-0.51), making it an excellent diversifier
- ML Ensemble correlates moderately with traditional factor models (0.59-0.80)
- Traditional models are highly correlated with each other (0.59-0.96), offering limited diversification benefit
- Quality-Value and Three Factor are 0.92 correlated; Quality-Value and Six Factor are 0.91

---

## Drawdown Analysis

| Model | Max Drawdown | Avg Drawdown | Drawdown Duration (days) | Recovery Factor |
|:---|---:|---:|---:|---:|
| Low Volatility | -3.19% | -0.83% | 53 | 2.98 |
| Six Factor | -3.77% | -0.96% | 74 | 0.44 |
| Quality-Value | -4.21% | -1.25% | 71 | 0.17 |
| Three Factor | -5.14% | -1.58% | 74 | 0.00 |
| Shareholder Yield | -6.05% | -2.60% | 81 | -0.65 |
| Piotroski | -6.26% | -2.44% | 73 | 0.13 |
| GARP | -6.87% | -2.24% | 74 | 0.19 |
| Magic Formula | -8.57% | -3.44% | 72 | -0.20 |
| ML Ensemble | -10.24% | -3.78% | 73 | 0.90 |

Low Volatility spent the fewest days in drawdown (53 vs 71-81 for others) and had the fastest recovery.

---

## Monthly Return Statistics

| Model | Best Month | Worst Month | Avg Month | Positive Months | Negative Months |
|:---|---:|---:|---:|---:|---:|
| Low Volatility | +5.88% | -3.19% | +1.58% | 3 | 2 |
| ML Ensemble | +6.80% | -1.44% | +1.52% | 2 | 3 |
| Six Factor | +1.77% | -3.11% | +0.29% | 4 | 1 |
| GARP | +3.69% | -3.51% | +0.25% | 2 | 3 |
| Piotroski | +3.65% | -2.05% | +0.15% | 2 | 3 |
| Quality-Value | +1.77% | -3.32% | +0.13% | 4 | 1 |
| Three Factor | +1.70% | -3.46% | +0.02% | 3 | 2 |
| Magic Formula | +2.28% | -4.14% | -0.27% | 2 | 3 |
| Shareholder Yield | +1.58% | -2.89% | -0.65% | 2 | 3 |

---

## ML Ensemble: Feature Importance

The ML model's top predictive features align with the defensive theme:

| Rank | Feature | Importance |
|---:|:---|---:|
| 1 | Distance from 52-week High | 28.0% |
| 2 | Moving Average Trend | 24.0% |
| 3 | Historical Volatility | 5.3% |
| 4 | 6-Month Momentum | 4.9% |
| 5 | Distance from 52-week Low | 3.7% |
| 6 | Downside Volatility | 3.0% |
| 7 | Revenue CAGR (3Y) | 2.8% |
| 8 | Relative Strength vs Market | 2.8% |
| 9 | 12-Month Momentum | 2.6% |
| 10 | Revenue Growth YoY | 2.6% |

Momentum and volatility features account for ~75% of model importance. Fundamental factors (value, quality, growth) contribute the remaining ~25%, with revenue growth being the most important fundamental signal.

---

## Conclusions & Recommendations

1. **Low Volatility is the clear winner** for defensive positioning. Its combination of strong absolute returns, minimal drawdowns, and near-zero market correlation makes it the ideal strategy for uncertain markets.

2. **ML Ensemble shows promise** but takes on excessive risk for similar returns. Consider constraining its beta exposure or blending it with Low Volatility for a better risk/return profile.

3. **A Low Volatility + ML Ensemble blend** could be compelling given their 0.17 correlation. A 70/30 (LowVol/ML) allocation would preserve most of the defensive characteristics while adding the ML model's alpha.

4. **Traditional factor models offered limited protection.** Most delivered near-zero returns with drawdowns of 4-9%. Only Six Factor showed modest positive performance among traditional approaches.

5. **Shareholder Yield needs better data.** The model's underperformance is likely driven by imprecise dividend/buyback estimation. Adding a dedicated dividend data feed (e.g., Polygon's dividend endpoint or a third-party source) would likely improve results.

6. **Consider running the full 2019-2026 backtest** with all 9 models to evaluate performance across both bull and bear markets before making allocation decisions.

---

*Report generated from factor_investing backtest engine. Charts available in results/charts/.*
