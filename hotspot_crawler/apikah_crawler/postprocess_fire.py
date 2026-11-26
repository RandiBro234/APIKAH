import sys
from .copernicus import postprocess_fire as _implementation

sys.modules[__name__] = _implementation
