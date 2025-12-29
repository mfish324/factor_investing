"""
Model comparison and analysis tools.
"""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from scipy import stats
import logging

from backtesting.metrics import BacktestResult, generate_performance_summary

logger = logging.getLogger(__name__)


class ModelComparison:
    """
    Compare performance across multiple factor models.
    """

    def __init__(self, results: Dict[str, BacktestResult] = None):
        self.results = results or {}

    def add_result(self, name: str, result: BacktestResult):
        """Add a backtest result."""
        self.results[name] = result

    def compare_models(self) -> pd.DataFrame:
        """
        Create comparison table of all model metrics.
        """
        if not self.results:
            return pd.DataFrame()

        rows = []
        for name, result in self.results.items():
            m = result.metrics
            rows.append({
                'Model': name,
                'Total Return': m.total_return,
                'Ann. Return': m.annualized_return,
                'Volatility': m.volatility,
                'Sharpe Ratio': m.sharpe_ratio,
                'Sortino Ratio': m.sortino_ratio,
                'Max Drawdown': m.max_drawdown,
                'Calmar Ratio': m.calmar_ratio,
                'Win Rate': m.win_rate,
                'Alpha': m.alpha,
                'Beta': m.beta,
                'Info Ratio': m.information_ratio,
            })

        df = pd.DataFrame(rows).set_index('Model')

        # Format percentages
        pct_cols = ['Total Return', 'Ann. Return', 'Volatility', 'Max Drawdown', 'Win Rate', 'Alpha']
        for col in pct_cols:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "N/A")

        # Format ratios
        ratio_cols = ['Sharpe Ratio', 'Sortino Ratio', 'Calmar Ratio', 'Beta', 'Info Ratio']
        for col in ratio_cols:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")

        return df

    def correlation_analysis(self) -> pd.DataFrame:
        """
        Analyze return correlations between models.
        """
        if not self.results:
            return pd.DataFrame()

        # Create DataFrame of returns
        returns_dict = {}
        for name, result in self.results.items():
            if not result.returns.empty:
                returns_dict[name] = result.returns

        if not returns_dict:
            return pd.DataFrame()

        returns_df = pd.DataFrame(returns_dict)
        return returns_df.corr()

    def relative_performance(self, benchmark_name: str = None) -> pd.DataFrame:
        """
        Calculate relative performance vs benchmark or best model.
        """
        if not self.results:
            return pd.DataFrame()

        if benchmark_name is None:
            # Use highest Sharpe as benchmark
            sharpes = {name: result.metrics.sharpe_ratio
                      for name, result in self.results.items()
                      if pd.notna(result.metrics.sharpe_ratio)}
            if not sharpes:
                return pd.DataFrame()
            benchmark_name = max(sharpes, key=sharpes.get)

        benchmark = self.results.get(benchmark_name)
        if benchmark is None:
            return pd.DataFrame()

        rows = []
        for name, result in self.results.items():
            if name == benchmark_name:
                continue

            m = result.metrics
            bm = benchmark.metrics

            rows.append({
                'Model': name,
                'Return Diff': m.annualized_return - bm.annualized_return,
                'Sharpe Diff': m.sharpe_ratio - bm.sharpe_ratio,
                'Vol Diff': m.volatility - bm.volatility,
                'DD Diff': m.max_drawdown - bm.max_drawdown,
            })

        return pd.DataFrame(rows).set_index('Model')

    def drawdown_comparison(self) -> pd.DataFrame:
        """
        Compare drawdown characteristics.
        """
        rows = []
        for name, result in self.results.items():
            if result.returns.empty:
                continue

            # Calculate drawdown series
            cumulative = (1 + result.returns).cumprod()
            rolling_max = cumulative.cummax()
            drawdown = (cumulative - rolling_max) / rolling_max

            rows.append({
                'Model': name,
                'Max Drawdown': drawdown.min(),
                'Avg Drawdown': drawdown[drawdown < 0].mean(),
                'Drawdown Duration': (drawdown < 0).sum(),
                'Recovery Factor': result.metrics.total_return / abs(drawdown.min()) if drawdown.min() < 0 else np.inf,
            })

        return pd.DataFrame(rows).set_index('Model')

    def monthly_returns_comparison(self) -> pd.DataFrame:
        """
        Compare monthly return statistics.
        """
        rows = []
        for name, result in self.results.items():
            if result.returns.empty:
                continue

            monthly = result.returns.resample('ME').apply(lambda x: (1 + x).prod() - 1)

            rows.append({
                'Model': name,
                'Best Month': monthly.max(),
                'Worst Month': monthly.min(),
                'Avg Month': monthly.mean(),
                'Positive Months': (monthly > 0).sum(),
                'Negative Months': (monthly < 0).sum(),
                'Monthly Std': monthly.std(),
            })

        return pd.DataFrame(rows).set_index('Model')

    def generate_report(self, output_path: str = None) -> str:
        """
        Generate comprehensive comparison report.
        """
        sections = []

        # Header
        sections.append("# Factor Model Comparison Report\n")

        # Main comparison
        sections.append("## Performance Summary\n")
        comparison = self.compare_models()
        if not comparison.empty:
            sections.append(comparison.to_markdown())
            sections.append("\n")

        # Correlation
        sections.append("## Return Correlations\n")
        corr = self.correlation_analysis()
        if not corr.empty:
            sections.append(corr.round(3).to_markdown())
            sections.append("\n")

        # Drawdown
        sections.append("## Drawdown Analysis\n")
        dd = self.drawdown_comparison()
        if not dd.empty:
            sections.append(dd.round(4).to_markdown())
            sections.append("\n")

        # Monthly stats
        sections.append("## Monthly Return Statistics\n")
        monthly = self.monthly_returns_comparison()
        if not monthly.empty:
            sections.append(monthly.round(4).to_markdown())
            sections.append("\n")

        report = "\n".join(sections)

        if output_path:
            with open(output_path, 'w') as f:
                f.write(report)
            logger.info(f"Report saved to {output_path}")

        return report

    def rank_models(self, metric: str = 'sharpe_ratio') -> List[str]:
        """
        Rank models by a specific metric.
        """
        metric_values = {}
        for name, result in self.results.items():
            value = getattr(result.metrics, metric, None)
            if value is not None and pd.notna(value):
                metric_values[name] = value

        # Sort descending (higher is better for most metrics)
        if metric in ['max_drawdown', 'volatility']:
            # Lower is better for these
            sorted_models = sorted(metric_values.keys(), key=lambda x: metric_values[x])
        else:
            sorted_models = sorted(metric_values.keys(), key=lambda x: metric_values[x], reverse=True)

        return sorted_models

    def statistical_significance(
        self,
        model1: str,
        model2: str
    ) -> Dict[str, float]:
        """
        Test statistical significance of performance difference.
        Uses paired t-test on returns.
        """
        result1 = self.results.get(model1)
        result2 = self.results.get(model2)

        if result1 is None or result2 is None:
            return {}

        # Align returns
        common_idx = result1.returns.index.intersection(result2.returns.index)
        if len(common_idx) < 30:
            return {'warning': 'Insufficient data for statistical test'}

        returns1 = result1.returns.loc[common_idx]
        returns2 = result2.returns.loc[common_idx]

        # Paired t-test
        t_stat, p_value = stats.ttest_rel(returns1, returns2)

        return {
            't_statistic': t_stat,
            'p_value': p_value,
            'significant_at_5pct': p_value < 0.05,
            'significant_at_1pct': p_value < 0.01,
            'mean_diff': (returns1 - returns2).mean(),
        }
