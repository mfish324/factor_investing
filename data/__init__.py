"""
Data layer for Factor Investing Application.
Handles API communication, caching, and universe management.
"""

from .polygon_client import PolygonClient
from .cache import CacheManager
from .universe import UniverseManager

__all__ = ['PolygonClient', 'CacheManager', 'UniverseManager']
