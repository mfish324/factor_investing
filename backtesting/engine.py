"""
Backtest execution engine.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import logging
from tqdm import tqdm

from models.base import FactorModel
from .portfolio import Portfolio
from .metrics import BacktestResult, PerformanceMetrics, calculate_metrics
from .point_in_time import PointInTimeView, truncate_one
from config import (
    BACKTEST_START_DATE,
    BACKTEST_END_DATE,
    DEFAULT_PORTFOLIO_SIZE,
    DEFAULT_REBALANCE_FREQUENCY,
    TRANSACTION_COST_BPS
)

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Backtest engine for factor-based strategies.

    Executes walk-forward backtests:
    1. At each rebalance date, score all stocks using the model
    2. Select top N stocks
    3. Rebalance to equal weight portfolio
    4. Track returns until next rebalance
    """

    def __init__(
        self,
        model: FactorModel,
        polygon_client=None,
        start_date: str = None,
        end_date: str = None,
        rebalance_freq: str = None,
        portfolio_size: int = None,
        initial_capital: float = 100000.0,
        transaction_cost_bps: float = None
    ):
        """
        Args:
            model: Factor model to use for stock selection
            polygon_client: Polygon API client for data
            start_date: Backtest start date (YYYY-MM-DD)
            end_date: Backtest end date (YYYY-MM-DD)
            rebalance_freq: Rebalance frequency ('monthly', 'quarterly', 'annual')
            portfolio_size: Number of stocks to hold
            initial_capital: Starting capital
            transaction_cost_bps: Transaction cost in basis points
        """
        self.model = model
        self.polygon_client = polygon_client
        self.start_date = start_date or BACKTEST_START_DATE
        self.end_date = end_date or BACKTEST_END_DATE
        self.rebalance_freq = rebalance_freq or DEFAULT_REBALANCE_FREQUENCY
        self.portfolio_size = portfolio_size or DEFAULT_PORTFOLIO_SIZE
        self.initial_capital = initial_capital
        self.transaction_cost_bps = transaction_cost_bps or TRANSACTION_COST_BPS

    def run(
        self,
        financials: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.DataFrame],
        market_caps: Dict[str, float] = None,
        benchmark_prices: pd.DataFrame = None,
        show_progress: bool = True,
        shares_outstanding: Dict[str, float] = None,
        **kwargs
    ) -> BacktestResult:
        """
        Execute the backtest.

        Args:
            financials: Dictionary of ticker -> financials DataFrame
            prices: Dictionary of ticker -> price DataFrame
            market_caps: Dictionary of ticker -> market cap
            benchmark_prices: Benchmark (SPY) price DataFrame
            show_progress: Whether to show progress bar
            **kwargs: Additional data passed to model.score()

        Returns:
            BacktestResult with performance data
        """
        logger.info(f"Starting backtest for {self.model.name}")
        logger.info(f"Period: {self.start_date} to {self.end_date}")
        logger.info(f"Rebalance: {self.rebalance_freq}, Size: {self.portfolio_size}")

        # Generate rebalance dates
        rebalance_dates = self._get_rebalance_dates()
        logger.info(f"Rebalance dates: {len(rebalance_dates)}")

        # Initialize portfolio
        portfolio = Portfolio(
            initial_capital=self.initial_capital,
            transaction_cost_bps=self.transaction_cost_bps
        )

        # Initialize tracking
        all_returns = []
        all_values = []
        all_trades = []
        holdings_history = []

        # Create combined price DataFrame for daily tracking
        price_matrix = self._create_price_matrix(prices, self.start_date, self.end_date)

        if price_matrix.empty:
            logger.error("No price data available for backtest period")
            return self._empty_result()

        # Get all trading days
        trading_days = price_matrix.index.tolist()

        # Track which rebalance we're on
        rebalance_idx = 0
        current_holdings = []

        iterator = tqdm(trading_days, desc="Backtesting") if show_progress else trading_days

        for date in iterator:
            date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)

            # Check if rebalance day
            is_rebalance = False
            if rebalance_idx < len(rebalance_dates):
                rebalance_date = rebalance_dates[rebalance_idx]
                if date >= pd.Timestamp(rebalance_date):
                    is_rebalance = True
                    rebalance_idx += 1

            # Get current prices
            current_prices = {}
            for ticker in price_matrix.columns:
                price = price_matrix.loc[date, ticker]
                if pd.notna(price) and price > 0:
                    current_prices[ticker] = price

            if is_rebalance and current_prices:
                # Wrap prices and financials in point-in-time views so the model
                # cannot reach data dated after the rebalance date. Future rows
                # are dropped at view construction; this is the architectural
                # guarantee against look-ahead bias.
                prices_view = PointInTimeView(prices, as_of=date, date_column='date')
                financials_view = PointInTimeView(
                    financials, as_of=date, date_column='filing_date'
                )
                benchmark_asof = truncate_one(benchmark_prices, date)
                if shares_outstanding:
                    market_caps_asof = self._market_caps_asof(prices_view, shares_outstanding)
                else:
                    market_caps_asof = market_caps

                # Select new portfolio
                try:
                    new_holdings = self.model.select_portfolio(
                        financials=financials_view,
                        prices=prices_view,
                        market_caps=market_caps_asof,
                        n=self.portfolio_size,
                        benchmark_prices=benchmark_asof,
                        **kwargs
                    )

                    # Filter to stocks with prices
                    new_holdings = [t for t in new_holdings if t in current_prices]

                    if new_holdings:
                        trades = portfolio.rebalance(
                            new_tickers=new_holdings,
                            prices=current_prices,
                            date=date
                        )
                        all_trades.append({
                            'date': date,
                            'holdings': new_holdings.copy(),
                            'trades': trades
                        })
                        current_holdings = new_holdings

                        # Record holdings
                        for ticker in current_holdings:
                            holdings_history.append({
                                'date': date,
                                'ticker': ticker,
                                'weight': 1.0 / len(current_holdings)
                            })

                except Exception as e:
                    logger.warning(f"Rebalance failed on {date_str}: {e}")

            # Update prices and calculate return
            if current_holdings:
                old_value = portfolio.total_value
                portfolio.update_prices(current_prices)
                new_value = portfolio.total_value

                daily_return = (new_value - old_value) / old_value if old_value > 0 else 0
            else:
                daily_return = 0
                new_value = portfolio.total_value

            all_returns.append({'date': date, 'return': daily_return})
            all_values.append({'date': date, 'value': new_value})

        # Create result DataFrames
        returns_df = pd.DataFrame(all_returns).set_index('date')['return']
        values_df = pd.DataFrame(all_values).set_index('date')['value']
        holdings_df = pd.DataFrame(holdings_history)
        if not holdings_df.empty:
            holdings_df = holdings_df.set_index('date')

        # Calculate cumulative returns
        cumulative_returns = (1 + returns_df).cumprod() - 1

        # Process benchmark
        bench_returns = pd.Series(dtype=float)
        bench_cumulative = pd.Series(dtype=float)
        if benchmark_prices is not None and not benchmark_prices.empty:
            bench_returns = self._calculate_benchmark_returns(
                benchmark_prices, trading_days
            )
            if not bench_returns.empty:
                bench_cumulative = (1 + bench_returns).cumprod() - 1

        # Calculate metrics
        metrics = calculate_metrics(
            returns=returns_df,
            benchmark_returns=bench_returns
        )

        # Create result
        result = BacktestResult(
            model_name=self.model.name,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital,
            final_value=portfolio.total_value,
            returns=returns_df,
            cumulative_returns=cumulative_returns,
            portfolio_values=values_df,
            holdings_history=holdings_df,
            benchmark_returns=bench_returns,
            benchmark_cumulative=bench_cumulative,
            metrics=metrics,
            trades=all_trades
        )

        logger.info(f"Backtest complete. Final value: ${result.final_value:,.2f}")
        logger.info(f"Total return: {metrics.total_return:.2%}")
        logger.info(f"Sharpe ratio: {metrics.sharpe_ratio:.2f}")

        return result

    def _get_rebalance_dates(self) -> List[str]:
        """Generate list of rebalance dates."""
        start = pd.Timestamp(self.start_date)
        end = pd.Timestamp(self.end_date)

        if self.rebalance_freq == 'monthly':
            dates = pd.date_range(start, end, freq='MS')
        elif self.rebalance_freq == 'quarterly':
            dates = pd.date_range(start, end, freq='QS')
        elif self.rebalance_freq == 'annual':
            dates = pd.date_range(start, end, freq='YS')
        else:
            # Default to quarterly
            dates = pd.date_range(start, end, freq='QS')

        return [d.strftime('%Y-%m-%d') for d in dates]

    def _create_price_matrix(
        self,
        prices: Dict[str, pd.DataFrame],
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Create a matrix of prices with tickers as columns and dates as rows.
        """
        price_series = {}

        for ticker, df in prices.items():
            if df.empty:
                continue
            if 'date' in df.columns and 'close' in df.columns:
                series = df.set_index('date')['close']
            elif 'close' in df.columns:
                series = df['close']
            else:
                continue

            series.index = pd.to_datetime(series.index)
            price_series[ticker] = series

        if not price_series:
            return pd.DataFrame()

        # Combine into DataFrame
        matrix = pd.DataFrame(price_series)

        # Filter to date range
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)
        matrix = matrix.loc[start:end]

        # Forward fill missing values (for non-trading days)
        matrix = matrix.ffill()

        return matrix

    def _calculate_benchmark_returns(
        self,
        benchmark_prices: pd.DataFrame,
        trading_days: List
    ) -> pd.Series:
        """Calculate benchmark returns aligned with trading days."""
        if 'close' not in benchmark_prices.columns:
            return pd.Series(dtype=float)

        if 'date' in benchmark_prices.columns:
            bench = benchmark_prices.set_index('date')['close']
        else:
            bench = benchmark_prices['close']

        bench.index = pd.to_datetime(bench.index)

        # Calculate returns
        returns = bench.pct_change()

        # Align with trading days
        trading_days = pd.DatetimeIndex(trading_days)
        returns = returns.reindex(trading_days)

        return returns.fillna(0)

    @staticmethod
    def _market_caps_asof(
        prices_view,
        shares_outstanding: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Compute market cap as of the rebalance date: shares * price[asof_date].

        `prices_view` is a PointInTimeView already truncated to as_of, so
        df.iloc[-1]['close'] is the as-of price.

        Holds shares constant at the load-time implied value. Constant-shares
        is a known approximation (ignores buybacks/issuances over the backtest
        window) but eliminates the much larger price-driven look-ahead.
        """
        if not shares_outstanding:
            return {}
        out = {}
        for ticker, shares in shares_outstanding.items():
            df = prices_view.get(ticker)
            if df is None or df.empty or shares is None or shares <= 0:
                continue
            if 'close' not in df.columns:
                continue
            asof_price = df.iloc[-1]['close']
            if pd.isna(asof_price) or asof_price <= 0:
                continue
            out[ticker] = float(shares) * float(asof_price)
        return out

    def _empty_result(self) -> BacktestResult:
        """Return empty result on failure."""
        return BacktestResult(
            model_name=self.model.name,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital,
            final_value=self.initial_capital,
            metrics=PerformanceMetrics()
        )


def run_multiple_backtests(
    models: List[FactorModel],
    financials: Dict[str, pd.DataFrame],
    prices: Dict[str, pd.DataFrame],
    market_caps: Dict[str, float],
    benchmark_prices: pd.DataFrame = None,
    **kwargs
) -> Dict[str, BacktestResult]:
    """
    Run backtests for multiple models.

    Args:
        models: List of factor models
        financials: Financial data
        prices: Price data
        market_caps: Market cap data
        benchmark_prices: Benchmark price data
        **kwargs: Additional arguments for BacktestEngine

    Returns:
        Dictionary of model name -> BacktestResult
    """
    results = {}

    for model in models:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running backtest for: {model.name}")
        logger.info('='*50)

        engine = BacktestEngine(model=model, **kwargs)
        result = engine.run(
            financials=financials,
            prices=prices,
            market_caps=market_caps,
            benchmark_prices=benchmark_prices
        )
        results[model.name] = result

    return results
