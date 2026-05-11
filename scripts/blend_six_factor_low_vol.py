"""
Six Factor + Low Volatility blend backtest.

Runs both models over the full history, then constructs a daily-rebalanced
weighted blend of their returns and computes performance metrics.

Tests three blend ratios: 60/40, 70/30, 80/20 (Six Factor / Low Vol).
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import RESULTS_DIR
from data.polygon_client import PolygonClient
from data.universe import UniverseManager
from models.six_factor import SixFactorModel
from models.low_volatility import LowVolatilityModel
from backtesting.engine import BacktestEngine
from backtesting.metrics import calculate_metrics
from main import load_data, get_polygon_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

START_DATE = "2019-01-01"
END_DATE = "2026-05-01"
PORTFOLIO_SIZE = 30
REBALANCE = "monthly"

OUTPUT_DIR = RESULTS_DIR / "full_history_2019_2026" / "blend"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BLEND_RATIOS = [
    ("80_20", 0.80, 0.20),
    ("70_30", 0.70, 0.30),
    ("60_40", 0.60, 0.40),
    ("50_50", 0.50, 0.50),
]


def run_model(model_class, financials, prices, market_caps, benchmark_prices, shares_outstanding):
    model = model_class()
    engine = BacktestEngine(
        model=model,
        start_date=START_DATE,
        end_date=END_DATE,
        rebalance_freq=REBALANCE,
        portfolio_size=PORTFOLIO_SIZE,
    )
    return engine.run(
        financials=financials,
        prices=prices,
        market_caps=market_caps,
        benchmark_prices=benchmark_prices,
        shares_outstanding=shares_outstanding,
    )


def fmt_metrics(name, m):
    return {
        "Strategy": name,
        "Total Return": f"{m.total_return:.2%}",
        "Ann. Return": f"{m.annualized_return:.2%}",
        "Volatility": f"{m.volatility:.2%}",
        "Sharpe": f"{m.sharpe_ratio:.2f}",
        "Sortino": f"{m.sortino_ratio:.2f}",
        "Max DD": f"{m.max_drawdown:.2%}",
        "Calmar": f"{m.calmar_ratio:.2f}",
        "Alpha": f"{m.alpha:.2%}",
        "Beta": f"{m.beta:.2f}",
        "Info Ratio": f"{m.information_ratio:.2f}",
    }


def main():
    polygon_client = get_polygon_client()
    universe = UniverseManager().get_universe('sp500', exclude_financials=True)
    logger.info(f"Universe: {len(universe)} stocks")

    financials, prices, market_caps, benchmark_prices, shares_outstanding, _ = load_data(
        polygon_client, universe, START_DATE, END_DATE
    )
    valid = set(financials) & set(prices) & set(market_caps)
    logger.info(f"Stocks with complete data: {len(valid)}")

    logger.info("Running Six Factor...")
    sf_result = run_model(SixFactorModel, financials, prices, market_caps, benchmark_prices, shares_outstanding)
    logger.info(f"  Six Factor: {sf_result.metrics.total_return:.2%} total, {sf_result.metrics.sharpe_ratio:.2f} Sharpe")

    logger.info("Running Low Volatility...")
    lv_result = run_model(LowVolatilityModel, financials, prices, market_caps, benchmark_prices, shares_outstanding)
    logger.info(f"  Low Volatility: {lv_result.metrics.total_return:.2%} total, {lv_result.metrics.sharpe_ratio:.2f} Sharpe")

    sf = sf_result.returns
    lv = lv_result.returns
    bench = sf_result.benchmark_returns

    # Align all series on common dates
    common_idx = sf.index.intersection(lv.index)
    sf = sf.reindex(common_idx).fillna(0)
    lv = lv.reindex(common_idx).fillna(0)
    bench_aligned = bench.reindex(common_idx).fillna(0) if bench is not None and not bench.empty else None

    # Daily-return correlation
    corr = sf.corr(lv)
    logger.info(f"Six Factor / Low Vol daily-return correlation: {corr:.3f}")

    rows = []
    rows.append(fmt_metrics("Six Factor (standalone)", sf_result.metrics))
    rows.append(fmt_metrics("Low Volatility (standalone)", lv_result.metrics))

    blend_curves = pd.DataFrame(index=common_idx)
    blend_curves["six_factor"] = (1 + sf).cumprod()
    blend_curves["low_volatility"] = (1 + lv).cumprod()

    for label, w_sf, w_lv in BLEND_RATIOS:
        # Daily-rebalanced blend (each day, w_sf * sf_return + w_lv * lv_return)
        blend_returns = w_sf * sf + w_lv * lv
        metrics = calculate_metrics(blend_returns, benchmark_returns=bench_aligned)
        name = f"Blend {int(w_sf*100)}/{int(w_lv*100)}"
        rows.append(fmt_metrics(name, metrics))
        blend_curves[f"blend_{label}"] = (1 + blend_returns).cumprod()

    summary = pd.DataFrame(rows)
    print()
    print(summary.to_string(index=False))

    # Save outputs
    summary.to_csv(OUTPUT_DIR / "blend_summary.csv", index=False)
    blend_curves.to_parquet(OUTPUT_DIR / "blend_curves.parquet")

    # Markdown table
    md_lines = ["# Six Factor + Low Volatility Blend Analysis", ""]
    md_lines.append(f"**Period:** {START_DATE} to {END_DATE}")
    md_lines.append(f"**Rebalance:** {REBALANCE}, {PORTFOLIO_SIZE} stocks per model")
    md_lines.append(f"**Daily-return correlation (Six Factor / Low Vol):** {corr:.3f}")
    md_lines.append("")
    md_lines.append("## Performance Summary")
    md_lines.append("")
    md_lines.append("| " + " | ".join(summary.columns) + " |")
    md_lines.append("|" + "|".join(["---"] * len(summary.columns)) + "|")
    for _, row in summary.iterrows():
        md_lines.append("| " + " | ".join(str(v) for v in row.values) + " |")
    md_lines.append("")
    md_lines.append("Blends are daily-rebalanced (weights re-applied each day to next-day returns).")
    md_lines.append("")
    (OUTPUT_DIR / "blend_summary.md").write_text("\n".join(md_lines))

    logger.info(f"Outputs saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
