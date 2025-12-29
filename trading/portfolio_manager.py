"""
Portfolio manager for rebalancing to target allocations.
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

from .alpaca_client import AlpacaClient, Position, Order

logger = logging.getLogger(__name__)


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
        max_drift_pct: float = 0.02
    ):
        """
        Initialize portfolio manager.

        Args:
            alpaca_client: Alpaca client for trading
            min_trade_notional: Minimum trade size in dollars (default $1)
            max_drift_pct: Maximum allowed drift before rebalance (default 2%)
        """
        self.client = alpaca_client
        self.min_trade_notional = min_trade_notional
        self.max_drift_pct = max_drift_pct

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

        # Calculate target weights
        if custom_weights:
            target_weights = custom_weights
        elif equal_weight:
            weight = 1.0 / len(target_symbols) if target_symbols else 0
            target_weights = {sym: weight for sym in target_symbols}
        else:
            target_weights = {sym: 1.0 / len(target_symbols) for sym in target_symbols}

        # Calculate target notional values
        target_notional = {
            sym: weight * portfolio_value
            for sym, weight in target_weights.items()
        }

        trades = []

        # First, identify sells (positions to exit or reduce)
        for symbol, current_value in current_holdings.items():
            target_value = target_notional.get(symbol, 0)
            diff = current_value - target_value

            if diff > self.min_trade_notional:
                if target_value < self.min_trade_notional:
                    # Full exit
                    trades.append(Trade(
                        symbol=symbol,
                        side='sell',
                        notional=current_value,
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
            diff = target_value - current_value

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

        # Calculate target weights
        if custom_weights:
            target_weights = custom_weights
        elif equal_weight:
            weight = 1.0 / len(target_symbols) if target_symbols else 0
            target_weights = {sym: weight for sym in target_symbols}
        else:
            target_weights = {sym: 1.0 / len(target_symbols) for sym in target_symbols}

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
        dry_run: bool = False
    ) -> RebalanceResult:
        """
        Execute a full portfolio rebalance.

        Args:
            target_symbols: List of symbols to hold
            strategy_name: Name of the strategy (for logging)
            equal_weight: If True, equal weight all positions
            custom_weights: Custom weights for each symbol
            dry_run: If True, calculate trades but don't execute

        Returns:
            RebalanceResult with details of the operation
        """
        timestamp = datetime.now()
        account_before = self.client.get_account()
        positions_before = self.client.get_positions()

        initial_positions = {pos.symbol: pos.market_value for pos in positions_before}

        # Calculate target positions
        portfolio_value = account_before['portfolio_value']
        if custom_weights:
            target_weights = custom_weights
        else:
            weight = 1.0 / len(target_symbols) if target_symbols else 0
            target_weights = {sym: weight for sym in target_symbols}

        target_positions = {
            sym: weight * portfolio_value
            for sym, weight in target_weights.items()
        }

        # Calculate trades
        trades = self.calculate_trades(target_symbols, equal_weight, custom_weights)

        logger.info(f"Rebalancing {strategy_name}: {len(trades)} trades to execute")

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
                    executed_orders.append(order)
                    logger.info(f"Executed: {trade.side} ${trade.notional:.2f} of {trade.symbol}")
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
            portfolio_value_before=account_before['portfolio_value'],
            portfolio_value_after=account_after['portfolio_value']
        )

        logger.info(
            f"Rebalance complete: {len(executed_orders)} executed, "
            f"{len(failed_trades)} failed"
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
