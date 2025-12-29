"""
Performance metrics for backtesting.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from scipy import stats
import logging

from config import RISK_FREE_RATE, TRADING_DAYS_PER_YEAR

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Calculated performance metrics."""
    total_return: float = 0.0
    annualized_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0

    # Benchmark comparison
    alpha: float = 0.0
    beta: float = 0.0
    information_ratio: float = 0.0
    tracking_error: float = 0.0

    # Additional stats
    best_month: float = 0.0
    worst_month: float = 0.0
    positive_months: int = 0
    negative_months: int = 0
    avg_monthly_return: float = 0.0


@dataclass
class BacktestResult:
    """
    Complete backtest results including returns and metrics.
    """
    model_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float

    # Time series
    returns: pd.Series = field(default_factory=pd.Series)
    cumulative_returns: pd.Series = field(default_factory=pd.Series)
    portfolio_values: pd.Series = field(default_factory=pd.Series)
    holdings_history: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Benchmark
    benchmark_returns: pd.Series = field(default_factory=pd.Series)
    benchmark_cumulative: pd.Series = field(default_factory=pd.Series)

    # Metrics
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)

    # Trades
    trades: List[Dict] = field(default_factory=list)
    turnover: pd.Series = field(default_factory=pd.Series)


def calculate_metrics(
    returns: pd.Series,
    benchmark_returns: pd.Series = None,
    risk_free_rate: float = None,
    periods_per_year: int = None
) -> PerformanceMetrics:
    """
    Calculate comprehensive performance metrics.

    Args:
        returns: Series of periodic returns
        benchmark_returns: Optional benchmark returns for relative metrics
        risk_free_rate: Annual risk-free rate (defaults to config)
        periods_per_year: Number of periods per year (defaults to config)

    Returns:
        PerformanceMetrics object
    """
    risk_free_rate = risk_free_rate or RISK_FREE_RATE
    periods_per_year = periods_per_year or TRADING_DAYS_PER_YEAR

    metrics = PerformanceMetrics()

    if returns.empty or len(returns) < 2:
        return metrics

    # Clean returns
    returns = returns.dropna()

    # Total and annualized return
    cumulative = (1 + returns).cumprod()
    metrics.total_return = cumulative.iloc[-1] - 1

    years = len(returns) / periods_per_year
    if years > 0:
        metrics.annualized_return = (1 + metrics.total_return) ** (1 / years) - 1

    # Volatility (annualized)
    metrics.volatility = returns.std() * np.sqrt(periods_per_year)

    # Sharpe Ratio
    excess_returns = returns - risk_free_rate / periods_per_year
    if returns.std() > 0:
        metrics.sharpe_ratio = excess_returns.mean() / returns.std() * np.sqrt(periods_per_year)

    # Sortino Ratio (downside deviation)
    negative_returns = returns[returns < 0]
    if len(negative_returns) > 0:
        downside_std = negative_returns.std()
        if downside_std > 0:
            metrics.sortino_ratio = excess_returns.mean() / downside_std * np.sqrt(periods_per_year)

    # Maximum Drawdown
    cumulative = (1 + returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max
    metrics.max_drawdown = drawdown.min()

    # Calmar Ratio
    if metrics.max_drawdown < 0:
        metrics.calmar_ratio = metrics.annualized_return / abs(metrics.max_drawdown)

    # Win Rate
    positive_returns = returns[returns > 0]
    negative_returns = returns[returns < 0]
    total_periods = len(returns)
    metrics.win_rate = len(positive_returns) / total_periods if total_periods > 0 else 0

    # Average Win/Loss
    metrics.avg_win = positive_returns.mean() if len(positive_returns) > 0 else 0
    metrics.avg_loss = negative_returns.mean() if len(negative_returns) > 0 else 0

    # Profit Factor
    gross_profit = positive_returns.sum() if len(positive_returns) > 0 else 0
    gross_loss = abs(negative_returns.sum()) if len(negative_returns) > 0 else 0
    if gross_loss > 0:
        metrics.profit_factor = gross_profit / gross_loss

    # Monthly stats (if we have daily data)
    if periods_per_year >= 252:  # Assume daily data
        monthly_returns = returns.resample('ME').apply(lambda x: (1 + x).prod() - 1)
        if len(monthly_returns) > 0:
            metrics.best_month = monthly_returns.max()
            metrics.worst_month = monthly_returns.min()
            metrics.positive_months = (monthly_returns > 0).sum()
            metrics.negative_months = (monthly_returns < 0).sum()
            metrics.avg_monthly_return = monthly_returns.mean()

    # Benchmark-relative metrics
    if benchmark_returns is not None and len(benchmark_returns) > 0:
        # Align indices
        common_idx = returns.index.intersection(benchmark_returns.index)
        if len(common_idx) > 10:
            aligned_returns = returns.loc[common_idx]
            aligned_bench = benchmark_returns.loc[common_idx]

            # Beta
            covariance = np.cov(aligned_returns, aligned_bench)[0, 1]
            bench_variance = np.var(aligned_bench)
            if bench_variance > 0:
                metrics.beta = covariance / bench_variance

            # Alpha (Jensen's alpha)
            bench_return = (1 + aligned_bench).prod() ** (periods_per_year / len(aligned_bench)) - 1
            expected_return = risk_free_rate + metrics.beta * (bench_return - risk_free_rate)
            metrics.alpha = metrics.annualized_return - expected_return

            # Tracking Error and Information Ratio
            excess = aligned_returns - aligned_bench
            metrics.tracking_error = excess.std() * np.sqrt(periods_per_year)
            if metrics.tracking_error > 0:
                metrics.information_ratio = (aligned_returns.mean() - aligned_bench.mean()) / excess.std() * np.sqrt(periods_per_year)

    return metrics


def calculate_drawdown_series(returns: pd.Series) -> pd.Series:
    """
    Calculate drawdown series from returns.

    Args:
        returns: Series of returns

    Returns:
        Series of drawdown values (negative)
    """
    cumulative = (1 + returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max
    return drawdown


def calculate_rolling_sharpe(
    returns: pd.Series,
    window: int = 252,
    risk_free_rate: float = None,
    periods_per_year: int = None
) -> pd.Series:
    """
    Calculate rolling Sharpe ratio.

    Args:
        returns: Series of returns
        window: Rolling window size
        risk_free_rate: Annual risk-free rate
        periods_per_year: Periods per year

    Returns:
        Series of rolling Sharpe ratios
    """
    risk_free_rate = risk_free_rate or RISK_FREE_RATE
    periods_per_year = periods_per_year or TRADING_DAYS_PER_YEAR

    excess = returns - risk_free_rate / periods_per_year
    rolling_mean = excess.rolling(window).mean()
    rolling_std = returns.rolling(window).std()

    sharpe = (rolling_mean / rolling_std) * np.sqrt(periods_per_year)
    return sharpe


def calculate_turnover(
    holdings_history: pd.DataFrame
) -> pd.Series:
    """
    Calculate portfolio turnover from holdings history.

    Args:
        holdings_history: DataFrame with holdings by date

    Returns:
        Series of turnover rates
    """
    if holdings_history.empty:
        return pd.Series(dtype=float)

    turnovers = []
    dates = holdings_history.index.unique()

    for i in range(1, len(dates)):
        prev_date = dates[i - 1]
        curr_date = dates[i]

        prev_holdings = set(
            holdings_history.loc[prev_date, 'ticker']
            if isinstance(holdings_history.loc[prev_date], pd.DataFrame)
            else [holdings_history.loc[prev_date, 'ticker']]
        )
        curr_holdings = set(
            holdings_history.loc[curr_date, 'ticker']
            if isinstance(holdings_history.loc[curr_date], pd.DataFrame)
            else [holdings_history.loc[curr_date, 'ticker']]
        )

        if prev_holdings:
            # Turnover = 1 - overlap
            overlap = len(prev_holdings.intersection(curr_holdings))
            turnover = 1 - overlap / len(prev_holdings)
            turnovers.append({'date': curr_date, 'turnover': turnover})

    if not turnovers:
        return pd.Series(dtype=float)

    df = pd.DataFrame(turnovers).set_index('date')
    return df['turnover']


def generate_performance_summary(result: BacktestResult) -> pd.DataFrame:
    """
    Generate a summary table of performance metrics.

    Args:
        result: BacktestResult object

    Returns:
        DataFrame with metrics
    """
    m = result.metrics

    summary = {
        'Metric': [
            'Total Return',
            'Annualized Return',
            'Volatility',
            'Sharpe Ratio',
            'Sortino Ratio',
            'Max Drawdown',
            'Calmar Ratio',
            'Win Rate',
            'Profit Factor',
            'Alpha',
            'Beta',
            'Information Ratio',
            'Best Month',
            'Worst Month',
        ],
        'Value': [
            f"{m.total_return:.2%}",
            f"{m.annualized_return:.2%}",
            f"{m.volatility:.2%}",
            f"{m.sharpe_ratio:.2f}",
            f"{m.sortino_ratio:.2f}",
            f"{m.max_drawdown:.2%}",
            f"{m.calmar_ratio:.2f}",
            f"{m.win_rate:.2%}",
            f"{m.profit_factor:.2f}",
            f"{m.alpha:.2%}",
            f"{m.beta:.2f}",
            f"{m.information_ratio:.2f}",
            f"{m.best_month:.2%}",
            f"{m.worst_month:.2%}",
        ]
    }

    return pd.DataFrame(summary)
