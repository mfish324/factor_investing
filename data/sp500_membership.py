"""
Point-in-time S&P 500 membership.

Sources the current member list and the changes log from Wikipedia, stores
both in SQLite, and answers `members_on(date)` by replaying the changes
backward from today's snapshot.

Wikipedia is the de-facto public authoritative source for S&P 500 membership
history; the changes table goes back decades and is regularly maintained.
"""

from __future__ import annotations

import io
import logging
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
USER_AGENT = "factor-investing/1.0 (educational backtest research)"

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "sp500_membership.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sp500_changes (
    effective_date   TEXT NOT NULL,
    added_ticker     TEXT,
    added_security   TEXT,
    removed_ticker   TEXT,
    removed_security TEXT,
    reason           TEXT,
    PRIMARY KEY (effective_date, added_ticker, removed_ticker)
);
CREATE INDEX IF NOT EXISTS idx_changes_date ON sp500_changes (effective_date);

CREATE TABLE IF NOT EXISTS sp500_current_members (
    ticker        TEXT PRIMARY KEY,
    security      TEXT,
    sector        TEXT,
    sub_industry  TEXT,
    date_added    TEXT,
    cik           TEXT,
    fetched_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sp500_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _normalize_ticker(t: object) -> Optional[str]:
    """Coerce Wikipedia ticker strings to a standard form. NaN/empty -> None."""
    if t is None:
        return None
    if isinstance(t, float) and pd.isna(t):
        return None
    s = str(t).strip()
    if not s or s.lower() == "nan":
        return None
    # Wikipedia sometimes annotates with footnote markers like "ABC[1]" — strip them.
    s = re.sub(r"\[\d+\]", "", s).strip()
    # Some entries use "BRK.B" while Polygon uses "BRK.B" or "BRKB" depending on context.
    # Keep the dotted form; downstream code can map if needed.
    return s.upper() if s else None


def _normalize_date(s: object) -> Optional[str]:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    text = str(s).strip()
    # Wikipedia uses formats like "May 7, 2026" or "2024-09-23". Try both.
    for fmt in ("%B %d, %Y", "%Y-%m-%d", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Fallback: pandas parser
    try:
        return pd.to_datetime(text).strftime("%Y-%m-%d")
    except Exception:
        return None


def fetch_wikipedia_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (current_members_df, changes_df). Raises on HTTP error."""
    r = requests.get(WIKIPEDIA_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    tables = pd.read_html(io.StringIO(r.text))
    if len(tables) < 2:
        raise RuntimeError(
            f"Expected >= 2 tables on Wikipedia page, found {len(tables)}"
        )

    members = tables[0].copy()
    changes = tables[1].copy()
    return members, changes


def _normalize_changes(changes: pd.DataFrame) -> pd.DataFrame:
    """Flatten the multi-index columns into added_ticker / added_security / etc."""
    if isinstance(changes.columns, pd.MultiIndex):
        new_cols = []
        for top, sub in changes.columns:
            top = str(top).strip()
            sub = str(sub).strip()
            if top == sub:
                new_cols.append(top)
            else:
                new_cols.append(f"{top}.{sub}")
        changes = changes.copy()
        changes.columns = new_cols

    column_map = {
        "Effective Date": "effective_date",
        "Effective Date.Effective Date": "effective_date",
        "Date.Date": "effective_date",
        "Date": "effective_date",
        "Added.Ticker": "added_ticker",
        "Added.Security": "added_security",
        "Removed.Ticker": "removed_ticker",
        "Removed.Security": "removed_security",
        "Reason": "reason",
        "Reason.Reason": "reason",
    }
    rename = {c: column_map[c] for c in changes.columns if c in column_map}
    changes = changes.rename(columns=rename)

    expected = {"effective_date", "added_ticker", "added_security",
                "removed_ticker", "removed_security", "reason"}
    missing = expected - set(changes.columns)
    if missing:
        raise RuntimeError(
            f"Wikipedia changes table missing expected columns: {missing}. "
            f"Got: {list(changes.columns)}"
        )

    changes = changes.assign(
        effective_date=changes["effective_date"].apply(_normalize_date),
        added_ticker=changes["added_ticker"].apply(_normalize_ticker),
        added_security=changes["added_security"].astype(str).where(
            changes["added_security"].notna(), None
        ),
        removed_ticker=changes["removed_ticker"].apply(_normalize_ticker),
        removed_security=changes["removed_security"].astype(str).where(
            changes["removed_security"].notna(), None
        ),
        reason=changes["reason"].astype(str).where(changes["reason"].notna(), None),
    )

    # Drop rows with no usable date
    changes = changes[changes["effective_date"].notna()].copy()

    # Drop rows where neither side has a ticker (rare, but Wikipedia has some
    # purely textual annotations).
    has_action = changes["added_ticker"].notna() | changes["removed_ticker"].notna()
    changes = changes[has_action].copy()
    return changes[
        ["effective_date", "added_ticker", "added_security",
         "removed_ticker", "removed_security", "reason"]
    ]


def _normalize_current(members: pd.DataFrame) -> pd.DataFrame:
    rename = {
        "Symbol": "ticker",
        "Security": "security",
        "GICS Sector": "sector",
        "GICS Sub-Industry": "sub_industry",
        "Date added": "date_added",
        "CIK": "cik",
    }
    members = members.rename(columns=rename)
    members["ticker"] = members["ticker"].apply(_normalize_ticker)
    members["date_added"] = members["date_added"].apply(_normalize_date)
    members["cik"] = members["cik"].astype(str)
    members = members.dropna(subset=["ticker"])
    keep = ["ticker", "security", "sector", "sub_industry", "date_added", "cik"]
    return members[keep].drop_duplicates(subset=["ticker"]).reset_index(drop=True)


class MembershipDB:
    """SQLite-backed historical S&P 500 membership."""

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

    def refresh_from_wikipedia(self) -> dict:
        """Fetch and normalize the Wikipedia tables. Returns counts."""
        logger.info("Fetching S&P 500 tables from Wikipedia...")
        raw_members, raw_changes = fetch_wikipedia_tables()
        members = _normalize_current(raw_members)
        changes = _normalize_changes(raw_changes)
        fetched_at = datetime.utcnow().isoformat(timespec="seconds")

        with self._conn() as conn:
            conn.execute("DELETE FROM sp500_current_members")
            conn.executemany(
                """INSERT INTO sp500_current_members
                   (ticker, security, sector, sub_industry, date_added, cik, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        r.ticker, r.security, r.sector, r.sub_industry,
                        r.date_added, r.cik, fetched_at,
                    )
                    for r in members.itertuples(index=False)
                ],
            )
            conn.execute("DELETE FROM sp500_changes")
            conn.executemany(
                """INSERT OR IGNORE INTO sp500_changes
                   (effective_date, added_ticker, added_security,
                    removed_ticker, removed_security, reason)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        r.effective_date, r.added_ticker, r.added_security,
                        r.removed_ticker, r.removed_security, r.reason,
                    )
                    for r in changes.itertuples(index=False)
                ],
            )
            conn.execute(
                "INSERT OR REPLACE INTO sp500_meta (key, value) VALUES (?, ?)",
                ("last_fetch", fetched_at),
            )
            conn.execute(
                "INSERT OR REPLACE INTO sp500_meta (key, value) VALUES (?, ?)",
                ("source", WIKIPEDIA_URL),
            )

        return {
            "current_members": len(members),
            "changes": len(changes),
            "fetched_at": fetched_at,
        }

    def current_members(self) -> set[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT ticker FROM sp500_current_members"
            ).fetchall()
        return {r["ticker"] for r in rows if r["ticker"]}

    def changes(self) -> pd.DataFrame:
        with self._conn() as conn:
            return pd.read_sql_query(
                "SELECT * FROM sp500_changes ORDER BY effective_date", conn
            )

    def members_on(self, date: str | datetime | pd.Timestamp) -> set[str]:
        """
        Return the set of S&P 500 tickers that were members on `date`.

        Algorithm: start from today's member list, walk every change with
        `effective_date > date` and undo it (additions become non-members,
        removals come back as members).
        """
        ts = pd.Timestamp(date).strftime("%Y-%m-%d")
        members = self.current_members()
        if not members:
            raise RuntimeError(
                "No current member list found. Run refresh_from_wikipedia()."
            )
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT effective_date, added_ticker, removed_ticker
                   FROM sp500_changes
                   WHERE effective_date > ?
                   ORDER BY effective_date DESC""",
                (ts,),
            ).fetchall()

        for row in rows:
            added = row["added_ticker"]
            removed = row["removed_ticker"]
            # Undo the change to get earlier-membership.
            if added:
                members.discard(added)
            if removed:
                members.add(removed)
        return members

    def status(self) -> dict:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT key, value FROM sp500_meta"
            ).fetchall()
            n_current = conn.execute(
                "SELECT COUNT(*) AS c FROM sp500_current_members"
            ).fetchone()["c"]
            n_changes = conn.execute(
                "SELECT COUNT(*) AS c FROM sp500_changes"
            ).fetchone()["c"]
            min_date = conn.execute(
                "SELECT MIN(effective_date) AS d FROM sp500_changes"
            ).fetchone()["d"]
            max_date = conn.execute(
                "SELECT MAX(effective_date) AS d FROM sp500_changes"
            ).fetchone()["d"]
        meta = {row["key"]: row["value"] for row in rows}
        return {
            "current_members": n_current,
            "changes": n_changes,
            "earliest_change": min_date,
            "latest_change": max_date,
            **meta,
        }
