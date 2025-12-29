"""
Portfolio construction and management.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class PortfolioHolding:
    """Represents a single position in the portfolio."""
    ticker: str
    shares: float
    entry_price: float
    entry_date: datetime
    current_price: float = 0.0
    weight: float = 0.0

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.shares * self.entry_price

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis

    @property
    def return_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return (self.market_value - self.cost_basis) / self.cost_basis


@dataclass
class Portfolio:
    """
    Portfolio manager for equal-weight stock portfolios.
    """
    initial_capital: float = 100000.0
    cash: float = field(default=0.0)
    holdings: Dict[str, PortfolioHolding] = field(default_factory=dict)
    transaction_cost_bps: float = 10.0  # Basis points per trade

    def __post_init__(self):
        if self.cash == 0.0:
            self.cash = self.initial_capital

    @property
    def total_value(self) -> float:
        """Total portfolio value including cash."""
        holdings_value = sum(h.market_value for h in self.holdings.values())
        return self.cash + holdings_value

    @property
    def holdings_value(self) -> float:
        """Total value of stock holdings."""
        return sum(h.market_value for h in self.holdings.values())

    @property
    def num_positions(self) -> int:
        """Number of current positions."""
        return len(self.holdings)

    def update_prices(self, prices: Dict[str, float]):
        """
        Update current prices for all holdings.

        Args:
            prices: Dict of ticker -> current price
        """
        for ticker, holding in self.holdings.items():
            if ticker in prices:
                holding.current_price = prices[ticker]

        # Update weights
        total = self.total_value
        for holding in self.holdings.values():
            holding.weight = holding.market_value / total if total > 0 else 0

    def rebalance(
        self,
        new_tickers: List[str],
        prices: Dict[str, float],
        date: datetime,
        target_weights: Dict[str, float] = None
    ) -> Dict[str, float]:
        """
        Rebalance portfolio to new set of tickers.

        Args:
            new_tickers: List of tickers to hold
            prices: Current prices for all tickers
            date: Rebalance date
            target_weights: Optional target weights (defaults to equal weight)

        Returns:
            Dictionary of trades executed (ticker -> dollar amount)
        """
        # Default to equal weight
        if target_weights is None:
            weight = 1.0 / len(new_tickers) if new_tickers else 0
            target_weights = {t: weight for t in new_tickers}

        # First, update prices for current holdings
        self.update_prices(prices)

        trades = {}
        current_value = self.total_value

        # Sell positions not in new portfolio
        for ticker in list(self.holdings.keys()):
            if ticker not in new_tickers:
                holding = self.holdings[ticker]
                sale_proceeds = holding.market_value
                # Apply transaction cost
                cost = sale_proceeds * (self.transaction_cost_bps / 10000)
                self.cash += sale_proceeds - cost
                trades[ticker] = -sale_proceeds
                del self.holdings[ticker]
                logger.debug(f"Sold {ticker}: ${sale_proceeds:.2f}")

        # Calculate target values
        target_values = {
            ticker: current_value * target_weights.get(ticker, 0)
            for ticker in new_tickers
        }

        # Adjust existing positions and add new ones
        for ticker in new_tickers:
            if ticker not in prices or prices[ticker] <= 0:
                logger.warning(f"No valid price for {ticker}, skipping")
                continue

            price = prices[ticker]
            target_value = target_values[ticker]

            current_value_position = 0
            if ticker in self.holdings:
                current_value_position = self.holdings[ticker].market_value

            trade_value = target_value - current_value_position

            if abs(trade_value) < 100:  # Skip small trades
                continue

            # Calculate shares to trade
            shares = trade_value / price

            # Apply transaction cost
            cost = abs(trade_value) * (self.transaction_cost_bps / 10000)

            if trade_value > 0:  # Buy
                if self.cash >= trade_value + cost:
                    if ticker in self.holdings:
                        # Add to existing position
                        old_shares = self.holdings[ticker].shares
                        old_cost = self.holdings[ticker].cost_basis
                        new_shares = old_shares + shares
                        # Update average cost
                        self.holdings[ticker].shares = new_shares
                        self.holdings[ticker].entry_price = (old_cost + trade_value) / new_shares
                    else:
                        # New position
                        self.holdings[ticker] = PortfolioHolding(
                            ticker=ticker,
                            shares=shares,
                            entry_price=price,
                            entry_date=date,
                            current_price=price
                        )
                    self.cash -= trade_value + cost
                    trades[ticker] = trade_value
                    logger.debug(f"Bought {ticker}: ${trade_value:.2f}")
            else:  # Sell
                shares_to_sell = abs(shares)
                if ticker in self.holdings:
                    current_shares = self.holdings[ticker].shares
                    shares_to_sell = min(shares_to_sell, current_shares)
                    sale_proceeds = shares_to_sell * price
                    self.holdings[ticker].shares -= shares_to_sell
                    self.cash += sale_proceeds - cost

                    if self.holdings[ticker].shares <= 0:
                        del self.holdings[ticker]

                    trades[ticker] = -sale_proceeds
                    logger.debug(f"Sold {ticker}: ${sale_proceeds:.2f}")

        # Update prices and weights
        self.update_prices(prices)

        return trades

    def calculate_return(self, prices: Dict[str, float]) -> float:
        """
        Calculate return since last price update.

        Args:
            prices: Current prices

        Returns:
            Return as decimal (e.g., 0.05 = 5%)
        """
        old_value = self.total_value
        self.update_prices(prices)
        new_value = self.total_value

        if old_value == 0:
            return 0.0
        return (new_value - old_value) / old_value

    def get_holdings_df(self) -> pd.DataFrame:
        """Get holdings as DataFrame."""
        if not self.holdings:
            return pd.DataFrame()

        records = []
        for ticker, holding in self.holdings.items():
            records.append({
                'ticker': ticker,
                'shares': holding.shares,
                'entry_price': holding.entry_price,
                'current_price': holding.current_price,
                'market_value': holding.market_value,
                'weight': holding.weight,
                'unrealized_pnl': holding.unrealized_pnl,
                'return_pct': holding.return_pct,
            })

        return pd.DataFrame(records).set_index('ticker')

    def get_summary(self) -> Dict:
        """Get portfolio summary."""
        return {
            'total_value': self.total_value,
            'cash': self.cash,
            'holdings_value': self.holdings_value,
            'num_positions': self.num_positions,
            'cash_weight': self.cash / self.total_value if self.total_value > 0 else 0,
        }
