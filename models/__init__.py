"""
Factor model implementations for the Factor Investing Application.
"""

from .base import FactorModel
from .magic_formula import MagicFormulaModel
from .piotroski import PiotroskiModel
from .garp import GARPModel
from .quality_value import QualityValueModel
from .three_factor import ThreeFactorModel
from .six_factor import SixFactorModel

# ML models (optional, may require additional dependencies)
try:
    from .ml_ensemble import MLEnsembleModel, MultiModelEnsemble
    _ML_AVAILABLE = True
except ImportError:
    _ML_AVAILABLE = False

__all__ = [
    'FactorModel',
    'MagicFormulaModel',
    'PiotroskiModel',
    'GARPModel',
    'QualityValueModel',
    'ThreeFactorModel',
    'SixFactorModel',
]

if _ML_AVAILABLE:
    __all__.extend(['MLEnsembleModel', 'MultiModelEnsemble'])
