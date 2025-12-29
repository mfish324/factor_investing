"""
Alpaca API client for paper and live trading.
"""

import os
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import time

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest,
        LimitOrderRequest,
        GetOrdersRequest
    )
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus, QueryOrderStatus
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents a position in a stock."""
    symbol: str
    qty: float
    market_value: float
    cost_basis: float
    unrealized_pl: float
    unrealized_plpc: float
    current_price: float


@dataclass
class Order:
    """Represents an order."""
    id: str
    symbol: str
    side: str
    qty: float
    filled_qty: float
    status: str
    submitted_at: datetime
    filled_at: Optional[datetime]


class AlpacaClient:
    """
    Client for interacting with Alpaca Trading API.

    Supports both paper and live trading accounts.
    """

    def __init__(
        self,
        api_key: str = None,
        secret_key: str = None,
        paper: bool = True
    ):
        """
        Initialize Alpaca client.

        Args:
            api_key: Alpaca API key (or set ALPACA_API_KEY env var)
            secret_key: Alpaca secret key (or set ALPACA_SECRET_KEY env var)
            paper: If True, use paper trading (default). If False, use live trading.
        """
        if not ALPACA_AVAILABLE:
            raise ImportError(
                "Alpaca SDK not installed. Install with: pip install alpaca-py"
            )

        self.api_key = api_key or os.environ.get('ALPACA_API_KEY')
        self.secret_key = secret_key or os.environ.get('ALPACA_SECRET_KEY')
        self.paper = paper

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Alpaca API credentials required. Set ALPACA_API_KEY and "
                "ALPACA_SECRET_KEY environment variables or pass them directly."
            )

        # Initialize trading client
        self.trading_client = TradingClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=paper
        )

        # Initialize data client for quotes
        self.data_client = StockHistoricalDataClient(
            api_key=self.api_key,
            secret_key=self.secret_key
        )

        logger.info(f"Alpaca client initialized (paper={paper})")

    def get_account(self) -> Dict:
        """Get account information."""
        account = self.trading_client.get_account()
        return {
            'id': account.id,
            'status': account.status,
            'currency': account.currency,
            'cash': float(account.cash),
            'portfolio_value': float(account.portfolio_value),
            'buying_power': float(account.buying_power),
            'equity': float(account.equity),
            'last_equity': float(account.last_equity),
            'long_market_value': float(account.long_market_value),
            'short_market_value': float(account.short_market_value),
            'daytrade_count': account.daytrade_count,
            'pattern_day_trader': account.pattern_day_trader,
        }

    def get_positions(self) -> List[Position]:
        """Get all current positions."""
        positions = self.trading_client.get_all_positions()
        return [
            Position(
                symbol=p.symbol,
                qty=float(p.qty),
                market_value=float(p.market_value),
                cost_basis=float(p.cost_basis),
                unrealized_pl=float(p.unrealized_pl),
                unrealized_plpc=float(p.unrealized_plpc),
                current_price=float(p.current_price)
            )
            for p in positions
        ]

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a specific symbol."""
        try:
            p = self.trading_client.get_open_position(symbol)
            return Position(
                symbol=p.symbol,
                qty=float(p.qty),
                market_value=float(p.market_value),
                cost_basis=float(p.cost_basis),
                unrealized_pl=float(p.unrealized_pl),
                unrealized_plpc=float(p.unrealized_plpc),
                current_price=float(p.current_price)
            )
        except Exception:
            return None

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol."""
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes = self.data_client.get_stock_latest_quote(request)
            if symbol in quotes:
                quote = quotes[symbol]
                # Use midpoint of bid/ask
                return (float(quote.bid_price) + float(quote.ask_price)) / 2
        except Exception as e:
            logger.warning(f"Failed to get price for {symbol}: {e}")
        return None

    def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices for multiple symbols."""
        prices = {}
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            quotes = self.data_client.get_stock_latest_quote(request)
            for symbol, quote in quotes.items():
                prices[symbol] = (float(quote.bid_price) + float(quote.ask_price)) / 2
        except Exception as e:
            logger.warning(f"Failed to get prices: {e}")
        return prices

    def submit_market_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        time_in_force: str = 'day'
    ) -> Order:
        """
        Submit a market order.

        Args:
            symbol: Stock symbol
            qty: Number of shares (can be fractional)
            side: 'buy' or 'sell'
            time_in_force: 'day', 'gtc', 'ioc', 'fok'

        Returns:
            Order object
        """
        order_side = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL
        tif_map = {
            'day': TimeInForce.DAY,
            'gtc': TimeInForce.GTC,
            'ioc': TimeInForce.IOC,
            'fok': TimeInForce.FOK
        }

        request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=tif_map.get(time_in_force, TimeInForce.DAY)
        )

        order = self.trading_client.submit_order(request)
        logger.info(f"Submitted {side} order for {qty} shares of {symbol}")

        return Order(
            id=str(order.id),
            symbol=order.symbol,
            side=str(order.side),
            qty=float(order.qty),
            filled_qty=float(order.filled_qty) if order.filled_qty else 0,
            status=str(order.status),
            submitted_at=order.submitted_at,
            filled_at=order.filled_at
        )

    def submit_notional_order(
        self,
        symbol: str,
        notional: float,
        side: str,
        time_in_force: str = 'day'
    ) -> Order:
        """
        Submit a notional (dollar amount) order.

        Args:
            symbol: Stock symbol
            notional: Dollar amount to buy/sell
            side: 'buy' or 'sell'
            time_in_force: 'day', 'gtc', 'ioc', 'fok'

        Returns:
            Order object
        """
        order_side = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL
        tif_map = {
            'day': TimeInForce.DAY,
            'gtc': TimeInForce.GTC,
            'ioc': TimeInForce.IOC,
            'fok': TimeInForce.FOK
        }

        request = MarketOrderRequest(
            symbol=symbol,
            notional=notional,
            side=order_side,
            time_in_force=tif_map.get(time_in_force, TimeInForce.DAY)
        )

        order = self.trading_client.submit_order(request)
        logger.info(f"Submitted {side} order for ${notional} of {symbol}")

        return Order(
            id=str(order.id),
            symbol=order.symbol,
            side=str(order.side),
            qty=float(order.qty) if order.qty else 0,
            filled_qty=float(order.filled_qty) if order.filled_qty else 0,
            status=str(order.status),
            submitted_at=order.submitted_at,
            filled_at=order.filled_at
        )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order by ID."""
        try:
            self.trading_client.cancel_order_by_id(order_id)
            logger.info(f"Cancelled order {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def cancel_all_orders(self) -> int:
        """Cancel all open orders. Returns count of cancelled orders."""
        try:
            result = self.trading_client.cancel_orders()
            count = len(result) if result else 0
            logger.info(f"Cancelled {count} orders")
            return count
        except Exception as e:
            logger.error(f"Failed to cancel all orders: {e}")
            return 0

    def get_orders(
        self,
        status: str = 'open',
        limit: int = 100
    ) -> List[Order]:
        """
        Get orders.

        Args:
            status: 'open', 'closed', or 'all'
            limit: Maximum number of orders to return
        """
        status_map = {
            'open': QueryOrderStatus.OPEN,
            'closed': QueryOrderStatus.CLOSED,
            'all': QueryOrderStatus.ALL
        }

        request = GetOrdersRequest(
            status=status_map.get(status, QueryOrderStatus.OPEN),
            limit=limit
        )

        orders = self.trading_client.get_orders(request)
        return [
            Order(
                id=str(o.id),
                symbol=o.symbol,
                side=str(o.side),
                qty=float(o.qty) if o.qty else 0,
                filled_qty=float(o.filled_qty) if o.filled_qty else 0,
                status=str(o.status),
                submitted_at=o.submitted_at,
                filled_at=o.filled_at
            )
            for o in orders
        ]

    def close_position(self, symbol: str) -> Optional[Order]:
        """Close entire position in a symbol."""
        try:
            order = self.trading_client.close_position(symbol)
            logger.info(f"Closed position in {symbol}")
            return Order(
                id=str(order.id),
                symbol=order.symbol,
                side=str(order.side),
                qty=float(order.qty) if order.qty else 0,
                filled_qty=float(order.filled_qty) if order.filled_qty else 0,
                status=str(order.status),
                submitted_at=order.submitted_at,
                filled_at=order.filled_at
            )
        except Exception as e:
            logger.error(f"Failed to close position in {symbol}: {e}")
            return None

    def close_all_positions(self) -> List[Order]:
        """Close all positions."""
        try:
            orders = self.trading_client.close_all_positions(cancel_orders=True)
            logger.info(f"Closed all positions ({len(orders)} orders)")
            return [
                Order(
                    id=str(o.id),
                    symbol=o.symbol,
                    side=str(o.side),
                    qty=float(o.qty) if o.qty else 0,
                    filled_qty=float(o.filled_qty) if o.filled_qty else 0,
                    status=str(o.status),
                    submitted_at=o.submitted_at,
                    filled_at=o.filled_at
                )
                for o in orders
            ]
        except Exception as e:
            logger.error(f"Failed to close all positions: {e}")
            return []

    def is_market_open(self) -> bool:
        """Check if the market is currently open."""
        clock = self.trading_client.get_clock()
        return clock.is_open

    def get_next_open(self) -> datetime:
        """Get the next market open time."""
        clock = self.trading_client.get_clock()
        return clock.next_open

    def get_next_close(self) -> datetime:
        """Get the next market close time."""
        clock = self.trading_client.get_clock()
        return clock.next_close

    def wait_for_order_fill(
        self,
        order_id: str,
        timeout_seconds: int = 60,
        poll_interval: float = 1.0
    ) -> Optional[Order]:
        """
        Wait for an order to fill.

        Args:
            order_id: Order ID to wait for
            timeout_seconds: Maximum time to wait
            poll_interval: Time between status checks

        Returns:
            Filled order or None if timeout/error
        """
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            try:
                order = self.trading_client.get_order_by_id(order_id)
                if order.status == OrderStatus.FILLED:
                    return Order(
                        id=str(order.id),
                        symbol=order.symbol,
                        side=str(order.side),
                        qty=float(order.qty) if order.qty else 0,
                        filled_qty=float(order.filled_qty) if order.filled_qty else 0,
                        status=str(order.status),
                        submitted_at=order.submitted_at,
                        filled_at=order.filled_at
                    )
                elif order.status in [OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED]:
                    logger.warning(f"Order {order_id} ended with status {order.status}")
                    return None
            except Exception as e:
                logger.error(f"Error checking order status: {e}")

            time.sleep(poll_interval)

        logger.warning(f"Timeout waiting for order {order_id} to fill")
        return None
