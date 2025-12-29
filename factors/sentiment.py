"""
Sentiment factors based on insider activity and institutional ownership.
"""

from typing import Dict, Optional, List
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

from .base import BaseFactor

logger = logging.getLogger(__name__)


class InsiderFactors(BaseFactor):
    """
    Insider transaction analysis factors.
    """

    name = "Insider Factors"
    description = "Insider buying/selling activity signals"

    def __init__(self, polygon_client=None):
        super().__init__()
        self.polygon_client = polygon_client

    def calculate(
        self,
        financials: pd.DataFrame,
        prices: pd.DataFrame = None,
        market_cap: float = None,
        insider_transactions: pd.DataFrame = None
    ) -> Dict[str, float]:
        """
        Calculate insider factors for a stock.
        """
        if insider_transactions is None or insider_transactions.empty:
            return {}

        results = {
            'net_insider_buying': self._net_insider_buying(insider_transactions, market_cap),
            'insider_buy_sell_ratio': self._insider_buy_sell_ratio(insider_transactions),
            'cluster_buying_signal': self._cluster_buying_signal(insider_transactions),
            'ceo_cfo_activity': self._ceo_cfo_activity(insider_transactions),
        }

        return results

    def _net_insider_buying(
        self,
        transactions: pd.DataFrame,
        market_cap: float,
        months: int = 3
    ) -> Optional[float]:
        """
        Net insider buying over specified period.
        Formula: (Buy $ Volume - Sell $ Volume) / Market Cap
        """
        if transactions.empty or market_cap is None or market_cap <= 0:
            return None

        # Filter to recent transactions
        if 'filing_date' in transactions.columns:
            cutoff = datetime.now() - timedelta(days=months * 30)
            transactions = transactions[
                pd.to_datetime(transactions['filing_date']) >= cutoff
            ]

        if transactions.empty:
            return None

        # Calculate buy and sell volumes
        buy_volume = 0
        sell_volume = 0

        for _, txn in transactions.iterrows():
            txn_type = str(txn.get('transaction_type', '')).upper()
            shares = txn.get('shares', 0) or 0
            price = txn.get('price_per_share', 0) or 0
            value = abs(shares * price)

            if 'BUY' in txn_type or 'PURCHASE' in txn_type or txn_type == 'P':
                buy_volume += value
            elif 'SELL' in txn_type or 'SALE' in txn_type or txn_type == 'S':
                sell_volume += value

        net_buying = buy_volume - sell_volume
        return net_buying / market_cap

    def _insider_buy_sell_ratio(
        self,
        transactions: pd.DataFrame,
        months: int = 6
    ) -> Optional[float]:
        """
        Ratio of buy transactions to total transactions.
        Returns value between 0 and 1, higher = more bullish.
        """
        if transactions.empty:
            return None

        # Filter to recent transactions
        if 'filing_date' in transactions.columns:
            cutoff = datetime.now() - timedelta(days=months * 30)
            transactions = transactions[
                pd.to_datetime(transactions['filing_date']) >= cutoff
            ]

        if transactions.empty:
            return None

        buy_count = 0
        total_count = 0

        for _, txn in transactions.iterrows():
            txn_type = str(txn.get('transaction_type', '')).upper()

            if 'BUY' in txn_type or 'PURCHASE' in txn_type or txn_type == 'P':
                buy_count += 1
                total_count += 1
            elif 'SELL' in txn_type or 'SALE' in txn_type or txn_type == 'S':
                total_count += 1

        if total_count == 0:
            return None

        return buy_count / total_count

    def _cluster_buying_signal(
        self,
        transactions: pd.DataFrame,
        days: int = 30,
        min_buyers: int = 3
    ) -> int:
        """
        Detect cluster buying (3+ unique insiders buying within window).
        Returns 1 if cluster detected, 0 otherwise.
        """
        if transactions.empty:
            return 0

        # Filter to recent buys
        if 'filing_date' in transactions.columns:
            cutoff = datetime.now() - timedelta(days=days)
            recent = transactions[
                pd.to_datetime(transactions['filing_date']) >= cutoff
            ]
        else:
            recent = transactions

        if recent.empty:
            return 0

        # Count unique buyers
        unique_buyers = set()
        for _, txn in recent.iterrows():
            txn_type = str(txn.get('transaction_type', '')).upper()
            if 'BUY' in txn_type or 'PURCHASE' in txn_type or txn_type == 'P':
                insider_name = txn.get('reporting_owner_name', txn.get('name', ''))
                if insider_name:
                    unique_buyers.add(insider_name)

        return 1 if len(unique_buyers) >= min_buyers else 0

    def _ceo_cfo_activity(
        self,
        transactions: pd.DataFrame,
        months: int = 6
    ) -> Optional[float]:
        """
        Focus on C-suite transactions (most informative).
        Returns weighted buy/sell ratio for CEO/CFO.
        """
        if transactions.empty:
            return None

        # Filter to recent transactions
        if 'filing_date' in transactions.columns:
            cutoff = datetime.now() - timedelta(days=months * 30)
            transactions = transactions[
                pd.to_datetime(transactions['filing_date']) >= cutoff
            ]

        if transactions.empty:
            return None

        c_suite_keywords = ['CEO', 'CFO', 'CHIEF', 'PRESIDENT', 'CHAIRMAN']

        c_suite_buys = 0
        c_suite_sells = 0

        for _, txn in transactions.iterrows():
            title = str(txn.get('reporting_owner_title', '')).upper()

            is_c_suite = any(kw in title for kw in c_suite_keywords)
            if not is_c_suite:
                continue

            txn_type = str(txn.get('transaction_type', '')).upper()
            shares = abs(txn.get('shares', 0) or 0)

            if 'BUY' in txn_type or 'PURCHASE' in txn_type or txn_type == 'P':
                c_suite_buys += shares
            elif 'SELL' in txn_type or 'SALE' in txn_type or txn_type == 'S':
                c_suite_sells += shares

        total = c_suite_buys + c_suite_sells
        if total == 0:
            return None

        # Return -1 to 1 scale: positive = net buying
        return (c_suite_buys - c_suite_sells) / total

    def insider_composite_score(
        self,
        factor_df: pd.DataFrame
    ) -> pd.Series:
        """
        Combined insider sentiment score.
        """
        higher_is_better = {
            'net_insider_buying': True,
            'insider_buy_sell_ratio': True,
            'cluster_buying_signal': True,
            'ceo_cfo_activity': True,
        }

        weights = {
            'net_insider_buying': 0.4,
            'insider_buy_sell_ratio': 0.3,
            'cluster_buying_signal': 0.2,
            'ceo_cfo_activity': 0.1,
        }

        return self.composite_score(factor_df, weights, higher_is_better)


class InstitutionalFactors(BaseFactor):
    """
    Institutional ownership analysis factors.
    """

    name = "Institutional Factors"
    description = "Institutional ownership signals"

    def __init__(self, polygon_client=None):
        super().__init__()
        self.polygon_client = polygon_client

    def calculate(
        self,
        financials: pd.DataFrame,
        prices: pd.DataFrame = None,
        market_cap: float = None,
        holdings: pd.DataFrame = None,
        shares_outstanding: float = None
    ) -> Dict[str, float]:
        """
        Calculate institutional factors for a stock.
        """
        if holdings is None or holdings.empty:
            return {}

        results = {
            'institutional_ownership_pct': self._institutional_ownership_pct(
                holdings, shares_outstanding
            ),
            'num_institutional_holders': self._num_institutional_holders(holdings),
            'holder_concentration': self._holder_concentration(holdings),
        }

        return results

    def _institutional_ownership_pct(
        self,
        holdings: pd.DataFrame,
        shares_outstanding: float
    ) -> Optional[float]:
        """
        Total institutional ownership as % of shares outstanding.
        """
        if holdings.empty or shares_outstanding is None or shares_outstanding <= 0:
            return None

        total_shares_held = holdings['shares'].sum() if 'shares' in holdings.columns else 0
        if total_shares_held <= 0:
            return None

        return total_shares_held / shares_outstanding

    def _num_institutional_holders(self, holdings: pd.DataFrame) -> int:
        """
        Count of institutional holders.
        """
        return len(holdings)

    def _holder_concentration(self, holdings: pd.DataFrame) -> Optional[float]:
        """
        Herfindahl index of institutional holdings.
        Higher = more concentrated among fewer large holders.
        """
        if holdings.empty or 'shares' not in holdings.columns:
            return None

        shares = holdings['shares'].dropna()
        if shares.sum() <= 0:
            return None

        # Calculate Herfindahl index
        market_shares = shares / shares.sum()
        hhi = (market_shares ** 2).sum()

        return hhi

    def institutional_composite_score(
        self,
        factor_df: pd.DataFrame
    ) -> pd.Series:
        """
        Combined institutional sentiment score.
        """
        higher_is_better = {
            'institutional_ownership_pct': True,  # More institutional = more coverage
            'num_institutional_holders': True,     # More holders = more liquidity
            'holder_concentration': False,         # Less concentration = less risk
        }

        weights = {
            'institutional_ownership_pct': 0.4,
            'num_institutional_holders': 0.3,
            'holder_concentration': 0.3,
        }

        return self.composite_score(factor_df, weights, higher_is_better)


class SentimentFactors(BaseFactor):
    """
    Combined sentiment factors from insider and institutional data.
    """

    name = "Sentiment Factors"
    description = "Combined insider and institutional sentiment"

    def __init__(self, polygon_client=None):
        super().__init__()
        self.insider_factors = InsiderFactors(polygon_client)
        self.institutional_factors = InstitutionalFactors(polygon_client)

    def calculate(
        self,
        financials: pd.DataFrame,
        prices: pd.DataFrame = None,
        market_cap: float = None,
        insider_transactions: pd.DataFrame = None,
        institutional_holdings: pd.DataFrame = None,
        shares_outstanding: float = None
    ) -> Dict[str, float]:
        """
        Calculate all sentiment factors.
        """
        results = {}

        # Insider factors
        insider_results = self.insider_factors.calculate(
            financials, prices, market_cap, insider_transactions
        )
        results.update(insider_results)

        # Institutional factors
        inst_results = self.institutional_factors.calculate(
            financials, prices, market_cap,
            institutional_holdings, shares_outstanding
        )
        results.update(inst_results)

        return results

    def sentiment_composite_score(
        self,
        factor_df: pd.DataFrame
    ) -> pd.Series:
        """
        Calculate composite sentiment score from all sentiment factors.
        """
        higher_is_better = {
            'net_insider_buying': True,
            'insider_buy_sell_ratio': True,
            'cluster_buying_signal': True,
            'ceo_cfo_activity': True,
            'institutional_ownership_pct': True,
            'num_institutional_holders': True,
            'holder_concentration': False,
        }

        weights = {
            'net_insider_buying': 1.5,
            'insider_buy_sell_ratio': 1.0,
            'cluster_buying_signal': 1.2,
            'ceo_cfo_activity': 0.8,
            'institutional_ownership_pct': 0.8,
            'num_institutional_holders': 0.5,
            'holder_concentration': 0.5,
        }

        return self.composite_score(factor_df, weights, higher_is_better)
