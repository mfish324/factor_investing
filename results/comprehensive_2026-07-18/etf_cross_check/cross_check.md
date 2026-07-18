# ETF Cross-Check: Are Our Strategies' Returns Realistic?

**Period:** 2021-08-01 to 2026-07-17
**Comparison basis:** split-adjusted close, price-only (dividends not reinvested on either side).
**Risk-free rate (for Sharpe):** 4%

## What this is

Our backtests claim ~22-26% annualized for value/quality/yield strategies on the S&P 500 ex-financials universe. Real-world ETFs running similar factor strategies are well-funded, professionally implemented, and have decades of academic research behind their construction. If our backtests are honest, they should at least be in the same ballpark as the real ETFs. If we're 10+ percentage points ahead, something is still wrong with the methodology.

## Both sides are price-only

Polygon's `adjusted=true` adjusts for splits but not dividends. Our shadow strategies don't reinvest dividends either. So both numbers under-state total return by their respective dividend yields:
- SPY / S&P 500 universe: ~1.5%/yr unmodeled dividends
- SYLD / high-shareholder-yield ETFs: ~3-4%/yr unmodeled dividends
- USMV / low-vol: ~2%/yr unmodeled dividends

This biases the comparison *against* the high-yield ETFs (which have more dividends to lose). The relative gap is the relevant signal.

## Real ETFs (price-only, from Polygon)

| Ticker | Total Return | Ann. Return | Sharpe | Max DD | Description |
|---|---:|---:|---:|---:|:---|
| SPY | 71.56% | 11.56% | 0.44 | -25.36% | S&P 500 (benchmark) |
| SYLD | 35.73% | 6.39% | 0.12 | -27.43% | Cambria Shareholder Yield --> our shareholder_yield |
| VLUE | 82.24% | 12.94% | 0.49 | -28.77% | iShares MSCI USA Value Factor --> our quality_value / three_factor |
| IUSV | 55.97% | 9.43% | 0.37 | -19.20% | iShares Core S&P US Value |
| SPHQ | 72.05% | 11.63% | 0.46 | -26.02% | Invesco S&P 500 Quality --> our quality_value |
| QUAL | 60.90% | 10.12% | 0.35 | -29.04% | iShares MSCI USA Quality Factor |
| MTUM | 73.49% | 11.82% | 0.36 | -32.77% | iShares MSCI USA Momentum (now BlackRock USA Momentum) |
| USMV | 27.65% | 5.07% | 0.09 | -18.87% | iShares MSCI USA Min Vol --> our low_volatility |
| SPLV | 21.88% | 4.09% | 0.01 | -18.01% | Invesco S&P 500 Low Volatility |

## Our backtested strategies (from shadow DB)

| Strategy | Total Return | Ann. Return | Sharpe | Max DD |
|---|---:|---:|---:|---:|
| magic_formula | 9.51% | 1.86% | -0.11 | -36.56% |
| piotroski | 68.46% | 11.14% | 0.40 | -27.10% |
| garp | 125.48% | 17.90% | 0.75 | -25.89% |
| quality_value | 97.94% | 14.83% | 0.59 | -30.85% |
| three_factor | 143.63% | 19.77% | 0.82 | -26.93% |
| six_factor | 158.01% | 21.17% | 0.94 | -23.09% |
| low_volatility | 46.58% | 8.05% | 0.31 | -16.65% |
| shareholder_yield | 189.33% | 24.01% | 0.73 | -21.01% |
| ml_ensemble | 75.18% | 12.03% | 0.34 | -28.38% |

## Pairwise: our strategy vs closest ETF analog

| Our Strategy | Our Ann. | Our Sharpe | ETF | ETF Ann. | ETF Sharpe | Ann. Gap | Sharpe Gap |
|---|---|---|---|---|---|---|---|
| shareholder_yield | 24.01% | 0.73 | SYLD | 6.39% | 0.12 | +17.62% | +0.62 |
| quality_value | 14.83% | 0.59 | SPHQ | 11.63% | 0.46 | +3.20% | +0.13 |
| quality_value | 14.83% | 0.59 | QUAL | 10.12% | 0.35 | +4.71% | +0.24 |
| three_factor | 19.77% | 0.82 | VLUE | 12.94% | 0.49 | +6.83% | +0.34 |
| three_factor | 19.77% | 0.82 | IUSV | 9.43% | 0.37 | +10.34% | +0.45 |
| six_factor | 21.17% | 0.94 | MTUM | 11.82% | 0.36 | +9.35% | +0.58 |
| low_volatility | 8.05% | 0.31 | USMV | 5.07% | 0.09 | +2.98% | +0.23 |
| low_volatility | 8.05% | 0.31 | SPLV | 4.09% | 0.01 | +3.96% | +0.31 |
| magic_formula | 1.86% | -0.11 | SPY | 11.56% | 0.44 | -9.71% | -0.55 |
| piotroski | 11.14% | 0.40 | SPHQ | 11.63% | 0.46 | -0.49% | -0.06 |

## How to read

- **`Ann. Gap`** is our strategy minus the ETF. Positive = we claim to beat the ETF. A 1-3% gap is plausible (the ETF has costs, broader holdings, etc.). A 5-10% gap is suspicious. A 10+% gap is almost certainly methodology bias.
- **`Sharpe Gap`** is the same idea on a risk-adjusted basis.
- The biggest expected sources of remaining bias are: survivorship bias in the universe (we use today's S&P 500), restated financials (Polygon serves the latest restated versions), and constant-shares approximation in market caps.