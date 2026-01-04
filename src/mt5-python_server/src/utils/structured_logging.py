"""
Structured logging system for the trading server
Provides JSON-formatted logs with correlation IDs, performance metrics, and event tracking
"""

import sys
import json
import logging
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional, Union, Type, Tuple
from types import TracebackType


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs as JSON
    Supports structured fields for log aggregation systems (ELK, Loki, etc.)
    """

    def __init__(self, include_traceback: bool = True):
        """
        Initialize JSON formatter
        :param include_traceback: Whether to include full traceback in exception logs
        """
        super().__init__()
        self.include_traceback = include_traceback

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON
        :param record: Log record
        :return: JSON string
        """
        # Base log structure
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }

        # Add correlation ID if present
        if hasattr(record, "correlation_id") and record.correlation_id:
            log_data["correlation_id"] = record.correlation_id

        # Add event type if present
        if hasattr(record, "event_type") and record.event_type:
            log_data["event_type"] = record.event_type

        # Add metrics if present
        if hasattr(record, "metrics") and record.metrics:
            log_data["metrics"] = record.metrics

        # Add custom fields if present
        if hasattr(record, "custom_fields") and record.custom_fields:
            log_data.update(record.custom_fields)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
            }
            if self.include_traceback and record.exc_text:
                log_data["exception"]["traceback"] = record.exc_text

        # Add thread information
        log_data["thread"] = {
            "id": record.thread,
            "name": record.threadName,
        }

        # Add process information
        log_data["process"] = {
            "id": record.process,
            "name": record.processName,
        }

        # Add file location
        log_data["location"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        return json.dumps(log_data, default=str, ensure_ascii=False)


class CorrelationContext:
    """
    Thread-local storage for correlation IDs
    Enables request tracing across multiple components
    """

    _local = threading.local()

    @classmethod
    def get_correlation_id(cls) -> Optional[str]:
        """
        Get current correlation ID for this thread
        :return: Correlation ID or None
        """
        return getattr(cls._local, "correlation_id", None)

    @classmethod
    def set_correlation_id(cls, correlation_id: Optional[str]) -> None:
        """
        Set correlation ID for this thread
        :param correlation_id: Correlation ID to set
        """
        cls._local.correlation_id = correlation_id

    @classmethod
    def generate_correlation_id(cls) -> str:
        """
        Generate and set a new correlation ID for this thread
        :return: Generated correlation ID
        """
        correlation_id = str(uuid.uuid4())
        cls.set_correlation_id(correlation_id)
        return correlation_id

    @classmethod
    @contextmanager
    def with_correlation_id(cls, correlation_id: Optional[str] = None):
        """
        Context manager to set correlation ID for a block of code
        :param correlation_id: Correlation ID to use (generates new one if None)
        """
        old_id = cls.get_correlation_id()
        new_id = correlation_id or cls.generate_correlation_id()
        cls.set_correlation_id(new_id)
        try:
            yield new_id
        finally:
            cls.set_correlation_id(old_id)


class PerformanceLogger:
    """
    Context manager for performance logging
    Automatically logs latency and calculates throughput
    """

    def __init__(self, logger: "StructuredLogger", operation_name: str, **kwargs):
        """
        Initialize performance logger
        :param logger: StructuredLogger instance
        :param operation_name: Name of the operation being timed
        :param kwargs: Additional fields to include in log
        """
        self.logger = logger
        self.operation_name = operation_name
        self.additional_fields = kwargs
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        """Start timing"""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End timing and log performance metrics"""
        self.end_time = time.perf_counter()
        latency_ms = (self.end_time - self.start_time) * 1000

        metrics = {
            "latency_ms": round(latency_ms, 2),
            "operation": self.operation_name,
        }

        # Add throughput if count is provided
        if "count" in self.additional_fields:
            count = self.additional_fields["count"]
            if count > 0 and latency_ms > 0:
                metrics["throughput"] = round(
                    (count / latency_ms) * 1000, 2
                )  # items per second

        # Remove latency_ms and operation from metrics since they're passed explicitly
        # to avoid duplicate keyword argument error
        metrics.pop("latency_ms", None)
        metrics.pop("operation", None)

        # Log performance
        self.logger.log_performance(
            operation=self.operation_name,
            latency_ms=latency_ms,
            **{**self.additional_fields, **metrics},
        )

        return False  # Don't suppress exceptions


class StructuredLogger:
    """
    Structured logger wrapper around Python's logging.Logger
    Provides structured logging methods with JSON output
    """

    def __init__(self, name: str, logger: Optional[logging.Logger] = None):
        """
        Initialize structured logger
        :param name: Logger name (component name)
        :param logger: Optional existing logger instance
        """
        self.name = name
        self.logger = logger or logging.getLogger(name)

    def _log(
        self,
        level: int,
        message: str,
        event_type: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        exc_info: Optional[
            Union[
                bool,
                BaseException,
                Tuple[
                    Optional[Type[BaseException]],
                    Optional[BaseException],
                    Optional[TracebackType],
                ],
            ]
        ] = None,
        **kwargs,
    ):
        """
        Internal logging method with structured fields
        :param level: Log level (logging.DEBUG, INFO, etc.)
        :param message: Log message
        :param event_type: Type of event (e.g., 'trade', 'error', 'checkpoint')
        :param metrics: Dictionary of metrics to include
        :param correlation_id: Correlation ID for request tracing
        :param exc_info: Exception info (True to include current exception, or Exception instance)
        :param kwargs: Additional custom fields
        """
        # Get correlation ID from context if not provided
        if correlation_id is None:
            correlation_id = CorrelationContext.get_correlation_id()

        # Create extra dict for custom fields
        extra = {
            "correlation_id": correlation_id,
            "event_type": event_type,
            "metrics": metrics,
            "custom_fields": kwargs if kwargs else None,
        }

        # Handle exception info
        # Type for exc_info: bool | tuple[type[BaseException], BaseException, TracebackType | None] | tuple[None, None, None] | BaseException | None
        exc_info_result: Optional[
            Union[
                bool,
                BaseException,
                Tuple[Type[BaseException], BaseException, Optional[TracebackType]],
                Tuple[None, None, None],
            ]
        ] = None
        if exc_info is True:
            exc_info_tuple = sys.exc_info()
            # Ensure tuple format matches expected type
            if exc_info_tuple[0] is not None and exc_info_tuple[1] is not None:
                exc_info_result = (exc_info_tuple[0], exc_info_tuple[1], exc_info_tuple[2])
            else:
                exc_info_result = (None, None, None)
        elif exc_info is False:
            exc_info_result = None
        elif isinstance(exc_info, BaseException):
            exc_info_result = exc_info
        elif isinstance(exc_info, tuple) and len(exc_info) == 3:
            # Ensure tuple format matches expected type
            if exc_info[0] is not None and exc_info[1] is not None:
                exc_info_result = (exc_info[0], exc_info[1], exc_info[2])
            else:
                exc_info_result = (None, None, None)

        self.logger.log(level, message, extra=extra, exc_info=exc_info_result)

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self._log(logging.CRITICAL, message, **kwargs)

    def log_trade(
        self,
        action: str,
        symbol: str,
        account_login: Optional[int] = None,
        lots: Optional[float] = None,
        price: Optional[float] = None,
        order_id: Optional[int] = None,
        profit: Optional[float] = None,
        **kwargs,
    ):
        """
        Log trade event
        :param action: Trade action (buy, sell, close, hold)
        :param symbol: Currency pair symbol
        :param account_login: Account login ID
        :param lots: Lot size
        :param price: Execution price
        :param order_id: Order ID
        :param profit: Profit/loss
        :param kwargs: Additional fields
        """
        metrics = {}
        if lots is not None:
            metrics["lots"] = lots
        if price is not None:
            metrics["price"] = price
        if profit is not None:
            metrics["profit"] = profit

        custom_fields = {
            "symbol": symbol,
            "action": action,
        }
        if account_login is not None:
            custom_fields["account_login"] = str(account_login)
        if order_id is not None:
            custom_fields["order_id"] = str(order_id)

        self.info(
            f"Trade {action} on {symbol}",
            event_type="trade",
            metrics=metrics if metrics else None,
            **{**custom_fields, **kwargs},
        )

    def log_performance(
        self,
        operation: str,
        latency_ms: float,
        throughput: Optional[float] = None,
        count: Optional[int] = None,
        **kwargs,
    ):
        """
        Log performance metrics
        :param operation: Operation name
        :param latency_ms: Latency in milliseconds
        :param throughput: Throughput (items per second)
        :param count: Number of items processed
        :param kwargs: Additional fields
        """
        metrics = {
            "latency_ms": latency_ms,
        }
        if throughput is not None:
            metrics["throughput"] = throughput
        if count is not None:
            metrics["count"] = count

        self.info(
            f"Performance: {operation}",
            event_type="performance",
            metrics=metrics,
            **kwargs,
        )

    def log_error(
        self,
        event_type: str,
        error: str,
        symbol: Optional[str] = None,
        account_login: Optional[int] = None,
        exc_info: Union[bool, Exception] = True,
        **kwargs,
    ):
        """
        Log error event
        :param event_type: Type of error event
        :param error: Error message
        :param symbol: Currency pair symbol (if applicable)
        :param account_login: Account login ID (if applicable)
        :param exc_info: Exception info to include
        :param kwargs: Additional fields
        """
        custom_fields: Dict[str, Any] = {}
        if symbol:
            custom_fields["symbol"] = symbol
        if account_login is not None:
            custom_fields["account_login"] = account_login

        self.error(
            error,
            event_type=event_type,
            exc_info=exc_info,
            **{**custom_fields, **kwargs},
        )

    def log_event(
        self,
        event_type: str,
        message: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        level: str = "INFO",
        **kwargs,
    ):
        """
        Log general event
        :param event_type: Type of event
        :param message: Event message (auto-generated if not provided)
        :param metrics: Dictionary of metrics
        :param level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        :param kwargs: Additional fields
        """
        if message is None:
            message = f"Event: {event_type}"

        log_level = getattr(logging, level.upper(), logging.INFO)
        self._log(log_level, message, event_type=event_type, metrics=metrics, **kwargs)

    @contextmanager
    def performance_context(self, operation_name: str, **kwargs):
        """
        Context manager for performance logging
        :param operation_name: Name of the operation
        :param kwargs: Additional fields to include
        :return: PerformanceLogger context manager
        """
        with PerformanceLogger(self, operation_name, **kwargs):
            yield

    def get_correlation_id(self) -> Optional[str]:
        """Get current correlation ID"""
        return CorrelationContext.get_correlation_id()

    def set_correlation_id(self, correlation_id: Optional[str]) -> None:
        """Set correlation ID for current thread"""
        CorrelationContext.set_correlation_id(correlation_id)

    def generate_correlation_id(self) -> str:
        """Generate and set new correlation ID"""
        return CorrelationContext.generate_correlation_id()

    @contextmanager
    def correlation_context(self, correlation_id: Optional[str] = None):
        """
        Context manager for correlation ID
        :param correlation_id: Correlation ID to use (generates new if None)
        :return: Correlation ID
        """
        with CorrelationContext.with_correlation_id(correlation_id):
            yield CorrelationContext.get_correlation_id()


# Import sys for exc_info handling
