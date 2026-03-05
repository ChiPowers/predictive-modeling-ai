"""Compatibility module.

The canonical FastAPI app now lives in :mod:`service.api`.
"""

from service.api import app

__all__ = ["app"]
