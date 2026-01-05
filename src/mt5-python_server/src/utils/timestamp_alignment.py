"""
Timestamp Alignment Service
Centralized service for timestamp extraction and alignment across data sources
Implements bitemporal timestamp system: event_time (valid time) and receive_time (transaction time)
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from utils.time_utils import get_utc_time, normalize_to_utc


@dataclass
class TimestampInfo:
    """Bitemporal timestamp information"""
    event_time: datetime  # When event occurred (valid time)
    receive_time: datetime  # When we received it (transaction time)
    latency_seconds: float  # Delay: receive_time - event_time
    metadata: Dict[str, Any] = field(default_factory=lambda: {
        'is_stale': False,
        'stale_age_seconds': None,
        'timestamp_source': 'event',  # 'event', 'receive', 'estimated'
        'original_timestamp': None,
    })


@dataclass
class SourceTimestampConfig:
    """Configuration per data source for timestamp extraction"""
    source: str
    timestamp_field: str  # Field name containing event timestamp
    timestamp_format: Optional[str] = None  # Format string if needed
    timezone_field: Optional[str] = None  # Field name for timezone info
    staleness_threshold_seconds: float = 300.0  # Threshold for considering stale
    alignment_strategy: str = 'preserve'  # 'preserve', 'estimate', 'interpolate'


class TimestampAlignmentService:
    """Unified timestamp alignment for all sources"""
    
    def __init__(self):
        """Initialize timestamp alignment service"""
        self.source_configs: Dict[str, SourceTimestampConfig] = {}
        self._register_default_sources()
    
    def _register_default_sources(self):
        """Register default configurations for known sources"""
        # MT5 source configuration
        self.register_source(
            source="mt5",
            config=SourceTimestampConfig(
                source="mt5",
                timestamp_field="date_time",
                timestamp_format="%Y.%m.%d %H:%M:%S",
                staleness_threshold_seconds=300.0,
                alignment_strategy="preserve"
            )
        )
        
        # API source configuration
        self.register_source(
            source="api",
            config=SourceTimestampConfig(
                source="api",
                timestamp_field="timestamp",
                timestamp_format=None,  # ISO format
                staleness_threshold_seconds=300.0,
                alignment_strategy="preserve"
            )
        )
    
    def register_source(self, source: str, config: SourceTimestampConfig):
        """
        Register source-specific timestamp extraction configuration
        
        :param source: Source identifier (e.g., "mt5", "api")
        :param config: Source timestamp configuration
        """
        self.source_configs[source] = config
    
    def extract_timestamps(
        self, 
        raw_event: Dict[str, Any], 
        source: str, 
        receive_time: Optional[datetime] = None
    ) -> TimestampInfo:
        """
        Extract bitemporal timestamps from raw event
        
        :param raw_event: Raw event dictionary
        :param source: Source identifier
        :param receive_time: When we received the event (defaults to current time)
        :return: TimestampInfo with event_time, receive_time, latency, and metadata
        """
        if receive_time is None:
            receive_time = get_utc_time()
        else:
            # Ensure receive_time is timezone-aware UTC
            receive_time = normalize_to_utc(receive_time)
        
        # Get source configuration
        config = self.source_configs.get(source)
        if config is None:
            # Default: try common timestamp fields
            timestamp_field = raw_event.get('timestamp') or raw_event.get('date_time') or raw_event.get('datetime')
            if timestamp_field:
                event_time = self._parse_timestamp(timestamp_field, source)
            else:
                # No timestamp found, use receive_time as event_time
                event_time = receive_time
                metadata = {
                    'is_stale': False,
                    'stale_age_seconds': None,
                    'timestamp_source': 'receive',
                    'original_timestamp': None,
                }
                latency_seconds = 0.0
                return TimestampInfo(
                    event_time=event_time,
                    receive_time=receive_time,
                    latency_seconds=latency_seconds,
                    metadata=metadata
                )
        else:
            # Use configured timestamp field
            timestamp_value = raw_event.get(config.timestamp_field)
            if timestamp_value is None:
                # Fallback to receive_time
                event_time = receive_time
                metadata = {
                    'is_stale': False,
                    'stale_age_seconds': None,
                    'timestamp_source': 'receive',
                    'original_timestamp': None,
                }
                latency_seconds = 0.0
                return TimestampInfo(
                    event_time=event_time,
                    receive_time=receive_time,
                    latency_seconds=latency_seconds,
                    metadata=metadata
                )
            
            # Parse timestamp based on source configuration
            event_time = self._parse_timestamp(timestamp_value, source, config)
        
        # Ensure event_time is timezone-aware UTC
        event_time = normalize_to_utc(event_time)
        
        # Calculate latency
        latency_seconds = (receive_time - event_time).total_seconds()
        
        # Check if stale
        staleness_threshold = config.staleness_threshold_seconds if config else 300.0
        is_stale = latency_seconds > staleness_threshold
        stale_age_seconds = int(latency_seconds) if is_stale else None
        
        # Build metadata
        metadata = {
            'is_stale': is_stale,
            'stale_age_seconds': stale_age_seconds,
            'timestamp_source': 'event',
            'original_timestamp': event_time.isoformat() if event_time else None,
        }
        
        return TimestampInfo(
            event_time=event_time,
            receive_time=receive_time,
            latency_seconds=latency_seconds,
            metadata=metadata
        )
    
    def _parse_timestamp(
        self, 
        timestamp_value: Any, 
        source: str, 
        config: Optional[SourceTimestampConfig] = None
    ) -> datetime:
        """
        Parse timestamp from various formats
        
        :param timestamp_value: Timestamp value (string, datetime, etc.)
        :param source: Source identifier
        :param config: Optional source configuration
        :return: Parsed datetime (timezone-aware UTC)
        """
        # If already a datetime, normalize it
        if isinstance(timestamp_value, datetime):
            return normalize_to_utc(timestamp_value)
        
        # If string, parse based on source
        if isinstance(timestamp_value, str):
            # Try ISO format first
            try:
                dt = datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
                return normalize_to_utc(dt)
            except ValueError:
                pass
            
            # Try source-specific format
            if config and config.timestamp_format:
                try:
                    dt = datetime.strptime(timestamp_value, config.timestamp_format)
                    return normalize_to_utc(dt)
                except ValueError:
                    pass
            
            # Try MT5 format
            if source == "mt5":
                # MT5 format: "YYYY.MM.DD HH:MM:SS" or "YYYY.MM.DD HH:MM:SS.mmm"
                try:
                    if len(timestamp_value) == 23 and timestamp_value[19] == '.':
                        dt = datetime.strptime(timestamp_value, "%Y.%m.%d %H:%M:%S.%f")
                    else:
                        dt = datetime.strptime(timestamp_value, "%Y.%m.%d %H:%M:%S")
                    return normalize_to_utc(dt)
                except ValueError:
                    pass
            
            # Try standard format
            try:
                dt = datetime.strptime(timestamp_value[:19], "%Y-%m-%d %H:%M:%S")
                return normalize_to_utc(dt)
            except ValueError:
                pass
        
        # Fallback: use current time
        return get_utc_time()
    
    def align_events(
        self, 
        events: List[Dict[str, Any]], 
        method: str = 'chronological'
    ) -> List[Dict[str, Any]]:
        """
        Align timestamps across multiple events
        
        :param events: List of events (should have timestamp info)
        :param method: Alignment method ('chronological', 'interpolate')
        :return: List of events with aligned timestamps
        """
        if method == 'chronological':
            # Sort by event_time
            sorted_events = sorted(
                events,
                key=lambda e: e.get('timestamp') or e.get('event_time') or datetime.min
            )
            return sorted_events
        else:
            # For now, just return sorted
            return sorted(
                events,
                key=lambda e: e.get('timestamp') or e.get('event_time') or datetime.min
            )


# Global instance
_timestamp_alignment_service = None


def get_timestamp_alignment_service() -> TimestampAlignmentService:
    """Get global timestamp alignment service instance"""
    global _timestamp_alignment_service
    if _timestamp_alignment_service is None:
        _timestamp_alignment_service = TimestampAlignmentService()
    return _timestamp_alignment_service
