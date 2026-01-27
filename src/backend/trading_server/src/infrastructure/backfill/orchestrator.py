"""
Backfill Orchestrator
Coordinates parallel backfills across multiple symbols with error handling
"""

from typing import List, Dict, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.logging_config import get_logger
from infrastructure.backfill.progress_tracker import BackfillProgressTracker
from connectors.mt5_tick_connector import MT5TickConnector
from connectors.base import ConnectorConfig


class BackfillOrchestrator:
    """
    Orchestrates backfill operations across multiple symbols
    Supports parallel execution with connection limits
    """

    def __init__(
        self,
        max_parallel: int = 5,
        progress_tracker: Optional[BackfillProgressTracker] = None,
    ):
        """
        Initialize orchestrator

        :param max_parallel: Maximum number of parallel backfills
        :param progress_tracker: Progress tracker instance (creates new if not provided)
        """
        self.max_parallel = max_parallel
        self.progress_tracker = (
            progress_tracker if progress_tracker else BackfillProgressTracker()
        )
        self.logger = get_logger("backfill_orchestrator", "backfill_orchestrator.log")

    def backfill_symbols(
        self,
        symbols: List[str],
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Dict]:
        """
        Backfill multiple symbols in parallel

        :param symbols: List of trading symbols
        :param start_time: Start time
        :param end_time: End time
        :return: Dictionary mapping symbol to result status
        """
        self.logger.info(
            f"Starting parallel backfill for {len(symbols)} symbols: {symbols}"
        )

        results = {}

        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            # Submit all backfill tasks
            future_to_symbol = {}
            for symbol in symbols:
                future = executor.submit(
                    self._backfill_single_symbol, symbol, start_time, end_time
                )
                future_to_symbol[future] = symbol

            # Collect results
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result()
                    results[symbol] = result
                    self.logger.info(f"Backfill completed for {symbol}: {result}")
                except Exception as e:
                    results[symbol] = {"status": "failed", "error": str(e)}
                    self.logger.error(
                        f"Backfill failed for {symbol}: {e}", exc_info=True
                    )

        return results

    def _backfill_single_symbol(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict:
        """
        Backfill a single symbol (internal method)

        :param symbol: Trading symbol
        :param start_time: Start time
        :param end_time: End time
        :return: Result dictionary
        """
        # Create progress record
        progress_id = self.progress_tracker.start_backfill(
            "mt5_tick", symbol, start_time, end_time
        )

        try:
            # Create connector
            class DummySocket:
                pass

            config = ConnectorConfig(
                source="mt5",
                symbol=symbol,
                extra_config={"digits": 5},
            )
            connector = MT5TickConnector(
                socket=DummySocket(),
                symbol=symbol,
                config=config,
            )

            # Backfill ticks
            records_collected = 0
            last_successful_time = start_time

            for normalized_tick in connector.backfill(start_time, end_time):
                # Update progress periodically
                records_collected += 1
                timestamp = normalized_tick.get("timestamp")
                if timestamp:
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        )
                    last_successful_time = timestamp

                # Update progress every 1000 records
                if records_collected % 1000 == 0:
                    self.progress_tracker.update_progress(
                        progress_id, last_successful_time, records_collected
                    )

            # Mark as completed
            self.progress_tracker.mark_completed(progress_id)

            return {
                "status": "completed",
                "records_collected": records_collected,
            }

        except Exception as e:
            self.progress_tracker.mark_failed(progress_id, str(e))
            raise

    def backfill_with_aggregation(
        self,
        symbols: List[str],
        start_time: datetime,
        end_time: datetime,
        timeframes: List[str],
    ) -> Dict[str, Dict]:
        """
        Backfill ticks and aggregate to OHLCV for multiple symbols

        :param symbols: List of trading symbols
        :param start_time: Start time
        :param end_time: End time
        :param timeframes: List of timeframes to generate
        :return: Dictionary mapping symbol to result status
        """
        # First backfill ticks
        tick_results = self.backfill_symbols(symbols, start_time, end_time)

        # Then aggregate OHLCV (can be done in parallel)
        # TODO: Implement OHLCV aggregation
        # For now, return tick results
        return tick_results

    def get_backfill_status(self, symbol: str) -> Optional[Dict]:
        """
        Get current backfill status for a symbol

        :param symbol: Trading symbol
        :return: Status dictionary or None if not found
        """
        # Get latest progress record for symbol
        # This would need to be implemented with proper database query
        # For now, return None
        return None

    def resume_failed_backfills(self, connector_type: str = "mt5_tick") -> List[Dict]:
        """
        Resume any failed backfills

        :param connector_type: Connector type to resume
        :return: List of resumed backfill results
        """
        failed_backfills = self.progress_tracker.get_failed_backfills(connector_type)

        if not failed_backfills:
            self.logger.info("No failed backfills to resume")
            return []

        self.logger.info(f"Resuming {len(failed_backfills)} failed backfills")

        results = []
        for backfill in failed_backfills:
            symbol = backfill["symbol"]
            end_time = backfill["end_time"]
            progress_id = backfill["id"]

            try:
                # Get resume point
                resume_point = self.progress_tracker.get_resume_point(progress_id)
                if not resume_point:
                    self.logger.warning(
                        f"Cannot resume {symbol}: no resume point available"
                    )
                    continue

                # Resume from checkpoint
                result = self._backfill_single_symbol(symbol, resume_point, end_time)
                results.append({"symbol": symbol, "result": result})

            except Exception as e:
                self.logger.error(
                    f"Failed to resume backfill for {symbol}: {e}", exc_info=True
                )
                results.append(
                    {"symbol": symbol, "result": {"status": "failed", "error": str(e)}}
                )

        return results
