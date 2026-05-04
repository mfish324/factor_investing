"""
Configuration settings for Factor Investing Application.
"""

import os
from pathlib import Path

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, rely on environment variables

# Base paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
MODELS_DIR = BASE_DIR / "models" / "saved"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)

# API Configuration
POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY", "")

# Alpaca Trading Configuration
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")
ALPACA_PAPER = True  # Set to False for live trading (use with caution!)

# Cache settings
CACHE_DB_PATH = DATA_DIR / "cache.db"
CACHE_EXPIRY_PRICES_HOURS = 24
CACHE_EXPIRY_FINANCIALS_DAYS = 7

# Universe settings
DEFAULT_UNIVERSE = "sp500"

# Backtest settings
DEFAULT_REBALANCE_FREQUENCY = "monthly"  # monthly, quarterly, annual
DEFAULT_PORTFOLIO_SIZE = 30
BACKTEST_START_DATE = "2025-10-31"
BACKTEST_END_DATE = "2026-03-12"

# Risk metrics
RISK_FREE_RATE = 0.04
TRADING_DAYS_PER_YEAR = 252

# Transaction costs (basis points)
TRANSACTION_COST_BPS = 10

# ML Settings
ML_TRAINING_START = "2015-01-01"
ML_VALIDATION_SPLIT = 0.2
ML_N_TRIALS = 50
ML_MODELS_DIR = MODELS_DIR

# Factor Weights (for non-ML composite models)
DEFAULT_FACTOR_WEIGHTS = {
    'value': 0.25,
    'quality': 0.25,
    'growth': 0.20,
    'momentum': 0.15,
    'sentiment': 0.10,
    'volatility': 0.05
}

# Feature Engineering
WINSORIZE_LIMITS = (0.01, 0.99)
SECTOR_NEUTRALIZE = True

# Polygon API rate limiting
POLYGON_RATE_LIMIT_CALLS = 100  # calls per second for paid tier
POLYGON_RATE_LIMIT_PERIOD = 1.0  # seconds

# Logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# =============================================================================
# Strategy Rotation Settings
# =============================================================================

# Rotation Strategy Settings
ROTATION_DEFAULT_METHOD = "weighted"  # binary, weighted, momentum, top_n
ROTATION_LOOKBACK_DAYS = 63  # ~3 months for momentum calculation
ROTATION_REBALANCE_FREQ = "weekly"  # daily, weekly, monthly
ROTATION_MIN_HOLDING_DAYS = 5  # Minimum days before switching strategies
ROTATION_TRANSACTION_COST_BPS = 10  # Basis points per strategy switch

# Technical Analysis Defaults for Equity Curves
TA_MACD_FAST = 12
TA_MACD_SLOW = 26
TA_MACD_SIGNAL = 9
TA_RSI_PERIOD = 14
TA_SMA_FAST = 20
TA_SMA_SLOW = 50
