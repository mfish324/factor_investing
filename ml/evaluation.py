"""
ML model evaluation metrics.
"""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from scipy import stats
import logging

logger = logging.getLogger(__name__)


class MLModelEvaluator:
    """
    Comprehensive evaluation metrics for factor ML models.
    """

    def __init__(self, benchmark_returns: pd.Series = None):
        self.benchmark = benchmark_returns

    def information_coefficient(
        self,
        predicted: pd.Series,
        actual: pd.Series
    ) -> float:
        """
        Spearman rank correlation between predictions and actual returns.
        IC > 0.05 is generally considered good for factor models.
        """
        # Align indices
        common = predicted.index.intersection(actual.index)
        if len(common) < 10:
            return np.nan

        return stats.spearmanr(
            predicted.loc[common],
            actual.loc[common]
        )[0]

    def ic_information_ratio(self, ic_series: pd.Series) -> float:
        """
        Mean IC / Std IC
        Measures consistency of predictive power.
        """
        if ic_series.std() == 0:
            return np.nan
        return ic_series.mean() / ic_series.std()

    def quantile_returns(
        self,
        scores: pd.Series,
        returns: pd.Series,
        n_quantiles: int = 5
    ) -> pd.DataFrame:
        """
        Compute returns for each quantile of predicted scores.
        Top quantile should significantly outperform bottom.
        """
        common = scores.index.intersection(returns.index)
        scores = scores.loc[common]
        returns = returns.loc[common]

        if len(common) < n_quantiles * 2:
            return pd.DataFrame()

        try:
            quantiles = pd.qcut(scores, n_quantiles, labels=range(n_quantiles))
            quantile_returns = returns.groupby(quantiles).agg(['mean', 'std', 'count'])
            quantile_returns.index.name = 'quantile'
            return quantile_returns
        except ValueError:
            return pd.DataFrame()

    def long_short_return(
        self,
        scores: pd.Series,
        returns: pd.Series,
        top_pct: float = 0.2,
        bottom_pct: float = 0.2
    ) -> float:
        """
        Return from going long top stocks, short bottom stocks.
        """
        common = scores.index.intersection(returns.index)
        scores = scores.loc[common]
        returns = returns.loc[common]

        n = len(scores)
        if n < 10:
            return np.nan

        top_n = max(1, int(n * top_pct))
        bottom_n = max(1, int(n * bottom_pct))

        top_tickers = scores.nlargest(top_n).index
        bottom_tickers = scores.nsmallest(bottom_n).index

        long_return = returns.loc[top_tickers].mean()
        short_return = returns.loc[bottom_tickers].mean()

        return long_return - short_return

    def hit_rate(
        self,
        scores: pd.Series,
        returns: pd.Series,
        top_pct: float = 0.2
    ) -> float:
        """
        Percentage of top-scored stocks with positive returns.
        """
        common = scores.index.intersection(returns.index)
        scores = scores.loc[common]
        returns = returns.loc[common]

        n = len(scores)
        top_n = max(1, int(n * top_pct))

        top_tickers = scores.nlargest(top_n).index
        top_returns = returns.loc[top_tickers]

        return (top_returns > 0).mean()

    def turnover_analysis(
        self,
        portfolios: List[set],
        dates: List[str]
    ) -> pd.Series:
        """
        Measure portfolio turnover between rebalancing periods.
        """
        if len(portfolios) < 2:
            return pd.Series(dtype=float)

        turnovers = []
        for i in range(1, len(portfolios)):
            prev = portfolios[i - 1]
            curr = portfolios[i]
            if prev:
                overlap = len(prev & curr)
                turnover = 1 - overlap / len(prev)
                turnovers.append(turnover)

        if len(turnovers) != len(dates) - 1:
            return pd.Series(turnovers)

        return pd.Series(turnovers, index=dates[1:])

    def factor_decay_analysis(
        self,
        scores: pd.Series,
        forward_returns: Dict[int, pd.Series]
    ) -> pd.Series:
        """
        Analyze how predictive power decays over time.
        Test IC at different horizons.
        """
        decay = {}
        for horizon, returns in forward_returns.items():
            ic = self.information_coefficient(scores, returns)
            decay[horizon] = ic

        return pd.Series(decay)

    def sector_analysis(
        self,
        scores: pd.Series,
        returns: pd.Series,
        sectors: pd.Series
    ) -> pd.DataFrame:
        """
        Analyze model performance by sector.
        """
        common = scores.index.intersection(returns.index).intersection(sectors.index)
        if len(common) < 20:
            return pd.DataFrame()

        scores = scores.loc[common]
        returns = returns.loc[common]
        sectors = sectors.loc[common]

        results = {}
        for sector in sectors.unique():
            sector_mask = sectors == sector
            sector_scores = scores[sector_mask]
            sector_returns = returns[sector_mask]

            if len(sector_scores) < 5:
                continue

            results[sector] = {
                'ic': self.information_coefficient(sector_scores, sector_returns),
                'long_short': self.long_short_return(sector_scores, sector_returns),
                'n_stocks': sector_mask.sum(),
                'avg_return': sector_returns.mean()
            }

        return pd.DataFrame(results).T

    def generate_evaluation_report(
        self,
        model,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        sectors: pd.Series = None
    ) -> Dict:
        """
        Generate comprehensive evaluation report.
        """
        predictions = model.predict(X_test)

        report = {
            'ic': self.information_coefficient(predictions, y_test),
            'quantile_returns': self.quantile_returns(predictions, y_test),
            'long_short_return': self.long_short_return(predictions, y_test),
            'hit_rate': self.hit_rate(predictions, y_test),
        }

        # Feature importance
        if hasattr(model, 'feature_importance_') and model.feature_importance_ is not None:
            report['feature_importance'] = model.feature_importance_.head(20).to_dict()

        # Sector analysis
        if sectors is not None:
            sector_report = self.sector_analysis(predictions, y_test, sectors)
            if not sector_report.empty:
                report['sector_analysis'] = sector_report.to_dict()

        return report

    def compare_models(
        self,
        models: Dict[str, 'FactorMLModel'],
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> pd.DataFrame:
        """
        Compare multiple ML models.
        """
        results = []

        for name, model in models.items():
            try:
                predictions = model.predict(X_test)
                results.append({
                    'model': name,
                    'ic': self.information_coefficient(predictions, y_test),
                    'long_short': self.long_short_return(predictions, y_test),
                    'hit_rate': self.hit_rate(predictions, y_test)
                })
            except Exception as e:
                logger.warning(f"Failed to evaluate {name}: {e}")

        return pd.DataFrame(results).set_index('model')
