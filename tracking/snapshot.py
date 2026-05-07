"""
Backfill and daily-update logic for the shadow tracker.

Two entry points:

- `backfill_strategy(...)` runs the full BacktestEngine for a strategy from
  start_date to end_date and writes the daily equity curve plus per-rebalance
  picks/holdings into the shadow DB. This is the one-time bootstrap.

- `update_strategy_daily(...)` does an incremental update for a single trading
  day after the backfill. It looks up current holdings, marks today's portfolio
  value using close prices, and (on rebalance days) re-runs the model to choose
  a new portfolio.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine import BacktestEngine
from backtesting.metrics import BacktestResult
from .shadow_db import ShadowDB

logger = logging.getLogger(__name__)

INITIAL_CAPITAL = 100_000.0


def _equity_curve_from_returns(returns: pd.Series, initial_capital: float) -> pd.DataFrame:
    """Convert daily returns -> per-day (date, equity, ret, cum_ret, drawdown)."""
    if returns.empty:
        return pd.DataFrame(
            columns=["date", "equity", "daily_return", "cumulative_return", "drawdown"]
        )
    cum = (1 + returns).cumprod()
    equity = initial_capital * cum
    rolling_max = cum.cummax()
    drawdown = cum / rolling_max - 1
    df = pd.DataFrame(
        {
            "date": returns.index,
            "equity": equity.values,
            "daily_return": returns.values,
            "cumulative_return": (cum - 1).values,
            "drawdown": drawdown.values,
        }
    )
    return df


def backfill_strategy(
    db: ShadowDB,
    strategy_name: str,
    model,
    financials,
    prices,
    market_caps,
    benchmark_prices,
    shares_outstanding,
    start_date: str,
    end_date: str,
    rebalance_freq: str = "monthly",
    portfolio_size: int = 30,
    initial_capital: float = INITIAL_CAPITAL,
    show_progress: bool = False,
    membership_db=None,
) -> BacktestResult:
    """Run the engine and dump its output into the shadow DB."""
    engine = BacktestEngine(
        model=model,
        start_date=start_date,
        end_date=end_date,
        rebalance_freq=rebalance_freq,
        portfolio_size=portfolio_size,
        initial_capital=initial_capital,
        membership_db=membership_db,
    )
    result = engine.run(
        financials=financials,
        prices=prices,
        market_caps=market_caps,
        benchmark_prices=benchmark_prices,
        shares_outstanding=shares_outstanding,
        show_progress=show_progress,
    )

    # Equity curve
    curve = _equity_curve_from_returns(result.returns, initial_capital)
    db.replace_equity_curve(strategy_name, curve)

    # Picks (one snapshot per rebalance with rank order). The engine returns
    # `trades`: each entry has 'date', 'holdings'. We treat the holdings list
    # as ordered by the model's selection rank and don't have per-pick scores
    # at this layer, so score is left null.
    last_holdings: dict[str, float] = {}
    last_rebalance_date: Optional[str] = None
    for tr in result.trades:
        rebalance_date = pd.Timestamp(tr["date"]).strftime("%Y-%m-%d")
        holdings = list(tr["holdings"])
        n = len(holdings)
        if n == 0:
            continue
        weight = 1.0 / n
        picks = [(t, i + 1, None) for i, t in enumerate(holdings)]
        db.append_picks(rebalance_date, strategy_name, picks)
        last_holdings = {t: weight for t in holdings}
        last_rebalance_date = rebalance_date

    if last_rebalance_date is not None:
        db.replace_holdings(strategy_name, last_rebalance_date, last_holdings)

    db.upsert_meta(
        strategy=strategy_name,
        initial_capital=initial_capital,
        backfill_start=start_date,
        last_update=end_date,
        notes=f"Backfilled via BacktestEngine on {datetime.now().isoformat(timespec='seconds')}",
    )

    return result


def update_strategy_daily(
    db: ShadowDB,
    strategy_name: str,
    model,
    financials,
    prices,
    market_caps,
    benchmark_prices,
    shares_outstanding,
    target_date: str,
    rebalance_freq: str = "monthly",
    portfolio_size: int = 30,
) -> dict:
    """
    Incremental update for one trading day.

    Strategy: rerun the engine for [last_recorded_date, target_date]. The
    engine is fast for short windows. This keeps shadow tracking exactly
    consistent with backfilled history (same code path) at the cost of being
    slightly less efficient than a true single-day update.

    Returns a small dict with `target_date`, `last_equity`, `last_return`.
    """
    last_seen = db.get_latest_equity_date(strategy_name)
    if last_seen is None:
        raise RuntimeError(
            f"{strategy_name}: no backfill found. Run `shadow backfill` first."
        )

    if last_seen >= target_date:
        return {
            "strategy": strategy_name,
            "target_date": target_date,
            "skipped": True,
            "reason": f"already have data through {last_seen}",
        }

    # Re-run from a buffer before last_seen so the rebalance schedule lines up
    # with how the historical backfill chose its rebalance dates. A 60-day
    # buffer is enough to recover the most recent rebalance and continue.
    buffer_start = (pd.Timestamp(last_seen) - pd.Timedelta(days=60)).strftime("%Y-%m-%d")

    engine = BacktestEngine(
        model=model,
        start_date=buffer_start,
        end_date=target_date,
        rebalance_freq=rebalance_freq,
        portfolio_size=portfolio_size,
        initial_capital=INITIAL_CAPITAL,
    )
    result = engine.run(
        financials=financials,
        prices=prices,
        market_caps=market_caps,
        benchmark_prices=benchmark_prices,
        shares_outstanding=shares_outstanding,
        show_progress=False,
    )

    # Splice: keep historical rows up to last_seen, append new rows after.
    new_rows = _equity_curve_from_returns(result.returns, INITIAL_CAPITAL)
    new_rows = new_rows[new_rows["date"] > pd.Timestamp(last_seen)]

    # The new rows' equity is computed assuming initial_capital at buffer_start.
    # Rescale to continue from the actual last_seen equity.
    if not new_rows.empty:
        existing = db.get_equity_curve(strategy_name)
        last_equity = float(existing.iloc[-1]["equity"])
        # Apply the daily returns from new_rows to last_equity to get proper equity
        eq_series = last_equity * (1 + new_rows["daily_return"]).cumprod()
        new_rows = new_rows.assign(equity=eq_series.values)
        # cumulative_return needs to anchor to the strategy's full history
        full_cum = float(existing.iloc[-1]["cumulative_return"])
        new_cum = (1 + full_cum) * (1 + new_rows["daily_return"]).cumprod() - 1
        new_rows = new_rows.assign(cumulative_return=new_cum.values)
        # Drawdown is computed against the running max across full history
        running_max = max(existing["cumulative_return"].max() + 1, full_cum + 1)
        new_dd = ((new_cum + 1) / np.maximum.accumulate(np.append(running_max, (new_cum + 1).values))[1:]) - 1
        new_rows = new_rows.assign(drawdown=new_dd)

        for row in new_rows.itertuples(index=False):
            db.append_equity_row(
                date=pd.Timestamp(row.date).strftime("%Y-%m-%d"),
                strategy=strategy_name,
                equity=float(row.equity),
                daily_return=float(row.daily_return),
                cumulative_return=float(row.cumulative_return),
                drawdown=float(row.drawdown),
            )

    # Latest holdings come from the engine's last rebalance trade.
    if result.trades:
        last_tr = result.trades[-1]
        rb_date = pd.Timestamp(last_tr["date"]).strftime("%Y-%m-%d")
        holdings = list(last_tr["holdings"])
        if holdings:
            weight = 1.0 / len(holdings)
            db.replace_holdings(strategy_name, rb_date, {t: weight for t in holdings})
            db.append_picks(
                rb_date,
                strategy_name,
                [(t, i + 1, None) for i, t in enumerate(holdings)],
            )

    db.upsert_meta(
        strategy=strategy_name,
        initial_capital=INITIAL_CAPITAL,
        last_update=target_date,
    )

    return {
        "strategy": strategy_name,
        "target_date": target_date,
        "skipped": False,
        "rows_added": len(new_rows),
    }
