"""
Margin / leverage P&L analysis for the top strategies.

For each (strategy, leverage L, annual margin rate r) combination, compute the
net daily return assuming daily-rebalanced constant leverage:

    net_t = L * gross_t - (L - 1) * (r / 252)

This is the standard "leveraged ETF" formula. It assumes leverage is reset
to L each day at no transaction cost, which is a slight optimism vs reality
where leverage drifts between rebalances. For a first-pass profitability
question (does this strategy survive the carry cost?) that's fine.

Outputs total return, Sharpe (vs RISK_FREE_RATE), max drawdown, final equity
at $100k starting capital.
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import RESULTS_DIR, RISK_FREE_RATE, TRADING_DAYS_PER_YEAR
from data.universe import UniverseManager
from models.three_factor import ThreeFactorModel
from models.six_factor import SixFactorModel
from models.shareholder_yield import ShareholderYieldModel
from backtesting.engine import BacktestEngine
from main import load_data, get_polygon_client

logging.basicConfig(level=logging.WARNING, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

START_DATE = "2019-01-01"
END_DATE = "2026-05-01"
PORTFOLIO_SIZE = 30
REBALANCE = "monthly"
INITIAL_CAPITAL = 100_000.0

LEVERAGES = [1.0, 1.5, 2.0, 3.0]
MARGIN_RATES = [0.00, 0.05, 0.07, 0.10]  # annual

STRATEGIES = [
    ("Shareholder Yield", ShareholderYieldModel),
    ("Three Factor", ThreeFactorModel),
    ("Six Factor", SixFactorModel),
]

OUTPUT_DIR = RESULTS_DIR / "full_history_2019_2026_v3" / "margin"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def levered_returns(gross: pd.Series, leverage: float, annual_rate: float) -> pd.Series:
    daily_rate = annual_rate / TRADING_DAYS_PER_YEAR
    return leverage * gross - (leverage - 1.0) * daily_rate


def metrics(returns: pd.Series) -> dict:
    if returns.empty:
        return dict(total_return=0, ann_return=0, vol=0, sharpe=0, max_dd=0, final_equity=INITIAL_CAPITAL)
    cumulative = (1 + returns).cumprod()
    final_equity = INITIAL_CAPITAL * float(cumulative.iloc[-1])
    total_return = float(cumulative.iloc[-1] - 1)

    n = len(returns)
    years = n / TRADING_DAYS_PER_YEAR
    ann_return = (cumulative.iloc[-1] ** (1 / years) - 1) if years > 0 else 0
    vol = returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    excess_ann = ann_return - RISK_FREE_RATE
    sharpe = excess_ann / vol if vol > 0 else 0

    rolling_max = cumulative.cummax()
    drawdown = cumulative / rolling_max - 1
    max_dd = float(drawdown.min())

    return dict(
        total_return=total_return,
        ann_return=ann_return,
        vol=vol,
        sharpe=sharpe,
        max_dd=max_dd,
        final_equity=final_equity,
    )


def margin_call_risk(returns: pd.Series, leverage: float, maintenance: float = 0.25) -> float:
    """
    Approximate margin-call exposure.

    For a position with leverage L, equity ratio is 1/L. A margin call is
    triggered when equity / market_value < maintenance margin (Reg-T = 0.25 on
    a 0.50 initial). Track the worst intra-period drop in equity/market_value
    and report whether it crossed the threshold.

    Returns the fraction of trading days where equity ratio fell below the
    maintenance margin (0 = never, 1 = always).
    """
    if leverage <= 1.0:
        return 0.0
    cum_gross = (1 + returns).cumprod()  # gross stock value path (per $1 of stock)
    # Equity path: starting equity = 1, debt = (L-1)/L * (initial market value).
    # Stock value path scales by cum_gross. Equity = stock_value - debt.
    # At t=0: stock_value = L (per $1 of equity), debt = L-1, equity ratio = 1/L.
    initial_stock = leverage
    debt = leverage - 1.0  # held flat (ignoring interest accrual for this metric)
    stock_path = initial_stock * cum_gross
    equity_path = stock_path - debt
    equity_ratio = equity_path / stock_path
    return float((equity_ratio < maintenance).mean())


def main():
    polygon = get_polygon_client()
    universe = UniverseManager().get_universe('sp500', exclude_financials=True)
    financials, prices, market_caps, benchmark_prices, shares_outstanding, _ = load_data(
        polygon, universe, START_DATE, END_DATE
    )
    logger.info(f"Loaded {len(financials)} financials, {len(prices)} prices, {len(market_caps)} mcs")

    # Run each strategy once, capture daily returns
    strategy_returns: dict[str, pd.Series] = {}
    for label, model_cls in STRATEGIES:
        print(f"Running {label}...")
        engine = BacktestEngine(
            model=model_cls(),
            start_date=START_DATE,
            end_date=END_DATE,
            rebalance_freq=REBALANCE,
            portfolio_size=PORTFOLIO_SIZE,
        )
        result = engine.run(
            financials=financials,
            prices=prices,
            market_caps=market_caps,
            benchmark_prices=benchmark_prices,
            shares_outstanding=shares_outstanding,
            show_progress=False,
        )
        strategy_returns[label] = result.returns
        m = metrics(result.returns)
        print(f"  Unlevered: {m['total_return']:.2%} total, Sharpe {m['sharpe']:.2f}, MaxDD {m['max_dd']:.2%}, ${m['final_equity']:,.0f}")

    # Sweep leverage x rate
    rows = []
    for label, gross in strategy_returns.items():
        for L in LEVERAGES:
            for r in MARGIN_RATES:
                net = levered_returns(gross, L, r)
                m = metrics(net)
                margin_call = margin_call_risk(gross, L)
                rows.append({
                    "Strategy": label,
                    "Leverage": f"{L:.1f}x",
                    "Margin Rate": f"{r:.0%}",
                    "Total Return": f"{m['total_return']:.2%}",
                    "Ann. Return": f"{m['ann_return']:.2%}",
                    "Vol": f"{m['vol']:.2%}",
                    "Sharpe": f"{m['sharpe']:.2f}",
                    "Max DD": f"{m['max_dd']:.2%}",
                    "Final Equity": f"${m['final_equity']:,.0f}",
                    "MarginCall%": f"{margin_call:.1%}",
                })
    df = pd.DataFrame(rows)
    csv_path = OUTPUT_DIR / "margin_sweep.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nSaved {csv_path}")
    print()
    print(df.to_string(index=False))

    # Markdown report
    md = ["# Margin / Leverage P&L Analysis", ""]
    md.append(f"**Period:** {START_DATE} to {END_DATE}")
    md.append(f"**Initial Capital:** ${INITIAL_CAPITAL:,.0f}")
    md.append(f"**Universe:** S&P 500 (excluding financials), 30 stocks per portfolio, monthly rebalance")
    md.append(f"**Risk-free rate (for Sharpe):** {RISK_FREE_RATE:.0%}")
    md.append("")
    md.append("**Method:** Constant daily-rebalanced leverage. Net daily return = L * gross - (L-1) * (annual_rate / 252).")
    md.append("`MarginCall%` is the fraction of trading days where equity / market value < 25% maintenance margin (Reg-T threshold), assuming flat debt and ignoring intraday volatility.")
    md.append("")
    md.append("## Sensitivity Table")
    md.append("")
    md.append("| " + " | ".join(df.columns) + " |")
    md.append("|" + "|".join(["---"] * len(df.columns)) + "|")
    for _, row in df.iterrows():
        md.append("| " + " | ".join(str(v) for v in row.values) + " |")
    md.append("")
    md.append("## Quick Read")
    md.append("")
    md.append("- **1.0x rows** are baseline (no margin); they are the same numbers as the unlevered backtest.")
    md.append("- **0% margin rate rows** show the pure-leverage scaling — useful as an upper bound.")
    md.append("- A strategy is **profitable on margin** at a given (L, rate) if Total Return is meaningfully higher than the 1.0x baseline AND the strategy didn't trigger a margin call (`MarginCall%` near 0).")
    md.append("- Sharpe under leverage is roughly L * gross_sharpe - (L-1) * rate / vol. With positive carry cost the levered Sharpe is always lower than the unlevered Sharpe.")
    md.append("- Max DD scales close to L * unlevered MaxDD; if a strategy has -25% unlevered DD, 2x leverage gets you -50%, 3x to -75% (bankruptcy risk).")
    (OUTPUT_DIR / "margin_analysis.md").write_text("\n".join(md))
    print(f"Saved {OUTPUT_DIR / 'margin_analysis.md'}")


if __name__ == "__main__":
    main()
