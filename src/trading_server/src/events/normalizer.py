"""
Core normalization logic converting raw events to canonical format
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from utils.time_utils import normalize_to_utc, get_utc_time
from utils.logging_config import get_logger
from .schema_registry import (
    CanonicalEventSchema,
    SchemaRegistry,
    SourceType,
    get_schema_registry,
)
from .quality_gates import EventQualityGates


class IEventNormalizer(ABC):
    """
    Abstract base class for event normalization
    Defines interface for converting raw events to canonical format
    """

    @abstractmethod
    def normalize(self, raw_event: Dict, source: str) -> Dict[str, Any]:
        """
        Convert raw event to canonical format

        :param raw_event: Raw event dictionary from source
        :param source: Source identifier (e.g., "mt5", "api")
        :return: Normalized event dictionary
        """
        pass

    @abstractmethod
    def validate(self, event: Dict[str, Any]) -> bool:
        """
        Validate event quality and schema

        :param event: Event dictionary (normalized or raw)
        :return: True if valid, False otherwise
        """
        pass

    @abstractmethod
    def align_timestamps(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Align timestamps across sources

        :param events: List of normalized events
        :return: List of events with aligned timestamps, sorted chronologically
        """
        pass


class EventNormalizer(IEventNormalizer):
    """
    Core event normalizer implementation
    Converts raw events from various sources to canonical format
    """

    def __init__(
        self,
        schema_registry: Optional[SchemaRegistry] = None,
        quality_gates: Optional[EventQualityGates] = None,
        max_timestamp_drift_seconds: float = 1.0,
    ):
        """
        Initialize event normalizer

        :param schema_registry: Schema registry instance (uses global if None)
        :param quality_gates: Quality gates instance (creates new if None)
        :param max_timestamp_drift_seconds: Maximum allowed drift for timestamp alignment
        """
        self.schema_registry = schema_registry or get_schema_registry()
        self.quality_gates = quality_gates or EventQualityGates()
        self.max_timestamp_drift = max_timestamp_drift_seconds
        self.logger = get_logger("event_normalizer", "event_normalizer.log")

        # Register default source schemas
        self._register_default_schemas()

    def _register_default_schemas(self) -> None:
        """Register default schemas for known sources"""
        # MT5 tick schema
        self.schema_registry.register_source_schema(
            source="mt5",
            schema={
                "symbol": str,
                "datetime": str,  #"YYYY.MM.DD HH:MM:SS"
                "ask": float,
                "bid": float,
            },
            required_fields=["symbol", "ask", "bid"],  # datetime handled flexibly in _normalize_mt5
        )

    def normalize(self, raw_event: Dict, source: str) -> Dict[str, Any]:
        """
        Convert raw event to canonical format with bitemporal timestamps

        :param raw_event: Raw event dictionary from source
        :param source: Source identifier (e.g., "mt5", "api")
        :return: Normalized event dictionary conforming to CanonicalEventSchema
        """
        try:
            # Validate source
            try:
                SourceType(source)
            except ValueError:
                self.logger.error(f"Invalid source: {source}")
                raise ValueError(f"Invalid source: {source}")

            # Validate against source schema
            is_valid, error = self.schema_registry.validate_source_event(
                source, raw_event
            )
            if not is_valid:
                self.logger.warning(f"Source event validation failed: {error}")
                # Continue anyway - schema validation is advisory

            # Extract receive_time (when we received the event)
            receive_time = raw_event.get("_receive_time")
            if receive_time is None:
                receive_time = get_utc_time()
            else:
                # Ensure receive_time is timezone-aware UTC
                receive_time = normalize_to_utc(receive_time)

            # Source-specific normalization
            if source == "mt5":
                canonical_event = self._normalize_mt5(raw_event, receive_time)
            elif source == "api":
                canonical_event = self._normalize_api(raw_event, receive_time)
            elif source == "scraper":
                canonical_event = self._normalize_scraped(raw_event, receive_time)
            elif source == "news":
                canonical_event = self._normalize_news(raw_event, receive_time)
            else:
                raise ValueError(f"Unsupported source for normalization: {source}")

            # Get timestamp_metadata from raw_event if available (from quality gate)
            timestamp_metadata = raw_event.get("_timestamp_metadata", {})

            # Extract event_time (timestamp) from canonical event
            event_time = canonical_event.get("timestamp")
            if event_time is None:
                event_time = receive_time

            # Calculate latency if not already in metadata
            if "latency_seconds" not in timestamp_metadata:
                latency_seconds = (receive_time - event_time).total_seconds()
                timestamp_metadata["latency_seconds"] = latency_seconds

            # Update metadata with receive_time
            timestamp_metadata["receive_time"] = (
                receive_time.isoformat()
                if isinstance(receive_time, datetime)
                else str(receive_time)
            )

            # Ensure timestamp_source is set
            if "timestamp_source" not in timestamp_metadata:
                timestamp_metadata["timestamp_source"] = "event"

            # Add bitemporal fields to canonical event
            canonical_event["receive_time"] = receive_time
            canonical_event["timestamp_metadata"] = timestamp_metadata

            return canonical_event

        except Exception as e:
            self.logger.error(
                f"Normalization failed for source {source}: {e}",
                exc_info=True,
            )
            raise

    def _normalize_mt5(
        self, raw_event: Dict, receive_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Normalize MT5 tick event to canonical format with bitemporal timestamps

        :param raw_event: Raw MT5 tick dictionary
        :param receive_time: When we received the event (optional)
        :return: Normalized event dictionary
        """
        # Extract fields (use "datetime" field name)
        date_time_value = raw_event.get("datetime")
        symbol = raw_event.get("symbol", "")
        ask = raw_event.get("ask", 0.0)
        bid = raw_event.get("bid", 0.0)

        # Normalize timestamp to UTC
        # Handle both datetime objects and strings
        date_time_str_for_logging: str = ""
        if isinstance(date_time_value, datetime):
            # Already a datetime object, ensure it's UTC and timezone-aware
            from utils.time_utils import ensure_utc_timezone

            timestamp = ensure_utc_timezone(date_time_value)
            date_time_str_for_logging = str(date_time_value)  # For logging/reference
        else:
            # String input - parse and normalize
            date_time_str_for_logging = (
                str(date_time_value) if date_time_value is not None else ""
            )
            # Check if timezone offset is provided in the raw event (from tick_streamer detection)
            mt5_timezone_offset = raw_event.get("_mt5_timezone_offset")
            try:
                if mt5_timezone_offset is not None:
                    # Use the detected timezone offset from tick_streamer
                    from utils.time_utils import parse_mt5_timestamp

                    timestamp = parse_mt5_timestamp(
                        date_time_str_for_logging, mt5_timezone_offset
                    )
                else:
                    # Fallback to default normalization (assumes UTC)
                    timestamp = normalize_to_utc(date_time_str_for_logging)
            except Exception as e:
                self.logger.error(f"Failed to normalize MT5 timestamp: {e}")
                # Fallback to current time
                timestamp = get_utc_time()

        # After timestamp normalization, add validation logging
        current_time = get_utc_time()
        time_diff = (timestamp - current_time).total_seconds()

        if abs(time_diff) > 300:  # More than 5 minutes
            self.logger.warning(
                f"Large timestamp difference detected: {time_diff:.1f}s "
                f"(raw: {date_time_str_for_logging}, normalized: {timestamp})"
            )

        # Extract digits if available (for accurate pip calculation)
        digits = raw_event.get("_digits")

        # Create canonical event with event_time (preserve original timestamp)
        canonical_event = {
            "timestamp": timestamp,  # event_time (preserved)
            "source": "mt5",
            "symbol": symbol,
            "data_type": "tick",
            "payload": {
                "bid": float(bid),
                "ask": float(ask),
                # Include original timestamp string for reference
                "original_timestamp": date_time_str_for_logging,
            },
        }

        # Add digits to payload if available (for quality gates to use)
        if digits is not None:
            canonical_event["payload"]["digits"] = int(digits)

        return canonical_event

    def _normalize_api(
        self, raw_event: Dict, receive_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Normalize API event to canonical format with bitemporal timestamps

        :param raw_event: Raw API event dictionary
        :param receive_time: When we received the event (optional)
        :return: Normalized event dictionary
        """
        # Extract timestamp (could be ISO string or datetime)
        timestamp_raw = raw_event.get("timestamp") or raw_event.get("datetime")
        if timestamp_raw:
            timestamp = normalize_to_utc(timestamp_raw)
        else:
            timestamp = get_utc_time()

        # Extract symbol
        symbol = raw_event.get("symbol", "")

        # Determine data type from payload structure
        data_type = raw_event.get("data_type", "tick")
        if "open" in raw_event and "high" in raw_event:
            data_type = "bar"

        # Create canonical event
        canonical_event = {
            "timestamp": timestamp,
            "source": "api",
            "symbol": symbol,
            "data_type": data_type,
            "payload": {
                # Include all original fields in payload
                **{
                    k: v
                    for k, v in raw_event.items()
                    if k
                    not in ["timestamp", "datetime", "symbol", "data_type", "source"]
                },
            },
        }

        return canonical_event

    def _normalize_scraped(
        self, raw_event: Dict, receive_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Normalize scraped data event to canonical format with bitemporal timestamps

        :param raw_event: Raw scraped data dictionary
        :param receive_time: When we received the event (optional)
        :return: Normalized event dictionary
        """
        # Extract timestamp
        timestamp_raw = raw_event.get("timestamp") or raw_event.get("datetime")
        if timestamp_raw:
            timestamp = normalize_to_utc(timestamp_raw)
        else:
            timestamp = get_utc_time()

        # Extract symbol (may not always be present for scraped data)
        symbol = raw_event.get("symbol", "")

        # Scraped data is typically news or economic data
        data_type = raw_event.get("data_type", "news")

        # Create canonical event
        canonical_event = {
            "timestamp": timestamp,
            "source": "scraper",
            "symbol": symbol,
            "data_type": data_type,
            "payload": {
                **{
                    k: v
                    for k, v in raw_event.items()
                    if k
                    not in ["timestamp", "datetime", "symbol", "data_type", "source"]
                },
            },
        }

        return canonical_event

    def _normalize_news(
        self, raw_event: Dict, receive_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Normalize news event to canonical format with bitemporal timestamps

        :param raw_event: Raw news event dictionary
        :param receive_time: When we received the event (optional)
        :return: Normalized event dictionary
        """
        # Extract timestamp
        timestamp_raw = (
            raw_event.get("timestamp")
            or raw_event.get("datetime")
            or raw_event.get("published_at")
        )
        if timestamp_raw:
            timestamp = normalize_to_utc(timestamp_raw)
        else:
            timestamp = get_utc_time()

        # Extract symbol (news may affect multiple symbols)
        symbol = raw_event.get("symbol") or raw_event.get("currency") or ""

        # Create canonical event
        canonical_event = {
            "timestamp": timestamp,
            "source": "news",
            "symbol": symbol,
            "data_type": "news",
            "payload": {
                **{
                    k: v
                    for k, v in raw_event.items()
                    if k
                    not in [
                        "timestamp",
                        "datetime",
                        "published_at",
                        "symbol",
                        "currency",
                        "data_type",
                        "source",
                    ]
                },
            },
        }

        return canonical_event

    def validate(self, event: Dict[str, Any]) -> bool:
        """
        Validate event quality and schema

        :param event: Event dictionary (normalized or raw)
        :return: True if valid, False otherwise
        """
        # First check if it's a canonical event
        try:
            canonical = CanonicalEventSchema.from_dict(event)
            schema_valid, schema_error = canonical.validate()
            if not schema_valid:
                self.logger.warning(f"Schema validation failed: {schema_error}")
                return False
        except Exception as e:
            self.logger.warning(f"Failed to create canonical schema: {e}")
            return False

        # Run quality gates
        is_valid, reason = self.quality_gates.validate(event)
        if not is_valid:
            self.logger.warning(f"Quality gate validation failed: {reason}")
            return False

        return True

    def align_timestamps(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Align timestamps across sources and sort chronologically

        :param events: List of normalized events
        :return: List of events with aligned timestamps, sorted chronologically
        """
        if not events:
            return []

        # Normalize all timestamps to UTC and ensure timezone-aware
        aligned_events = []
        current_time = get_utc_time()

        for event in events:
            try:
                # Extract and normalize timestamp
                timestamp = event.get("timestamp")
                if isinstance(timestamp, str):
                    normalized_timestamp = normalize_to_utc(timestamp)
                elif isinstance(timestamp, datetime):
                    normalized_timestamp = normalize_to_utc(timestamp)
                else:
                    self.logger.warning(f"Invalid timestamp type: {type(timestamp)}")
                    continue

                # Ensure timezone-aware
                if normalized_timestamp.tzinfo is None:
                    from utils.time_utils import get_server_timezone

                    normalized_timestamp = get_server_timezone().localize(
                        normalized_timestamp
                    )

                # Check for future timestamps (validation)
                time_diff = (normalized_timestamp - current_time).total_seconds()
                if time_diff > self.max_timestamp_drift:
                    self.logger.warning(
                        f"Future timestamp detected: {time_diff:.2f}s ahead, "
                        f"clamping to current time"
                    )
                    normalized_timestamp = current_time

                # Update event with normalized timestamp
                aligned_event = event.copy()
                aligned_event["timestamp"] = normalized_timestamp
                aligned_events.append(aligned_event)

            except Exception as e:
                self.logger.error(f"Failed to align timestamp for event: {e}")
                continue

        # Sort chronologically
        aligned_events.sort(key=lambda e: e.get("timestamp", datetime.min))

        # Validate alignment (check for excessive drift between sources)
        if len(aligned_events) > 1:
            self._validate_timestamp_alignment(aligned_events)

        return aligned_events

    def _validate_timestamp_alignment(self, events: List[Dict[str, Any]]) -> None:
        """
        Validate timestamp alignment across sources

        :param events: List of aligned events
        """
        if len(events) < 2:
            return

        # Group by source
        sources: Dict[str, List[Dict[str, Any]]] = {}
        for event in events:
            source = event.get("source", "unknown")
            if source not in sources:
                sources[source] = []
            sources[source].append(event)

        # Check drift between sources (if multiple sources present)
        if len(sources) > 1:
            source_timestamps = {
                source: events[0].get("timestamp") if events else None
                for source, events in sources.items()
            }

            # Find max drift
            timestamps = [ts for ts in source_timestamps.values() if ts is not None]
            if timestamps:
                min_ts = min(timestamps)
                max_ts = max(timestamps)
                drift = (max_ts - min_ts).total_seconds()

                if drift > self.max_timestamp_drift:
                    self.logger.warning(
                        f"Timestamp drift detected between sources: {drift:.2f}s "
                        f"(threshold: {self.max_timestamp_drift}s)"
                    )
