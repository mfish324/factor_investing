# Meta-Strategy Rotation Analysis Report

**Date:** January 22, 2026
**Analysis Period:** January 2010 - January 2026 (16 years)
**Rebalance Frequency:** Weekly

---

## Executive Summary

This report evaluates a meta-strategy rotation system that applies technical analysis to factor strategy equity curves to dynamically allocate capital between strategies. The goal was to determine whether TA-based rotation could outperform simpler approaches like equal-weight allocation or buy-and-hold of the best single strategy.

**Key Finding:** The rotation system underperformed both equal-weight allocation and the best single strategy. Simple diversification proved more effective than active rotation based on technical signals.

---

## Methodology

### Factor Strategies Evaluated

| Strategy | Description |
|----------|-------------|
| Magic Formula | Joel Greenblatt's earnings yield + return on capital |
| Piotroski F-Score | Financial strength scoring (0-9) |
| GARP | Growth at a Reasonable Price |
| Quality-Value | Quality metrics combined with value |
| Three-Factor | Fama-French size, value, momentum |
| Six-Factor | Extended multi-factor model |

### Technical Indicators Applied to Equity Curves

| Indicator | Parameters | Signal Logic |
|-----------|------------|--------------|
| MACD | 12/26/9 | Bullish when MACD > Signal line |
| RSI | 14-day | Bullish in 30-70 range, caution at extremes |
| SMA Crossover | 20/50-day | Bullish when fast > slow |
| EMA Crossover | 12/26-day | Bullish when fast > slow |

Indicators are combined into a **composite signal** ranging from -1 (bearish) to +1 (bullish).

### Allocation Methods Tested

| Method | Description |
|--------|-------------|
| Binary | 100% allocation to highest-signal strategy |
| Weighted | Proportional allocation based on signal strength |
| Momentum | Combines TA signals with recent performance |
| Top-N | Equal weight top 2 strategies by signal |

---

## Individual Strategy Performance

### Backtest Results (Jan 2010 - Jan 2026)

| Strategy | Final Value | Total Return | Ann. Return | Volatility | Sharpe | Max DD |
|----------|-------------|--------------|-------------|------------|--------|--------|
| Magic Formula | $653,986 | 401.66% | 38.28% | 162.16% | 0.44 | - |
| Three-Factor | $260,949 | 129.40% | 18.16% | 26.70% | 0.59 | - |
| Six-Factor | $256,775 | 113.37% | 16.45% | 17.23% | **0.74** | - |
| GARP | $246,553 | 113.13% | 16.42% | 26.52% | 0.54 | - |
| Quality-Value | $210,286 | 84.76% | 13.13% | 26.09% | 0.43 | - |
| Piotroski | $115,247 | -4.08% | -0.83% | 18.62% | -0.17 | - |

*Starting capital: $100,000*

### Observations

- **Magic Formula** delivered exceptional absolute returns (401%) but with high volatility
- **Six-Factor** achieved the best risk-adjusted returns (Sharpe 0.74) with lowest volatility
- **Piotroski** was the only strategy with negative returns over this period
- Wide dispersion in outcomes suggests potential value in rotation if signals were predictive

---

## Rotation Strategy Results

### Performance Comparison

| Method | Total Return | Ann. Return | Volatility | Sharpe | Max DD | Switches |
|--------|--------------|-------------|------------|--------|--------|----------|
| Equal Weight | 171.19% | 22.20% | 32.98% | **0.62** | - | 0 |
| Weighted Rotation | 111.27% | 17.21% | 28.86% | 0.53 | -20.22% | 225 |
| Momentum Rotation | 63.37% | 10.98% | 18.80% | 0.43 | -19.59% | 226 |
| Binary Rotation | 44.81% | 8.18% | 26.55% | 0.26 | -24.56% | 124 |
| Top-N Rotation | 27.99% | 5.38% | 19.69% | 0.16 | -21.69% | 167 |

### Alpha vs Benchmarks

| Rotation Method | vs Equal Weight | vs Best Strategy |
|-----------------|-----------------|------------------|
| Weighted | -59.92% | -290.39% |
| Momentum | -107.82% | -338.29% |
| Binary | -126.38% | -356.86% |
| Top-N | -143.19% | -373.67% |

**All rotation methods underperformed both benchmarks.**

---

## Current Signal Analysis

### Latest TA Readings (as of Jan 21, 2026)

| Strategy | Composite Signal | MACD | RSI | SMA Trend | EMA Trend |
|----------|------------------|------|-----|-----------|-----------|
| Six-Factor | **0.70** | +1 | 73.2 | +1 | +1 |
| GARP | 0.50 | -1 | 51.8 | +1 | +1 |
| Magic Formula | 0.50 | -1 | 54.2 | +1 | +1 |
| Piotroski | 0.50 | -1 | 55.1 | +1 | +1 |
| Quality-Value | 0.50 | -1 | 47.7 | +1 | +1 |
| Three-Factor | 0.50 | -1 | 55.8 | +1 | +1 |

### Current Recommended Allocation (Weighted Method)

| Strategy | Allocation |
|----------|------------|
| Six-Factor | 18.5% |
| GARP | 16.3% |
| Magic Formula | 16.3% |
| Piotroski | 16.3% |
| Quality-Value | 16.3% |
| Three-Factor | 16.3% |

---

## Analysis of Underperformance

### Why Rotation Failed to Add Value

1. **Dominant Single Strategy**
   - Magic Formula's 401% return was difficult to capture
   - Rotation system frequently underweighted it when signals weakened temporarily
   - Missing even a few big up-moves significantly impacted returns

2. **Signal Homogeneity**
   - Most strategies showed similar TA patterns (all at 0.50 signal)
   - Lack of differentiation made meaningful rotation difficult
   - Strategies are correlated since they trade the same universe

3. **Transaction Costs**
   - 124-226 switches over the period
   - Each switch incurred 10 bps cost
   - Cumulative friction eroded returns

4. **Lagging Indicators**
   - TA signals are inherently backward-looking
   - By the time MACD/RSI signaled a trend, much of the move had occurred
   - Factor strategies may not exhibit the trending behavior TA is designed to capture

5. **Regime Changes**
   - Factor performance varies by market regime
   - TA on equity curves may not capture fundamental regime shifts
   - Value factors (Magic Formula) had strong performance that wasn't predictable from price patterns

---

## Conclusions

### Key Takeaways

1. **Simple diversification won** - Equal-weight allocation across all 6 strategies delivered the best risk-adjusted returns (Sharpe 0.62)

2. **TA signals lacked predictive power** - Technical analysis on strategy equity curves did not provide actionable information for rotation

3. **Best single strategy dominated** - Buy-and-hold Magic Formula returned 401%, but with high volatility and concentration risk

4. **Rotation added friction without benefit** - Transaction costs from switching reduced returns without corresponding gains

### Recommendations

1. **For conservative investors:** Use equal-weight allocation across strategies for diversification benefits

2. **For aggressive investors:** Consider concentrated allocation to Magic Formula or Six-Factor based on risk tolerance

3. **For rotation refinement:** Consider:
   - Fundamental regime indicators instead of TA
   - Longer holding periods (monthly vs weekly rebalance)
   - Higher signal thresholds before switching
   - Factor momentum based on 6-12 month performance rather than TA

---

## Appendix: Data Sources and Parameters

### Backtest Configuration
- **Universe:** S&P 500 (excluding financials)
- **Portfolio Size:** 30 stocks per strategy
- **Rebalance:** Monthly for underlying strategies
- **Transaction Cost:** 10 bps per switch
- **Data Source:** Polygon.io

### Rotation Parameters
- **Lookback:** 63 days for momentum calculation
- **Min Holding:** 5 days
- **MACD:** 12/26/9
- **RSI:** 14-day
- **SMA:** 20/50-day
- **EMA:** 12/26-day

---

*Report generated by Factor Investing Analysis System*
