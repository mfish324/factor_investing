"""
Point-in-time view over per-ticker DataFrames.

Models receive this in place of raw dicts during a backtest. It pre-truncates
each ticker's DataFrame to rows on or before `as_of`, making look-ahead bias
architecturally impossible: the future data is not reachable from the view.

Used for both prices (date column = 'date') and financials (filing_date).
"""

from typing import Dict, Iterator, Optional
import pandas as pd


class PointInTimeView:
    """
    Read-only dict-like view that exposes only data on or before `as_of`.

    Wraps a dict of {ticker -> DataFrame}. Each frame is truncated once at
    construction time to rows with the date column <= as_of (or the index
    if no date column is supplied / found). Tickers whose truncated frame is
    empty are dropped.

    The view exposes the standard read-only dict protocol (`in`, `[]`, `.get()`,
    `.keys()`, `.items()`, `.values()`, iteration, `len()`, truthiness) so it
    drops in wherever a `Dict[str, pd.DataFrame]` was previously accepted —
    no model changes required.
    """

    def __init__(
        self,
        data: Optional[Dict[str, pd.DataFrame]],
        as_of,
        date_column: str = "date",
    ):
        self._as_of = pd.Timestamp(as_of)
        self._date_column = date_column
        self._cache: Dict[str, pd.DataFrame] = {}

        if not data:
            return

        for key, df in data.items():
            truncated = self._truncate(df)
            if truncated is not None and not truncated.empty:
                self._cache[key] = truncated

    def _truncate(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        if df is None or len(df) == 0:
            return df
        col = self._date_column
        if col in df.columns:
            mask = pd.to_datetime(df[col], errors="coerce") <= self._as_of
            return df.loc[mask]
        # Fall back to index if the index is datetime-like
        try:
            idx = pd.to_datetime(df.index, errors="raise")
            return df.loc[idx <= self._as_of]
        except (TypeError, ValueError):
            return df

    @property
    def as_of(self) -> pd.Timestamp:
        return self._as_of

    @property
    def date_column(self) -> str:
        return self._date_column

    # --- read-only dict protocol ---
    def __contains__(self, key) -> bool:
        return key in self._cache

    def __getitem__(self, key) -> pd.DataFrame:
        return self._cache[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._cache)

    def __len__(self) -> int:
        return len(self._cache)

    def __bool__(self) -> bool:
        return bool(self._cache)

    def get(self, key, default=None):
        return self._cache.get(key, default)

    def keys(self):
        return self._cache.keys()

    def items(self):
        return self._cache.items()

    def values(self):
        return self._cache.values()

    def __repr__(self) -> str:
        return (
            f"PointInTimeView(as_of={self._as_of.date()}, "
            f"date_column={self._date_column!r}, n_keys={len(self._cache)})"
        )


def truncate_one(df: Optional[pd.DataFrame], as_of, date_column: str = "date") -> Optional[pd.DataFrame]:
    """Truncate a single DataFrame (e.g., benchmark prices) to <= as_of."""
    if df is None or len(df) == 0:
        return df
    ts = pd.Timestamp(as_of)
    if date_column in df.columns:
        return df.loc[pd.to_datetime(df[date_column], errors="coerce") <= ts]
    try:
        idx = pd.to_datetime(df.index, errors="raise")
        return df.loc[idx <= ts]
    except (TypeError, ValueError):
        return df
