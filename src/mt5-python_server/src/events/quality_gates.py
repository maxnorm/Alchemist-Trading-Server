"""
Event-level quality gates integrated with normalization
Provides quality checks for normalized events
"""

import os
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from utils.time_utils import get_utc_time, normalize_to_utc
from utils.logging_config import get_logger
from .schema_registry import CanonicalEventSchema


class EventQualityGates:
    """
    Event-level quality checks integrated with normalization
    Validates normalized events before they enter the system
    """
    
    def __init__(
        self,
        future_timestamp_buffer_seconds: float = None,  # Make configurable
        stale_threshold_seconds: float = 300.0,
    ):
        """
        Initialize event quality gates
        
        :param future_timestamp_buffer_seconds: Buffer for future timestamp validation (default: 60s, configurable via env var)
        :param stale_threshold_seconds: Maximum age for events (default: 300s / 5 minutes)
        """
        # Allow buffer to be configured via environment variable
        if future_timestamp_buffer_seconds is None:
            future_timestamp_buffer_seconds = float(
                os.getenv("EVENT_QUALITY_GATES_FUTURE_BUFFER_SECONDS", "60.0")
            )
        self.future_timestamp_buffer = future_timestamp_buffer_seconds
        self.stale_threshold = stale_threshold_seconds
        self.logger = get_logger("event_quality_gates", "event_quality_gates.log")
        
        # Metrics tracking
        self.metrics = {
            "total_checked": 0,
            "passed": 0,
            "failed_timestamp": 0,
            "failed_required_fields": 0,
            "failed_data_type": 0,
            "failed_value_range": 0,
        }
    
    def validate(
        self, event: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate event quality
        
        :param event: Normalized event dictionary
        :return: Tuple of (is_valid, rejection_reason)
        """
        self.metrics["total_checked"] += 1
        
        # Check 1: Required fields
        required_fields = ["timestamp", "source", "symbol", "data_type", "payload"]
        for field in required_fields:
            if field not in event:
                self.metrics["failed_required_fields"] += 1
                return False, f"Missing required field: {field}"
        
        # Check 2: Timestamp validation
        timestamp_valid, timestamp_reason = self._validate_timestamp(event["timestamp"])
        if not timestamp_valid:
            self.metrics["failed_timestamp"] += 1
            return False, timestamp_reason
        
        # Check 3: Data type validation
        data_type_valid, data_type_reason = self._validate_data_type(
            event["data_type"], event.get("payload", {})
        )
        if not data_type_valid:
            self.metrics["failed_data_type"] += 1
            return False, data_type_reason
        
        # Check 4: Value range checks (source-specific)
        range_valid, range_reason = self._validate_value_ranges(event)
        if not range_valid:
            self.metrics["failed_value_range"] += 1
            return False, range_reason
        
        # All checks passed
        self.metrics["passed"] += 1
        return True, None
    
    def _validate_timestamp(
        self, timestamp: Any
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate timestamp (not future, not too stale)
        
        :param timestamp: Timestamp to validate (datetime or string)
        :return: Tuple of (is_valid, rejection_reason)
        """
        try:
            # Normalize to UTC datetime
            if isinstance(timestamp, str):
                dt = normalize_to_utc(timestamp)
            elif isinstance(timestamp, datetime):
                dt = normalize_to_utc(timestamp)
            else:
                return False, f"Invalid timestamp type: {type(timestamp)}"
            
            # Ensure timezone-aware
            if dt.tzinfo is None:
                return False, "Timestamp must be timezone-aware"
            
            current_time = get_utc_time()
            
            # Check for future timestamps (with buffer)
            time_diff = (dt - current_time).total_seconds()
            if time_diff > self.future_timestamp_buffer:
                return False, (
                    f"Future timestamp detected: {time_diff:.2f}s ahead of current time "
                    f"(buffer: {self.future_timestamp_buffer}s)"
                )
            
            # Check for stale timestamps
            age_seconds = (current_time - dt).total_seconds()
            if age_seconds > self.stale_threshold:
                return False, (
                    f"Stale timestamp: {age_seconds:.1f}s old "
                    f"(threshold: {self.stale_threshold}s)"
                )
            
            return True, None
            
        except Exception as e:
            return False, f"Timestamp validation error: {e}"
    
    def _validate_data_type(
        self, data_type: str, payload: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate data type and payload structure
        
        :param data_type: Data type string
        :param payload: Payload dictionary
        :return: Tuple of (is_valid, rejection_reason)
        """
        from .schema_registry import DataType
        
        # Validate data type enum
        try:
            DataType(data_type)
        except ValueError:
            return False, f"Invalid data_type: {data_type}"
        
        # Type-specific payload validation
        if data_type == "tick":
            # Ticks must have bid and ask
            if "bid" not in payload or "ask" not in payload:
                return False, "Tick payload missing bid or ask"
            
            # Validate bid/ask are numeric
            try:
                float(payload["bid"])
                float(payload["ask"])
            except (ValueError, TypeError):
                return False, "Tick bid/ask must be numeric"
        
        elif data_type == "bar":
            # Bars should have OHLC
            required = ["open", "high", "low", "close"]
            for field in required:
                if field not in payload:
                    return False, f"Bar payload missing {field}"
        
        # Other types can have flexible payloads for now
        return True, None
    
    def _validate_value_ranges(
        self, event: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate value ranges (e.g., bid < ask for ticks)
        
        :param event: Event dictionary
        :return: Tuple of (is_valid, rejection_reason)
        """
        data_type = event.get("data_type")
        payload = event.get("payload", {})
        
        if data_type == "tick":
            # Check bid < ask
            try:
                bid = float(payload.get("bid", 0))
                ask = float(payload.get("ask", 0))
                
                if bid <= 0 or ask <= 0:
                    return False, f"Invalid prices: bid={bid}, ask={ask} (must be > 0)"
                
                if ask <= bid:
                    return False, f"Invalid spread: bid={bid}, ask={ask} (ask must be > bid)"
                
                # Check for unrealistic spread (> 10 pips = 0.001 for most pairs)
                spread = ask - bid
                if spread > 0.001:
                    return False, f"Unrealistic spread: {spread:.6f} (> 0.001 / 10 pips)"
                
            except (ValueError, TypeError) as e:
                return False, f"Invalid price values: {e}"
        
        elif data_type == "bar":
            # Check OHLC consistency
            try:
                open_price = float(payload.get("open", 0))
                high = float(payload.get("high", 0))
                low = float(payload.get("low", 0))
                close = float(payload.get("close", 0))
                
                if high < low:
                    return False, f"Invalid bar: high={high} < low={low}"
                
                if high < open or high < close:
                    return False, f"Invalid bar: high must be >= open and close"
                
                if low > open or low > close:
                    return False, f"Invalid bar: low must be <= open and close"
                
            except (ValueError, TypeError) as e:
                return False, f"Invalid bar values: {e}"
        
        return True, None
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get quality gate metrics
        
        :return: Dictionary of metrics
        """
        total = self.metrics["total_checked"]
        passed = self.metrics["passed"]
        pass_rate = (passed / total * 100) if total > 0 else 0.0
        
        return {
            **self.metrics,
            "pass_rate": pass_rate,
            "fail_rate": 100.0 - pass_rate,
        }
    
    def reset_metrics(self) -> None:
        """Reset all metrics"""
        self.metrics = {
            "total_checked": 0,
            "passed": 0,
            "failed_timestamp": 0,
            "failed_required_fields": 0,
            "failed_data_type": 0,
            "failed_value_range": 0,
        }
