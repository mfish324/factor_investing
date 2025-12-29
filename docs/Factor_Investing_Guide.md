# A Beginner's Guide to Factor Investing
### Strategies for Smarter Stock Selection

*Last Updated: December 2025*

---

## What is Factor Investing?

Factor investing is an investment approach that targets specific characteristics (or "factors") that have historically been associated with higher returns. Instead of picking individual stocks based on hunches or tips, factor investing uses data-driven rules to systematically select stocks.

Think of it like this: if you were buying a used car, you might look for specific factors like low mileage, recent maintenance, and a reliable brand. Factor investing applies similar logic to stocks - looking for measurable characteristics that indicate a good investment.

---

## The Six Strategies We Tested

We backtested six different factor-based strategies using data from 2010 to 2025. Here's what each one does and how it performed.

---

## 1. Magic Formula

**Created by:** Joel Greenblatt (from his book "The Little Book That Beats the Market")

**The Big Idea:** Find good companies at bargain prices.

**How it Works:**
The Magic Formula looks at just two things:
1. **Earnings Yield** - How much profit you get for each dollar invested (higher = cheaper stock)
2. **Return on Capital** - How efficiently the company uses its money to make profits (higher = better business)

Stocks are ranked on both measures, and the ones with the best combined score make the cut.

**In Plain English:** It's like finding a well-run restaurant that's somehow underpriced compared to its competitors.

| Pros | Cons |
|------|------|
| Simple to understand | Can pick stocks that are "cheap for a reason" |
| Only needs basic financial data | Ignores whether the stock price is trending up or down |
| Famous track record | Can concentrate in troubled industries |

---

## 2. Piotroski F-Score

**Created by:** Professor Joseph Piotroski (Stanford)

**The Big Idea:** Among cheap stocks, find the ones with improving financials.

**How it Works:**
Each stock gets a score from 0-9 based on nine yes/no questions about its finances:

| Category | What It Checks |
|----------|----------------|
| **Profitability** | Is the company profitable? Is cash flow positive? Are profits improving? |
| **Financial Health** | Is debt decreasing? Can it pay its bills? Is it avoiding diluting shareholders? |
| **Efficiency** | Are profit margins improving? Is it using assets more efficiently? |

Stocks scoring 7-9 (out of 9) are considered strong buys, but only if they're also cheap (low price-to-book ratio).

**In Plain English:** It's like checking a company's financial health report card before buying.

| Pros | Cons |
|------|------|
| Rigorous financial analysis | Very restrictive - few stocks qualify |
| Identifies improving businesses | Requires 2+ years of financial history |
| Academically validated | Pure "deep value" can underperform for long periods |

---

## 3. GARP (Growth at a Reasonable Price)

**Made Famous by:** Peter Lynch (legendary Fidelity fund manager)

**The Big Idea:** Find growing companies that aren't overpriced.

**How it Works:**
GARP uses the **PEG ratio**:

```
PEG = Price-to-Earnings Ratio / Earnings Growth Rate

Example:
- Company A: P/E of 20, growing at 25% per year = PEG of 0.8 (attractive!)
- Company B: P/E of 20, growing at 10% per year = PEG of 2.0 (expensive!)
```

A PEG under 1.0 means you're paying less for growth than the growth rate itself - a potential bargain.

**In Plain English:** It's like finding a fast-growing company whose stock price hasn't caught up to its growth yet.

| Pros | Cons |
|------|------|
| Balances growth and value | Doesn't work for money-losing companies |
| Intuitive and widely used | Relies on growth estimates (which can be wrong) |
| Avoids overhyped stocks | Single metric focus |

---

## 4. Quality-Value Composite

**The Big Idea:** Buy cheap stocks, but only if the underlying business is high quality.

**How it Works:**
This strategy scores stocks on two dimensions:

**Quality Score (50% weight):**
- Return on Equity (ROE)
- Return on Invested Capital (ROIC)
- Profit margins
- Efficiency ratios

**Value Score (50% weight):**
- Price-to-Earnings (P/E)
- Price-to-Book (P/B)
- Free Cash Flow Yield

Stocks must score well on BOTH quality AND value to be selected.

**In Plain English:** It's like finding a Mercedes at Honda prices - high quality at a discount.

| Pros | Cons |
|------|------|
| Avoids "value traps" (cheap but bad businesses) | More complex |
| Quality filter provides safety | May miss high-growth opportunities |
| Diversified approach | Requires comprehensive data |

---

## 5. Three-Factor Model

**The Big Idea:** Combine value, quality, AND growth for a well-rounded approach.

**How it Works:**
Equal weighting of three factor categories:

| Factor | Weight | What It Captures |
|--------|--------|------------------|
| **Value** | 33% | Cheap stocks relative to fundamentals |
| **Quality** | 33% | Profitable, well-run companies |
| **Growth** | 33% | Companies with expanding revenues and earnings |

**In Plain English:** Don't put all your eggs in one basket - look for stocks that check multiple boxes.

| Pros | Cons |
|------|------|
| Diversified factor exposure | Factors can sometimes conflict |
| Captures multiple return drivers | More complex than single-factor strategies |
| Academically supported | Requires more data |

---

## 6. Six-Factor Model (The Kitchen Sink)

**The Big Idea:** Use ALL the major factors that academics have found to predict returns.

**How it Works:**
This comprehensive model adds three more factors to the Three-Factor base:

| Factor | Weight | What It Captures |
|--------|--------|------------------|
| **Value** | 20% | Cheap stocks |
| **Quality** | 20% | Well-run companies |
| **Growth** | 20% | Expanding businesses |
| **Momentum** | 15% | Stocks already going up tend to keep going up |
| **Low Volatility** | 15% | Boring, stable stocks often outperform on a risk-adjusted basis |
| **Sentiment** | 10% | Insider buying and institutional interest |

**In Plain English:** Why pick just one factor when you can use them all?

| Pros | Cons |
|------|------|
| Most comprehensive approach | Most complex to implement |
| Captures multiple market anomalies | Higher trading turnover (costs) |
| Best risk-adjusted returns in our tests | Requires extensive data |

---

## Performance Results

### Overall Performance (2010-2024)

| Strategy | Total Return | Annual Return | Risk-Adjusted Return (Sharpe) | Worst Drawdown |
|----------|-------------|---------------|------------------------------|----------------|
| **Six-Factor** | 171% | 39% | **0.97 (Best)** | -20% |
| Magic Formula | 386% | 68% | 0.56 | -35% |
| Three-Factor | 81% | 21% | 0.65 | -15% |
| GARP | 79% | 21% | 0.59 | **-14% (Safest)** |
| Quality-Value | 71% | 19% | 0.54 | -20% |
| Piotroski | -16% | -6% | -0.40 | -41% |

**Key Takeaway:** The Six-Factor model delivered the best *risk-adjusted* returns (highest Sharpe ratio), meaning it gave you the most return per unit of risk taken.

---

### Recent Performance

#### 2024 Results (Bull Market: SPY +23%)

| Strategy | Return | vs. SPY |
|----------|--------|---------|
| **Six-Factor** | **+46%** | +23% |
| GARP | +27% | +4% |
| Quality-Value | +27% | +4% |
| Piotroski | +24% | +1% |
| Three-Factor | +23% | 0% |
| Magic Formula | +11% | -12% |

#### 2025 Results Year-to-Date (Mixed Market: SPY +16%)

| Strategy | Return | vs. SPY |
|----------|--------|---------|
| **Six-Factor** | **+52%** | +36% |
| Three-Factor | +9% | -7% |
| GARP | +6% | -10% |
| Piotroski | +6% | -10% |
| Quality-Value | +2% | -14% |
| Magic Formula | +1% | -15% |

---

## The Critical Question: What Works in a Down Market?

### 2022 Bear Market Performance (SPY: -19.5%)

This is where things get really interesting:

| Strategy | Return | vs. SPY | Max Drawdown |
|----------|--------|---------|--------------|
| **GARP** | **+39%** | **+59%** | -13% |
| **Three-Factor** | **+33%** | **+52%** | -15% |
| **Quality-Value** | **+17%** | **+36%** | -20% |
| Six-Factor | +2% | +22% | -23% |
| Piotroski | -25% | -5% | -33% |
| Magic Formula | -30% | -11% | -35% |

**The Surprise:** The Six-Factor model, which dominated in bull markets, was merely okay in the 2022 bear market. **GARP was the star**, turning a -19.5% market into a +39% gain!

**Why?** GARP's focus on "reasonable prices" meant it avoided the overvalued growth stocks that crashed hardest in 2022. Meanwhile, the momentum component of Six-Factor actually hurt it (last year's winners became this year's losers).

---

## Which Strategy Should You Use?

### Decision Guide

| Your Priority | Best Choice | Why |
|---------------|-------------|-----|
| **Simplicity** | GARP | One metric (PEG ratio), easy to understand |
| **Best risk-adjusted returns** | Six-Factor | Highest Sharpe ratio over time |
| **Bear market protection** | GARP or Three-Factor | Significantly outperformed in 2022 crash |
| **Lowest drawdowns** | GARP | Smoothest ride with -14% max drawdown |
| **Bull market gains** | Six-Factor | Momentum factor captures uptrends |
| **Deep value investing** | Piotroski | If you believe value will make a comeback |

### A Practical Approach

Based on our research, here's a sensible approach:

1. **If you can only pick one:** GARP offers the best balance of simplicity, decent returns, and downside protection.

2. **If you want the highest returns and can stomach volatility:** Six-Factor, but be prepared for periods of underperformance.

3. **If you're worried about a market crash:** GARP or Three-Factor - they actually made money in 2022 while the market dropped 20%.

4. **If you want to hedge your bets:** Consider splitting between Six-Factor (for bull markets) and GARP (for bear market protection).

---

## Important Disclaimers

1. **Past performance doesn't guarantee future results.** These backtests show what *would have* happened, not what *will* happen.

2. **Transaction costs matter.** Our backtests don't include trading costs, which would reduce returns (especially for Six-Factor with higher turnover).

3. **Taxes matter.** Frequent rebalancing creates taxable events.

4. **This is not financial advice.** This is educational research. Consult a financial advisor before making investment decisions.

5. **All strategies can underperform.** Even the best strategy will have bad years. The key is sticking with it through the rough patches.

---

## Glossary of Terms

| Term | Definition |
|------|------------|
| **Sharpe Ratio** | Return per unit of risk. Higher is better. Above 1.0 is excellent. |
| **Max Drawdown** | The largest peak-to-trough decline. Measures worst-case scenario. |
| **Alpha** | Return above what the market delivered. Positive = beating the market. |
| **P/E Ratio** | Stock price divided by earnings per share. Lower = cheaper. |
| **P/B Ratio** | Stock price divided by book value per share. Lower = cheaper. |
| **PEG Ratio** | P/E divided by growth rate. Under 1.0 is attractive. |
| **ROE** | Return on Equity. Measures profitability relative to shareholder investment. |
| **ROIC** | Return on Invested Capital. Measures how efficiently capital is deployed. |
| **Momentum** | The tendency for recent winners to keep winning (and losers to keep losing). |
| **Beta** | How much a stock moves relative to the market. Beta > 1 = more volatile than market. |

---

## Summary

Factor investing offers a systematic, data-driven approach to stock selection. Our research found:

- **Six-Factor** is the best overall performer on a risk-adjusted basis
- **GARP** is the best defensive strategy and simplest to understand
- **Three-Factor** offers a good balance of performance and downside protection
- **Magic Formula** can generate high returns but with significant volatility
- **Piotroski** and **Quality-Value** are solid but have struggled recently

The most important insight: **different strategies work in different market conditions.** GARP and Three-Factor shine in down markets, while Six-Factor dominates in up markets. A blend of approaches may be the wisest path.

---

*This analysis was conducted using historical S&P 500 data from 2010-2025, with quarterly rebalancing and 30-stock portfolios. Results are for educational purposes only.*
