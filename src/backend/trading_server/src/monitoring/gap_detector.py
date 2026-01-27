"""
Gap Detection Service

Detects data gaps in tick data collection and sends alerts.
"""

import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from utils.time_utils import get_utc_time
from utils.market_utils import check_if_market_open
from utils.logging_config import get_logger
from database import Database
from monitoring.metrics import data_gaps_detected_total, data_gap_minutes
from infrastructure.messaging.alert_publisher import AlertPublisher


class GapDetector:
    """
    Detects gaps in tick data collection
    """

    def __init__(
        self,
        gap_threshold_minutes: float = 5.0,
        check_interval_minutes: float = 5.0,
        lookback_minutes: float = 10.0,
        enabled: bool = True,
    ):
        """
        Initialize gap detector

        :param gap_threshold_minutes: Minimum gap duration to alert (minutes)
        :param check_interval_minutes: Interval between gap checks (minutes)
        :param lookback_minutes: How far back to check for gaps (minutes)
        :param enabled: Whether gap detection is enabled
        """
        self.gap_threshold_seconds = gap_threshold_minutes * 60
        self.check_interval_seconds = check_interval_minutes * 60
        self.lookback_seconds = lookback_minutes * 60
        self.enabled = enabled

        # Initialize logger
        try:
            self.logger = get_logger("gap_detector", "gap_detector.log")
            self._use_structured = hasattr(self.logger, "log_event")
        except Exception:
            import logging

            self.logger = logging.getLogger("gap_detector")
            self._use_structured = False

        # Database connection
        self.db = Database()

        # Alert publisher for Redis Pub/Sub
        self._alert_publisher: Optional[AlertPublisher] = None

        # Monitoring state
        self._monitoring_thread: Optional[threading.Thread] = None
        self._shutdown_flag = threading.Event()
        self._last_check_time: Optional[datetime] = None
        self._gap_count = 0
        self._system_wide_gap_count = 0

    def start(self):
        """Start gap detection in background thread"""
        if not self.enabled:
            return

        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return  # Already running

        self._shutdown_flag.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self._monitoring_thread.start()

        if self._use_structured:
            self.logger.log_event(
                event_type="gap_detector_started",
                message="Gap detector started",
                metrics={
                    "gap_threshold_seconds": self.gap_threshold_seconds,
                    "check_interval_seconds": self.check_interval_seconds,
                },
            )
        else:
            self.logger.info(
                f"Gap detector started (threshold: {self.gap_threshold_seconds}s, "
                f"interval: {self.check_interval_seconds}s)"
            )

    def stop(self):
        """Stop gap detection"""
        self._shutdown_flag.set()
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=5.0)

        if self._use_structured:
            self.logger.log_event(
                event_type="gap_detector_stopped",
                message="Gap detector stopped",
            )
        else:
            self.logger.info("Gap detector stopped")

    def _monitoring_loop(self):
        """Background monitoring loop"""
        while not self._shutdown_flag.is_set():
            try:
                # Only check during market hours
                if check_if_market_open():
                    self.detect_gaps()
            except Exception as e:
                if self._use_structured:
                    self.logger.log_event(
                        event_type="gap_detection_error",
                        message=f"Error during gap detection: {e}",
                        level="ERROR",
                    )
                else:
                    self.logger.error(f"Error during gap detection: {e}", exc_info=True)

            # Wait for next check or shutdown
            self._shutdown_flag.wait(self.check_interval_seconds)

    def detect_gaps(self) -> List[Dict]:
        """
        Detect gaps in tick data

        :return: List of detected gaps
        """
        current_time = get_utc_time()
        lookback_time = current_time - timedelta(seconds=self.lookback_seconds)

        # Query for gaps using SQL
        query = """
        WITH tick_times AS (
            SELECT
                fp.symbol,
                tf.datetime,
                LAG(tf.datetime) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime) AS prev_datetime
            FROM ticks_forex tf
            JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
            WHERE tf.datetime >= :lookback_time
        ),
        gaps AS (
            SELECT
                symbol,
                prev_datetime AS gap_start,
                datetime AS gap_end,
                EXTRACT(EPOCH FROM (datetime - prev_datetime)) AS gap_seconds
            FROM tick_times
            WHERE prev_datetime IS NOT NULL
                AND EXTRACT(EPOCH FROM (datetime - prev_datetime)) > :gap_threshold
        )
        SELECT
            symbol,
            gap_start,
            gap_end,
            gap_seconds
        FROM gaps
        ORDER BY gap_seconds DESC
        LIMIT 100
        """

        try:
            # Use execute_with_result with parameterized query
            gaps = self.db.execute_with_result(
                query,
                {
                    "lookback_time": lookback_time,
                    "gap_threshold": self.gap_threshold_seconds,
                },
            )

            detected_gaps: List[Dict[str, Any]] = []
            for gap in gaps:
                gap_info = {
                    "data_type": "tick",
                    "symbol": gap[0],
                    "gap_start": gap[1],
                    "gap_end": gap[2],
                    "gap_seconds": float(gap[3]),
                }
                detected_gaps.append(gap_info)

            # Check for system-wide gaps (multiple symbols gap simultaneously)
            system_wide_gaps = self._detect_system_wide_gaps(detected_gaps)

            # Log and alert on gaps
            if detected_gaps:
                self._log_gaps(detected_gaps, system_wide_gaps)

                # Emit metrics for detected gaps
                try:
                    # Group gaps by data_type and symbol for metrics
                    gap_counts: Dict[tuple, int] = {}
                    max_gap_duration: Dict[tuple, float] = {}
                    for gap_dict in detected_gaps:
                        key = (gap_dict["data_type"], gap_dict["symbol"])
                        gap_counts[key] = gap_counts.get(key, 0) + 1
                        # Track maximum gap duration per symbol/data_type
                        gap_minutes = gap_dict["gap_seconds"] / 60.0
                        if (
                            key not in max_gap_duration
                            or gap_minutes > max_gap_duration[key]
                        ):
                            max_gap_duration[key] = gap_minutes

                    for (data_type, symbol), count in gap_counts.items():
                        data_gaps_detected_total.labels(
                            data_type=data_type, symbol=symbol
                        ).inc(count)
                        # Update gap duration metric with maximum gap
                        data_gap_minutes.labels(symbol=symbol, data_type=data_type).set(
                            max_gap_duration[(data_type, symbol)]
                        )
                except Exception as metric_error:
                    if self._use_structured:
                        self.logger.log_event(
                            event_type="gap_metric_error",
                            message=f"Failed to emit gap metrics: {metric_error}",
                            level="WARNING",
                        )
                    else:
                        self.logger.warning(
                            f"Failed to emit gap metrics: {metric_error}"
                        )
            else:
                # No gaps detected - update metrics to 0 for tick data type
                # We need to track which symbols we've checked to reset their metrics
                # For now, we'll leave metrics as-is if no gaps (they represent current state)
                pass

            self._last_check_time = current_time
            return detected_gaps

        except Exception as e:
            if self._use_structured:
                self.logger.log_event(
                    event_type="gap_detection_query_error",
                    message=f"Error querying for gaps: {e}",
                    level="ERROR",
                )
            else:
                self.logger.error(f"Error querying for gaps: {e}", exc_info=True)
            return []

    def detect_bar_gaps(
        self, symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> List[Dict]:
        """
        Detect gaps in bar (OHLCV) data

        :param symbol: Optional symbol to filter by (e.g., "EURUSD")
        :param timeframe: Optional timeframe to filter by (e.g., "M1", "M5", "H1")
        :return: List of detected gaps
        """
        current_time = get_utc_time()
        lookback_time = current_time - timedelta(seconds=self.lookback_seconds)

        # Build query with optional filters
        symbol_filter = ""
        timeframe_filter = ""
        params = {
            "lookback_time": lookback_time,
            "gap_threshold": self.gap_threshold_seconds,
        }

        if symbol:
            symbol_filter = "AND fp.symbol = :symbol"
            params["symbol"] = symbol.upper()

        if timeframe:
            timeframe_filter = "AND bf.timeframe = :timeframe"
            params["timeframe"] = timeframe

        query = f"""
        WITH bar_times AS (
            SELECT
                fp.symbol,
                bf.timeframe,
                bf.datetime,
                LAG(bf.datetime) OVER (PARTITION BY fp.symbol, bf.timeframe ORDER BY bf.datetime) AS prev_datetime
            FROM bars_forex bf
            JOIN forex_pairs fp ON bf.forex_pairs_id = fp.id
            WHERE bf.datetime >= :lookback_time
                {symbol_filter}
                {timeframe_filter}
        ),
        gaps AS (
            SELECT
                symbol,
                timeframe,
                prev_datetime AS gap_start,
                datetime AS gap_end,
                EXTRACT(EPOCH FROM (datetime - prev_datetime)) AS gap_seconds
            FROM bar_times
            WHERE prev_datetime IS NOT NULL
                AND EXTRACT(EPOCH FROM (datetime - prev_datetime)) > :gap_threshold
        )
        SELECT
            symbol,
            timeframe,
            gap_start,
            gap_end,
            gap_seconds
        FROM gaps
        ORDER BY gap_seconds DESC
        LIMIT 100
        """

        try:
            gaps = self.db.execute_with_result(query, params)

            detected_gaps: List[Dict[str, Any]] = []
            for gap in gaps:
                gap_info = {
                    "data_type": "bar",
                    "symbol": gap[0],
                    "timeframe": gap[1],
                    "gap_start": gap[2],
                    "gap_end": gap[3],
                    "gap_seconds": float(gap[4]),
                }
                detected_gaps.append(gap_info)

            if detected_gaps:
                self._log_gaps(detected_gaps, [])

                # Emit metrics for detected gaps
                try:
                    gap_counts: Dict[tuple, int] = {}
                    max_gap_duration: Dict[tuple, float] = {}
                    for gap_dict in detected_gaps:
                        key = (gap_dict["data_type"], gap_dict["symbol"])
                        gap_counts[key] = gap_counts.get(key, 0) + 1
                        # Track maximum gap duration per symbol/data_type
                        gap_minutes = gap_dict["gap_seconds"] / 60.0
                        if (
                            key not in max_gap_duration
                            or gap_minutes > max_gap_duration[key]
                        ):
                            max_gap_duration[key] = gap_minutes

                    for (data_type, symbol), count in gap_counts.items():
                        data_gaps_detected_total.labels(
                            data_type=data_type, symbol=symbol
                        ).inc(count)
                        # Update gap duration metric with maximum gap
                        data_gap_minutes.labels(symbol=symbol, data_type=data_type).set(
                            max_gap_duration[(data_type, symbol)]
                        )
                except Exception as metric_error:
                    if self._use_structured:
                        self.logger.log_event(
                            event_type="gap_metric_error",
                            message=f"Failed to emit bar gap metrics: {metric_error}",
                            level="WARNING",
                        )
                    else:
                        self.logger.warning(
                            f"Failed to emit bar gap metrics: {metric_error}"
                        )

            return detected_gaps

        except Exception as e:
            if self._use_structured:
                self.logger.log_event(
                    event_type="gap_detection_query_error",
                    message=f"Error querying for bar gaps: {e}",
                    level="ERROR",
                )
            else:
                self.logger.error(f"Error querying for bar gaps: {e}", exc_info=True)
            return []

    def detect_news_gaps(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Detect gaps in news article data

        :param symbol: Optional symbol to filter by (e.g., "EURUSD")
        :return: List of detected gaps
        """
        current_time = get_utc_time()
        lookback_time = current_time - timedelta(seconds=self.lookback_seconds)

        # News gaps are detected based on expected frequency
        # For news, we expect at least one article per hour during market hours
        # Gaps are periods with no news for > 2 hours
        symbol_filter = ""
        params = {
            "lookback_time": lookback_time,
            "gap_threshold": max(
                self.gap_threshold_seconds, 2 * 3600
            ),  # At least 2 hours for news
        }

        if symbol:
            symbol_filter = "AND na.symbol = :symbol"
            params["symbol"] = symbol.upper()

        query = f"""
        WITH news_times AS (
            SELECT
                COALESCE(na.symbol, '*') AS symbol,
                na.timestamp,
                LAG(na.timestamp) OVER (PARTITION BY COALESCE(na.symbol, '*') ORDER BY na.timestamp) AS prev_timestamp
            FROM news_articles na
            WHERE na.timestamp >= :lookback_time
                {symbol_filter}
        ),
        gaps AS (
            SELECT
                symbol,
                prev_timestamp AS gap_start,
                timestamp AS gap_end,
                EXTRACT(EPOCH FROM (timestamp - prev_timestamp)) AS gap_seconds
            FROM news_times
            WHERE prev_timestamp IS NOT NULL
                AND EXTRACT(EPOCH FROM (timestamp - prev_timestamp)) > :gap_threshold
        )
        SELECT
            symbol,
            gap_start,
            gap_end,
            gap_seconds
        FROM gaps
        ORDER BY gap_seconds DESC
        LIMIT 100
        """

        try:
            gaps = self.db.execute_with_result(query, params)

            detected_gaps: List[Dict[str, Any]] = []
            for gap in gaps:
                gap_info = {
                    "data_type": "news",
                    "symbol": gap[0],
                    "gap_start": gap[1],
                    "gap_end": gap[2],
                    "gap_seconds": float(gap[3]),
                }
                detected_gaps.append(gap_info)

            if detected_gaps:
                self._log_gaps(detected_gaps, [])

                # Emit metrics for detected gaps
                try:
                    gap_counts: Dict[tuple, int] = {}
                    max_gap_duration: Dict[tuple, float] = {}
                    for gap_dict in detected_gaps:
                        key = (gap_dict["data_type"], gap_dict["symbol"])
                        gap_counts[key] = gap_counts.get(key, 0) + 1
                        # Track maximum gap duration per symbol/data_type
                        gap_minutes = gap_dict["gap_seconds"] / 60.0
                        if (
                            key not in max_gap_duration
                            or gap_minutes > max_gap_duration[key]
                        ):
                            max_gap_duration[key] = gap_minutes

                    for (data_type, symbol), count in gap_counts.items():
                        data_gaps_detected_total.labels(
                            data_type=data_type, symbol=symbol
                        ).inc(count)
                        # Update gap duration metric with maximum gap
                        data_gap_minutes.labels(symbol=symbol, data_type=data_type).set(
                            max_gap_duration[(data_type, symbol)]
                        )
                except Exception as metric_error:
                    if self._use_structured:
                        self.logger.log_event(
                            event_type="gap_metric_error",
                            message=f"Failed to emit news gap metrics: {metric_error}",
                            level="WARNING",
                        )
                    else:
                        self.logger.warning(
                            f"Failed to emit news gap metrics: {metric_error}"
                        )

            return detected_gaps

        except Exception as e:
            if self._use_structured:
                self.logger.log_event(
                    event_type="gap_detection_query_error",
                    message=f"Error querying for news gaps: {e}",
                    level="ERROR",
                )
            else:
                self.logger.error(f"Error querying for news gaps: {e}", exc_info=True)
            return []

    def detect_economic_gaps(
        self, series_id: Optional[str] = None, source: Optional[str] = None
    ) -> List[Dict]:
        """
        Detect gaps in economic indicator data

        :param series_id: Optional series_id to filter by (e.g., "FEDFUNDS")
        :param source: Optional source to filter by (e.g., "FRED", "ECB")
        :return: List of detected gaps
        """
        current_time = get_utc_time()
        lookback_time = current_time - timedelta(seconds=self.lookback_seconds)

        # Economic indicators have different frequencies (daily, weekly, monthly, etc.)
        # Gaps are detected per series_id, as each series has its own expected frequency
        series_filter = ""
        source_filter = ""
        params = {
            "lookback_time": lookback_time,
            "gap_threshold": max(
                self.gap_threshold_seconds, 7 * 24 * 3600
            ),  # At least 7 days for economic data
        }

        if series_id:
            series_filter = "AND ei.series_id = :series_id"
            params["series_id"] = series_id

        if source:
            source_filter = "AND ei.source = :source"
            params["source"] = source

        query = f"""
        WITH economic_times AS (
            SELECT
                ei.series_id,
                ei.source,
                ei.timestamp,
                LAG(ei.timestamp) OVER (PARTITION BY ei.series_id ORDER BY ei.timestamp) AS prev_timestamp
            FROM economic_indicators ei
            WHERE ei.timestamp >= :lookback_time
                {series_filter}
                {source_filter}
        ),
        gaps AS (
            SELECT
                series_id,
                source,
                prev_timestamp AS gap_start,
                timestamp AS gap_end,
                EXTRACT(EPOCH FROM (timestamp - prev_timestamp)) AS gap_seconds
            FROM economic_times
            WHERE prev_timestamp IS NOT NULL
                AND EXTRACT(EPOCH FROM (timestamp - prev_timestamp)) > :gap_threshold
        )
        SELECT
            series_id,
            source,
            gap_start,
            gap_end,
            gap_seconds
        FROM gaps
        ORDER BY gap_seconds DESC
        LIMIT 100
        """

        try:
            gaps = self.db.execute_with_result(query, params)

            detected_gaps: List[Dict[str, Any]] = []
            for gap in gaps:
                gap_info = {
                    "data_type": "economic",
                    "series_id": gap[0],
                    "source": gap[1],
                    "symbol": gap[0],  # Use series_id as symbol for metrics
                    "gap_start": gap[2],
                    "gap_end": gap[3],
                    "gap_seconds": float(gap[4]),
                }
                detected_gaps.append(gap_info)

            if detected_gaps:
                self._log_gaps(detected_gaps, [])

                # Emit metrics for detected gaps
                try:
                    gap_counts: Dict[tuple, int] = {}
                    max_gap_duration: Dict[tuple, float] = {}
                    for gap_dict in detected_gaps:
                        key = (gap_dict["data_type"], gap_dict["symbol"])
                        gap_counts[key] = gap_counts.get(key, 0) + 1
                        # Track maximum gap duration per symbol/data_type
                        gap_minutes = gap_dict["gap_seconds"] / 60.0
                        if (
                            key not in max_gap_duration
                            or gap_minutes > max_gap_duration[key]
                        ):
                            max_gap_duration[key] = gap_minutes

                    for (data_type, symbol), count in gap_counts.items():
                        data_gaps_detected_total.labels(
                            data_type=data_type, symbol=symbol
                        ).inc(count)
                        # Update gap duration metric with maximum gap
                        data_gap_minutes.labels(symbol=symbol, data_type=data_type).set(
                            max_gap_duration[(data_type, symbol)]
                        )
                except Exception as metric_error:
                    if self._use_structured:
                        self.logger.log_event(
                            event_type="gap_metric_error",
                            message=f"Failed to emit economic gap metrics: {metric_error}",
                            level="WARNING",
                        )
                    else:
                        self.logger.warning(
                            f"Failed to emit economic gap metrics: {metric_error}"
                        )

            return detected_gaps

        except Exception as e:
            if self._use_structured:
                self.logger.log_event(
                    event_type="gap_detection_query_error",
                    message=f"Error querying for economic gaps: {e}",
                    level="ERROR",
                )
            else:
                self.logger.error(
                    f"Error querying for economic gaps: {e}", exc_info=True
                )
            return []

    def detect_all_gaps(self) -> Dict[str, List[Dict]]:
        """
        Detect gaps across all data types

        :return: Dictionary with gaps by data type
        """
        return {
            "ticks": self.detect_gaps(),
            "bars": self.detect_bar_gaps(),
            "news": self.detect_news_gaps(),
            "economic": self.detect_economic_gaps(),
        }

    def _detect_system_wide_gaps(self, gaps: List[Dict]) -> List[Dict]:
        """
        Detect system-wide gaps (multiple symbols gap simultaneously)

        :param gaps: List of detected gaps
        :return: List of system-wide gaps
        """
        # Group gaps by time window (within 1 minute)
        time_windows: Dict[str, List[Dict]] = {}
        for gap in gaps:
            gap_start = gap["gap_start"]
            if isinstance(gap_start, str):
                from datetime import datetime

                gap_start = datetime.fromisoformat(gap_start.replace("Z", "+00:00"))

            # Round to nearest minute for grouping
            window_key = gap_start.strftime("%Y-%m-%d %H:%M")
            if window_key not in time_windows:
                time_windows[window_key] = []
            time_windows[window_key].append(gap)

        # Find windows with 3+ symbols (system-wide)
        system_wide = []
        for window_key, window_gaps in time_windows.items():
            if len(window_gaps) >= 3:
                symbols = [g["symbol"] for g in window_gaps]
                avg_gap = sum(g["gap_seconds"] for g in window_gaps) / len(window_gaps)
                system_wide.append(
                    {
                        "window": window_key,
                        "symbols": symbols,
                        "symbol_count": len(symbols),
                        "avg_gap_seconds": avg_gap,
                        "gaps": window_gaps,
                    }
                )

        return system_wide

    def _send_alert(self, alert_type: str, message: str, severity: str, metrics: Dict):
        """
        Send alert via Redis Pub/Sub (if Redis is available)

        :param alert_type: Type of alert
        :param message: Alert message
        :param severity: Alert severity (info, warning, error)
        :param metrics: Additional metrics
        """
        try:
            # Lazy initialization of alert publisher
            if self._alert_publisher is None:
                self._alert_publisher = AlertPublisher.get_instance()

            # Publish alert to Redis
            success = self._alert_publisher.publish_alert(
                alert_type=alert_type,
                message=message,
                severity=severity,
                metrics=metrics,
            )

            if not success:
                # Alert system not available - log warning
                if self._use_structured:
                    self.logger.log_event(
                        event_type="alert_send_failed",
                        message="Failed to send alert: Redis unavailable",
                        level="WARNING",
                    )
                else:
                    self.logger.warning("Failed to send alert: Redis unavailable")
        except Exception as e:
            # Alert system not available - log warning
            if self._use_structured:
                self.logger.log_event(
                    event_type="alert_send_failed",
                    message=f"Failed to send alert: {e}",
                    level="WARNING",
                )
            else:
                self.logger.warning(f"Failed to send alert: {e}")

    def _log_gaps(self, gaps: List[Dict], system_wide: List[Dict]):
        """
        Log detected gaps and send alerts

        :param gaps: List of detected gaps
        :param system_wide: List of system-wide gaps
        """
        # Log individual gaps
        for gap in gaps:
            self._gap_count += 1
            data_type = gap.get("data_type", "tick")

            # Build identifier based on data type
            if data_type == "tick" or data_type == "bar":
                identifier = gap.get("symbol", "unknown")
                if data_type == "bar" and "timeframe" in gap:
                    identifier = f"{identifier} ({gap['timeframe']})"
            elif data_type == "news":
                identifier = gap.get("symbol", "*")
            elif data_type == "economic":
                identifier = f"{gap.get('series_id', 'unknown')} ({gap.get('source', 'unknown')})"
            else:
                identifier = "unknown"

            if self._use_structured:
                self.logger.log_event(
                    event_type="data_gap_detected",
                    message=(
                        f"Data gap detected for {data_type} data ({identifier}): "
                        f"{gap['gap_seconds']/60:.1f} minutes"
                    ),
                    data_type=data_type,
                    identifier=identifier,
                    metrics={
                        "gap_seconds": gap["gap_seconds"],
                        "gap_start": (
                            gap["gap_start"].isoformat()
                            if isinstance(gap["gap_start"], datetime)
                            else str(gap["gap_start"])
                        ),
                        "gap_end": (
                            gap["gap_end"].isoformat()
                            if isinstance(gap["gap_end"], datetime)
                            else str(gap["gap_end"])
                        ),
                    },
                    level="WARNING",
                )
            else:
                self.logger.warning(
                    f"Data gap detected for {data_type} data ({identifier}): "
                    f"{gap['gap_seconds']/60:.1f} minutes "
                    f"({gap['gap_start']} to {gap['gap_end']})"
                )

            # Send alert for individual gap
            self._send_alert(
                alert_type="data_gap_detected",
                message=f"Data gap detected for {data_type} data ({identifier}): {gap['gap_seconds']/60:.1f} minutes",
                severity="warning",
                metrics={
                    "data_type": data_type,
                    "identifier": identifier,
                    "gap_seconds": gap["gap_seconds"],
                },
            )

        # Log system-wide gaps
        for sw_gap in system_wide:
            self._system_wide_gap_count += 1
            if self._use_structured:
                self.logger.log_event(
                    event_type="system_wide_gap",
                    message=(
                        f"System-wide gap detected: {sw_gap['symbol_count']} symbols "
                        f"affected, avg gap: {sw_gap['avg_gap_seconds']/60:.1f} minutes"
                    ),
                    metrics={
                        "symbol_count": sw_gap["symbol_count"],
                        "symbols": sw_gap["symbols"],
                        "avg_gap_seconds": sw_gap["avg_gap_seconds"],
                        "window": sw_gap["window"],
                    },
                    level="ERROR",
                )
            else:
                self.logger.error(
                    f"System-wide gap detected: {sw_gap['symbol_count']} symbols "
                    f"affected at {sw_gap['window']}, "
                    f"avg gap: {sw_gap['avg_gap_seconds']/60:.1f} minutes"
                )

            # Send alert for system-wide gap
            self._send_alert(
                alert_type="system_wide_gap",
                message=(
                    f"System-wide gap: {sw_gap['symbol_count']} symbols affected, "
                    f"avg gap: {sw_gap['avg_gap_seconds']/60:.1f} minutes"
                ),
                severity="error",
                metrics={
                    "symbol_count": sw_gap["symbol_count"],
                    "avg_gap_seconds": sw_gap["avg_gap_seconds"],
                },
            )

        # Check for prolonged gaps (>30 minutes)
        prolonged_gaps = [g for g in gaps if g["gap_seconds"] > 30 * 60]
        for gap in prolonged_gaps:
            self._send_alert(
                alert_type="prolonged_gap",
                message=(
                    f"Prolonged gap for {gap['symbol']}: "
                    f"{gap['gap_seconds']/60:.1f} minutes"
                ),
                severity="error",
                metrics={
                    "symbol": gap["symbol"],
                    "gap_seconds": gap["gap_seconds"],
                },
            )

    def get_status(self) -> Dict:
        """
        Get current gap detection status

        :return: Dictionary with current status
        """
        return {
            "enabled": self.enabled,
            "last_check_time": (
                self._last_check_time.isoformat() if self._last_check_time else None
            ),
            "gap_count": self._gap_count,
            "system_wide_gap_count": self._system_wide_gap_count,
            "gap_threshold_seconds": self.gap_threshold_seconds,
            "gap_threshold_minutes": self.gap_threshold_seconds / 60.0,
            "check_interval_seconds": self.check_interval_seconds,
        }


# Module-level singleton for global gap detector access
_global_gap_detector: Optional["GapDetector"] = None


def get_global_gap_detector() -> Optional["GapDetector"]:
    """
    Get the global GapDetector instance.

    :return: GapDetector instance or None if not set
    """
    return _global_gap_detector


def set_global_gap_detector(detector: "GapDetector") -> None:
    """
    Set the global GapDetector instance.

    :param detector: GapDetector instance to set as global
    """
    global _global_gap_detector
    _global_gap_detector = detector
