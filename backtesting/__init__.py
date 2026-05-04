"""
Backtesting engine for factor investing strategies.
"""

from .engine import BacktestEngine
from .portfolio import Portfolio, PortfolioHolding
from .metrics import BacktestResult, PerformanceMetrics
from .export import StrategyDataExporter

# Rotation backtester (optional, requires pandas-ta)
try:
    from .rotation_backtest import (
        RotationBacktester,
        RotationBacktestResult,
        compare_rotation_methods,
        generate_rotation_comparison_report,
    )
    _ROTATION_AVAILABLE = True
except ImportError:
    _ROTATION_AVAILABLE = False

__all__ = [
    'BacktestEngine',
    'Portfolio',
    'PortfolioHolding',
    'BacktestResult',
    'PerformanceMetrics',
    'StrategyDataExporter',
]

if _ROTATION_AVAILABLE:
    __all__.extend([
        'RotationBacktester',
        'RotationBacktestResult',
        'compare_rotation_methods',
        'generate_rotation_comparison_report',
    ])
