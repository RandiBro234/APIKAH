import sys
from .shared import climate_tables as _implementation

sys.modules[__name__] = _implementation
