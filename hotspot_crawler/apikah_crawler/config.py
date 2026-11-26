import sys
from .shared import config as _implementation

sys.modules[__name__] = _implementation
