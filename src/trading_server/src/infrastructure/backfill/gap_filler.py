"""
Gap Filler Module

Fills data gaps using multiple strategies:
1. Re-query: Fetch missing data from source connectors
2. Interpolation: Interpolate missing values from surrounding data
3. Forward-fill: Use last known value
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum

from utils.logging_config import get_logger
from database import Database
from monitoring.gap_detector import GapDetector
from monitoring.metrics import (
    gap_fill_attempts_total,
    gap_fill_success_total,
    gap_fill_success_rate,
)


class FillStrategy(str, Enum):
    """Gap filling strategies"""

    RE_QUERY = "re_query"  # Fetch from source connector
    INTERPOLATE = "interpolate"  # Interpolate from surrounding data
    FORWARD_FILL = "forward_fill"  # Use last known value
    SKIP = "skip"  # Don't fill (mark as known gap)


class GapFiller:
    """
    Fills data gaps using multiple strategies
    """

    def __init__(
        self,
        database: Optional[Database] = None,
        gap_detector: Optional[GapDetector] = None,
    ):
        """
        Initialize gap filler

        :param database: Database instance (creates new if not provided)
        :param gap_detector: GapDetector instance (creates new if not provided)
        """
        self.db = database or Database()
        self.gap_detector = gap_detector or GapDetector()

        try:
            self.logger = get_logger("gap_filler", "gap_filler.log")
            self._use_structured = hasattr(self.logger, "log_event")
        except Exception:
            self.logger = logging.getLogger("gap_filler")
            self._use_structured = False

    def fill_gaps(
        self,
        data_type: str,
        gaps: List[Dict],
        strategy: FillStrategy = FillStrategy.RE_QUERY,
        connector: Optional[Any] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Fill data gaps using specified strategy

        :param data_type: Data type ("tick", "bar", "news", "economic")
        :param gaps: List of gap dictionaries from GapDetector
        :param strategy: Filling strategy to use
        :param connector: Optional connector instance for re-query strategy
        :param kwargs: Additional strategy-specific parameters
        :return: Dictionary with fill results
        """
        if not gaps:
            return {
                "filled": 0,
                "failed": 0,
                "skipped": 0,
            }

        results: Dict[str, int] = {"filled": 0, "failed": 0, "skipped": 0}

        for gap in gaps:
            try:
                if strategy == FillStrategy.RE_QUERY:
                    success = self._fill_by_re_query(data_type, gap, connector)
                elif strategy == FillStrategy.INTERPOLATE:
                    success = self._fill_by_interpolation(data_type, gap, **kwargs)
                elif strategy == FillStrategy.FORWARD_FILL:
                    success = self._fill_by_forward_fill(data_type, gap, **kwargs)
                elif strategy == FillStrategy.SKIP:
                    success = self._mark_gap(data_type, gap)
                else:
                    self.logger.warning(f"Unknown strategy: {strategy}")
                    results["skipped"] += 1
                    continue

                if success:
                    results["filled"] += 1
                else:
                    results["failed"] += 1

            except Exception as e:
                self.logger.error(f"Error filling gap: {e}", exc_info=True)
                results["failed"] += 1

        # Emit Prometheus metrics
        try:
            total_attempts = len(gaps)
            if total_attempts > 0:
                gap_fill_attempts_total.labels(
                    data_type=data_type, strategy=strategy.value
                ).inc(total_attempts)

                gap_fill_success_total.labels(
                    data_type=data_type, strategy=strategy.value
                ).inc(results["filled"])

                # Calculate success rate
                success_rate = (
                    results["filled"] / total_attempts if total_attempts > 0 else 0.0
                )
                gap_fill_success_rate.labels(
                    data_type=data_type, strategy=strategy.value
                ).set(success_rate)
        except Exception as metric_error:
            self.logger.warning(f"Failed to emit gap fill metrics: {metric_error}")

        if self._use_structured:
            self.logger.log_event(
                event_type="gap_fill_completed",
                message=f"Filled {results['filled']} gaps using {strategy.value}",
                metrics=results,
            )
        else:
            self.logger.info(
                f"Gap fill completed: {results['filled']} filled, "
                f"{results['failed']} failed, {results['skipped']} skipped"
            )

        return results

    def _fill_by_re_query(
        self, data_type: str, gap: Dict, connector: Optional[Any]
    ) -> bool:
        """
        Fill gap by re-querying from source connector

        :param data_type: Data type
        :param gap: Gap dictionary
        :param connector: Connector instance
        :return: True if successful
        """
        if not connector:
            self.logger.warning("No connector provided for re-query strategy")
            return False

        try:
            gap_start = gap["gap_start"]
            gap_end = gap["gap_end"]

            if isinstance(gap_start, str):
                gap_start = datetime.fromisoformat(gap_start.replace("Z", "+00:00"))
            if isinstance(gap_end, str):
                gap_end = datetime.fromisoformat(gap_end.replace("Z", "+00:00"))

            # Add small buffer to ensure we get data around the gap
            buffer = timedelta(seconds=60)
            query_start = gap_start - buffer
            query_end = gap_end + buffer

            # Query connector for data in gap range
            events = list(connector.backfill(query_start, query_end))

            if not events:
                self.logger.warning(
                    f"No data found from connector for gap {gap_start} to {gap_end}"
                )
                return False

            # Store events in database
            if data_type == "tick":
                return self._store_ticks(events)
            elif data_type == "bar":
                return self._store_bars(events)
            elif data_type == "news":
                return self._store_news(events)
            elif data_type == "economic":
                return self._store_economic(events)
            else:
                self.logger.warning(f"Unknown data type for storage: {data_type}")
                return False

        except Exception as e:
            self.logger.error(f"Error in re-query fill: {e}", exc_info=True)
            return False

    def _fill_by_interpolation(self, data_type: str, gap: Dict, **kwargs) -> bool:
        """
        Fill gap by interpolating from surrounding data

        :param data_type: Data type
        :param gap: Gap dictionary
        :param kwargs: Additional parameters
        :return: True if successful
        """
        # Interpolation is only suitable for numeric time series (ticks, bars)
        if data_type not in ["tick", "bar"]:
            self.logger.warning(f"Interpolation not suitable for {data_type} data type")
            return False

        try:
            gap_start = gap["gap_start"]
            gap_end = gap["gap_end"]

            if isinstance(gap_start, str):
                gap_start = datetime.fromisoformat(gap_start.replace("Z", "+00:00"))
            if isinstance(gap_end, str):
                gap_end = datetime.fromisoformat(gap_end.replace("Z", "+00:00"))

            # Get data before and after gap
            # lookback = timedelta(hours=1)  # Not used currently
            # lookahead = timedelta(hours=1)  # Not used currently

            if data_type == "tick":
                # For ticks, interpolation is complex - use forward-fill instead
                return self._fill_by_forward_fill(data_type, gap, **kwargs)
            elif data_type == "bar":
                # For bars, we can't interpolate - bars are discrete
                # Use forward-fill or re-query
                return False

            return False

        except Exception as e:
            self.logger.error(f"Error in interpolation fill: {e}", exc_info=True)
            return False

    def _fill_by_forward_fill(self, data_type: str, gap: Dict, **kwargs) -> bool:
        """
        Fill gap by forward-filling last known value

        :param data_type: Data type
        :param gap: Gap dictionary
        :param kwargs: Additional parameters
        :return: True if successful
        """
        # Forward-fill is only suitable for certain data types
        if data_type not in ["tick", "bar"]:
            self.logger.warning(f"Forward-fill not suitable for {data_type} data type")
            return False

        try:
            gap_start = gap["gap_start"]
            gap_end = gap["gap_end"]

            if isinstance(gap_start, str):
                gap_start = datetime.fromisoformat(gap_start.replace("Z", "+00:00"))
            if isinstance(gap_end, str):
                gap_end = datetime.fromisoformat(gap_end.replace("Z", "+00:00"))

            # Get last known value before gap
            if data_type == "tick":
                symbol = gap.get("symbol")
                if not symbol:
                    return False

                # Get last tick before gap
                query = """
                    SELECT datetime, bid, ask, volume
                    FROM ticks_forex tf
                    JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
                    WHERE fp.symbol = :symbol
                        AND tf.datetime < :gap_start
                    ORDER BY tf.datetime DESC
                    LIMIT 1
                """
                result = self.db.execute_with_result(
                    query, {"symbol": symbol, "gap_start": gap_start}
                )

                if not result:
                    self.logger.warning(f"No previous data found for {symbol}")
                    return False

                # last_tick = result[0]  # Not used currently
                # For ticks, forward-fill is not recommended (prices change)
                # This is a placeholder - in practice, re-query is better
                self.logger.warning(
                    "Forward-fill for ticks is not recommended. Use re-query instead."
                )
                return False

            elif data_type == "bar":
                # For bars, forward-fill doesn't make sense
                self.logger.warning("Forward-fill for bars is not suitable")
                return False

            return False

        except Exception as e:
            self.logger.error(f"Error in forward-fill: {e}", exc_info=True)
            return False

    def _mark_gap(self, data_type: str, gap: Dict) -> bool:
        """
        Mark gap as known (don't fill, just record)

        :param data_type: Data type
        :param gap: Gap dictionary
        :return: True if successful
        """
        # Store gap information in a gaps table (if it exists)
        # For now, just log it
        if self._use_structured:
            self.logger.log_event(
                event_type="gap_marked",
                message=f"Gap marked (not filled) for {data_type}",
                data_type=data_type,
                metrics=gap,
            )
        else:
            self.logger.info(f"Gap marked (not filled) for {data_type}: {gap}")

        return True

    def _store_ticks(self, events: List[Dict]) -> bool:
        """Store tick events in database"""
        try:
            tick_list = []
            for event in events:
                tick_list.append(
                    {
                        "symbol": event.get("symbol"),
                        "datetime": event.get("timestamp") or event.get("datetime"),
                        "bid": event.get("bid"),
                        "ask": event.get("ask"),
                        "volume": event.get("volume"),
                    }
                )

            if tick_list:
                inserted = self.db.insert_forex_ticks_batch(tick_list)
                return inserted > 0
            return False

        except Exception as e:
            self.logger.error(f"Error storing ticks: {e}", exc_info=True)
            return False

    def _store_bars(self, events: List[Dict]) -> bool:
        """Store bar events in database"""
        try:
            bar_list = []
            for event in events:
                bar_list.append(
                    {
                        "symbol": event.get("symbol"),
                        "datetime": event.get("timestamp") or event.get("datetime"),
                        "open": event.get("open"),
                        "high": event.get("high"),
                        "low": event.get("low"),
                        "close": event.get("close"),
                        "volume": event.get("volume"),
                        "timeframe": event.get("timeframe", "M1"),
                    }
                )

            if bar_list:
                inserted = self.db.insert_forex_bars_batch(bar_list)
                return inserted > 0
            return False

        except Exception as e:
            self.logger.error(f"Error storing bars: {e}", exc_info=True)
            return False

    def _store_news(self, events: List[Dict]) -> bool:
        """Store news events in database"""
        try:
            article_list = []
            for event in events:
                article_list.append(
                    {
                        "timestamp": event.get("timestamp") or event.get("datetime"),
                        "source": event.get("source"),
                        "title": event.get("title"),
                        "content": event.get("content"),
                        "url": event.get("url"),
                        "symbol": event.get("symbol"),
                        "sentiment_score": event.get("sentiment_score"),
                        "sentiment_label": event.get("sentiment_label"),
                        "entities": event.get("entities"),
                    }
                )

            if article_list:
                inserted = self.db.insert_news_articles_batch(article_list)
                return inserted > 0
            return False

        except Exception as e:
            self.logger.error(f"Error storing news: {e}", exc_info=True)
            return False

    def _store_economic(self, events: List[Dict]) -> bool:
        """Store economic indicator events in database"""
        try:
            indicator_list = []
            for event in events:
                indicator_list.append(
                    {
                        "timestamp": event.get("timestamp") or event.get("datetime"),
                        "series_id": event.get("series_id"),
                        "value": event.get("value"),
                        "source": event.get("source"),
                        "country": event.get("country"),
                        "frequency": event.get("frequency"),
                    }
                )

            if indicator_list:
                inserted = self.db.insert_economic_indicators_batch(indicator_list)
                return inserted > 0
            return False

        except Exception as e:
            self.logger.error(f"Error storing economic indicators: {e}", exc_info=True)
            return False

    def fill_all_gaps(
        self,
        data_type: str,
        strategy: FillStrategy = FillStrategy.RE_QUERY,
        connector: Optional[Any] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Detect and fill all gaps for a data type

        :param data_type: Data type ("tick", "bar", "news", "economic")
        :param strategy: Filling strategy
        :param connector: Optional connector for re-query
        :param kwargs: Additional parameters
        :return: Fill results
        """
        # Detect gaps
        if data_type == "tick":
            gaps = self.gap_detector.detect_gaps()
        elif data_type == "bar":
            gaps = self.gap_detector.detect_bar_gaps()
        elif data_type == "news":
            gaps = self.gap_detector.detect_news_gaps()
        elif data_type == "economic":
            gaps = self.gap_detector.detect_economic_gaps()
        else:
            self.logger.error(f"Unknown data type: {data_type}")
            return {"filled": 0, "failed": 0, "skipped": 0}

        # Fill gaps
        return self.fill_gaps(data_type, gaps, strategy, connector, **kwargs)
