"""
Strategy data export utilities for rotation analysis.
"""

from pathlib import Path
from typing import Dict, Optional
import pandas as pd
import logging

from .metrics import BacktestResult
from config import RESULTS_DIR

logger = logging.getLogger(__name__)


class StrategyDataExporter:
    """
    Export and manage daily strategy equity curves for rotation analysis.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize the exporter.

        Args:
            output_dir: Directory to store exported data. Defaults to results/strategy_curves/
        """
        self.output_dir = output_dir or RESULTS_DIR / "strategy_curves"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_results(
        self,
        results: Dict[str, BacktestResult],
        format: str = 'parquet'
    ) -> Path:
        """
        Export daily P&L data for all strategies to a single file.

        Args:
            results: Dictionary of strategy name -> BacktestResult
            format: Output format ('parquet' or 'csv')

        Returns:
            Path to the exported file
        """
        all_data = []

        for strategy_name, result in results.items():
            if result.returns.empty:
                logger.warning(f"No returns data for {strategy_name}, skipping")
                continue

            # Build daily data from BacktestResult
            df = pd.DataFrame({
                'date': result.returns.index,
                'strategy': strategy_name,
                'daily_return': result.returns.values,
                'cumulative_return': result.cumulative_returns.values,
                'portfolio_value': result.portfolio_values.values,
            })

            # Calculate drawdown
            cumulative = (1 + result.returns).cumprod()
            rolling_max = cumulative.cummax()
            df['drawdown'] = ((cumulative - rolling_max) / rolling_max).values

            all_data.append(df)

        if not all_data:
            raise ValueError("No valid strategy data to export")

        combined = pd.concat(all_data, ignore_index=True)

        # Export to file
        if format == 'parquet':
            output_path = self.output_dir / "all_strategies_daily.parquet"
            combined.to_parquet(output_path, index=False)
        elif format == 'csv':
            output_path = self.output_dir / "all_strategies_daily.csv"
            combined.to_csv(output_path, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Exported {len(results)} strategies to {output_path}")
        logger.info(f"Date range: {combined['date'].min()} to {combined['date'].max()}")
        logger.info(f"Total rows: {len(combined)}")

        return output_path

    def load_strategy_curves(self, format: str = 'parquet') -> pd.DataFrame:
        """
        Load previously exported strategy curves.

        Args:
            format: File format to load ('parquet' or 'csv')

        Returns:
            DataFrame with all strategy data
        """
        if format == 'parquet':
            file_path = self.output_dir / "all_strategies_daily.parquet"
            if not file_path.exists():
                raise FileNotFoundError(f"No exported data found at {file_path}")
            return pd.read_parquet(file_path)
        elif format == 'csv':
            file_path = self.output_dir / "all_strategies_daily.csv"
            if not file_path.exists():
                raise FileNotFoundError(f"No exported data found at {file_path}")
            df = pd.read_csv(file_path)
            df['date'] = pd.to_datetime(df['date'])
            return df
        else:
            raise ValueError(f"Unsupported format: {format}")

    def get_strategy_equity_curve(
        self,
        strategy_name: str,
        df: Optional[pd.DataFrame] = None
    ) -> pd.Series:
        """
        Extract a single strategy's equity curve (portfolio values).

        Args:
            strategy_name: Name of the strategy
            df: Optional pre-loaded DataFrame, otherwise loads from file

        Returns:
            Series with date index and portfolio values
        """
        if df is None:
            df = self.load_strategy_curves()

        strategy_data = df[df['strategy'] == strategy_name].copy()
        if strategy_data.empty:
            raise ValueError(f"Strategy '{strategy_name}' not found in data")

        strategy_data = strategy_data.set_index('date').sort_index()
        return strategy_data['portfolio_value']

    def get_strategy_returns(
        self,
        strategy_name: str,
        df: Optional[pd.DataFrame] = None
    ) -> pd.Series:
        """
        Extract a single strategy's daily returns.

        Args:
            strategy_name: Name of the strategy
            df: Optional pre-loaded DataFrame, otherwise loads from file

        Returns:
            Series with date index and daily returns
        """
        if df is None:
            df = self.load_strategy_curves()

        strategy_data = df[df['strategy'] == strategy_name].copy()
        if strategy_data.empty:
            raise ValueError(f"Strategy '{strategy_name}' not found in data")

        strategy_data = strategy_data.set_index('date').sort_index()
        return strategy_data['daily_return']

    def get_all_strategy_returns(
        self,
        df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Get daily returns for all strategies as a wide-format DataFrame.

        Args:
            df: Optional pre-loaded DataFrame, otherwise loads from file

        Returns:
            DataFrame with date index and strategy columns
        """
        if df is None:
            df = self.load_strategy_curves()

        # Pivot to wide format
        returns_wide = df.pivot(
            index='date',
            columns='strategy',
            values='daily_return'
        )
        returns_wide.index = pd.to_datetime(returns_wide.index)
        return returns_wide.sort_index()

    def get_all_strategy_values(
        self,
        df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Get portfolio values for all strategies as a wide-format DataFrame.

        Args:
            df: Optional pre-loaded DataFrame, otherwise loads from file

        Returns:
            DataFrame with date index and strategy columns
        """
        if df is None:
            df = self.load_strategy_curves()

        # Pivot to wide format
        values_wide = df.pivot(
            index='date',
            columns='strategy',
            values='portfolio_value'
        )
        values_wide.index = pd.to_datetime(values_wide.index)
        return values_wide.sort_index()

    def list_strategies(self, df: Optional[pd.DataFrame] = None) -> list:
        """
        List all available strategies in the exported data.

        Args:
            df: Optional pre-loaded DataFrame, otherwise loads from file

        Returns:
            List of strategy names
        """
        if df is None:
            df = self.load_strategy_curves()
        return df['strategy'].unique().tolist()

    def get_date_range(self, df: Optional[pd.DataFrame] = None) -> tuple:
        """
        Get the date range of the exported data.

        Args:
            df: Optional pre-loaded DataFrame, otherwise loads from file

        Returns:
            Tuple of (start_date, end_date)
        """
        if df is None:
            df = self.load_strategy_curves()
        return df['date'].min(), df['date'].max()
