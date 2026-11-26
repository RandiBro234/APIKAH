import sys
from .nasa import firms as _implementation

sys.modules[__name__] = _implementation
