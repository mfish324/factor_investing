"""
Polygon.io API client for fetching financial data.
Handles rate limiting, pagination, and data transformation.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    POLYGON_API_KEY,
    POLYGON_RATE_LIMIT_CALLS,
    POLYGON_RATE_LIMIT_PERIOD
)
from .cache import CacheManager

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, calls_per_period: int, period_seconds: float):
        self.calls_per_period = calls_per_period
        self.period_seconds = period_seconds
        self.calls = []

    def wait_if_needed(self):
        """Block if rate limit would be exceeded."""
        now = time.time()
        # Remove old calls outside the window
        self.calls = [t for t in self.calls if now - t < self.period_seconds]

        if len(self.calls) >= self.calls_per_period:
            sleep_time = self.period_seconds - (now - self.calls[0])
            if sleep_time > 0:
                logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)

        self.calls.append(time.time())


class PolygonClient:
    """
    Client for Polygon.io API.
    Fetches financial statements, prices, and reference data.
    """

    BASE_URL = "https://api.polygon.io"

    def __init__(self, api_key: str = None, cache: CacheManager = None):
        self.api_key = api_key or POLYGON_API_KEY
        if not self.api_key:
            raise ValueError("Polygon API key is required. Set POLYGON_API_KEY environment variable.")

        self.cache = cache or CacheManager()
        self.rate_limiter = RateLimiter(
            POLYGON_RATE_LIMIT_CALLS,
            POLYGON_RATE_LIMIT_PERIOD
        )

        # Set up session with retries
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def _request(self, endpoint: str, params: Dict = None) -> Dict[str, Any]:
        """Make rate-limited API request."""
        self.rate_limiter.wait_if_needed()

        params = params or {}
        params['apiKey'] = self.api_key

        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    def get_financials(
        self,
        ticker: str,
        period: str = "annual",
        limit: int = 10,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch financial statements for a ticker.

        Args:
            ticker: Stock ticker symbol
            period: 'annual' or 'quarterly'
            limit: Number of periods to fetch
            use_cache: Whether to use cached data

        Returns:
            DataFrame with financial data
        """
        ticker = ticker.upper()

        # Check cache
        if use_cache:
            cached = self.cache.get_financials(ticker, period)
            if cached is not None:
                logger.debug(f"Using cached financials for {ticker}")
                return cached

        # Fetch from API
        timeframe = "annual" if period == "annual" else "quarterly"
        endpoint = "/vX/reference/financials"
        params = {
            "ticker": ticker,
            "timeframe": timeframe,
            "limit": limit,
            "sort": "filing_date",
            "order": "desc"
        }

        try:
            data = self._request(endpoint, params)
            results = data.get('results', [])

            if not results:
                logger.warning(f"No financial data found for {ticker}")
                return pd.DataFrame()

            # Parse financial statements
            records = []
            for result in results:
                record = self._parse_financial_statement(result)
                if record:
                    records.append(record)

            df = pd.DataFrame(records)

            if not df.empty:
                # Use filing_date for sorting since fiscal_period is categorical (FY, Q1, Q2, etc.)
                if 'filing_date' in df.columns:
                    df['filing_date'] = pd.to_datetime(df['filing_date'], errors='coerce')
                    df = df.sort_values('filing_date', ascending=False)
                elif 'fiscal_year' in df.columns:
                    df = df.sort_values('fiscal_year', ascending=False)
                self.cache.set_financials(ticker, df, period)

            return df

        except Exception as e:
            logger.error(f"Failed to fetch financials for {ticker}: {e}")
            return pd.DataFrame()

    def _parse_financial_statement(self, result: Dict) -> Optional[Dict]:
        """Parse a single financial statement result."""
        try:
            financials = result.get('financials', {})

            # Extract income statement items
            income = financials.get('income_statement', {})
            balance = financials.get('balance_sheet', {})
            cash_flow = financials.get('cash_flow_statement', {})

            def get_value(section: Dict, key: str) -> Optional[float]:
                item = section.get(key, {})
                return item.get('value') if isinstance(item, dict) else None

            record = {
                'ticker': result.get('tickers', [''])[0] if result.get('tickers') else '',
                'fiscal_period': result.get('fiscal_period'),
                'fiscal_year': result.get('fiscal_year'),
                'filing_date': result.get('filing_date'),

                # Income Statement
                'revenue': get_value(income, 'revenues'),
                'cost_of_revenue': get_value(income, 'cost_of_revenue'),
                'gross_profit': get_value(income, 'gross_profit'),
                'operating_income': get_value(income, 'operating_income_loss'),
                'ebit': get_value(income, 'operating_income_loss'),
                'ebitda': get_value(income, 'ebitda'),
                'net_income': get_value(income, 'net_income_loss'),
                'eps_basic': get_value(income, 'basic_earnings_per_share'),
                'eps_diluted': get_value(income, 'diluted_earnings_per_share'),
                'interest_expense': get_value(income, 'interest_expense_operating'),

                # Balance Sheet
                'total_assets': get_value(balance, 'assets'),
                'current_assets': get_value(balance, 'current_assets'),
                'total_liabilities': get_value(balance, 'liabilities'),
                'current_liabilities': get_value(balance, 'current_liabilities'),
                'total_equity': get_value(balance, 'equity'),
                'total_debt': get_value(balance, 'long_term_debt'),
                'cash': get_value(balance, 'cash'),
                'shares_outstanding': get_value(balance, 'common_stock_shares_outstanding'),

                # Cash Flow Statement
                'operating_cash_flow': get_value(cash_flow, 'net_cash_flow_from_operating_activities'),
                'capex': get_value(cash_flow, 'capital_expenditure'),
                'free_cash_flow': None,  # Calculated below
            }

            # Calculate free cash flow if components available
            if record['operating_cash_flow'] and record['capex']:
                record['free_cash_flow'] = record['operating_cash_flow'] - abs(record['capex'])

            return record

        except Exception as e:
            logger.warning(f"Failed to parse financial statement: {e}")
            return None

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch historical price data.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            use_cache: Whether to use cached data

        Returns:
            DataFrame with OHLCV data
        """
        ticker = ticker.upper()

        # Check cache
        if use_cache:
            cached = self.cache.get_prices(ticker, start_date, end_date)
            if cached is not None:
                logger.debug(f"Using cached prices for {ticker}")
                return cached

        # Fetch from API
        endpoint = f"/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000
        }

        try:
            data = self._request(endpoint, params)
            results = data.get('results', [])

            if not results:
                logger.warning(f"No price data found for {ticker}")
                return pd.DataFrame()

            df = pd.DataFrame(results)
            df = df.rename(columns={
                't': 'timestamp',
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume',
                'vw': 'vwap',
                'n': 'transactions'
            })

            # Convert timestamp to datetime
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.sort_values('date')

            # Cache results
            self.cache.set_prices(ticker, df, start_date, end_date)

            return df

        except Exception as e:
            logger.error(f"Failed to fetch prices for {ticker}: {e}")
            return pd.DataFrame()

    def get_ticker_details(self, ticker: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Fetch ticker details including market cap and sector.

        Args:
            ticker: Stock ticker symbol
            use_cache: Whether to use cached data

        Returns:
            Dictionary with ticker details
        """
        ticker = ticker.upper()

        # Check cache
        if use_cache:
            cached = self.cache.get_ticker_details(ticker)
            if cached is not None:
                return cached

        endpoint = f"/v3/reference/tickers/{ticker}"

        try:
            data = self._request(endpoint)
            result = data.get('results', {})

            if result:
                self.cache.set_ticker_details(ticker, result)

            return result

        except Exception as e:
            logger.error(f"Failed to fetch ticker details for {ticker}: {e}")
            return None

    def get_insider_transactions(
        self,
        ticker: str,
        limit: int = 100,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch insider transactions for a ticker.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of transactions
            use_cache: Whether to use cached data

        Returns:
            DataFrame with insider transactions
        """
        ticker = ticker.upper()

        # Check cache
        if use_cache:
            cached = self.cache.get_insider_transactions(ticker)
            if cached is not None:
                return cached

        endpoint = "/v2/reference/insider_transactions"
        params = {
            "ticker": ticker,
            "limit": limit
        }

        try:
            data = self._request(endpoint, params)
            results = data.get('results', [])

            if not results:
                return pd.DataFrame()

            df = pd.DataFrame(results)

            if not df.empty:
                if 'filing_date' in df.columns:
                    df['filing_date'] = pd.to_datetime(df['filing_date'])
                self.cache.set_insider_transactions(ticker, df)

            return df

        except Exception as e:
            logger.error(f"Failed to fetch insider transactions for {ticker}: {e}")
            return pd.DataFrame()

    def get_institutional_holdings(
        self,
        ticker: str,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch institutional holdings for a ticker.

        Args:
            ticker: Stock ticker symbol
            use_cache: Whether to use cached data

        Returns:
            DataFrame with institutional holdings
        """
        ticker = ticker.upper()

        # Check cache
        if use_cache:
            cached = self.cache.get_institutional_holdings(ticker)
            if cached is not None:
                return cached

        endpoint = f"/vX/reference/tickers/{ticker}/institutional_holders"
        params = {"limit": 100}

        try:
            data = self._request(endpoint, params)
            results = data.get('results', [])

            if not results:
                return pd.DataFrame()

            df = pd.DataFrame(results)

            if not df.empty:
                self.cache.set_institutional_holdings(ticker, df)

            return df

        except Exception as e:
            logger.error(f"Failed to fetch institutional holdings for {ticker}: {e}")
            return pd.DataFrame()

    def get_market_cap(self, ticker: str) -> Optional[float]:
        """Get current market capitalization for a ticker."""
        details = self.get_ticker_details(ticker)
        if details:
            return details.get('market_cap')
        return None

    def get_shares_outstanding(self, ticker: str) -> Optional[float]:
        """Get shares outstanding for a ticker."""
        details = self.get_ticker_details(ticker)
        if details:
            return details.get('share_class_shares_outstanding') or details.get('weighted_shares_outstanding')
        return None

    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get the most recent closing price."""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        prices = self.get_prices(ticker, start_date, end_date)
        if not prices.empty:
            return prices.iloc[-1]['close']
        return None

    def get_multiple_financials(
        self,
        tickers: List[str],
        period: str = "annual",
        progress_callback=None
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch financials for multiple tickers.

        Args:
            tickers: List of ticker symbols
            period: 'annual' or 'quarterly'
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary mapping tickers to their financial DataFrames
        """
        results = {}
        total = len(tickers)

        for i, ticker in enumerate(tickers):
            try:
                results[ticker] = self.get_financials(ticker, period)
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")
                results[ticker] = pd.DataFrame()

            if progress_callback:
                progress_callback(i + 1, total, ticker)

        return results

    def get_multiple_prices(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        progress_callback=None
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch prices for multiple tickers.

        Args:
            tickers: List of ticker symbols
            start_date: Start date
            end_date: End date
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary mapping tickers to their price DataFrames
        """
        results = {}
        total = len(tickers)

        for i, ticker in enumerate(tickers):
            try:
                results[ticker] = self.get_prices(ticker, start_date, end_date)
            except Exception as e:
                logger.warning(f"Failed to fetch prices for {ticker}: {e}")
                results[ticker] = pd.DataFrame()

            if progress_callback:
                progress_callback(i + 1, total, ticker)

        return results
