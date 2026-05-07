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
| magic_formula | 12.38% | 2.38% | -0.08 | -38.37% |
| piotroski | 122.09% | 17.44% | 0.67 | -26.29% |
| garp | 121.00% | 17.32% | 0.70 | -25.49% |
| quality_value | 117.57% | 16.95% | 0.74 | -22.84% |
| three_factor | 174.78% | 22.58% | 0.98 | -19.75% |
| six_factor | 146.68% | 19.95% | 0.90 | -19.99% |
| low_volatility | 37.89% | 6.69% | 0.22 | -17.64% |
| shareholder_yield | 221.82% | 26.55% | 0.81 | -18.41% |
| ml_ensemble | 85.10% | 13.21% | 0.44 | -26.85% |

## Pairwise: our strategy vs closest ETF analog

| Our Strategy | Our Ann. | Our Sharpe | ETF | ETF Ann. | ETF Sharpe | Ann. Gap | Sharpe Gap |
|---|---|---|---|---|---|---|---|
| shareholder_yield | 26.55% | 0.81 | SYLD | 3.83% | -0.01 | +22.71% | +0.82 |
| quality_value | 16.95% | 0.74 | SPHQ | 12.13% | 0.49 | +4.82% | +0.24 |
| quality_value | 16.95% | 0.74 | QUAL | 10.15% | 0.35 | +6.80% | +0.38 |
| three_factor | 22.58% | 0.98 | VLUE | 9.38% | 0.31 | +13.20% | +0.67 |
| three_factor | 22.58% | 0.98 | IUSV | 8.12% | 0.28 | +14.46% | +0.70 |
| six_factor | 19.95% | 0.90 | MTUM | 11.66% | 0.37 | +8.29% | +0.53 |
| low_volatility | 6.69% | 0.22 | USMV | 5.37% | 0.11 | +1.32% | +0.11 |
| low_volatility | 6.69% | 0.22 | SPLV | 3.79% | -0.02 | +2.90% | +0.24 |
| magic_formula | 2.38% | -0.08 | SPY | 11.56% | 0.44 | -9.18% | -0.52 |
| piotroski | 17.44% | 0.67 | SPHQ | 12.13% | 0.49 | +5.31% | +0.17 |

## How to read

- **`Ann. Gap`** is our strategy minus the ETF. Positive = we claim to beat the ETF. A 1-3% gap is plausible (the ETF has costs, broader holdings, etc.). A 5-10% gap is suspicious. A 10+% gap is almost certainly methodology bias.
- **`Sharpe Gap`** is the same idea on a risk-adjusted basis.
- The biggest expected sources of remaining bias are: survivorship bias in the universe (we use today's S&P 500), restated financials (Polygon serves the latest restated versions), and constant-shares approximation in market caps.