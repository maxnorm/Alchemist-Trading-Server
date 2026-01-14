"""
Schema Registry module
Provides versioned schema management with compatibility checking
"""

from .registry import SchemaRegistry
from .compatibility import CompatibilityChecker, CompatibilityMode, CompatibilityError

__all__ = [
    "SchemaRegistry",
    "CompatibilityChecker",
    "CompatibilityMode",
    "CompatibilityError",
]
