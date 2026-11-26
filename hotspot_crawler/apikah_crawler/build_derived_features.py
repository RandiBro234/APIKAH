import sys
from .copernicus import build_derived_features as _implementation

sys.modules[__name__] = _implementation
