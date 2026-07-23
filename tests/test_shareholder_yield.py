"""
Tests for the shareholder yield factor fixes:
- buyback yield must be split-adjusted (a 4:1 split is not a -300% buyback)
- dividend yield uses real per-share dividends, split-adjusted, PIT-filtered
"""

import pandas as pd
import pytest

from models.shareholder_yield import ShareholderYieldFactors


@pytest.fixture
def factors():
    return ShareholderYieldFactors()


def _financials(rows):
    """rows: list of (filing_date, shares_outstanding)  (most recent first)"""
    return pd.DataFrame([
        {"filing_date": pd.Timestamp(fd), "shares_outstanding": sh}
        for fd, sh in rows
    ])


def _prices(last_date="2024-06-28", close=100.0):
    dates = pd.date_range(end=last_date, periods=10, freq="B")
    return pd.DataFrame({"date": dates, "close": [close] * len(dates)})


class TestBuybackYield:
    def test_no_split_real_buyback(self, factors):
        fin = _financials([("2024-02-01", 90.0), ("2023-02-01", 100.0)])
        yld = factors._buyback_yield(fin, market_cap=1e9, splits=[])
        assert yld == pytest.approx(0.10)

    def test_forward_split_between_filings_is_not_dilution(self, factors):
        # 4:1 split between the two filings: as-reported shares quadruple.
        # Unadjusted this reads as -300% "dilution"; adjusted it is ~0.
        fin = _financials([("2024-02-01", 400.0), ("2023-02-01", 100.0)])
        splits = [{"execution_date": "2023-06-15", "split_from": 1, "split_to": 4}]
        yld = factors._buyback_yield(fin, market_cap=1e9, splits=splits)
        assert yld == pytest.approx(0.0)

    def test_reverse_split_is_not_a_buyback(self, factors):
        # 1:10 reverse split: as-reported shares drop 10x, not a real buyback.
        fin = _financials([("2024-02-01", 10.0), ("2023-02-01", 100.0)])
        splits = [{"execution_date": "2023-06-15", "split_from": 10, "split_to": 1}]
        yld = factors._buyback_yield(fin, market_cap=1e9, splits=splits)
        assert yld == pytest.approx(0.0)

    def test_split_plus_buyback(self, factors):
        # 2:1 split AND a 5% buyback: 100 -> 190 as-reported (2x - 5%).
        fin = _financials([("2024-02-01", 190.0), ("2023-02-01", 100.0)])
        splits = [{"execution_date": "2023-06-15", "split_from": 1, "split_to": 2}]
        yld = factors._buyback_yield(fin, market_cap=1e9, splits=splits)
        assert yld == pytest.approx(0.05)

    def test_missing_shares_returns_none(self, factors):
        fin = _financials([("2024-02-01", None), ("2023-02-01", 100.0)])
        assert factors._buyback_yield(fin, market_cap=1e9, splits=[]) is None


class TestDividendYield:
    def test_ttm_sum_over_price(self, factors):
        divs = [
            {"ex_dividend_date": "2024-05-10", "cash_amount": 1.0},
            {"ex_dividend_date": "2024-02-09", "cash_amount": 1.0},
            {"ex_dividend_date": "2023-11-10", "cash_amount": 1.0},
            {"ex_dividend_date": "2023-08-11", "cash_amount": 1.0},
            # Older than 12 months: excluded
            {"ex_dividend_date": "2023-05-12", "cash_amount": 1.0},
        ]
        yld = factors._dividend_yield(_prices(close=100.0), [], divs)
        assert yld == pytest.approx(0.04)

    def test_point_in_time_excludes_future_ex_dates(self, factors):
        divs = [
            {"ex_dividend_date": "2024-05-10", "cash_amount": 1.0},
            # After as_of: invisible at the rebalance date
            {"ex_dividend_date": "2024-08-09", "cash_amount": 1.0},
        ]
        yld = factors._dividend_yield(
            _prices(close=100.0), [], divs, as_of="2024-06-28"
        )
        assert yld == pytest.approx(0.01)

    def test_split_adjusts_per_share_amounts(self, factors):
        # $4/share declared pre-split; 4:1 split afterwards means $1/share
        # on today's basis, matching today's-basis price of $100.
        divs = [{"ex_dividend_date": "2024-01-10", "cash_amount": 4.0}]
        splits = [{"execution_date": "2024-03-01", "split_from": 1, "split_to": 4}]
        yld = factors._dividend_yield(_prices(close=100.0), splits, divs)
        assert yld == pytest.approx(0.01)

    def test_no_data_is_none_no_dividends_is_zero(self, factors):
        assert factors._dividend_yield(_prices(), [], None) is None
        assert factors._dividend_yield(_prices(), [], []) == pytest.approx(0.0)


class TestCalculateUniverse:
    def test_plumbs_per_ticker_actions(self, factors):
        fin = {"AAA": _financials([("2024-02-01", 95.0), ("2023-02-01", 100.0)])}
        prices = {"AAA": _prices(close=50.0)}
        mcaps = {"AAA": 1e9}
        divs = {"AAA": [{"ex_dividend_date": "2024-05-10", "cash_amount": 0.5}]}
        df = factors.calculate_universe(
            fin, prices, mcaps,
            splits_by_ticker={"AAA": []},
            dividends_by_ticker=divs,
        )
        assert df.loc["AAA", "buyback_yield"] == pytest.approx(0.05)
        assert df.loc["AAA", "dividend_yield"] == pytest.approx(0.01)
