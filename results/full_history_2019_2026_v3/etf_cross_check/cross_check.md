# ETF Cross-Check: Are Our Strategies' Returns Realistic?

**Period:** 2019-01-01 to 2026-05-01
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
| SPY | 77.27% | 12.26% | 0.48 | -25.36% | S&P 500 (benchmark) |
| SYLD | 25.20% | 4.65% | 0.03 | -27.43% | Cambria Shareholder Yield --> our shareholder_yield |
| VLUE | 62.14% | 10.26% | 0.36 | -28.77% | iShares MSCI USA Value Factor --> our quality_value / three_factor |
| IUSV | 51.98% | 8.83% | 0.33 | -19.20% | iShares Core S&P US Value |
| SPHQ | 81.31% | 12.78% | 0.53 | -26.02% | Invesco S&P 500 Quality --> our quality_value |
| QUAL | 66.53% | 10.86% | 0.39 | -29.04% | iShares MSCI USA Quality Factor |
| MTUM | 77.83% | 12.34% | 0.41 | -32.77% | iShares MSCI USA Momentum (now BlackRock USA Momentum) |
| USMV | 33.05% | 5.94% | 0.16 | -18.87% | iShares MSCI USA Min Vol --> our low_volatility |
| SPLV | 23.66% | 4.38% | 0.03 | -18.01% | Invesco S&P 500 Low Volatility |

## Our backtested strategies (from shadow DB)

| Strategy | Total Return | Ann. Return | Sharpe | Max DD |
|---|---:|---:|---:|---:|
| magic_formula | 10.47% | 2.03% | -0.10 | -38.37% |
| piotroski | 71.74% | 11.54% | 0.38 | -31.71% |
| garp | 104.86% | 15.58% | 0.62 | -27.71% |
| quality_value | 100.59% | 15.09% | 0.61 | -28.15% |
| three_factor | 126.44% | 17.94% | 0.79 | -23.81% |
| six_factor | 140.74% | 19.41% | 0.88 | -23.81% |
| low_volatility | 32.95% | 5.92% | 0.16 | -19.27% |
| shareholder_yield | 166.08% | 21.85% | 0.66 | -17.35% |
| ml_ensemble | 72.56% | 11.65% | 0.36 | -29.35% |

## Pairwise: our strategy vs closest ETF analog

| Our Strategy | Our Ann. | Our Sharpe | ETF | ETF Ann. | ETF Sharpe | Ann. Gap | Sharpe Gap |
|---|---|---|---|---|---|---|---|
| shareholder_yield | 21.85% | 0.66 | SYLD | 4.65% | 0.03 | +17.20% | +0.63 |
| quality_value | 15.09% | 0.61 | SPHQ | 12.78% | 0.53 | +2.31% | +0.08 |
| quality_value | 15.09% | 0.61 | QUAL | 10.86% | 0.39 | +4.24% | +0.22 |
| three_factor | 17.94% | 0.79 | VLUE | 10.26% | 0.36 | +7.68% | +0.43 |
| three_factor | 17.94% | 0.79 | IUSV | 8.83% | 0.33 | +9.12% | +0.46 |
| six_factor | 19.41% | 0.88 | MTUM | 12.34% | 0.41 | +7.07% | +0.48 |
| low_volatility | 5.92% | 0.16 | USMV | 5.94% | 0.16 | -0.02% | -0.00 |
| low_volatility | 5.92% | 0.16 | SPLV | 4.38% | 0.03 | +1.54% | +0.12 |
| magic_formula | 2.03% | -0.10 | SPY | 12.26% | 0.48 | -10.23% | -0.58 |
| piotroski | 11.54% | 0.38 | SPHQ | 12.78% | 0.53 | -1.24% | -0.15 |

## How to read

- **`Ann. Gap`** is our strategy minus the ETF. Positive = we claim to beat the ETF. A 1-3% gap is plausible (the ETF has costs, broader holdings, etc.). A 5-10% gap is suspicious. A 10+% gap is almost certainly methodology bias.
- **`Sharpe Gap`** is the same idea on a risk-adjusted basis.
- The biggest expected sources of remaining bias are: survivorship bias in the universe (we use today's S&P 500), restated financials (Polygon serves the latest restated versions), and constant-shares approximation in market caps.