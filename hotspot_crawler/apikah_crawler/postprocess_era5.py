import sys
from .copernicus import postprocess_era5 as _implementation

sys.modules[__name__] = _implementation
