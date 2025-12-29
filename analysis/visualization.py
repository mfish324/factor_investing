"""
Visualization tools for factor investing analysis.
"""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from pathlib import Path
import logging

from backtesting.metrics import BacktestResult, calculate_drawdown_series, calculate_rolling_sharpe

logger = logging.getLogger(__name__)

# Try to import visualization libraries
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("Matplotlib not installed. Static charts will be unavailable.")

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False
    logger.warning("Plotly not installed. Interactive charts will be unavailable.")


class FactorVisualizer:
    """
    Generate charts and visualizations for factor analysis.
    """

    def __init__(self, output_dir: str = None, use_plotly: bool = True):
        self.output_dir = Path(output_dir) if output_dir else Path("results/charts")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_plotly = use_plotly and HAS_PLOTLY

    def cumulative_returns_chart(
        self,
        results: Dict[str, BacktestResult],
        title: str = "Cumulative Returns Comparison",
        save_path: str = None
    ):
        """
        Plot cumulative returns for all models + benchmark.
        """
        if self.use_plotly:
            return self._cumulative_returns_plotly(results, title, save_path)
        elif HAS_MATPLOTLIB:
            return self._cumulative_returns_matplotlib(results, title, save_path)
        else:
            logger.warning("No visualization library available")
            return None

    def _cumulative_returns_plotly(
        self,
        results: Dict[str, BacktestResult],
        title: str,
        save_path: str = None
    ):
        """Create cumulative returns chart with Plotly."""
        fig = go.Figure()

        for name, result in results.items():
            if not result.cumulative_returns.empty:
                fig.add_trace(go.Scatter(
                    x=result.cumulative_returns.index,
                    y=result.cumulative_returns.values * 100,
                    name=name,
                    mode='lines'
                ))

        # Add benchmark if available
        first_result = next(iter(results.values()), None)
        if first_result and not first_result.benchmark_cumulative.empty:
            fig.add_trace(go.Scatter(
                x=first_result.benchmark_cumulative.index,
                y=first_result.benchmark_cumulative.values * 100,
                name='Benchmark (SPY)',
                mode='lines',
                line=dict(dash='dash', color='gray')
            ))

        fig.update_layout(
            title=title,
            xaxis_title='Date',
            yaxis_title='Cumulative Return (%)',
            hovermode='x unified',
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
        )

        if save_path:
            fig.write_html(save_path)
            logger.info(f"Chart saved to {save_path}")

        return fig

    def _cumulative_returns_matplotlib(
        self,
        results: Dict[str, BacktestResult],
        title: str,
        save_path: str = None
    ):
        """Create cumulative returns chart with Matplotlib."""
        fig, ax = plt.subplots(figsize=(12, 6))

        for name, result in results.items():
            if not result.cumulative_returns.empty:
                ax.plot(
                    result.cumulative_returns.index,
                    result.cumulative_returns.values * 100,
                    label=name
                )

        # Add benchmark
        first_result = next(iter(results.values()), None)
        if first_result and not first_result.benchmark_cumulative.empty:
            ax.plot(
                first_result.benchmark_cumulative.index,
                first_result.benchmark_cumulative.values * 100,
                label='Benchmark (SPY)',
                linestyle='--',
                color='gray'
            )

        ax.set_title(title)
        ax.set_xlabel('Date')
        ax.set_ylabel('Cumulative Return (%)')
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150)
            logger.info(f"Chart saved to {save_path}")

        return fig

    def drawdown_chart(
        self,
        results: Dict[str, BacktestResult],
        title: str = "Drawdown Comparison",
        save_path: str = None
    ):
        """Plot drawdown series for all models."""
        if self.use_plotly:
            fig = go.Figure()

            for name, result in results.items():
                if result.returns.empty:
                    continue

                drawdown = calculate_drawdown_series(result.returns)
                fig.add_trace(go.Scatter(
                    x=drawdown.index,
                    y=drawdown.values * 100,
                    name=name,
                    mode='lines',
                    fill='tozeroy'
                ))

            fig.update_layout(
                title=title,
                xaxis_title='Date',
                yaxis_title='Drawdown (%)',
                hovermode='x unified'
            )

            if save_path:
                fig.write_html(save_path)

            return fig

        elif HAS_MATPLOTLIB:
            fig, ax = plt.subplots(figsize=(12, 6))

            for name, result in results.items():
                if result.returns.empty:
                    continue

                drawdown = calculate_drawdown_series(result.returns)
                ax.fill_between(drawdown.index, drawdown.values * 100, 0, alpha=0.3, label=name)
                ax.plot(drawdown.index, drawdown.values * 100)

            ax.set_title(title)
            ax.set_xlabel('Date')
            ax.set_ylabel('Drawdown (%)')
            ax.legend()
            ax.grid(True, alpha=0.3)

            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=150)

            return fig

        return None

    def rolling_sharpe_chart(
        self,
        results: Dict[str, BacktestResult],
        window: int = 252,
        title: str = "Rolling Sharpe Ratio (12-month)",
        save_path: str = None
    ):
        """Plot rolling Sharpe ratio for all models."""
        if self.use_plotly:
            fig = go.Figure()

            for name, result in results.items():
                if result.returns.empty:
                    continue

                rolling_sharpe = calculate_rolling_sharpe(result.returns, window)
                fig.add_trace(go.Scatter(
                    x=rolling_sharpe.index,
                    y=rolling_sharpe.values,
                    name=name,
                    mode='lines'
                ))

            fig.update_layout(
                title=title,
                xaxis_title='Date',
                yaxis_title='Sharpe Ratio',
                hovermode='x unified'
            )

            # Add horizontal line at 0
            fig.add_hline(y=0, line_dash="dash", line_color="gray")

            if save_path:
                fig.write_html(save_path)

            return fig

        elif HAS_MATPLOTLIB:
            fig, ax = plt.subplots(figsize=(12, 6))

            for name, result in results.items():
                if result.returns.empty:
                    continue

                rolling_sharpe = calculate_rolling_sharpe(result.returns, window)
                ax.plot(rolling_sharpe.index, rolling_sharpe.values, label=name)

            ax.axhline(y=0, linestyle='--', color='gray')
            ax.set_title(title)
            ax.set_xlabel('Date')
            ax.set_ylabel('Sharpe Ratio')
            ax.legend()
            ax.grid(True, alpha=0.3)

            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=150)

            return fig

        return None

    def performance_table(
        self,
        results: Dict[str, BacktestResult],
        title: str = "Performance Summary",
        save_path: str = None
    ):
        """Create performance summary table."""
        if not HAS_PLOTLY:
            return None

        rows = []
        for name, result in results.items():
            m = result.metrics
            rows.append([
                name,
                f"{m.total_return:.2%}",
                f"{m.annualized_return:.2%}",
                f"{m.volatility:.2%}",
                f"{m.sharpe_ratio:.2f}",
                f"{m.sortino_ratio:.2f}",
                f"{m.max_drawdown:.2%}",
                f"{m.calmar_ratio:.2f}",
                f"{m.win_rate:.2%}",
            ])

        fig = go.Figure(data=[go.Table(
            header=dict(
                values=['Model', 'Total Return', 'Ann. Return', 'Volatility',
                       'Sharpe', 'Sortino', 'Max DD', 'Calmar', 'Win Rate'],
                fill_color='lightgray',
                align='left'
            ),
            cells=dict(
                values=list(zip(*rows)),
                fill_color='white',
                align='left'
            )
        )])

        fig.update_layout(title=title)

        if save_path:
            fig.write_html(save_path)

        return fig

    def factor_heatmap(
        self,
        factor_df: pd.DataFrame,
        title: str = "Factor Exposures",
        save_path: str = None
    ):
        """Create heatmap of factor exposures."""
        if factor_df.empty:
            return None

        if self.use_plotly:
            # Limit to top 30 stocks and key factors
            if len(factor_df) > 30:
                factor_df = factor_df.head(30)

            fig = go.Figure(data=go.Heatmap(
                z=factor_df.values,
                x=factor_df.columns,
                y=factor_df.index,
                colorscale='RdBu',
                zmid=0
            ))

            fig.update_layout(
                title=title,
                xaxis_title='Factor',
                yaxis_title='Stock'
            )

            if save_path:
                fig.write_html(save_path)

            return fig

        elif HAS_MATPLOTLIB:
            fig, ax = plt.subplots(figsize=(14, 10))

            if len(factor_df) > 30:
                factor_df = factor_df.head(30)

            im = ax.imshow(factor_df.values, cmap='RdBu', aspect='auto')

            ax.set_xticks(range(len(factor_df.columns)))
            ax.set_xticklabels(factor_df.columns, rotation=45, ha='right')
            ax.set_yticks(range(len(factor_df.index)))
            ax.set_yticklabels(factor_df.index)

            plt.colorbar(im)
            ax.set_title(title)

            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=150)

            return fig

        return None

    def holdings_over_time(
        self,
        result: BacktestResult,
        title: str = "Holdings Over Time",
        save_path: str = None
    ):
        """Visualize how holdings change over time."""
        if result.holdings_history.empty:
            return None

        if not HAS_PLOTLY:
            return None

        # Pivot to get stocks over time
        if 'ticker' in result.holdings_history.columns:
            holdings = result.holdings_history.reset_index()
            holdings['held'] = 1

            # Group by date and ticker
            pivot = holdings.pivot_table(
                values='held',
                index='date',
                columns='ticker',
                fill_value=0
            )

            # Create heatmap
            fig = go.Figure(data=go.Heatmap(
                z=pivot.values.T,
                x=pivot.index,
                y=pivot.columns,
                colorscale=[[0, 'white'], [1, 'blue']],
                showscale=False
            ))

            fig.update_layout(
                title=title,
                xaxis_title='Date',
                yaxis_title='Stock'
            )

            if save_path:
                fig.write_html(save_path)

            return fig

        return None

    def generate_report(
        self,
        results: Dict[str, BacktestResult],
        output_dir: str = None
    ) -> str:
        """
        Generate complete HTML report with all visualizations.
        """
        if not HAS_PLOTLY:
            logger.warning("Plotly required for HTML report generation")
            return ""

        output_dir = Path(output_dir) if output_dir else self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate all charts
        charts = {}

        charts['cumulative'] = self.cumulative_returns_chart(
            results, save_path=str(output_dir / 'cumulative_returns.html')
        )
        charts['drawdown'] = self.drawdown_chart(
            results, save_path=str(output_dir / 'drawdown.html')
        )
        charts['sharpe'] = self.rolling_sharpe_chart(
            results, save_path=str(output_dir / 'rolling_sharpe.html')
        )
        charts['table'] = self.performance_table(
            results, save_path=str(output_dir / 'performance_table.html')
        )

        # Create combined HTML report
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>Factor Investing Analysis Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            "h1 { color: #333; }",
            "h2 { color: #666; }",
            ".chart { margin: 20px 0; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Factor Investing Analysis Report</h1>",
        ]

        for name, chart in charts.items():
            if chart is not None:
                html_parts.append(f"<div class='chart'>")
                html_parts.append(chart.to_html(full_html=False, include_plotlyjs='cdn'))
                html_parts.append("</div>")

        html_parts.extend(["</body>", "</html>"])

        report_path = output_dir / 'full_report.html'
        with open(report_path, 'w') as f:
            f.write("\n".join(html_parts))

        logger.info(f"Full report saved to {report_path}")

        return str(report_path)
