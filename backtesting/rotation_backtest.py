"""
Backtester for the strategy rotation meta-strategy.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import logging

from .metrics import BacktestResult, PerformanceMetrics, calculate_metrics
from models.rotation import StrategyRotationModel, AllocationMethod
from config import (
    ROTATION_TRANSACTION_COST_BPS,
    ROTATION_MIN_HOLDING_DAYS,
    TRADING_DAYS_PER_YEAR,
)

logger = logging.getLogger(__name__)


@dataclass
class RotationBacktestResult:
    """
    Results from a rotation strategy backtest.
    """
    # Core backtest result
    backtest_result: BacktestResult

    # Allocation history
    allocation_history: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Switch statistics
    switch_count: int = 0
    switches: List[Dict] = field(default_factory=list)

    # Benchmark comparisons
    vs_best_strategy: float = 0.0      # Alpha vs best single strategy
    vs_equal_weight: float = 0.0       # Alpha vs equal-weight benchmark
    vs_individual: Dict[str, float] = field(default_factory=dict)  # Alpha vs each strategy

    # Additional metrics
    avg_strategies_held: float = 0.0
    transaction_costs_total: float = 0.0


class RotationBacktester:
    """
    Backtest the strategy rotation meta-strategy.
    """

    def __init__(
        self,
        rotation_model: StrategyRotationModel = None,
        method: str = "weighted",
        rebalance_freq: str = "weekly",
        transaction_cost_bps: float = None,
        min_holding_days: int = None,
        initial_capital: float = 100000.0,
    ):
        """
        Initialize the rotation backtester.

        Args:
            rotation_model: Pre-configured StrategyRotationModel (or creates one)
            method: Allocation method if creating a new model
            rebalance_freq: Rebalance frequency
            transaction_cost_bps: Transaction cost in basis points per switch
            min_holding_days: Minimum days before switching
            initial_capital: Starting capital
        """
        if rotation_model is None:
            rotation_model = StrategyRotationModel(
                method=method,
                rebalance_freq=rebalance_freq,
                min_holding_days=min_holding_days or ROTATION_MIN_HOLDING_DAYS,
            )

        self.rotation_model = rotation_model
        self.transaction_cost_bps = transaction_cost_bps or ROTATION_TRANSACTION_COST_BPS
        self.initial_capital = initial_capital
        self.min_holding_days = min_holding_days or ROTATION_MIN_HOLDING_DAYS

    def run(
        self,
        strategy_returns: pd.DataFrame,
        strategy_values: pd.DataFrame,
    ) -> RotationBacktestResult:
        """
        Run the rotation backtest.

        Args:
            strategy_returns: DataFrame with date index and strategy return columns
            strategy_values: DataFrame with date index and strategy value columns

        Returns:
            RotationBacktestResult with full backtest results
        """
        logger.info("Starting rotation backtest...")
        logger.info(f"Method: {self.rotation_model.method.value}")
        logger.info(f"Rebalance frequency: {self.rotation_model.rebalance_freq}")
        logger.info(f"Date range: {strategy_returns.index.min()} to {strategy_returns.index.max()}")

        # Generate allocation history
        allocation_history = self.rotation_model.generate_rotation_history(
            strategy_values,
            rebalance_freq=self.rotation_model.rebalance_freq
        )

        if allocation_history.empty:
            logger.error("No allocation history generated")
            return self._empty_result()

        # Forward fill allocations to all trading days
        full_allocations = allocation_history.reindex(strategy_returns.index).ffill()

        # Skip initial period where we don't have allocations
        first_valid_date = full_allocations.dropna().index.min()
        full_allocations = full_allocations.loc[first_valid_date:]
        strategy_returns_aligned = strategy_returns.loc[first_valid_date:]

        # Calculate rotation strategy returns
        rotation_returns, transaction_costs, switches = self._calculate_returns(
            strategy_returns_aligned,
            full_allocations
        )

        # Calculate cumulative returns
        cumulative_returns = (1 + rotation_returns).cumprod() - 1

        # Calculate portfolio values
        portfolio_values = self.initial_capital * (1 + cumulative_returns)

        # Calculate performance metrics
        metrics = calculate_metrics(rotation_returns)

        # Create BacktestResult
        backtest_result = BacktestResult(
            model_name="Rotation Strategy",
            start_date=str(rotation_returns.index.min().date()),
            end_date=str(rotation_returns.index.max().date()),
            initial_capital=self.initial_capital,
            final_value=portfolio_values.iloc[-1],
            returns=rotation_returns,
            cumulative_returns=cumulative_returns,
            portfolio_values=portfolio_values,
            metrics=metrics,
        )

        # Calculate benchmark comparisons
        benchmarks = self._calculate_benchmarks(
            strategy_returns_aligned,
            rotation_returns
        )

        # Calculate average strategies held
        avg_held = (full_allocations > 0).sum(axis=1).mean()

        # Create result
        result = RotationBacktestResult(
            backtest_result=backtest_result,
            allocation_history=allocation_history,
            switch_count=len(switches),
            switches=switches,
            vs_best_strategy=benchmarks['vs_best'],
            vs_equal_weight=benchmarks['vs_equal_weight'],
            vs_individual=benchmarks['vs_individual'],
            avg_strategies_held=avg_held,
            transaction_costs_total=sum(transaction_costs),
        )

        self._log_results(result)
        return result

    def _calculate_returns(
        self,
        strategy_returns: pd.DataFrame,
        allocations: pd.DataFrame
    ) -> tuple:
        """
        Calculate rotation strategy returns including transaction costs.

        Returns:
            Tuple of (returns Series, transaction_costs list, switches list)
        """
        rotation_returns = []
        transaction_costs = []
        switches = []
        prev_allocation = None

        for date in strategy_returns.index:
            if date not in allocations.index:
                rotation_returns.append(0)
                continue

            current_allocation = allocations.loc[date]

            # Calculate weighted return for this day
            daily_returns = strategy_returns.loc[date]
            weighted_return = (current_allocation * daily_returns).sum()

            # Calculate transaction costs if allocation changed
            cost = 0
            if prev_allocation is not None:
                allocation_change = (current_allocation - prev_allocation).abs().sum()
                if allocation_change > 0.01:  # Meaningful change
                    # Cost is proportional to turnover
                    cost = allocation_change * (self.transaction_cost_bps / 10000)
                    transaction_costs.append(cost)

                    switches.append({
                        'date': date,
                        'from': prev_allocation.to_dict(),
                        'to': current_allocation.to_dict(),
                        'turnover': allocation_change,
                        'cost': cost,
                    })

            net_return = weighted_return - cost
            rotation_returns.append(net_return)
            prev_allocation = current_allocation.copy()

        return pd.Series(rotation_returns, index=strategy_returns.index), transaction_costs, switches

    def _calculate_benchmarks(
        self,
        strategy_returns: pd.DataFrame,
        rotation_returns: pd.Series
    ) -> Dict[str, float]:
        """Calculate benchmark comparisons."""
        benchmarks = {
            'vs_best': 0.0,
            'vs_equal_weight': 0.0,
            'vs_individual': {},
        }

        # Equal weight benchmark
        equal_weight_returns = strategy_returns.mean(axis=1)
        equal_weight_total = (1 + equal_weight_returns).prod() - 1
        rotation_total = (1 + rotation_returns).prod() - 1

        benchmarks['vs_equal_weight'] = rotation_total - equal_weight_total

        # Best single strategy
        best_return = -np.inf
        best_strategy = None
        for strategy in strategy_returns.columns:
            strat_total = (1 + strategy_returns[strategy]).prod() - 1
            benchmarks['vs_individual'][strategy] = rotation_total - strat_total
            if strat_total > best_return:
                best_return = strat_total
                best_strategy = strategy

        benchmarks['vs_best'] = rotation_total - best_return
        benchmarks['best_strategy'] = best_strategy

        return benchmarks

    def _log_results(self, result: RotationBacktestResult):
        """Log backtest results."""
        m = result.backtest_result.metrics

        logger.info("\n" + "=" * 60)
        logger.info("ROTATION BACKTEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"Total Return: {m.total_return:.2%}")
        logger.info(f"Annualized Return: {m.annualized_return:.2%}")
        logger.info(f"Sharpe Ratio: {m.sharpe_ratio:.2f}")
        logger.info(f"Max Drawdown: {m.max_drawdown:.2%}")
        logger.info(f"\nStrategy Switches: {result.switch_count}")
        logger.info(f"Avg Strategies Held: {result.avg_strategies_held:.1f}")
        logger.info(f"Transaction Costs: ${result.transaction_costs_total:,.2f}")
        logger.info(f"\nAlpha vs Equal Weight: {result.vs_equal_weight:.2%}")
        logger.info(f"Alpha vs Best Strategy: {result.vs_best_strategy:.2%}")

    def _empty_result(self) -> RotationBacktestResult:
        """Return empty result on failure."""
        return RotationBacktestResult(
            backtest_result=BacktestResult(
                model_name="Rotation Strategy",
                start_date="",
                end_date="",
                initial_capital=self.initial_capital,
                final_value=self.initial_capital,
                metrics=PerformanceMetrics()
            )
        )


def compare_rotation_methods(
    strategy_returns: pd.DataFrame,
    strategy_values: pd.DataFrame,
    methods: List[str] = None
) -> Dict[str, RotationBacktestResult]:
    """
    Compare different rotation methods.

    Args:
        strategy_returns: DataFrame with strategy daily returns
        strategy_values: DataFrame with strategy portfolio values
        methods: List of methods to compare (default: all)

    Returns:
        Dictionary of method -> RotationBacktestResult
    """
    if methods is None:
        methods = ['binary', 'weighted', 'momentum', 'top_n']

    results = {}

    for method in methods:
        logger.info(f"\nRunning backtest with method: {method}")
        backtester = RotationBacktester(method=method)
        results[method] = backtester.run(strategy_returns, strategy_values)

    return results


def generate_rotation_comparison_report(
    results: Dict[str, RotationBacktestResult]
) -> pd.DataFrame:
    """
    Generate a comparison table of rotation methods.

    Args:
        results: Dictionary of method -> RotationBacktestResult

    Returns:
        DataFrame with comparison metrics
    """
    rows = []

    for method, result in results.items():
        m = result.backtest_result.metrics
        rows.append({
            'Method': method,
            'Total Return': m.total_return,
            'Ann. Return': m.annualized_return,
            'Volatility': m.volatility,
            'Sharpe': m.sharpe_ratio,
            'Max DD': m.max_drawdown,
            'Switches': result.switch_count,
            'Avg Held': result.avg_strategies_held,
            'Costs': result.transaction_costs_total,
            'vs EW': result.vs_equal_weight,
            'vs Best': result.vs_best_strategy,
        })

    df = pd.DataFrame(rows)

    # Format percentages
    pct_cols = ['Total Return', 'Ann. Return', 'Volatility', 'Max DD', 'vs EW', 'vs Best']
    for col in pct_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"{x:.2%}")

    return df
