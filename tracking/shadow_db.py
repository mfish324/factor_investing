"""
SQLite-backed store for shadow-tracked strategy state.

Tables:
- strategy_equity:   per-day equity / return / cumulative return / drawdown
- strategy_holdings: current portfolio per strategy (replaced on rebalance)
- strategy_picks:    snapshot of picks at each rebalance (with score/rank)
- strategy_meta:     per-strategy bookkeeping (last update, initial capital)
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "shadow.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS strategy_equity (
    date              TEXT NOT NULL,
    strategy          TEXT NOT NULL,
    equity            REAL NOT NULL,
    daily_return      REAL,
    cumulative_return REAL,
    drawdown          REAL,
    PRIMARY KEY (date, strategy)
);
CREATE INDEX IF NOT EXISTS idx_equity_strategy_date ON strategy_equity (strategy, date);

CREATE TABLE IF NOT EXISTS strategy_holdings (
    rebalance_date TEXT NOT NULL,
    strategy       TEXT NOT NULL,
    ticker         TEXT NOT NULL,
    weight         REAL NOT NULL,
    PRIMARY KEY (rebalance_date, strategy, ticker)
);
CREATE INDEX IF NOT EXISTS idx_holdings_strategy_date ON strategy_holdings (strategy, rebalance_date);

CREATE TABLE IF NOT EXISTS strategy_picks (
    rebalance_date TEXT NOT NULL,
    strategy       TEXT NOT NULL,
    ticker         TEXT NOT NULL,
    rank           INTEGER NOT NULL,
    score          REAL,
    PRIMARY KEY (rebalance_date, strategy, ticker)
);

CREATE TABLE IF NOT EXISTS strategy_meta (
    strategy        TEXT PRIMARY KEY,
    initial_capital REAL NOT NULL,
    backfill_start  TEXT,
    last_update     TEXT,
    notes           TEXT
);
"""


class ShadowDB:
    """Thin wrapper around the shadow-tracking SQLite store."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    # --- meta ---

    def upsert_meta(
        self,
        strategy: str,
        initial_capital: float,
        backfill_start: Optional[str] = None,
        last_update: Optional[str] = None,
        notes: Optional[str] = None,
    ):
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT * FROM strategy_meta WHERE strategy = ?", (strategy,)
            ).fetchone()
            if existing is None:
                conn.execute(
                    """INSERT INTO strategy_meta
                       (strategy, initial_capital, backfill_start, last_update, notes)
                       VALUES (?, ?, ?, ?, ?)""",
                    (strategy, initial_capital, backfill_start, last_update, notes),
                )
            else:
                # Keep existing values when caller doesn't supply new ones
                conn.execute(
                    """UPDATE strategy_meta SET
                          initial_capital = COALESCE(?, initial_capital),
                          backfill_start  = COALESCE(?, backfill_start),
                          last_update     = COALESCE(?, last_update),
                          notes           = COALESCE(?, notes)
                       WHERE strategy = ?""",
                    (initial_capital, backfill_start, last_update, notes, strategy),
                )

    def get_meta(self, strategy: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM strategy_meta WHERE strategy = ?", (strategy,)
            ).fetchone()
            return dict(row) if row else None

    def list_strategies(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT strategy FROM strategy_meta ORDER BY strategy"
            ).fetchall()
            return [r["strategy"] for r in rows]

    # --- equity curve ---

    def replace_equity_curve(self, strategy: str, df: pd.DataFrame):
        """
        Bulk-overwrite a strategy's equity curve.

        DataFrame columns required: date, equity, daily_return, cumulative_return, drawdown.
        """
        required = {"date", "equity", "daily_return", "cumulative_return", "drawdown"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"replace_equity_curve missing columns: {missing}")

        rows = [
            (
                pd.Timestamp(row.date).strftime("%Y-%m-%d"),
                strategy,
                float(row.equity),
                None if pd.isna(row.daily_return) else float(row.daily_return),
                None if pd.isna(row.cumulative_return) else float(row.cumulative_return),
                None if pd.isna(row.drawdown) else float(row.drawdown),
            )
            for row in df.itertuples(index=False)
        ]
        with self._conn() as conn:
            conn.execute("DELETE FROM strategy_equity WHERE strategy = ?", (strategy,))
            conn.executemany(
                """INSERT INTO strategy_equity
                   (date, strategy, equity, daily_return, cumulative_return, drawdown)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                rows,
            )

    def append_equity_row(
        self,
        date: str,
        strategy: str,
        equity: float,
        daily_return: Optional[float],
        cumulative_return: Optional[float],
        drawdown: Optional[float],
    ):
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO strategy_equity
                   (date, strategy, equity, daily_return, cumulative_return, drawdown)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (date, strategy, equity, daily_return, cumulative_return, drawdown),
            )

    def get_equity_curve(
        self,
        strategy: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        q = "SELECT date, equity, daily_return, cumulative_return, drawdown FROM strategy_equity WHERE strategy = ?"
        args: list = [strategy]
        if start:
            q += " AND date >= ?"
            args.append(start)
        if end:
            q += " AND date <= ?"
            args.append(end)
        q += " ORDER BY date"
        with self._conn() as conn:
            df = pd.read_sql_query(q, conn, params=args)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def get_latest_equity_date(self, strategy: str) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(date) AS d FROM strategy_equity WHERE strategy = ?",
                (strategy,),
            ).fetchone()
            return row["d"] if row and row["d"] else None

    # --- holdings ---

    def replace_holdings(self, strategy: str, rebalance_date: str, holdings: dict):
        """Replace this strategy's current holdings with `holdings: {ticker: weight}`."""
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM strategy_holdings WHERE strategy = ?",
                (strategy,),
            )
            conn.executemany(
                """INSERT INTO strategy_holdings (rebalance_date, strategy, ticker, weight)
                   VALUES (?, ?, ?, ?)""",
                [(rebalance_date, strategy, t, float(w)) for t, w in holdings.items()],
            )

    def get_current_holdings(self, strategy: str) -> pd.DataFrame:
        """Return the most recent holdings for a strategy."""
        with self._conn() as conn:
            df = pd.read_sql_query(
                """SELECT rebalance_date, ticker, weight
                   FROM strategy_holdings
                   WHERE strategy = ?
                   ORDER BY rebalance_date DESC, ticker""",
                conn,
                params=(strategy,),
            )
        return df

    # --- picks history ---

    def append_picks(
        self,
        rebalance_date: str,
        strategy: str,
        picks: Iterable[tuple[str, int, Optional[float]]],
    ):
        """`picks` is an iterable of (ticker, rank, score)."""
        rows = [(rebalance_date, strategy, t, int(r), s) for (t, r, s) in picks]
        with self._conn() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO strategy_picks
                   (rebalance_date, strategy, ticker, rank, score)
                   VALUES (?, ?, ?, ?, ?)""",
                rows,
            )

    def get_picks_history(
        self,
        strategy: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        q = """SELECT rebalance_date, ticker, rank, score FROM strategy_picks
               WHERE strategy = ?"""
        args: list = [strategy]
        if start:
            q += " AND rebalance_date >= ?"
            args.append(start)
        if end:
            q += " AND rebalance_date <= ?"
            args.append(end)
        q += " ORDER BY rebalance_date, rank"
        with self._conn() as conn:
            df = pd.read_sql_query(q, conn, params=args)
        if not df.empty:
            df["rebalance_date"] = pd.to_datetime(df["rebalance_date"])
        return df

    # --- summary ---

    def summary(self) -> pd.DataFrame:
        """One row per strategy: latest equity, total return, max drawdown."""
        with self._conn() as conn:
            df = pd.read_sql_query(
                """
                WITH agg AS (
                    SELECT
                        strategy,
                        MIN(date) AS start_date,
                        MAX(date) AS last_date,
                        MIN(drawdown) AS worst_drawdown,
                        MAX(cumulative_return) AS best_cumulative_return,
                        COUNT(*) AS n_days
                    FROM strategy_equity
                    GROUP BY strategy
                )
                SELECT
                    a.strategy,
                    m.initial_capital,
                    a.start_date,
                    a.last_date,
                    last_row.equity            AS last_equity,
                    last_row.cumulative_return AS last_cumulative_return,
                    a.worst_drawdown,
                    a.best_cumulative_return,
                    a.n_days
                FROM agg a
                LEFT JOIN strategy_meta m ON m.strategy = a.strategy
                LEFT JOIN strategy_equity last_row
                    ON last_row.strategy = a.strategy AND last_row.date = a.last_date
                ORDER BY last_cumulative_return DESC
                """,
                conn,
            )
        return df
