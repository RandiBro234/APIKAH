import sys
from .copernicus import crawl as _implementation

sys.modules[__name__] = _implementation
