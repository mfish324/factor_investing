"""
SQLite-based caching layer for financial data.
Reduces API calls by storing fetched data locally.
"""

import sqlite3
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from config import (
    CACHE_DB_PATH,
    CACHE_EXPIRY_PRICES_HOURS,
    CACHE_EXPIRY_FINANCIALS_DAYS
)

logger = logging.getLogger(__name__)


class CacheManager:
    """
    SQLite-based cache for financial data.
    Supports expiration and automatic cleanup.
    """

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or CACHE_DB_PATH
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Financials cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS financials_cache (
                    ticker TEXT,
                    period TEXT,
                    data TEXT,
                    cached_at TIMESTAMP,
                    PRIMARY KEY (ticker, period)
                )
            """)

            # Prices cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prices_cache (
                    ticker TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    data TEXT,
                    cached_at TIMESTAMP,
                    PRIMARY KEY (ticker, start_date, end_date)
                )
            """)

            # Ticker details cache
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ticker_details_cache (
                    ticker TEXT PRIMARY KEY,
                    data TEXT,
                    cached_at TIMESTAMP
                )
            """)

            # Insider transactions cache
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS insider_cache (
                    ticker TEXT PRIMARY KEY,
                    data TEXT,
                    cached_at TIMESTAMP
                )
            """)

            # Institutional holdings cache
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS institutional_cache (
                    ticker TEXT PRIMARY KEY,
                    data TEXT,
                    cached_at TIMESTAMP
                )
            """)

            conn.commit()

    def _is_expired(self, cached_at: str, expiry_hours: float) -> bool:
        """Check if cached data has expired."""
        if cached_at is None:
            return True
        cached_time = datetime.fromisoformat(cached_at)
        return datetime.now() - cached_time > timedelta(hours=expiry_hours)

    def get_financials(self, ticker: str, period: str = "annual") -> Optional[pd.DataFrame]:
        """
        Retrieve cached financial statements.

        Args:
            ticker: Stock ticker symbol
            period: 'annual' or 'quarterly'

        Returns:
            DataFrame of financials or None if not cached/expired
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT data, cached_at FROM financials_cache WHERE ticker = ? AND period = ?",
                (ticker.upper(), period)
            )
            result = cursor.fetchone()

            if result is None:
                return None

            data, cached_at = result
            expiry_hours = CACHE_EXPIRY_FINANCIALS_DAYS * 24

            if self._is_expired(cached_at, expiry_hours):
                logger.debug(f"Cache expired for {ticker} financials")
                return None

            try:
                return pd.read_json(data)
            except Exception as e:
                logger.warning(f"Failed to parse cached financials for {ticker}: {e}")
                return None

    def set_financials(self, ticker: str, data: pd.DataFrame, period: str = "annual"):
        """Cache financial statements."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO financials_cache
                   (ticker, period, data, cached_at) VALUES (?, ?, ?, ?)""",
                (ticker.upper(), period, data.to_json(), datetime.now().isoformat())
            )
            conn.commit()

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        Retrieve cached price data.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame of prices or None if not cached/expired
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT data, cached_at FROM prices_cache
                   WHERE ticker = ? AND start_date = ? AND end_date = ?""",
                (ticker.upper(), start_date, end_date)
            )
            result = cursor.fetchone()

            if result is None:
                return None

            data, cached_at = result

            if self._is_expired(cached_at, CACHE_EXPIRY_PRICES_HOURS):
                logger.debug(f"Cache expired for {ticker} prices")
                return None

            try:
                df = pd.read_json(data)
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                return df
            except Exception as e:
                logger.warning(f"Failed to parse cached prices for {ticker}: {e}")
                return None

    def set_prices(self, ticker: str, data: pd.DataFrame, start_date: str, end_date: str):
        """Cache price data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO prices_cache
                   (ticker, start_date, end_date, data, cached_at) VALUES (?, ?, ?, ?, ?)""",
                (ticker.upper(), start_date, end_date, data.to_json(), datetime.now().isoformat())
            )
            conn.commit()

    def get_ticker_details(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached ticker details."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT data, cached_at FROM ticker_details_cache WHERE ticker = ?",
                (ticker.upper(),)
            )
            result = cursor.fetchone()

            if result is None:
                return None

            data, cached_at = result
            expiry_hours = CACHE_EXPIRY_FINANCIALS_DAYS * 24

            if self._is_expired(cached_at, expiry_hours):
                return None

            try:
                return json.loads(data)
            except Exception:
                return None

    def set_ticker_details(self, ticker: str, data: Dict[str, Any]):
        """Cache ticker details."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO ticker_details_cache
                   (ticker, data, cached_at) VALUES (?, ?, ?)""",
                (ticker.upper(), json.dumps(data), datetime.now().isoformat())
            )
            conn.commit()

    def get_insider_transactions(self, ticker: str) -> Optional[pd.DataFrame]:
        """Retrieve cached insider transactions."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT data, cached_at FROM insider_cache WHERE ticker = ?",
                (ticker.upper(),)
            )
            result = cursor.fetchone()

            if result is None:
                return None

            data, cached_at = result

            if self._is_expired(cached_at, CACHE_EXPIRY_PRICES_HOURS):
                return None

            try:
                return pd.read_json(data)
            except Exception:
                return None

    def set_insider_transactions(self, ticker: str, data: pd.DataFrame):
        """Cache insider transactions."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO insider_cache
                   (ticker, data, cached_at) VALUES (?, ?, ?)""",
                (ticker.upper(), data.to_json(), datetime.now().isoformat())
            )
            conn.commit()

    def get_institutional_holdings(self, ticker: str) -> Optional[pd.DataFrame]:
        """Retrieve cached institutional holdings."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT data, cached_at FROM institutional_cache WHERE ticker = ?",
                (ticker.upper(),)
            )
            result = cursor.fetchone()

            if result is None:
                return None

            data, cached_at = result
            expiry_hours = CACHE_EXPIRY_FINANCIALS_DAYS * 24

            if self._is_expired(cached_at, expiry_hours):
                return None

            try:
                return pd.read_json(data)
            except Exception:
                return None

    def set_institutional_holdings(self, ticker: str, data: pd.DataFrame):
        """Cache institutional holdings."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO institutional_cache
                   (ticker, data, cached_at) VALUES (?, ?, ?)""",
                (ticker.upper(), data.to_json(), datetime.now().isoformat())
            )
            conn.commit()

    def clear_all(self):
        """Clear all cached data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM financials_cache")
            cursor.execute("DELETE FROM prices_cache")
            cursor.execute("DELETE FROM ticker_details_cache")
            cursor.execute("DELETE FROM insider_cache")
            cursor.execute("DELETE FROM institutional_cache")
            conn.commit()
        logger.info("Cache cleared")

    def clear_expired(self):
        """Remove expired entries from cache."""
        now = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Clear expired financials
            expiry = now - timedelta(days=CACHE_EXPIRY_FINANCIALS_DAYS)
            cursor.execute(
                "DELETE FROM financials_cache WHERE cached_at < ?",
                (expiry.isoformat(),)
            )

            # Clear expired prices
            expiry = now - timedelta(hours=CACHE_EXPIRY_PRICES_HOURS)
            cursor.execute(
                "DELETE FROM prices_cache WHERE cached_at < ?",
                (expiry.isoformat(),)
            )

            # Clear expired ticker details
            expiry = now - timedelta(days=CACHE_EXPIRY_FINANCIALS_DAYS)
            cursor.execute(
                "DELETE FROM ticker_details_cache WHERE cached_at < ?",
                (expiry.isoformat(),)
            )

            conn.commit()

        logger.info("Expired cache entries cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get statistics about cached data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            stats = {}
            for table in ['financials_cache', 'prices_cache', 'ticker_details_cache',
                         'insider_cache', 'institutional_cache']:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]

            return stats
