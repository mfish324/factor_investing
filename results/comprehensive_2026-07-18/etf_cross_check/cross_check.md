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
| magic_formula | 16.28% | 3.10% | -0.05 | -35.53% |
| piotroski | 30.73% | 5.58% | 0.09 | -21.79% |
| garp | 41.64% | 7.31% | 0.18 | -25.21% |
| quality_value | 37.19% | 6.62% | 0.14 | -25.82% |
| three_factor | 39.23% | 6.93% | 0.16 | -26.24% |
| six_factor | 89.74% | 13.85% | 0.54 | -21.04% |
| low_volatility | 34.16% | 6.13% | 0.18 | -20.27% |
| shareholder_yield | 38.25% | 6.78% | 0.15 | -27.12% |
| ml_ensemble | 72.19% | 11.64% | 0.31 | -33.38% |

## Pairwise: our strategy vs closest ETF analog

| Our Strategy | Our Ann. | Our Sharpe | ETF | ETF Ann. | ETF Sharpe | Ann. Gap | Sharpe Gap |
|---|---|---|---|---|---|---|---|
| shareholder_yield | 6.78% | 0.15 | SYLD | 6.39% | 0.12 | +0.39% | +0.03 |
| quality_value | 6.62% | 0.14 | SPHQ | 11.63% | 0.46 | -5.01% | -0.31 |
| quality_value | 6.62% | 0.14 | QUAL | 10.12% | 0.35 | -3.51% | -0.21 |
| three_factor | 6.93% | 0.16 | VLUE | 12.94% | 0.49 | -6.00% | -0.33 |
| three_factor | 6.93% | 0.16 | IUSV | 9.43% | 0.37 | -2.50% | -0.21 |
| six_factor | 13.85% | 0.54 | MTUM | 11.82% | 0.36 | +2.04% | +0.18 |
| low_volatility | 6.13% | 0.18 | USMV | 5.07% | 0.09 | +1.06% | +0.09 |
| low_volatility | 6.13% | 0.18 | SPLV | 4.09% | 0.01 | +2.04% | +0.17 |
| magic_formula | 3.10% | -0.05 | SPY | 11.56% | 0.44 | -8.46% | -0.49 |
| piotroski | 5.58% | 0.09 | SPHQ | 11.63% | 0.46 | -6.05% | -0.36 |

## How to read

- **`Ann. Gap`** is our strategy minus the ETF. Positive = we claim to beat the ETF. A 1-3% gap is plausible (the ETF has costs, broader holdings, etc.). A 5-10% gap is suspicious. A 10+% gap is almost certainly methodology bias.
- **`Sharpe Gap`** is the same idea on a risk-adjusted basis.
- The biggest expected sources of remaining bias are: survivorship bias in the universe (we use today's S&P 500), restated financials (Polygon serves the latest restated versions), and constant-shares approximation in market caps.