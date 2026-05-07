"""
ETF cross-check: real-world sanity test for our backtested strategies.

For each comparable ETF, fetch its split-adjusted close price series from
Polygon and compute the same set of metrics we report for our strategies.
Then compare side-by-side.

Comparison is **price-only** (no dividend reinvestment) on BOTH sides:
- Our shadow strategies: hold individual stocks, use Polygon split-adjusted
  close. Dividends are not reinvested.
- The benchmark ETFs here: same split-adjusted close, dividends not added.

Both sides are under-stated by their respective dividend yields (~1.5% for
SPY/Three Factor universe, ~3-4% for SYLD-like high-yield strategies). The
*gap* between them is what matters.

Output: results/full_history_2019_2026_v3/etf_cross_check/cross_check.md
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import RESULTS_DIR, RISK_FREE_RATE, TRADING_DAYS_PER_YEAR
from data.polygon_client import PolygonClient
from tracking import ShadowDB

logging.basicConfig(level=logging.WARNING, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

START_DATE = "2019-01-01"
END_DATE = "2026-05-01"
INITIAL_CAPITAL = 100_000.0

# Each pair: ETF ticker -> what it represents / closest analog among our strategies
ETFS = {
    "SPY":  "S&P 500 (benchmark)",
    "SYLD": "Cambria Shareholder Yield --> our shareholder_yield",
    "VLUE": "iShares MSCI USA Value Factor --> our quality_value / three_factor",
    "IUSV": "iShares Core S&P US Value",
    "SPHQ": "Invesco S&P 500 Quality --> our quality_value",
    "QUAL": "iShares MSCI USA Quality Factor",
    "MTUM": "iShares MSCI USA Momentum (now BlackRock USA Momentum)",
    "USMV": "iShares MSCI USA Min Vol --> our low_volatility",
    "SPLV": "Invesco S&P 500 Low Volatility",
}

OUR_STRATEGIES = [
    "magic_formula",
    "piotroski",
    "garp",
    "quality_value",
    "three_factor",
    "six_factor",
    "low_volatility",
    "shareholder_yield",
    "ml_ensemble",
]

OUTPUT_DIR = RESULTS_DIR / "full_history_2019_2026_v3" / "etf_cross_check"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def metrics_from_returns(returns: pd.Series) -> dict:
    if returns.empty:
        return {"total_return": 0, "ann_return": 0, "vol": 0, "sharpe": 0, "max_dd": 0, "n_days": 0}
    cum = (1 + returns).cumprod()
    total_return = float(cum.iloc[-1] - 1)
    n = len(returns)
    years = n / TRADING_DAYS_PER_YEAR
    ann_return = (cum.iloc[-1] ** (1 / years) - 1) if years > 0 else 0
    vol = returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    sharpe = (ann_return - RISK_FREE_RATE) / vol if vol > 0 else 0
    rolling_max = cum.cummax()
    drawdown = cum / rolling_max - 1
    max_dd = float(drawdown.min())
    return {
        "total_return": total_return,
        "ann_return": float(ann_return),
        "vol": float(vol),
        "sharpe": float(sharpe),
        "max_dd": max_dd,
        "n_days": n,
    }


def returns_for_etf(client: PolygonClient, ticker: str) -> pd.Series:
    df = client.get_prices(ticker, START_DATE, END_DATE)
    if df is None or df.empty or "close" not in df.columns:
        logger.warning(f"No data for {ticker}")
        return pd.Series(dtype=float)
    if "date" in df.columns:
        df = df.assign(date=pd.to_datetime(df["date"])).sort_values("date")
    else:
        df = df.assign(date=pd.to_datetime(df.index)).sort_values("date")
    end_ts = pd.Timestamp(END_DATE)
    df = df[df["date"] <= end_ts]
    rets = df.set_index("date")["close"].pct_change().dropna()
    return rets


def returns_for_strategy(db: ShadowDB, name: str) -> pd.Series:
    df = db.get_equity_curve(name, start=START_DATE, end=END_DATE)
    if df.empty:
        return pd.Series(dtype=float)
    return df.set_index("date")["daily_return"].dropna()


def fmt_row(label: str, m: dict, tag: str = "") -> dict:
    return {
        "Series": label,
        "Tag": tag,
        "Total Return": f"{m['total_return']:.2%}" if m["n_days"] else "n/a",
        "Ann. Return": f"{m['ann_return']:.2%}" if m["n_days"] else "n/a",
        "Vol": f"{m['vol']:.2%}" if m["n_days"] else "n/a",
        "Sharpe": f"{m['sharpe']:.2f}" if m["n_days"] else "n/a",
        "Max DD": f"{m['max_dd']:.2%}" if m["n_days"] else "n/a",
        "Days": m["n_days"],
    }


def main():
    client = PolygonClient()
    db = ShadowDB()

    rows = []

    print("Loading ETF returns from Polygon (split-adjusted close)...")
    etf_metrics: dict[str, dict] = {}
    for ticker, desc in ETFS.items():
        rets = returns_for_etf(client, ticker)
        m = metrics_from_returns(rets)
        etf_metrics[ticker] = m
        print(f"  {ticker:6s}  Total {m['total_return']:>8.2%}  Ann {m['ann_return']:>7.2%}  Sharpe {m['sharpe']:>5.2f}  ({m['n_days']} days)")
        rows.append(fmt_row(f"{ticker} (real ETF)", m, tag="ETF"))

    print("\nLoading our shadow-DB strategies...")
    strategy_metrics: dict[str, dict] = {}
    for name in OUR_STRATEGIES:
        rets = returns_for_strategy(db, name)
        m = metrics_from_returns(rets)
        strategy_metrics[name] = m
        print(f"  {name:18s}  Total {m['total_return']:>8.2%}  Ann {m['ann_return']:>7.2%}  Sharpe {m['sharpe']:>5.2f}  ({m['n_days']} days)")
        rows.append(fmt_row(name, m, tag="our backtest"))

    df = pd.DataFrame(rows)
    csv_path = OUTPUT_DIR / "cross_check.csv"
    df.to_csv(csv_path, index=False)

    # Pairwise comparison: our strategy vs closest ETF analog
    pairings = [
        ("shareholder_yield", "SYLD"),
        ("quality_value",     "SPHQ"),
        ("quality_value",     "QUAL"),
        ("three_factor",      "VLUE"),
        ("three_factor",      "IUSV"),
        ("six_factor",        "MTUM"),
        ("low_volatility",    "USMV"),
        ("low_volatility",    "SPLV"),
        ("magic_formula",     "SPY"),
        ("piotroski",         "SPHQ"),
    ]

    pair_rows = []
    for ours, etf in pairings:
        s = strategy_metrics.get(ours, {})
        e = etf_metrics.get(etf, {})
        if not s or not e or not s.get("n_days") or not e.get("n_days"):
            continue
        ann_gap = s["ann_return"] - e["ann_return"]
        sharpe_gap = s["sharpe"] - e["sharpe"]
        pair_rows.append({
            "Our Strategy": ours,
            "Our Ann.": f"{s['ann_return']:.2%}",
            "Our Sharpe": f"{s['sharpe']:.2f}",
            "ETF": etf,
            "ETF Ann.": f"{e['ann_return']:.2%}",
            "ETF Sharpe": f"{e['sharpe']:.2f}",
            "Ann. Gap": f"{ann_gap:+.2%}",
            "Sharpe Gap": f"{sharpe_gap:+.2f}",
        })
    pair_df = pd.DataFrame(pair_rows)
    pair_df.to_csv(OUTPUT_DIR / "pairwise.csv", index=False)

    # Markdown report
    md = ["# ETF Cross-Check: Are Our Strategies' Returns Realistic?", ""]
    md.append(f"**Period:** {START_DATE} to {END_DATE}")
    md.append(f"**Comparison basis:** split-adjusted close, price-only (dividends not reinvested on either side).")
    md.append(f"**Risk-free rate (for Sharpe):** {RISK_FREE_RATE:.0%}")
    md.append("")
    md.append("## What this is")
    md.append("")
    md.append("Our backtests claim ~22-26% annualized for value/quality/yield strategies on the S&P 500 ex-financials universe. Real-world ETFs running similar factor strategies are well-funded, professionally implemented, and have decades of academic research behind their construction. If our backtests are honest, they should at least be in the same ballpark as the real ETFs. If we're 10+ percentage points ahead, something is still wrong with the methodology.")
    md.append("")
    md.append("## Both sides are price-only")
    md.append("")
    md.append("Polygon's `adjusted=true` adjusts for splits but not dividends. Our shadow strategies don't reinvest dividends either. So both numbers under-state total return by their respective dividend yields:")
    md.append("- SPY / S&P 500 universe: ~1.5%/yr unmodeled dividends")
    md.append("- SYLD / high-shareholder-yield ETFs: ~3-4%/yr unmodeled dividends")
    md.append("- USMV / low-vol: ~2%/yr unmodeled dividends")
    md.append("")
    md.append("This biases the comparison *against* the high-yield ETFs (which have more dividends to lose). The relative gap is the relevant signal.")
    md.append("")
    md.append("## Real ETFs (price-only, from Polygon)")
    md.append("")
    md.append("| Ticker | Total Return | Ann. Return | Sharpe | Max DD | Description |")
    md.append("|---|---:|---:|---:|---:|:---|")
    for ticker, desc in ETFS.items():
        m = etf_metrics[ticker]
        if m["n_days"] == 0:
            md.append(f"| {ticker} | n/a | n/a | n/a | n/a | {desc} |")
            continue
        md.append(
            f"| {ticker} | {m['total_return']:.2%} | {m['ann_return']:.2%} | "
            f"{m['sharpe']:.2f} | {m['max_dd']:.2%} | {desc} |"
        )
    md.append("")
    md.append("## Our backtested strategies (from shadow DB)")
    md.append("")
    md.append("| Strategy | Total Return | Ann. Return | Sharpe | Max DD |")
    md.append("|---|---:|---:|---:|---:|")
    for name in OUR_STRATEGIES:
        m = strategy_metrics[name]
        if m["n_days"] == 0:
            continue
        md.append(
            f"| {name} | {m['total_return']:.2%} | {m['ann_return']:.2%} | "
            f"{m['sharpe']:.2f} | {m['max_dd']:.2%} |"
        )
    md.append("")
    md.append("## Pairwise: our strategy vs closest ETF analog")
    md.append("")
    if not pair_df.empty:
        md.append("| " + " | ".join(pair_df.columns) + " |")
        md.append("|" + "|".join(["---"] * len(pair_df.columns)) + "|")
        for _, row in pair_df.iterrows():
            md.append("| " + " | ".join(str(v) for v in row.values) + " |")
    md.append("")
    md.append("## How to read")
    md.append("")
    md.append("- **`Ann. Gap`** is our strategy minus the ETF. Positive = we claim to beat the ETF. A 1-3% gap is plausible (the ETF has costs, broader holdings, etc.). A 5-10% gap is suspicious. A 10+% gap is almost certainly methodology bias.")
    md.append("- **`Sharpe Gap`** is the same idea on a risk-adjusted basis.")
    md.append("- The biggest expected sources of remaining bias are: survivorship bias in the universe (we use today's S&P 500), restated financials (Polygon serves the latest restated versions), and constant-shares approximation in market caps.")
    out_md = OUTPUT_DIR / "cross_check.md"
    out_md.write_text("\n".join(md), encoding="utf-8")
    print(f"\nSaved {csv_path}")
    print(f"Saved {out_md}")


if __name__ == "__main__":
    main()
