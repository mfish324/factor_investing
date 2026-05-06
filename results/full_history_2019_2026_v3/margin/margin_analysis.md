# Margin / Leverage P&L Analysis

**Period:** 2019-01-01 to 2026-05-01
**Initial Capital:** $100,000
**Universe:** S&P 500 (excluding financials), 30 stocks per portfolio, monthly rebalance
**Risk-free rate (for Sharpe):** 4%

**Method:** Constant daily-rebalanced leverage. Net daily return = L * gross - (L-1) * (annual_rate / 252).
`MarginCall%` is the fraction of trading days where equity / market value < 25% maintenance margin (Reg-T threshold), assuming flat debt and ignoring intraday volatility.

## Sensitivity Table

| Strategy | Leverage | Margin Rate | Total Return | Ann. Return | Vol | Sharpe | Max DD | Final Equity | MarginCall% |
|---|---|---|---|---|---|---|---|---|---|
| Shareholder Yield | 1.0x | 0% | 221.82% | 26.55% | 27.73% | 0.81 | -18.41% | $321,820 | 0.0% |
| Shareholder Yield | 1.0x | 5% | 221.82% | 26.55% | 27.73% | 0.81 | -18.41% | $321,820 | 0.0% |
| Shareholder Yield | 1.0x | 7% | 221.82% | 26.55% | 27.73% | 0.81 | -18.41% | $321,820 | 0.0% |
| Shareholder Yield | 1.0x | 10% | 221.82% | 26.55% | 27.73% | 0.81 | -18.41% | $321,820 | 0.0% |
| Shareholder Yield | 1.5x | 0% | 417.77% | 39.27% | 41.60% | 0.85 | -26.75% | $517,771 | 0.0% |
| Shareholder Yield | 1.5x | 5% | 357.40% | 35.83% | 41.60% | 0.77 | -27.38% | $457,397 | 0.0% |
| Shareholder Yield | 1.5x | 7% | 335.27% | 34.48% | 41.60% | 0.73 | -27.63% | $435,265 | 0.0% |
| Shareholder Yield | 1.5x | 10% | 304.06% | 32.48% | 41.60% | 0.68 | -28.01% | $404,058 | 0.0% |
| Shareholder Yield | 2.0x | 0% | 682.09% | 51.33% | 55.47% | 0.85 | -34.51% | $782,089 | 0.0% |
| Shareholder Yield | 2.0x | 5% | 510.35% | 43.96% | 55.47% | 0.72 | -35.64% | $610,351 | 0.0% |
| Shareholder Yield | 2.0x | 7% | 452.72% | 41.11% | 55.47% | 0.67 | -36.08% | $552,717 | 0.0% |
| Shareholder Yield | 2.0x | 10% | 376.30% | 36.95% | 55.47% | 0.59 | -36.74% | $476,300 | 0.0% |
| Shareholder Yield | 3.0x | 0% | 1398.36% | 72.51% | 83.20% | 0.82 | -48.35% | $1,498,364 | 0.0% |
| Shareholder Yield | 3.0x | 5% | 812.55% | 56.11% | 83.20% | 0.63 | -50.12% | $912,550 | 0.0% |
| Shareholder Yield | 3.0x | 7% | 648.32% | 49.99% | 83.20% | 0.55 | -50.81% | $748,322 | 0.0% |
| Shareholder Yield | 3.0x | 10% | 455.66% | 41.26% | 83.20% | 0.45 | -51.82% | $555,662 | 0.0% |
| Three Factor | 1.0x | 0% | 174.78% | 22.58% | 19.04% | 0.98 | -19.75% | $274,776 | 0.0% |
| Three Factor | 1.0x | 5% | 174.78% | 22.58% | 19.04% | 0.98 | -19.75% | $274,776 | 0.0% |
| Three Factor | 1.0x | 7% | 174.78% | 22.58% | 19.04% | 0.98 | -19.75% | $274,776 | 0.0% |
| Three Factor | 1.0x | 10% | 174.78% | 22.58% | 19.04% | 0.98 | -19.75% | $274,776 | 0.0% |
| Three Factor | 1.5x | 0% | 326.68% | 33.94% | 28.56% | 1.05 | -29.10% | $426,676 | 0.0% |
| Three Factor | 1.5x | 5% | 276.92% | 30.64% | 28.56% | 0.93 | -30.07% | $376,921 | 0.0% |
| Three Factor | 1.5x | 7% | 258.68% | 29.34% | 28.56% | 0.89 | -30.45% | $358,683 | 0.0% |
| Three Factor | 1.5x | 10% | 232.96% | 27.42% | 28.56% | 0.82 | -31.02% | $332,964 | 0.0% |
| Three Factor | 2.0x | 0% | 534.90% | 45.11% | 38.08% | 1.08 | -37.95% | $634,900 | 0.0% |
| Three Factor | 2.0x | 5% | 395.48% | 38.04% | 38.08% | 0.89 | -39.64% | $495,481 | 0.0% |
| Three Factor | 2.0x | 7% | 348.69% | 35.31% | 38.08% | 0.82 | -40.30% | $448,693 | 0.0% |
| Three Factor | 2.0x | 10% | 286.66% | 31.31% | 38.08% | 0.72 | -41.27% | $386,657 | 0.0% |
| Three Factor | 3.0x | 0% | 1139.17% | 66.03% | 57.12% | 1.09 | -53.82% | $1,239,167 | 0.0% |
| Three Factor | 3.0x | 5% | 654.73% | 50.25% | 57.12% | 0.81 | -56.30% | $754,733 | 0.0% |
| Three Factor | 3.0x | 7% | 518.92% | 44.37% | 57.12% | 0.71 | -57.25% | $618,921 | 0.0% |
| Three Factor | 3.0x | 10% | 359.59% | 35.97% | 57.12% | 0.56 | -59.12% | $459,591 | 0.0% |
| Six Factor | 1.0x | 0% | 146.68% | 19.95% | 17.65% | 0.90 | -19.99% | $246,678 | 0.0% |
| Six Factor | 1.0x | 5% | 146.68% | 19.95% | 17.65% | 0.90 | -19.99% | $246,678 | 0.0% |
| Six Factor | 1.0x | 7% | 146.68% | 19.95% | 17.65% | 0.90 | -19.99% | $246,678 | 0.0% |
| Six Factor | 1.0x | 10% | 146.68% | 19.95% | 17.65% | 0.90 | -19.99% | $246,678 | 0.0% |
| Six Factor | 1.5x | 0% | 265.54% | 29.84% | 26.48% | 0.98 | -29.45% | $365,545 | 0.0% |
| Six Factor | 1.5x | 5% | 222.91% | 26.63% | 26.48% | 0.85 | -30.85% | $322,914 | 0.0% |
| Six Factor | 1.5x | 7% | 207.29% | 25.37% | 26.48% | 0.81 | -31.41% | $307,287 | 0.0% |
| Six Factor | 1.5x | 10% | 185.25% | 23.51% | 26.48% | 0.74 | -32.23% | $285,252 | 0.0% |
| Six Factor | 2.0x | 0% | 421.08% | 39.45% | 35.30% | 1.00 | -38.44% | $521,075 | 0.0% |
| Six Factor | 2.0x | 5% | 306.64% | 32.65% | 35.30% | 0.81 | -40.87% | $406,637 | 0.0% |
| Six Factor | 2.0x | 7% | 268.23% | 30.03% | 35.30% | 0.74 | -41.81% | $368,234 | 0.0% |
| Six Factor | 2.0x | 10% | 217.32% | 26.19% | 35.30% | 0.63 | -43.20% | $317,317 | 0.0% |
| Six Factor | 3.0x | 0% | 842.11% | 57.12% | 52.95% | 1.00 | -54.54% | $942,107 | 1.3% |
| Six Factor | 3.0x | 5% | 473.76% | 42.18% | 52.95% | 0.72 | -58.06% | $573,756 | 1.3% |
| Six Factor | 3.0x | 7% | 370.49% | 36.61% | 52.95% | 0.62 | -59.91% | $470,494 | 1.3% |
| Six Factor | 3.0x | 10% | 249.36% | 28.66% | 52.95% | 0.47 | -62.94% | $349,356 | 1.3% |

## Quick Read

- **1.0x rows** are baseline (no margin); they are the same numbers as the unlevered backtest.
- **0% margin rate rows** show the pure-leverage scaling — useful as an upper bound.
- A strategy is **profitable on margin** at a given (L, rate) if Total Return is meaningfully higher than the 1.0x baseline AND the strategy didn't trigger a margin call (`MarginCall%` near 0).
- Sharpe under leverage is roughly L * gross_sharpe - (L-1) * rate / vol. With positive carry cost the levered Sharpe is always lower than the unlevered Sharpe.
- Max DD scales close to L * unlevered MaxDD; if a strategy has -25% unlevered DD, 2x leverage gets you -50%, 3x to -75% (bankruptcy risk).