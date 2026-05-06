"""
Determinism test: run Six Factor twice in the same process and check if results match.
Then also report set-iteration-order behavior.
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.universe import UniverseManager
from models.six_factor import SixFactorModel
from backtesting.engine import BacktestEngine
from main import load_data, get_polygon_client

logging.basicConfig(level=logging.WARNING, format='%(levelname)s - %(message)s')

START_DATE = "2019-01-01"
END_DATE = "2026-05-01"

def run_once(financials, prices, market_caps, benchmark_prices, shares_outstanding, label):
    model = SixFactorModel()
    engine = BacktestEngine(
        model=model,
        start_date=START_DATE,
        end_date=END_DATE,
        rebalance_freq="monthly",
        portfolio_size=30,
    )
    result = engine.run(
        financials=financials,
        prices=prices,
        market_caps=market_caps,
        benchmark_prices=benchmark_prices,
        shares_outstanding=shares_outstanding,
        show_progress=False,
    )
    print(f"[{label}] Total: {result.metrics.total_return:.4%}  Sharpe: {result.metrics.sharpe_ratio:.4f}  Vol: {result.metrics.volatility:.4%}  Final: ${result.final_value:,.2f}")
    return result

def main():
    print(f"sys.flags.hash_randomization = {sys.flags.hash_randomization}")
    print(f"PYTHONHASHSEED env = {__import__('os').environ.get('PYTHONHASHSEED', '<unset>')}")

    polygon_client = get_polygon_client()
    universe = UniverseManager().get_universe('sp500', exclude_financials=True)
    financials, prices, market_caps, benchmark_prices, shares_outstanding = load_data(
        polygon_client, universe, START_DATE, END_DATE
    )

    # Run 3 times in same process
    r1 = run_once(financials, prices, market_caps, benchmark_prices, shares_outstanding, "Run 1")
    r2 = run_once(financials, prices, market_caps, benchmark_prices, shares_outstanding, "Run 2")
    r3 = run_once(financials, prices, market_caps, benchmark_prices, shares_outstanding, "Run 3")

    # Compare daily returns
    diff_12 = (r1.returns - r2.returns).abs().max()
    diff_13 = (r1.returns - r3.returns).abs().max()
    print(f"\nMax abs diff in daily returns: r1 vs r2 = {diff_12:.6e}, r1 vs r3 = {diff_13:.6e}")

    # Compare holdings on first rebalance
    h1 = sorted(r1.trades[0]['holdings']) if r1.trades else []
    h2 = sorted(r2.trades[0]['holdings']) if r2.trades else []
    print(f"\nFirst-rebalance holdings identical (sorted): {h1 == h2}")
    if h1 != h2:
        only_1 = set(h1) - set(h2)
        only_2 = set(h2) - set(h1)
        print(f"  Only in run 1: {only_1}")
        print(f"  Only in run 2: {only_2}")

    # Compare unsorted (order-sensitive)
    u1 = r1.trades[0]['holdings'] if r1.trades else []
    u2 = r2.trades[0]['holdings'] if r2.trades else []
    print(f"First-rebalance holdings identical (order): {u1 == u2}")

if __name__ == "__main__":
    main()
