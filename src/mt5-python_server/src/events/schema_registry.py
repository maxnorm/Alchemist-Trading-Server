"""
Schema registry for event normalization
Defines canonical event schema and source-specific schemas
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


class DataType(str, Enum):
    """Canonical data types for events"""
    TICK = "tick"
    BAR = "bar"
    NEWS = "news"
    ECONOMIC = "economic"


class SourceType(str, Enum):
    """Canonical source types"""
    MT5 = "mt5"
    API = "api"
    SCRAPER = "scraper"
    NEWS = "news"


@dataclass
class CanonicalEventSchema:
    """
    Canonical event schema for all data sources
    
    All events must conform to this schema after normalization.
    Timestamps are always UTC and timezone-aware.
    
    Bitemporal timestamp system:
    - timestamp: event_time (valid time) - when event occurred
    - receive_time: transaction time - when we received it
    - timestamp_metadata: quality and latency information
    """
    
    timestamp: datetime  # UTC normalized, timezone-aware (event_time)
    source: str  # "mt5", "api", "scraper", "news"
    symbol: str  # "EURUSD", "GBPUSD", etc.
    data_type: str  # "tick", "bar", "news", "economic"
    payload: Dict[str, Any]  # Source-specific data
    receive_time: Optional[datetime] = None  # UTC normalized, timezone-aware (transaction time)
    timestamp_metadata: Dict[str, Any] = field(default_factory=lambda: {
        'is_stale': False,
        'stale_age_seconds': None,
        'latency_seconds': None,
        'timestamp_source': 'event',  # 'event', 'receive', 'estimated'
        'original_timestamp': None,
    })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        result = {
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            "source": self.source,
            "symbol": self.symbol,
            "data_type": self.data_type,
            "payload": self.payload,
        }
        # Add optional bitemporal fields
        if self.receive_time is not None:
            result["receive_time"] = self.receive_time.isoformat() if isinstance(self.receive_time, datetime) else str(self.receive_time)
        if self.timestamp_metadata:
            result["timestamp_metadata"] = self.timestamp_metadata
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalEventSchema":
        """Create from dictionary representation"""
        # Parse timestamp if it's a string
        timestamp = data["timestamp"]
        if isinstance(timestamp, str):
            # Try ISO format first
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                # Fallback to other formats
                try:
                    timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    raise ValueError(f"Unsupported timestamp format: {timestamp}")
        
        # Parse receive_time if present
        receive_time = None
        if "receive_time" in data and data["receive_time"] is not None:
            receive_time_value = data["receive_time"]
            if isinstance(receive_time_value, str):
                try:
                    receive_time = datetime.fromisoformat(receive_time_value.replace('Z', '+00:00'))
                except ValueError:
                    try:
                        receive_time = datetime.strptime(receive_time_value, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        receive_time = None
            elif isinstance(receive_time_value, datetime):
                receive_time = receive_time_value
        
        # Get timestamp_metadata if present
        timestamp_metadata = data.get("timestamp_metadata", {
            'is_stale': False,
            'stale_age_seconds': None,
            'latency_seconds': None,
            'timestamp_source': 'event',
            'original_timestamp': None,
        })
        
        return cls(
            timestamp=timestamp,
            source=data["source"],
            symbol=data["symbol"],
            data_type=data["data_type"],
            payload=data["payload"],
            receive_time=receive_time,
            timestamp_metadata=timestamp_metadata,
        )
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate schema compliance
        
        :return: Tuple of (is_valid, error_message)
        """
        # Check required fields
        if not self.timestamp:
            return False, "Missing timestamp"
        
        if not isinstance(self.timestamp, datetime):
            return False, f"Invalid timestamp type: {type(self.timestamp)}"
        
        # Timestamp must be timezone-aware
        if self.timestamp.tzinfo is None:
            return False, "Timestamp must be timezone-aware"
        
        # Check receive_time if provided (optional but must be timezone-aware if present)
        if self.receive_time is not None:
            if not isinstance(self.receive_time, datetime):
                return False, f"Invalid receive_time type: {type(self.receive_time)}"
            if self.receive_time.tzinfo is None:
                return False, "receive_time must be timezone-aware"
        
        # Check timestamp_metadata if provided
        if self.timestamp_metadata is not None:
            if not isinstance(self.timestamp_metadata, dict):
                return False, f"Invalid timestamp_metadata type: {type(self.timestamp_metadata)}"
        
        # Check source
        if not self.source:
            return False, "Missing source"
        
        try:
            SourceType(self.source)  # Validate against enum
        except ValueError:
            return False, f"Invalid source: {self.source}"
        
        # Check symbol
        if not self.symbol:
            return False, "Missing symbol"
        
        # Check data_type
        if not self.data_type:
            return False, "Missing data_type"
        
        try:
            DataType(self.data_type)  # Validate against enum
        except ValueError:
            return False, f"Invalid data_type: {self.data_type}"
        
        # Check payload
        if not isinstance(self.payload, dict):
            return False, f"Invalid payload type: {type(self.payload)}"
        
        return True, None


class SchemaRegistry:
    """
    Registry for source-specific schemas
    Allows registration and validation of source-specific event formats
    """
    
    def __init__(self):
        """Initialize schema registry"""
        self._source_schemas: Dict[str, Dict[str, Any]] = {}
    
    def register_source_schema(
        self, source: str, schema: Dict[str, Any], required_fields: List[str]
    ) -> None:
        """
        Register a source-specific schema
        
        :param source: Source identifier (e.g., "mt5")
        :param schema: Schema definition dictionary
        :param required_fields: List of required field names
        """
        self._source_schemas[source] = {
            "schema": schema,
            "required_fields": required_fields,
        }
    
    def validate_source_event(
        self, source: str, event: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate event against source-specific schema
        
        :param source: Source identifier
        :param event: Event dictionary to validate
        :return: Tuple of (is_valid, error_message)
        """
        if source not in self._source_schemas:
            # If schema not registered, only check basic structure
            return True, None
        
        schema_info = self._source_schemas[source]
        required_fields = schema_info["required_fields"]
        
        # Check required fields
        for field_name in required_fields:
            if field_name not in event:
                return False, f"Missing required field: {field_name}"
        
        return True, None
    
    def get_source_schema(self, source: str) -> Optional[Dict[str, Any]]:
        """
        Get registered schema for a source
        
        :param source: Source identifier
        :return: Schema dictionary or None if not registered
        """
        if source in self._source_schemas:
            return self._source_schemas[source]["schema"]
        return None
    
    def list_sources(self) -> List[str]:
        """
        List all registered sources
        
        :return: List of source identifiers
        """
        return list(self._source_schemas.keys())


# Global schema registry instance
_schema_registry = SchemaRegistry()


def get_schema_registry() -> SchemaRegistry:
    """Get global schema registry instance"""
    return _schema_registry
