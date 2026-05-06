"""
Unit tests for PointInTimeView. The architectural guarantee: data dated after
`as_of` is unreachable through the view.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.point_in_time import PointInTimeView, truncate_one


def _make_prices(start: str, end: str) -> pd.DataFrame:
    dates = pd.date_range(start, end, freq="B")
    return pd.DataFrame({"date": dates, "close": range(len(dates))})


def _make_filings(years):
    """Each row has a filing_date column."""
    return pd.DataFrame(
        {"filing_date": [pd.Timestamp(f"{y}-03-15") for y in years], "rev": list(years)}
    )


def test_view_drops_rows_after_as_of():
    prices = {
        "AAPL": _make_prices("2020-01-01", "2026-05-01"),
        "MSFT": _make_prices("2020-01-01", "2026-05-01"),
    }
    view = PointInTimeView(prices, as_of="2023-06-30", date_column="date")
    for ticker, df in view.items():
        assert pd.to_datetime(df["date"]).max() <= pd.Timestamp("2023-06-30"), ticker


def test_view_works_with_filing_date():
    fin = {
        "AAPL": _make_filings([2018, 2019, 2020, 2021, 2022, 2023, 2024]),
    }
    view = PointInTimeView(fin, as_of="2021-06-30", date_column="filing_date")
    df = view["AAPL"]
    assert df["filing_date"].max() <= pd.Timestamp("2021-06-30")
    assert set(df["rev"]) == {2018, 2019, 2020, 2021}


def test_view_drops_empty_keys():
    """Tickers whose truncated frame is empty should not appear in the view."""
    prices = {
        "OLD": _make_prices("2018-01-01", "2018-12-31"),
        "NEW": _make_prices("2024-01-01", "2026-01-01"),
    }
    view = PointInTimeView(prices, as_of="2020-01-01", date_column="date")
    assert "OLD" in view
    assert "NEW" not in view  # all rows are after as_of -> dropped


def test_view_dict_protocol():
    prices = {"AAPL": _make_prices("2020-01-01", "2024-01-01")}
    view = PointInTimeView(prices, as_of="2022-06-30")
    assert "AAPL" in view
    assert view.get("AAPL") is not None
    assert view.get("MISSING") is None
    assert len(view) == 1
    assert bool(view) is True
    assert list(view) == ["AAPL"]
    assert list(view.keys()) == ["AAPL"]
    assert next(iter(view.values())) is view["AAPL"]


def test_empty_view_is_falsy():
    view = PointInTimeView({}, as_of="2020-01-01")
    assert bool(view) is False
    assert len(view) == 0


def test_view_accepts_none_data():
    view = PointInTimeView(None, as_of="2020-01-01")
    assert len(view) == 0


def test_view_handles_missing_date_column_gracefully():
    """If the date column is absent and the index isn't datetime, return as-is."""
    df = pd.DataFrame({"a": [1, 2, 3]})  # no 'date' column, RangeIndex
    view = PointInTimeView({"X": df}, as_of="2020-01-01", date_column="date")
    assert "X" in view
    assert view["X"].equals(df)


def test_truncate_one():
    df = _make_prices("2020-01-01", "2024-12-31")
    truncated = truncate_one(df, as_of="2022-06-30")
    assert pd.to_datetime(truncated["date"]).max() <= pd.Timestamp("2022-06-30")


def test_truncate_one_handles_none():
    assert truncate_one(None, as_of="2020-01-01") is None


def test_view_is_immutable_to_caller_mutations():
    """Mutating the source dict after view construction does not affect the view."""
    prices = {"AAPL": _make_prices("2020-01-01", "2024-01-01")}
    view = PointInTimeView(prices, as_of="2022-06-30")
    n_before = len(view["AAPL"])
    prices["AAPL"] = _make_prices("2030-01-01", "2030-12-31")  # poison the source
    assert len(view["AAPL"]) == n_before  # view holds its own truncated copy
