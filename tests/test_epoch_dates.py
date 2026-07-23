"""
Regression tests for the epoch-integer filing_date bug (found 2026-07-18).

DataFrame.to_json/read_json round-trips serialize datetime columns to epoch
integers. Naive pd.to_datetime reads bare ints as NANOSECONDS -> ~1970, which
made PointInTimeView's `filing_date <= as_of` mask all-True: cached financials
were NEVER truncated, silently reintroducing look-ahead bias for every run
that hit the financials cache.
"""

from io import StringIO

import pandas as pd
import pytest

from backtesting.point_in_time import PointInTimeView, truncate_one
from data.corporate_actions import flexible_to_datetime


EPOCH_S_2022 = int(pd.Timestamp("2022-06-15").timestamp())
EPOCH_S_2025 = int(pd.Timestamp("2025-06-15").timestamp())


class TestFlexibleToDatetime:
    def test_epoch_seconds(self):
        out = flexible_to_datetime(pd.Series([EPOCH_S_2022]))
        assert out.iloc[0] == pd.Timestamp("2022-06-15")

    def test_epoch_milliseconds(self):
        out = flexible_to_datetime(pd.Series([EPOCH_S_2022 * 1000]))
        assert out.iloc[0] == pd.Timestamp("2022-06-15")

    def test_epoch_nanoseconds(self):
        out = flexible_to_datetime(pd.Series([EPOCH_S_2022 * 10**9]))
        assert out.iloc[0] == pd.Timestamp("2022-06-15")

    def test_strings_and_timestamps_unchanged(self):
        out = flexible_to_datetime(pd.Series(["2022-06-15", "2025-01-02"]))
        assert out.iloc[0] == pd.Timestamp("2022-06-15")
        out2 = flexible_to_datetime(pd.Series([pd.Timestamp("2022-06-15")]))
        assert out2.iloc[0] == pd.Timestamp("2022-06-15")


class TestPointInTimeWithEpochInts:
    def test_epoch_second_filing_dates_are_truncated(self):
        # The bug: with int64 epoch-second filing dates, nothing was dropped.
        fin = pd.DataFrame({
            "filing_date": [EPOCH_S_2025, EPOCH_S_2022],  # 2025 filing is future
            "net_income": [200.0, 100.0],
        })
        view = PointInTimeView({"AAA": fin}, as_of="2023-01-01",
                               date_column="filing_date")
        assert len(view["AAA"]) == 1
        assert view["AAA"].iloc[0]["net_income"] == 100.0

    def test_truncate_one_with_epoch_ints(self):
        df = pd.DataFrame({
            "date": [EPOCH_S_2022, EPOCH_S_2025],
            "close": [1.0, 2.0],
        })
        out = truncate_one(df, "2023-01-01")
        assert len(out) == 1

    def test_json_roundtrip_financials_are_truncated(self):
        # End-to-end shape of the real failure: datetime df -> to_json ->
        # read_json -> PIT view must still truncate.
        fin = pd.DataFrame({
            "filing_date": pd.to_datetime(["2025-06-15", "2022-06-15"]),
            "net_income": [200.0, 100.0],
        })
        roundtripped = pd.read_json(StringIO(fin.to_json()))
        view = PointInTimeView({"AAA": roundtripped}, as_of="2023-01-01",
                               date_column="filing_date")
        assert len(view["AAA"]) == 1
        assert view["AAA"].iloc[0]["net_income"] == 100.0


class TestCacheRoundTrip:
    def test_financials_cache_restores_datetime(self, tmp_path, monkeypatch):
        import data.cache as cache_mod
        cm = cache_mod.CacheManager.__new__(cache_mod.CacheManager)
        cm.db_path = str(tmp_path / "test_cache.db")
        cm._init_db()

        fin = pd.DataFrame({
            "filing_date": pd.to_datetime(["2025-06-15", "2022-06-15"]),
            "net_income": [200.0, 100.0],
        })
        cm.set_financials("AAA", fin, period="annual")
        out = cm.get_financials("AAA", period="annual")
        assert pd.api.types.is_datetime64_any_dtype(out["filing_date"])
        assert out["filing_date"].iloc[0] == pd.Timestamp("2025-06-15")
