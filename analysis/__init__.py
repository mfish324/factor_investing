"""
Analysis and visualization tools for factor investing.
"""

from .comparison import ModelComparison
from .visualization import FactorVisualizer

# TA module (optional, requires pandas-ta)
try:
    from .equity_ta import EquityCurveAnalyzer
    _TA_AVAILABLE = True
except ImportError:
    _TA_AVAILABLE = False

__all__ = ['ModelComparison', 'FactorVisualizer']

if _TA_AVAILABLE:
    __all__.append('EquityCurveAnalyzer')
