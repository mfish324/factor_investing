"""
Tests for the trading risk controls added to PortfolioManager:
- position cap + pro-rata redistribution, with structural cash buffer
- turnover guard (aborts a rebalance that would trade too much of the portfolio)
- fill verification (a submitted-but-unfilled order must not count as executed)
"""

from datetime import datetime

import pytest

from trading.alpaca_client import Position, Order
from trading.portfolio_manager import PortfolioManager, TurnoverGuardError


def _order(order_id, symbol, side, status='filled'):
    return Order(
        id=order_id, symbol=symbol, side=side, qty=1, filled_qty=1,
        status=status, submitted_at=datetime.now(), filled_at=datetime.now()
    )


class FakeAlpacaClient:
    """Minimal stand-in for AlpacaClient, no network calls."""

    def __init__(self, portfolio_value, positions=None, fills_orders=True):
        self.portfolio_value = portfolio_value
        self._positions = positions or []
        self.fills_orders = fills_orders
        self.submitted = []

    def get_account(self):
        held = sum(p.market_value for p in self._positions)
        return {'portfolio_value': self.portfolio_value, 'cash': self.portfolio_value - held}

    def get_positions(self):
        return self._positions

    def submit_notional_order(self, symbol, notional, side):
        order = _order(f"order-{symbol}-{side}", symbol, side, status='new')
        self.submitted.append(order)
        return order

    def close_position(self, symbol):
        order = _order(f"close-{symbol}", symbol, 'sell')
        self.submitted.append(order)
        return order

    def wait_for_order_fill(self, order_id, timeout_seconds=60, poll_interval=1.0):
        if self.fills_orders:
            return _order(order_id, order_id.split('-')[1], 'buy')
        return None


class TestTargetWeights:
    def test_cap_and_redistribute_with_cash_buffer(self):
        pm = PortfolioManager(
            FakeAlpacaClient(10_000),
            max_position_pct=0.5,
            cash_buffer_pct=0.1,
        )
        weights = pm._target_weights(
            ['A', 'B', 'C'],
            custom_weights={'A': 0.7, 'B': 0.2, 'C': 0.1}
        )

        assert weights['A'] == pytest.approx(0.45)   # capped at 0.5, then *0.9 buffer
        assert weights['B'] == pytest.approx(0.3)
        assert weights['C'] == pytest.approx(0.15)
        assert max(weights.values()) <= 0.5
        assert sum(weights.values()) == pytest.approx(0.9)

    def test_no_cap_needed_still_applies_cash_buffer(self):
        pm = PortfolioManager(
            FakeAlpacaClient(10_000),
            max_position_pct=0.5,
            cash_buffer_pct=0.02,
        )
        weights = pm._target_weights(['A', 'B', 'C'])
        assert sum(weights.values()) == pytest.approx(0.98)
        for w in weights.values():
            assert w == pytest.approx((1 / 3) * 0.98)


class TestTurnoverGuard:
    # max_position_pct=1.0 (uncapped) isolates the turnover guard from the
    # position-cap logic, which would otherwise shrink a single-symbol target
    # below the turnover threshold on its own.

    def test_large_rebalance_is_blocked_without_force(self):
        client = FakeAlpacaClient(10_000, positions=[])
        pm = PortfolioManager(client, max_position_pct=1.0, max_rebalance_turnover_pct=0.6)

        with pytest.raises(TurnoverGuardError):
            pm.execute_rebalance(target_symbols=['AAA'], strategy_name='test')

        # Nothing should have been submitted before the guard raised.
        assert client.submitted == []

    def test_large_rebalance_dry_run_previews_without_raising(self):
        # dry_run must still show what WOULD happen even when it would trip
        # the guard -- that's the whole point of previewing before --force.
        client = FakeAlpacaClient(10_000, positions=[])
        pm = PortfolioManager(client, max_position_pct=1.0, max_rebalance_turnover_pct=0.6)

        result = pm.execute_rebalance(
            target_symbols=['AAA'], strategy_name='test', dry_run=True
        )

        assert result.portfolio_value_before == result.portfolio_value_after == 10_000
        assert client.submitted == []

    def test_large_rebalance_proceeds_with_force(self):
        client = FakeAlpacaClient(10_000, positions=[])
        pm = PortfolioManager(client, max_position_pct=1.0, max_rebalance_turnover_pct=0.6)

        result = pm.execute_rebalance(
            target_symbols=['AAA'], strategy_name='test', force=True
        )

        assert len(result.trades_executed) == 1
        assert result.trades_failed == []
        assert result.trades_unfilled == []


class TestNotionalRounding:
    # Alpaca's notional order API rejects amounts with more than 2 decimal
    # places (error 42210000) -- caught live when a real rebalance's 30 buy
    # orders all failed because portfolio_value * weight produced amounts
    # like $3789.36518...

    def test_calculate_trades_notional_has_at_most_2_decimal_places(self):
        client = FakeAlpacaClient(114_889.16, positions=[])
        pm = PortfolioManager(client)

        # An odd portfolio value with an odd number of symbols is exactly the
        # kind of division that produces long float tails.
        symbols = ['MU', 'WDC', 'STX', 'WELL', 'NTAP', 'GILD', 'FTNT']
        trades = pm.calculate_trades(symbols)

        for t in trades:
            cents = round(t.notional * 100)
            assert t.notional == pytest.approx(cents / 100, abs=1e-9), (
                f"{t.symbol} notional {t.notional} has more than 2 decimal places"
            )


class TestFillVerification:
    def test_unfilled_order_is_not_counted_as_executed(self):
        client = FakeAlpacaClient(10_000, positions=[], fills_orders=False)
        pm = PortfolioManager(client, max_rebalance_turnover_pct=0.6)

        result = pm.execute_rebalance(
            target_symbols=['AAA'], strategy_name='test', force=True
        )

        assert result.trades_executed == []
        assert len(result.trades_unfilled) == 1
        assert result.trades_unfilled[0][0].symbol == 'AAA'
