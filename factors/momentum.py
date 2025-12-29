"""
Momentum factor calculations.
"""

from typing import Dict, Optional
import pandas as pd
import numpy as np
import logging

from .base import BaseFactor

logger = logging.getLogger(__name__)


class MomentumFactors(BaseFactor):
    """
    Price and earnings momentum factors.
    """

    name = "Momentum Factors"
    description = "Price momentum and relative strength metrics"

    def calculate(
        self,
        financials: pd.DataFrame,
        prices: pd.DataFrame = None,
        market_cap: float = None,
        benchmark_prices: pd.DataFrame = None
    ) -> Dict[str, float]:
        """
        Calculate all momentum factors for a stock.
        """
        if prices is None or prices.empty:
            return {}

        results = {
            'momentum_12_1': self._price_momentum_12_1(prices),
            'momentum_6_1': self._price_momentum_6_1(prices),
            'relative_strength_vs_market': self._relative_strength_vs_market(
                prices, benchmark_prices
            ),
            'distance_from_52w_high': self._distance_from_52w_high(prices),
            'distance_from_52w_low': self._distance_from_52w_low(prices),
            'moving_average_trend': self._moving_average_trend(prices),
        }

        return results

    def _price_momentum_12_1(self, prices: pd.DataFrame) -> Optional[float]:
        """
        Classic momentum: 12-month return excluding most recent month.
        Excluding recent month avoids short-term reversal effect.
        """
        if len(prices) < 252:  # Need ~1 year of data
            return None

        # Get closing prices
        close = prices['close'].values

        # Current price (1 month ago to exclude recent)
        current_idx = -21 if len(close) > 21 else -1
        current_price = close[current_idx]

        # Price 12 months ago
        past_idx = -252 if len(close) >= 252 else 0
        past_price = close[past_idx]

        if past_price <= 0:
            return None

        return (current_price - past_price) / past_price

    def _price_momentum_6_1(self, prices: pd.DataFrame) -> Optional[float]:
        """
        6-month momentum excluding most recent month.
        """
        if len(prices) < 126:  # Need ~6 months of data
            return None

        close = prices['close'].values

        # Current price (1 month ago)
        current_idx = -21 if len(close) > 21 else -1
        current_price = close[current_idx]

        # Price 6 months ago
        past_idx = -126 if len(close) >= 126 else 0
        past_price = close[past_idx]

        if past_price <= 0:
            return None

        return (current_price - past_price) / past_price

    def _relative_strength_vs_market(
        self,
        prices: pd.DataFrame,
        benchmark_prices: pd.DataFrame,
        months: int = 12
    ) -> Optional[float]:
        """
        Stock return minus SPY return over period.
        Positive = outperforming market.
        """
        if benchmark_prices is None or benchmark_prices.empty:
            return None

        days = months * 21
        if len(prices) < days or len(benchmark_prices) < days:
            return None

        # Calculate stock return
        stock_close = prices['close'].values
        stock_return = (stock_close[-1] - stock_close[-days]) / stock_close[-days]

        # Calculate benchmark return
        bench_close = benchmark_prices['close'].values
        bench_return = (bench_close[-1] - bench_close[-days]) / bench_close[-days]

        return stock_return - bench_return

    def _distance_from_52w_high(self, prices: pd.DataFrame) -> Optional[float]:
        """
        Current price / 52-week high.
        Range: 0 to 1, higher = closer to 52w high.
        """
        if len(prices) < 252:
            return None

        close = prices['close'].values
        current_price = close[-1]
        high_52w = close[-252:].max()

        if high_52w <= 0:
            return None

        return current_price / high_52w

    def _distance_from_52w_low(self, prices: pd.DataFrame) -> Optional[float]:
        """
        Current price / 52-week low.
        Higher values = further from lows.
        """
        if len(prices) < 252:
            return None

        close = prices['close'].values
        current_price = close[-1]
        low_52w = close[-252:].min()

        if low_52w <= 0:
            return None

        return current_price / low_52w

    def _moving_average_trend(self, prices: pd.DataFrame) -> Optional[float]:
        """
        Price relative to moving averages.
        Score based on: Price > 50 DMA > 200 DMA (bullish alignment)
        Returns: -1 to +1 scale
        """
        if len(prices) < 200:
            return None

        close = prices['close'].values
        current_price = close[-1]

        # Calculate moving averages
        ma_50 = close[-50:].mean()
        ma_200 = close[-200:].mean()

        score = 0

        # Price vs 50 DMA
        if current_price > ma_50:
            score += 0.5
        else:
            score -= 0.5

        # 50 DMA vs 200 DMA (golden cross / death cross)
        if ma_50 > ma_200:
            score += 0.5
        else:
            score -= 0.5

        return score

    def momentum_composite_score(
        self,
        factor_df: pd.DataFrame
    ) -> pd.Series:
        """
        Combined momentum score.
        """
        higher_is_better = {
            'momentum_12_1': True,
            'momentum_6_1': True,
            'relative_strength_vs_market': True,
            'distance_from_52w_high': True,
            'distance_from_52w_low': True,
            'moving_average_trend': True,
        }

        weights = {
            'momentum_12_1': 1.5,  # Primary momentum signal
            'momentum_6_1': 1.0,
            'relative_strength_vs_market': 1.0,
            'distance_from_52w_high': 0.8,
            'distance_from_52w_low': 0.4,
            'moving_average_trend': 0.8,
        }

        return self.composite_score(factor_df, weights, higher_is_better)

    def calculate_universe(
        self,
        prices_dict: Dict[str, pd.DataFrame],
        benchmark_prices: pd.DataFrame = None
    ) -> pd.DataFrame:
        """
        Calculate momentum factors for all stocks in universe.
        """
        results = []

        for ticker, prices in prices_dict.items():
            try:
                factors = self.calculate(
                    pd.DataFrame(),  # No financials needed
                    prices,
                    market_cap=None,
                    benchmark_prices=benchmark_prices
                )
                factors['ticker'] = ticker
                results.append(factors)
            except Exception as e:
                logger.warning(f"Failed to calculate momentum for {ticker}: {e}")
                continue

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results).set_index('ticker')
        return df

    def calculate_universe_with_composite(
        self,
        prices_dict: Dict[str, pd.DataFrame],
        benchmark_prices: pd.DataFrame = None
    ) -> pd.DataFrame:
        """
        Calculate momentum factors for universe with composite score.
        """
        df = self.calculate_universe(prices_dict, benchmark_prices)

        if not df.empty:
            df['momentum_composite'] = self.momentum_composite_score(df)

        return df


class VolatilityFactors(BaseFactor):
    """
    Volatility and risk-based factors.
    Low volatility anomaly: low vol stocks historically outperform risk-adjusted.
    """

    name = "Volatility Factors"
    description = "Volatility and beta metrics"

    def calculate(
        self,
        financials: pd.DataFrame,
        prices: pd.DataFrame = None,
        market_cap: float = None,
        benchmark_prices: pd.DataFrame = None
    ) -> Dict[str, float]:
        """
        Calculate volatility factors.
        """
        if prices is None or prices.empty:
            return {}

        results = {
            'historical_volatility': self._historical_volatility(prices),
            'beta': self._beta(prices, benchmark_prices),
            'downside_volatility': self._downside_volatility(prices),
        }

        return results

    def _calculate_returns(self, prices: pd.DataFrame) -> pd.Series:
        """Calculate daily returns from price data."""
        if 'close' not in prices.columns:
            return pd.Series()
        return prices['close'].pct_change().dropna()

    def _historical_volatility(
        self,
        prices: pd.DataFrame,
        days: int = 252
    ) -> Optional[float]:
        """
        Annualized standard deviation of daily returns.
        """
        returns = self._calculate_returns(prices)
        if len(returns) < min(days, 63):  # At least 3 months
            return None

        recent_returns = returns.tail(days)
        daily_vol = recent_returns.std()

        # Annualize
        return daily_vol * np.sqrt(252)

    def _beta(
        self,
        prices: pd.DataFrame,
        benchmark_prices: pd.DataFrame,
        days: int = 252
    ) -> Optional[float]:
        """
        Beta relative to benchmark (SPY).
        Beta = Covariance(stock, market) / Variance(market)
        """
        if benchmark_prices is None or benchmark_prices.empty:
            return None

        stock_returns = self._calculate_returns(prices)
        bench_returns = self._calculate_returns(benchmark_prices)

        if len(stock_returns) < days or len(bench_returns) < days:
            return None

        # Align dates
        stock_returns = stock_returns.tail(days)
        bench_returns = bench_returns.tail(days)

        # Need to align by date if indices differ
        if len(stock_returns) != len(bench_returns):
            # Simple approach: use last N days
            min_len = min(len(stock_returns), len(bench_returns))
            stock_returns = stock_returns.tail(min_len)
            bench_returns = bench_returns.tail(min_len)

        if len(stock_returns) < 63:
            return None

        covariance = np.cov(stock_returns.values, bench_returns.values)[0, 1]
        variance = np.var(bench_returns.values)

        if variance == 0:
            return None

        return covariance / variance

    def _downside_volatility(
        self,
        prices: pd.DataFrame,
        days: int = 252
    ) -> Optional[float]:
        """
        Standard deviation of negative returns only.
        More relevant for risk-averse investors.
        """
        returns = self._calculate_returns(prices)
        if len(returns) < min(days, 63):
            return None

        recent_returns = returns.tail(days)
        negative_returns = recent_returns[recent_returns < 0]

        if len(negative_returns) < 10:
            return None

        daily_downside_vol = negative_returns.std()

        # Annualize
        return daily_downside_vol * np.sqrt(252)

    def volatility_composite_score(
        self,
        factor_df: pd.DataFrame
    ) -> pd.Series:
        """
        Combined low-volatility score.
        Invert so higher = lower volatility (more attractive).
        """
        # For low volatility factor, lower is better
        higher_is_better = {
            'historical_volatility': False,
            'beta': False,  # Lower beta = less market risk
            'downside_volatility': False,
        }

        weights = {
            'historical_volatility': 1.0,
            'beta': 0.8,
            'downside_volatility': 1.2,  # Downside vol more important
        }

        return self.composite_score(factor_df, weights, higher_is_better)

    def calculate_universe(
        self,
        prices_dict: Dict[str, pd.DataFrame],
        benchmark_prices: pd.DataFrame = None
    ) -> pd.DataFrame:
        """
        Calculate volatility factors for all stocks in universe.
        """
        results = []

        for ticker, prices in prices_dict.items():
            try:
                factors = self.calculate(
                    pd.DataFrame(),
                    prices,
                    market_cap=None,
                    benchmark_prices=benchmark_prices
                )
                factors['ticker'] = ticker
                results.append(factors)
            except Exception as e:
                logger.warning(f"Failed to calculate volatility for {ticker}: {e}")
                continue

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results).set_index('ticker')
        return df
