# Factor Investing Strategies

This document describes the six factor investing strategies implemented in this backtesting framework.

---

## 1. Magic Formula (Joel Greenblatt)

**Source:** "The Little Book That Beats the Market" by Joel Greenblatt

### Philosophy
The Magic Formula seeks to buy "good companies at bargain prices" by combining two fundamental metrics that identify quality businesses trading at attractive valuations.

### Factors Used
| Factor | Description | Why It Matters |
|--------|-------------|----------------|
| **Earnings Yield** | EBIT / Enterprise Value | Measures how cheap a stock is relative to its operating earnings. Higher = more undervalued. |
| **Return on Invested Capital (ROIC)** | EBIT / (Net Working Capital + Net Fixed Assets) | Measures how efficiently a company uses its capital to generate profits. Higher = better business quality. |

### Methodology
1. Rank all stocks by Earnings Yield (highest = rank 1)
2. Rank all stocks by ROIC (highest = rank 1)
3. Sum the two ranks for each stock
4. Select stocks with the **lowest combined rank**

### Strengths
- Simple, transparent methodology
- Backed by academic research and real-world performance
- Focuses on fundamental business quality + valuation

### Weaknesses
- Can concentrate in cyclical or distressed sectors
- ROIC calculation varies by data availability
- Doesn't account for growth or momentum

---

## 2. Piotroski F-Score

**Source:** Joseph Piotroski's 2000 paper "Value Investing: The Use of Historical Financial Statement Information"

### Philosophy
The F-Score identifies financially strong companies among cheap value stocks by analyzing 9 binary signals from financial statements. Originally designed to separate "winners" from "losers" within deep value stocks.

### The 9 F-Score Signals

**Profitability (4 points)**
| Signal | Criteria | Point |
|--------|----------|-------|
| ROA | Net Income > 0 | +1 |
| Operating Cash Flow | CFO > 0 | +1 |
| ROA Change | ROA improved vs prior year | +1 |
| Accruals | CFO > Net Income (quality of earnings) | +1 |

**Leverage & Liquidity (3 points)**
| Signal | Criteria | Point |
|--------|----------|-------|
| Leverage | Long-term debt ratio decreased | +1 |
| Liquidity | Current ratio improved | +1 |
| Dilution | No new shares issued | +1 |

**Operating Efficiency (2 points)**
| Signal | Criteria | Point |
|--------|----------|-------|
| Gross Margin | Gross margin improved | +1 |
| Asset Turnover | Asset turnover improved | +1 |

### Methodology
1. Calculate F-Score (0-9) for each stock
2. Filter for stocks with **low Price-to-Book** (bottom 33%)
3. Select stocks with F-Score >= 7 (strong financial health)

### Strengths
- Rigorous fundamental analysis
- Identifies improving businesses
- Works well in deep value universes

### Weaknesses
- Requires 2+ years of financial history
- Can be too restrictive (few stocks qualify)
- Pure fundamental focus ignores price momentum

---

## 3. GARP (Growth at Reasonable Price)

**Source:** Made famous by Peter Lynch at Fidelity Magellan Fund

### Philosophy
GARP seeks to find the "sweet spot" between growth and value - companies with strong growth prospects that aren't overpriced. Avoids both expensive growth stocks and cheap-but-dying value traps.

### Key Metric: PEG Ratio
```
PEG Ratio = P/E Ratio / Annual Earnings Growth Rate

Example:
- Stock A: P/E = 20, Growth = 25% → PEG = 0.8 (attractive)
- Stock B: P/E = 20, Growth = 10% → PEG = 2.0 (expensive)
```

### Methodology
1. Calculate PEG ratio for each stock
2. Filter for:
   - Positive earnings (P/E > 0)
   - Reasonable P/E (< 40x)
   - Minimum growth rate (> 5% annually)
3. Select stocks with **PEG < 1.0** (paying less for growth than the growth rate)

### Interpretation
| PEG Range | Interpretation |
|-----------|----------------|
| < 0.5 | Potentially very undervalued |
| 0.5 - 1.0 | Fairly valued to undervalued |
| 1.0 - 2.0 | Fairly valued to slightly expensive |
| > 2.0 | Potentially overvalued |

### Strengths
- Balances growth and value
- Intuitive and widely used
- Avoids expensive "story stocks"

### Weaknesses
- Relies on earnings growth estimates/history
- Doesn't work for negative earnings companies
- Single metric dependency

---

## 4. Quality-Value Composite

### Philosophy
Combines traditional value metrics with quality metrics to find cheap, high-quality businesses. The idea is that cheap stocks are only attractive if the underlying business is fundamentally sound.

### Quality Factors
| Factor | Description | Target |
|--------|-------------|--------|
| ROE | Return on Equity | Higher is better |
| ROIC | Return on Invested Capital | Higher is better |
| Gross Margin | Gross Profit / Revenue | Higher is better |
| Operating Margin | Operating Income / Revenue | Higher is better |
| Asset Turnover | Revenue / Total Assets | Higher is better |

### Value Factors
| Factor | Description | Target |
|--------|-------------|--------|
| P/E Ratio | Price / Earnings | Lower is better |
| P/B Ratio | Price / Book Value | Lower is better |
| EV/EBITDA | Enterprise Value / EBITDA | Lower is better |
| Earnings Yield | Earnings / Price | Higher is better |
| FCF Yield | Free Cash Flow / Price | Higher is better |

### Methodology
1. Calculate composite quality score (z-score normalized)
2. Calculate composite value score (z-score normalized)
3. Combine with equal weights (50% quality + 50% value)
4. Select stocks with highest combined score

### Strengths
- Balanced approach avoids value traps
- Quality screen filters out distressed companies
- Diversified factor exposure

### Weaknesses
- More complex to implement
- May miss pure growth opportunities
- Requires comprehensive financial data

---

## 5. Three-Factor Model

### Philosophy
Extends Quality-Value by adding a Growth dimension. This creates a more comprehensive stock selection model that captures three distinct return drivers.

### Factor Categories

**Value (33.3% weight)**
- P/E, P/B, EV/EBITDA, Earnings Yield, FCF Yield

**Quality (33.3% weight)**
- ROE, ROIC, Gross Margin, Operating Margin, F-Score

**Growth (33.3% weight)**
- Revenue Growth (YoY)
- Earnings Growth (YoY)
- Earnings Growth (3-year CAGR)

### Methodology
1. Calculate composite score for each factor category
2. Z-score normalize each composite
3. Combine with equal weights
4. Select stocks with highest combined score

### Strengths
- Well-diversified factor exposure
- Captures multiple return drivers
- Academic support for each factor

### Weaknesses
- Complexity increases
- Factors can conflict (value vs growth)
- Requires more data inputs

---

## 6. Six-Factor Model (Comprehensive)

### Philosophy
The most comprehensive model, incorporating all major documented factor premiums. Adds Momentum, Volatility (low-vol anomaly), and Sentiment to the three-factor base.

### All Six Factors

| Factor | Weight | Description |
|--------|--------|-------------|
| **Value** | 20% | Cheap stocks outperform expensive ones |
| **Quality** | 20% | Profitable, stable companies outperform |
| **Growth** | 20% | Growing companies command premium valuations |
| **Momentum** | 15% | Recent winners continue winning (12-1 month) |
| **Volatility** | 15% | Low-volatility stocks deliver better risk-adjusted returns |
| **Sentiment** | 10% | Insider buying and institutional flows signal conviction |

### Momentum Factors
| Metric | Calculation |
|--------|-------------|
| 12-1 Month Momentum | Price return over 12 months, excluding last month |
| Relative Strength | Stock return vs benchmark return |
| 6-Month Momentum | Medium-term price trend |

### Volatility Factors (Low-Vol Anomaly)
| Metric | Target |
|--------|--------|
| Historical Volatility | Lower is better |
| Beta | Lower is better (defensive) |
| Downside Volatility | Lower is better |

### Sentiment Factors
| Metric | Signal |
|--------|--------|
| Insider Buying | Net insider purchases (bullish) |
| Insider Buy/Sell Ratio | > 1 indicates net buying |
| Institutional Ownership Changes | Increasing = positive |

### Methodology
1. Calculate composite score for each of the six factors
2. Z-score normalize each composite
3. Apply factor weights (configurable)
4. Select stocks with highest combined score

### Strengths
- Most comprehensive approach
- Captures multiple documented anomalies
- Momentum + low-vol provides timing benefit
- Sentiment adds information edge

### Weaknesses
- Most complex implementation
- Requires extensive data (prices, fundamentals, insider data)
- Factors can occasionally conflict
- Higher turnover from momentum factor

---

## Backtest Results Comparison (2010-2024)

| Model | Total Return | Ann. Return | Sharpe | Max Drawdown | Alpha |
|-------|--------------|-------------|--------|--------------|-------|
| **six_factor** | 170.51% | 38.56% | **0.97** | -19.51% | 30.18% |
| magic_formula | 385.66% | 67.85% | 0.56 | -34.59% | 58.66% |
| three_factor | 80.82% | 21.42% | 0.65 | -15.21% | 13.48% |
| garp | 79.42% | 21.11% | 0.59 | -13.88% | 13.63% |
| quality_value | 70.52% | 19.11% | 0.54 | -20.17% | 10.82% |
| piotroski | -15.93% | -5.53% | -0.40 | -41.40% | -13.81% |

### Key Observations

1. **Best Risk-Adjusted Return**: Six-Factor model achieved the highest Sharpe ratio (0.97), indicating superior return per unit of risk.

2. **Highest Raw Return**: Magic Formula delivered the highest absolute return but with extreme volatility (219% annualized!), making it unsuitable for risk-averse investors.

3. **Most Stable**: GARP had the lowest maximum drawdown (-13.88%), providing the smoothest ride.

4. **Worst Performer**: Piotroski F-Score struggled in this period, likely due to its restrictive filtering criteria and concentration in deep value stocks that underperformed.

---

## Choosing a Strategy

| If You Prioritize... | Consider |
|---------------------|----------|
| Simplicity | Magic Formula or GARP |
| Risk-adjusted returns | Six-Factor |
| Low drawdowns | GARP or Three-Factor |
| Fundamental quality | Piotroski or Quality-Value |
| Comprehensive approach | Six-Factor |
| Growth exposure | GARP or Three-Factor |

---

## Implementation Notes

- **Rebalancing**: Quarterly rebalancing captures factor exposure without excessive turnover
- **Portfolio Size**: 30 stocks provides diversification while maintaining factor concentration
- **Universe**: S&P 500 (ex-financials) provides liquid, data-rich stocks
- **Transaction Costs**: Not included in backtests; real-world returns will be lower
