"""
Feature metadata model for data sources
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Feature:
    """Feature metadata for data sources"""

    name: str  # Unique feature identifier
    data_type: type  # Python type (float, int, str, etc.)
    source: str  # Provider name
    description: str  # Human-readable description
    category: Optional[str] = (
        None  # Feature category (price, technical, economic, etc.)
    )

    def __post_init__(self):
        """Validate feature data"""
        if not self.name:
            raise ValueError("Feature name cannot be empty")
        if not self.source:
            raise ValueError("Feature source cannot be empty")
