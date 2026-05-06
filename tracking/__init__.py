"""
Shadow tracking for parallel-strategy monitoring.

Maintains a SQLite database of daily equity curves, holdings, and picks for
each strategy. The dashboard and the rotation/allocation engine both read
from this database. Only one strategy (or a blend) is actually executed on
the broker; the rest are shadow-tracked for comparison and regime detection.
"""

from .shadow_db import ShadowDB

__all__ = ["ShadowDB"]
