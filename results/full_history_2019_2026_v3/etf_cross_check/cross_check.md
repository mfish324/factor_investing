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
| SPY | 71.95% | 11.56% | 0.44 | -25.36% | S&P 500 (benchmark) |
| SYLD | 20.50% | 3.83% | -0.01 | -27.43% | Cambria Shareholder Yield --> our shareholder_yield |
| VLUE | 55.97% | 9.38% | 0.31 | -28.77% | iShares MSCI USA Value Factor --> our quality_value / three_factor |
| IUSV | 47.27% | 8.12% | 0.28 | -19.20% | iShares Core S&P US Value |
| SPHQ | 76.38% | 12.13% | 0.49 | -26.02% | Invesco S&P 500 Quality --> our quality_value |
| QUAL | 61.46% | 10.15% | 0.35 | -29.04% | iShares MSCI USA Quality Factor |
| MTUM | 72.71% | 11.66% | 0.37 | -32.77% | iShares MSCI USA Momentum (now BlackRock USA Momentum) |
| USMV | 29.59% | 5.37% | 0.11 | -18.87% | iShares MSCI USA Min Vol --> our low_volatility |
| SPLV | 20.24% | 3.79% | -0.02 | -18.01% | Invesco S&P 500 Low Volatility |

## Our backtested strategies (from shadow DB)

| Strategy | Total Return | Ann. Return | Sharpe | Max DD |
|---|---:|---:|---:|---:|
| magic_formula | -19.29% | -4.23% | -0.40 | -46.31% |
| piotroski | 84.40% | 13.13% | 0.46 | -31.10% |
| garp | 105.26% | 15.60% | 0.62 | -26.99% |
| quality_value | 98.69% | 14.84% | 0.60 | -28.06% |
| three_factor | 118.20% | 17.03% | 0.74 | -21.73% |
| six_factor | 114.13% | 16.59% | 0.72 | -23.76% |
| low_volatility | 32.53% | 5.84% | 0.15 | -20.66% |
| shareholder_yield | 140.29% | 19.33% | 0.55 | -19.39% |
| ml_ensemble | 72.15% | 11.57% | 0.36 | -28.36% |

## Pairwise: our strategy vs closest ETF analog

| Our Strategy | Our Ann. | Our Sharpe | ETF | ETF Ann. | ETF Sharpe | Ann. Gap | Sharpe Gap |
|---|---|---|---|---|---|---|---|
| shareholder_yield | 19.33% | 0.55 | SYLD | 3.83% | -0.01 | +15.50% | +0.56 |
| quality_value | 14.84% | 0.60 | SPHQ | 12.13% | 0.49 | +2.71% | +0.11 |
| quality_value | 14.84% | 0.60 | QUAL | 10.15% | 0.35 | +4.70% | +0.25 |
| three_factor | 17.03% | 0.74 | VLUE | 9.38% | 0.31 | +7.65% | +0.44 |
| three_factor | 17.03% | 0.74 | IUSV | 8.12% | 0.28 | +8.91% | +0.46 |
| six_factor | 16.59% | 0.72 | MTUM | 11.66% | 0.37 | +4.94% | +0.35 |
| low_volatility | 5.84% | 0.15 | USMV | 5.37% | 0.11 | +0.47% | +0.04 |
| low_volatility | 5.84% | 0.15 | SPLV | 3.79% | -0.02 | +2.05% | +0.17 |
| magic_formula | -4.23% | -0.40 | SPY | 11.56% | 0.44 | -15.78% | -0.84 |
| piotroski | 13.13% | 0.46 | SPHQ | 12.13% | 0.49 | +1.00% | -0.04 |

## How to read

- **`Ann. Gap`** is our strategy minus the ETF. Positive = we claim to beat the ETF. A 1-3% gap is plausible (the ETF has costs, broader holdings, etc.). A 5-10% gap is suspicious. A 10+% gap is almost certainly methodology bias.
- **`Sharpe Gap`** is the same idea on a risk-adjusted basis.
- The biggest expected sources of remaining bias are: survivorship bias in the universe (we use today's S&P 500), restated financials (Polygon serves the latest restated versions), and constant-shares approximation in market caps.