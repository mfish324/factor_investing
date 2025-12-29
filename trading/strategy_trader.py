"""
Strategy trader for running factor strategies with live/paper trading.
"""

import logging
import json
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import pandas as pd

from .alpaca_client import AlpacaClient
from .portfolio_manager import PortfolioManager, RebalanceResult
from models.base import FactorModel
from data.polygon_client import PolygonClient
from data.universe import UniverseManager
from config import POLYGON_API_KEY, RESULTS_DIR

logger = logging.getLogger(__name__)


class StrategyTrader:
    """
    Runs factor strategies for paper/live trading.

    Handles:
    - Loading data and running the model
    - Generating target portfolio
    - Executing rebalances via PortfolioManager
    - Logging and tracking trades
    """

    def __init__(
        self,
        model: FactorModel,
        alpaca_client: AlpacaClient,
        polygon_client: PolygonClient = None,
        portfolio_size: int = 30,
        log_dir: Path = None
    ):
        """
        Initialize strategy trader.

        Args:
            model: Factor model to use for stock selection
            alpaca_client: Alpaca client for trading
            polygon_client: Polygon client for data (optional, creates one if not provided)
            portfolio_size: Number of stocks to hold
            log_dir: Directory for trade logs
        """
        self.model = model
        self.alpaca = alpaca_client
        self.polygon = polygon_client or PolygonClient()
        self.portfolio_manager = PortfolioManager(alpaca_client)
        self.portfolio_size = portfolio_size
        self.log_dir = log_dir or RESULTS_DIR / 'trading_logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.universe_manager = UniverseManager()

    def get_current_picks(self) -> List[str]:
        """
        Get current stock picks from the model.

        Returns:
            List of ticker symbols to hold
        """
        # Get universe
        universe = self.universe_manager.get_universe('sp500', exclude_financials=True)

        # Load recent data
        today = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - pd.Timedelta(days=400)).strftime('%Y-%m-%d')

        logger.info(f"Loading data for {len(universe)} stocks...")

        # Load financials
        financials = {}
        for ticker in universe:
            try:
                df = self.polygon.get_financials(ticker, period='annual')
                if not df.empty:
                    financials[ticker] = df
            except Exception as e:
                pass

        # Load prices
        prices = {}
        for ticker in universe:
            try:
                df = self.polygon.get_prices(ticker, start, today)
                if not df.empty:
                    prices[ticker] = df
            except Exception as e:
                pass

        # Get market caps
        market_caps = {}
        for ticker in universe:
            try:
                mc = self.polygon.get_market_cap(ticker)
                if mc:
                    market_caps[ticker] = mc
            except Exception as e:
                pass

        logger.info(
            f"Loaded: {len(financials)} financials, "
            f"{len(prices)} prices, {len(market_caps)} market caps"
        )

        # Get model picks
        picks = self.model.select_portfolio(
            financials=financials,
            prices=prices,
            market_caps=market_caps,
            n=self.portfolio_size
        )

        logger.info(f"{self.model.name} selected {len(picks)} stocks")
        return picks

    def run_rebalance(
        self,
        dry_run: bool = False,
        force: bool = False
    ) -> Optional[RebalanceResult]:
        """
        Run a rebalance for the strategy.

        Args:
            dry_run: If True, calculate trades but don't execute
            force: If True, rebalance even if within drift threshold

        Returns:
            RebalanceResult or None if no rebalance needed
        """
        logger.info(f"Running rebalance for {self.model.name}...")

        # Get current picks from model
        target_symbols = self.get_current_picks()

        if not target_symbols:
            logger.error("No stocks selected by model")
            return None

        # Check if rebalance is needed
        if not force and not self.portfolio_manager.needs_rebalance(target_symbols):
            logger.info("Portfolio within drift threshold, no rebalance needed")
            return None

        # Execute rebalance
        result = self.portfolio_manager.execute_rebalance(
            target_symbols=target_symbols,
            strategy_name=self.model.name,
            equal_weight=True,
            dry_run=dry_run
        )

        # Log the rebalance
        self._log_rebalance(result)

        return result

    def _log_rebalance(self, result: RebalanceResult):
        """Log rebalance result to file."""
        log_file = self.log_dir / f"{self.model.name.lower().replace(' ', '_')}_trades.jsonl"

        log_entry = {
            'timestamp': result.timestamp.isoformat(),
            'strategy': result.strategy,
            'portfolio_value_before': result.portfolio_value_before,
            'portfolio_value_after': result.portfolio_value_after,
            'num_trades_executed': len(result.trades_executed),
            'num_trades_failed': len(result.trades_failed),
            'target_positions': list(result.target_positions.keys()),
            'trades': [
                {
                    'symbol': o.symbol,
                    'side': o.side,
                    'qty': o.qty,
                    'status': o.status
                }
                for o in result.trades_executed
            ],
            'failures': [
                {'symbol': t.symbol, 'side': t.side, 'error': e}
                for t, e in result.trades_failed
            ]
        }

        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        logger.info(f"Logged rebalance to {log_file}")

    def get_status(self) -> Dict:
        """
        Get current status of the strategy.

        Returns:
            Dictionary with strategy status
        """
        account = self.alpaca.get_account()
        summary = self.portfolio_manager.get_portfolio_summary()

        return {
            'strategy': self.model.name,
            'description': self.model.description,
            'portfolio_size_target': self.portfolio_size,
            'portfolio_size_actual': summary['num_positions'],
            'portfolio_value': summary['portfolio_value'],
            'cash': summary['cash'],
            'holdings': summary['holdings'],
            'account_status': account['status'],
            'is_paper': self.alpaca.paper,
            'market_open': self.alpaca.is_market_open()
        }

    def print_status(self):
        """Print current status to console."""
        status = self.get_status()

        print(f"\n{'='*60}")
        print(f"Strategy: {status['strategy']}")
        print(f"{'='*60}")
        print(f"Description: {status['description']}")
        print(f"Paper Trading: {status['is_paper']}")
        print(f"Market Open: {status['market_open']}")
        print(f"\nPortfolio Value: ${status['portfolio_value']:,.2f}")
        print(f"Cash: ${status['cash']:,.2f}")
        print(f"Positions: {status['portfolio_size_actual']} / {status['portfolio_size_target']}")

        if status['holdings']:
            print(f"\n{'Symbol':<8} {'Weight':>8} {'Value':>12} {'P/L':>10} {'P/L%':>8}")
            print('-' * 50)
            for h in status['holdings'][:10]:
                print(
                    f"{h['symbol']:<8} {h['weight']:>7.1%} "
                    f"${h['market_value']:>10,.2f} "
                    f"${h['unrealized_pl']:>9,.2f} "
                    f"{h['unrealized_plpc']:>7.1%}"
                )
            if len(status['holdings']) > 10:
                print(f"... and {len(status['holdings']) - 10} more positions")

    def print_current_picks(self):
        """Print current model picks."""
        picks = self.get_current_picks()

        print(f"\n{self.model.name} Current Picks ({len(picks)} stocks):")
        print("=" * 40)

        for i, ticker in enumerate(picks, 1):
            sector = self.universe_manager.get_sector(ticker) or "Unknown"
            print(f"{i:2}. {ticker:<6} | {sector}")


class MultiStrategyTrader:
    """
    Manages multiple strategy traders for running all strategies in parallel.

    Note: Each strategy needs its own Alpaca account (sub-account) to run
    independently. This class helps manage multiple strategies but assumes
    separate account credentials for each.
    """

    def __init__(self, strategies: Dict[str, StrategyTrader]):
        """
        Initialize with multiple strategy traders.

        Args:
            strategies: Dictionary of strategy_name -> StrategyTrader
        """
        self.strategies = strategies

    def get_all_picks(self) -> Dict[str, List[str]]:
        """Get current picks from all strategies."""
        picks = {}
        for name, trader in self.strategies.items():
            picks[name] = trader.get_current_picks()
        return picks

    def print_all_picks(self):
        """Print picks from all strategies."""
        picks = self.get_all_picks()

        print("\n" + "=" * 60)
        print("ALL STRATEGY PICKS")
        print("=" * 60)

        for strategy_name, symbols in picks.items():
            print(f"\n{strategy_name} ({len(symbols)} stocks):")
            print(", ".join(symbols[:10]))
            if len(symbols) > 10:
                print(f"... and {len(symbols) - 10} more")

        # Find overlaps
        all_symbols = [set(s) for s in picks.values()]
        if len(all_symbols) > 1:
            common = set.intersection(*all_symbols)
            if common:
                print(f"\nStocks in ALL strategies: {', '.join(sorted(common))}")

    def get_all_status(self) -> Dict[str, Dict]:
        """Get status of all strategies."""
        return {name: trader.get_status() for name, trader in self.strategies.items()}
