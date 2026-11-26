import sys
from .shared import common as _implementation

sys.modules[__name__] = _implementation
