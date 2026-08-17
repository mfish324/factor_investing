"""
Portfolio manager for rebalancing to target allocations.
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .alpaca_client import AlpacaClient, Position, Order
from config import (
    MAX_POSITION_PCT,
    CASH_BUFFER_PCT,
    MAX_REBALANCE_TURNOVER_PCT,
    ORDER_FILL_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)


class TurnoverGuardError(Exception):
    """Raised when a rebalance would trade more of the portfolio than MAX_REBALANCE_TURNOVER_PCT."""


@dataclass
class Trade:
    """Represents a trade to execute."""
    symbol: str
    side: str  # 'buy' or 'sell'
    notional: float  # Dollar amount
    reason: str  # 'new', 'rebalance', 'exit'


@dataclass
class RebalanceResult:
    """Result of a rebalance operation."""
    timestamp: datetime
    strategy: str
    initial_positions: Dict[str, float]
    target_positions: Dict[str, float]
    trades_executed: List[Order]
    trades_failed: List[Tuple[Trade, str]]
    portfolio_value_before: float
    portfolio_value_after: float
    trades_unfilled: List[Tuple[Trade, Order]] = field(default_factory=list)


class PortfolioManager:
    """
    Manages portfolio rebalancing to target allocations.

    Handles the logic of:
    - Calculating trades needed to reach target allocation
    - Executing sells before buys (to free up cash)
    - Handling partial fills and errors
    """

    def __init__(
        self,
        alpaca_client: AlpacaClient,
        min_trade_notional: float = 1.0,
        max_drift_pct: float = 0.02,
        max_position_pct: float = MAX_POSITION_PCT,
        cash_buffer_pct: float = CASH_BUFFER_PCT,
        max_rebalance_turnover_pct: float = MAX_REBALANCE_TURNOVER_PCT,
    ):
        """
        Initialize portfolio manager.

        Args:
            alpaca_client: Alpaca client for trading
            min_trade_notional: Minimum trade size in dollars (default $1)
            max_drift_pct: Maximum allowed drift before rebalance (default 2%)
            max_position_pct: No single position may exceed this fraction of portfolio value
            cash_buffer_pct: Fraction of portfolio value always left uninvested
            max_rebalance_turnover_pct: Abort a rebalance if trades would exceed this
                fraction of portfolio value (guards against a data bug silently
                liquidating/rebuilding the whole book)
        """
        self.client = alpaca_client
        self.min_trade_notional = min_trade_notional
        self.max_drift_pct = max_drift_pct
        self.max_position_pct = max_position_pct
        self.cash_buffer_pct = cash_buffer_pct
        self.max_rebalance_turnover_pct = max_rebalance_turnover_pct

    def _target_weights(
        self,
        target_symbols: List[str],
        custom_weights: Dict[str, float] = None
    ) -> Dict[str, float]:
        """
        Compute risk-adjusted target weights: equal-weight (or custom_weights) with
        any position above max_position_pct capped and the excess redistributed
        pro-rata across the remaining symbols, then scaled down by cash_buffer_pct
        so the buffer is structural rather than incidental.
        """
        if custom_weights:
            weights = dict(custom_weights)
        else:
            weight = 1.0 / len(target_symbols) if target_symbols else 0
            weights = {sym: weight for sym in target_symbols}

        # Cap-and-redistribute (single pass -- fine at typical 20-40 position counts)
        capped = {}
        uncapped = dict(weights)
        excess = 0.0
        for sym, w in list(uncapped.items()):
            if w > self.max_position_pct:
                excess += w - self.max_position_pct
                capped[sym] = self.max_position_pct
                del uncapped[sym]
        if excess > 0 and uncapped:
            uncapped_total = sum(uncapped.values())
            for sym, w in uncapped.items():
                capped[sym] = w + excess * (w / uncapped_total)
        else:
            capped.update(uncapped)

        # Structural cash buffer
        return {sym: w * (1 - self.cash_buffer_pct) for sym, w in capped.items()}

    def get_current_allocation(self) -> Dict[str, float]:
        """
        Get current portfolio allocation as percentages.

        Returns:
            Dictionary of symbol -> allocation percentage (0-1)
        """
        account = self.client.get_account()
        portfolio_value = account['portfolio_value']

        if portfolio_value <= 0:
            return {}

        positions = self.client.get_positions()
        allocation = {}

        for pos in positions:
            allocation[pos.symbol] = pos.market_value / portfolio_value

        # Add cash allocation
        cash_pct = account['cash'] / portfolio_value
        allocation['_CASH'] = cash_pct

        return allocation

    def calculate_trades(
        self,
        target_symbols: List[str],
        equal_weight: bool = True,
        custom_weights: Dict[str, float] = None
    ) -> List[Trade]:
        """
        Calculate trades needed to reach target portfolio.

        Args:
            target_symbols: List of symbols to hold
            equal_weight: If True, equal weight all positions
            custom_weights: Custom weights for each symbol (must sum to ~1.0)

        Returns:
            List of Trade objects to execute
        """
        account = self.client.get_account()
        portfolio_value = account['portfolio_value']
        positions = self.client.get_positions()

        # Build current holdings map
        current_holdings = {pos.symbol: pos.market_value for pos in positions}

        # Calculate target weights (risk-capped + cash buffer applied)
        target_weights = self._target_weights(target_symbols, custom_weights)

        # Calculate target notional values (rounded to cents -- Alpaca's notional
        # order API rejects amounts with more than 2 decimal places)
        target_notional = {
            sym: round(weight * portfolio_value, 2)
            for sym, weight in target_weights.items()
        }

        trades = []

        # First, identify sells (positions to exit or reduce)
        for symbol, current_value in current_holdings.items():
            target_value = target_notional.get(symbol, 0)
            diff = round(current_value - target_value, 2)

            if diff > self.min_trade_notional:
                if target_value < self.min_trade_notional:
                    # Full exit
                    trades.append(Trade(
                        symbol=symbol,
                        side='sell',
                        notional=round(current_value, 2),
                        reason='exit'
                    ))
                else:
                    # Partial sell (rebalance down)
                    trades.append(Trade(
                        symbol=symbol,
                        side='sell',
                        notional=diff,
                        reason='rebalance'
                    ))

        # Then, identify buys (new positions or increases)
        for symbol, target_value in target_notional.items():
            current_value = current_holdings.get(symbol, 0)
            diff = round(target_value - current_value, 2)

            if diff > self.min_trade_notional:
                if current_value < self.min_trade_notional:
                    # New position
                    trades.append(Trade(
                        symbol=symbol,
                        side='buy',
                        notional=diff,
                        reason='new'
                    ))
                else:
                    # Increase position (rebalance up)
                    trades.append(Trade(
                        symbol=symbol,
                        side='buy',
                        notional=diff,
                        reason='rebalance'
                    ))

        # Sort: sells first, then buys
        trades.sort(key=lambda t: (0 if t.side == 'sell' else 1, -t.notional))

        return trades

    def needs_rebalance(
        self,
        target_symbols: List[str],
        equal_weight: bool = True,
        custom_weights: Dict[str, float] = None
    ) -> bool:
        """
        Check if portfolio needs rebalancing based on drift threshold.

        Returns:
            True if any position has drifted beyond max_drift_pct
        """
        account = self.client.get_account()
        portfolio_value = account['portfolio_value']

        if portfolio_value <= 0:
            return True

        positions = self.client.get_positions()
        current_holdings = {pos.symbol: pos.market_value for pos in positions}

        # Calculate target weights (risk-capped + cash buffer applied)
        target_weights = self._target_weights(target_symbols, custom_weights)

        # Check for new symbols not in portfolio
        current_symbols = set(current_holdings.keys())
        target_set = set(target_symbols)

        if current_symbols != target_set:
            return True

        # Check drift for each position
        for symbol in target_symbols:
            target_pct = target_weights[symbol]
            current_pct = current_holdings.get(symbol, 0) / portfolio_value
            drift = abs(current_pct - target_pct)

            if drift > self.max_drift_pct:
                logger.info(f"{symbol} drifted {drift:.1%} (threshold: {self.max_drift_pct:.1%})")
                return True

        return False

    def execute_rebalance(
        self,
        target_symbols: List[str],
        strategy_name: str = "unknown",
        equal_weight: bool = True,
        custom_weights: Dict[str, float] = None,
        dry_run: bool = False,
        force: bool = False
    ) -> RebalanceResult:
        """
        Execute a full portfolio rebalance.

        Args:
            target_symbols: List of symbols to hold
            strategy_name: Name of the strategy (for logging)
            equal_weight: If True, equal weight all positions
            custom_weights: Custom weights for each symbol
            dry_run: If True, calculate trades but don't execute
            force: If True, bypass the turnover guard (max_rebalance_turnover_pct)

        Returns:
            RebalanceResult with details of the operation

        Raises:
            TurnoverGuardError: if trades would move more than
                max_rebalance_turnover_pct of the portfolio and force=False --
                a guard against silently trading a corrupted/truncated pick list.
        """
        timestamp = datetime.now()
        account_before = self.client.get_account()
        positions_before = self.client.get_positions()

        initial_positions = {pos.symbol: pos.market_value for pos in positions_before}

        # Calculate target positions (risk-capped + cash buffer applied)
        portfolio_value = account_before['portfolio_value']
        target_weights = self._target_weights(target_symbols, custom_weights)

        target_positions = {
            sym: weight * portfolio_value
            for sym, weight in target_weights.items()
        }

        # Calculate trades
        trades = self.calculate_trades(target_symbols, equal_weight, custom_weights)

        logger.info(f"Rebalancing {strategy_name}: {len(trades)} trades to execute")

        # Turnover guard: abort a *live* rebalance that would trade an implausibly
        # large fraction of the portfolio in one shot (typically a symptom of a
        # bad/truncated pick list, not a real rebalance need). In dry_run mode this
        # only warns, since previewing trades is the whole point of --dry-run.
        turnover = sum(t.notional for t in trades) / portfolio_value if portfolio_value > 0 else 0
        if turnover > self.max_rebalance_turnover_pct:
            msg = (
                f"Rebalance for {strategy_name} would trade {turnover:.1%} of "
                f"portfolio value (limit {self.max_rebalance_turnover_pct:.1%})"
            )
            if dry_run:
                logger.warning(f"{msg} -- would be blocked without --force outside of dry-run")
            elif not force:
                logger.error(f"{msg}; aborting. Pass force=True to override.")
                raise TurnoverGuardError(f"{msg}; aborting. Pass force=True to override.")

        if dry_run:
            logger.info("DRY RUN - No trades will be executed")
            for trade in trades:
                logger.info(f"  Would {trade.side} ${trade.notional:.2f} of {trade.symbol} ({trade.reason})")

            return RebalanceResult(
                timestamp=timestamp,
                strategy=strategy_name,
                initial_positions=initial_positions,
                target_positions=target_positions,
                trades_executed=[],
                trades_failed=[],
                portfolio_value_before=portfolio_value,
                portfolio_value_after=portfolio_value
            )

        # Execute trades
        executed_orders = []
        failed_trades = []
        unfilled_trades = []

        for trade in trades:
            try:
                if trade.side == 'sell' and trade.reason == 'exit':
                    # Use close_position for full exits
                    order = self.client.close_position(trade.symbol)
                else:
                    # Use notional orders for partial trades
                    order = self.client.submit_notional_order(
                        symbol=trade.symbol,
                        notional=trade.notional,
                        side=trade.side
                    )

                if order:
                    filled_order = self.client.wait_for_order_fill(
                        order.id, timeout_seconds=ORDER_FILL_TIMEOUT_SECONDS
                    )
                    if filled_order:
                        executed_orders.append(filled_order)
                        logger.info(f"Filled: {trade.side} ${trade.notional:.2f} of {trade.symbol}")
                    else:
                        unfilled_trades.append((trade, order))
                        logger.warning(
                            f"Order not confirmed filled within timeout: "
                            f"{trade.side} {trade.symbol} (order {order.id})"
                        )
                else:
                    failed_trades.append((trade, "Order returned None"))

            except Exception as e:
                error_msg = str(e)
                failed_trades.append((trade, error_msg))
                logger.error(f"Failed to execute {trade.side} {trade.symbol}: {error_msg}")

        # Get final portfolio value
        account_after = self.client.get_account()

        result = RebalanceResult(
            timestamp=timestamp,
            strategy=strategy_name,
            initial_positions=initial_positions,
            target_positions=target_positions,
            trades_executed=executed_orders,
            trades_failed=failed_trades,
            trades_unfilled=unfilled_trades,
            portfolio_value_before=account_before['portfolio_value'],
            portfolio_value_after=account_after['portfolio_value']
        )

        logger.info(
            f"Rebalance complete: {len(executed_orders)} filled, "
            f"{len(unfilled_trades)} unfilled, {len(failed_trades)} failed"
        )

        return result

    def get_portfolio_summary(self) -> Dict:
        """Get a summary of the current portfolio."""
        account = self.client.get_account()
        positions = self.client.get_positions()

        holdings = []
        for pos in positions:
            pct = pos.market_value / account['portfolio_value'] if account['portfolio_value'] > 0 else 0
            holdings.append({
                'symbol': pos.symbol,
                'qty': pos.qty,
                'market_value': pos.market_value,
                'cost_basis': pos.cost_basis,
                'unrealized_pl': pos.unrealized_pl,
                'unrealized_plpc': pos.unrealized_plpc,
                'weight': pct
            })

        # Sort by weight descending
        holdings.sort(key=lambda x: x['weight'], reverse=True)

        return {
            'portfolio_value': account['portfolio_value'],
            'cash': account['cash'],
            'buying_power': account['buying_power'],
            'equity': account['equity'],
            'num_positions': len(positions),
            'holdings': holdings
        }
