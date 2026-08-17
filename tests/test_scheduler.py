"""
Tests for trading.scheduler.TradingScheduler.is_due() and the persisted
last-rebalance-time it depends on (StrategyTrader.get_last_rebalance_time).

TradingScheduler is constructed via object.__new__ to skip __init__, which
would otherwise build a real AlpacaClient/PolygonClient/model -- is_due() and
the rebalance-log persistence it reads from only depend on the attributes
set directly here.
"""

import json
from datetime import datetime, timedelta

import pytest

from trading.scheduler import TradingScheduler
from trading.strategy_trader import StrategyTrader


def _scheduler(frequency, day='monday'):
    s = object.__new__(TradingScheduler)
    s.rebalance_frequency = frequency
    s.rebalance_day = day
    return s


class TestIsDueWeekly:
    def test_due_on_matching_weekday_no_prior_rebalance(self):
        s = _scheduler('weekly', day='wednesday')
        wednesday = datetime(2026, 8, 19)  # a Wednesday
        assert s.is_due(wednesday, last_rebalance=None) is True

    def test_not_due_on_other_weekday(self):
        s = _scheduler('weekly', day='wednesday')
        thursday = datetime(2026, 8, 20)
        assert s.is_due(thursday, last_rebalance=None) is False

    def test_not_due_again_within_the_same_week(self):
        s = _scheduler('weekly', day='wednesday')
        wednesday = datetime(2026, 8, 19)
        last = wednesday - timedelta(days=1)
        assert s.is_due(wednesday, last_rebalance=last) is False


class TestIsDueMonthly:
    def test_due_on_first_trading_day(self):
        s = _scheduler('monthly')
        first = datetime(2026, 9, 1)  # a Tuesday
        assert s.is_due(first, last_rebalance=None) is True

    def test_not_due_mid_month(self):
        s = _scheduler('monthly')
        mid = datetime(2026, 9, 15)
        assert s.is_due(mid, last_rebalance=None) is False

    def test_not_due_again_same_month(self):
        s = _scheduler('monthly')
        first = datetime(2026, 9, 1)
        last = datetime(2026, 8, 20)  # 12 days before -- within the same rebalance cycle
        assert s.is_due(first, last_rebalance=last) is False


class TestIsDueQuarterly:
    def test_due_on_first_trading_day_of_quarter(self):
        s = _scheduler('quarterly')
        first = datetime(2026, 10, 1)
        assert s.is_due(first, last_rebalance=None) is True

    def test_not_due_outside_quarter_start_month(self):
        s = _scheduler('quarterly')
        mid_quarter = datetime(2026, 11, 1)
        assert s.is_due(mid_quarter, last_rebalance=None) is False

    def test_not_due_again_within_the_same_quarter(self):
        s = _scheduler('quarterly')
        first = datetime(2026, 10, 1)
        last = datetime(2026, 7, 2)  # ~90 days prior, previous quarter's rebalance
        # 90 days >= 80-day gap requirement, so a genuinely new quarter IS due
        assert s.is_due(first, last_rebalance=last) is True

        recent = datetime(2026, 9, 20)  # 11 days prior -- same cycle, not due
        assert s.is_due(first, last_rebalance=recent) is False


class TestLastRebalancePersistence:
    """
    Confirms StrategyTrader.get_last_rebalance_time() -- what is_due() is
    fed in real (non-test) use -- actually round-trips through the JSONL
    trade log, so due-date state survives a fresh process invocation
    (the whole point of --check-and-run being driven by an external scheduler).
    """

    class _FakeModel:
        name = "Test Model"

    def test_no_log_file_returns_none(self, tmp_path):
        trader = StrategyTrader(
            model=self._FakeModel(),
            alpaca_client=object(),
            polygon_client=object(),
            log_dir=tmp_path,
        )
        assert trader.get_last_rebalance_time() is None

    def test_reads_timestamp_of_last_log_entry(self, tmp_path):
        trader = StrategyTrader(
            model=self._FakeModel(),
            alpaca_client=object(),
            polygon_client=object(),
            log_dir=tmp_path,
        )
        log_file = trader._log_file_path()
        ts1 = datetime(2026, 7, 1, 10, 0, 0)
        ts2 = datetime(2026, 8, 1, 10, 0, 0)
        with open(log_file, 'w') as f:
            f.write(json.dumps({"timestamp": ts1.isoformat()}) + "\n")
            f.write(json.dumps({"timestamp": ts2.isoformat()}) + "\n")

        # A fresh StrategyTrader instance (simulating a new process) must
        # read the same persisted value back.
        trader2 = StrategyTrader(
            model=self._FakeModel(),
            alpaca_client=object(),
            polygon_client=object(),
            log_dir=tmp_path,
        )
        assert trader2.get_last_rebalance_time() == ts2

    def test_malformed_last_line_returns_none(self, tmp_path):
        trader = StrategyTrader(
            model=self._FakeModel(),
            alpaca_client=object(),
            polygon_client=object(),
            log_dir=tmp_path,
        )
        with open(trader._log_file_path(), 'w') as f:
            f.write("not json\n")
        assert trader.get_last_rebalance_time() is None
