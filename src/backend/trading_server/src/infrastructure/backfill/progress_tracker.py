"""
Backfill progress tracker for historical data collection
Tracks progress per connector, symbol, and time range to enable resume capability
"""

from typing import Dict, Optional, List
from datetime import datetime
from sqlalchemy import text
from database import Database
from utils.logging_config import get_logger
from monitoring.metrics import (
    data_collection_backfill_progress,
    data_collection_backfill_records,
    backfill_progress_percent,
    backfill_records_processed_total,
)


class BackfillProgressTracker:
    """
    Tracks backfill progress in database to enable resuming failed backfills
    """

    def __init__(self, db: Optional[Database] = None):
        """
        Initialize progress tracker

        :param db: Database instance (creates new one if not provided)
        """
        self.db = db if db is not None else Database()
        self.logger = get_logger(
            "backfill_progress_tracker", "backfill_progress_tracker.log"
        )

    def start_backfill(
        self,
        connector_type: str,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """
        Create a new backfill progress record

        :param connector_type: Type of connector (e.g., 'mt5_tick')
        :param symbol: Trading symbol
        :param start_time: Start time of backfill range
        :param end_time: End time of backfill range
        :return: Progress record ID
        """
        try:
            query = text("""
                INSERT INTO backfill_progress
                (connector_type, symbol, start_time, end_time, status)
                VALUES (:connector_type, :symbol, :start_time, :end_time, 'pending')
                RETURNING id
            """)

            params = {
                "connector_type": connector_type,
                "symbol": symbol,
                "start_time": start_time,
                "end_time": end_time,
            }

            result = self.db.execute_with_result(query, params)
            progress_id = result[0][0] if result else None

            if progress_id:
                self.logger.info(
                    f"Started backfill tracking: {connector_type}/{symbol} "
                    f"from {start_time} to {end_time} (id={progress_id})"
                )
                return progress_id
            else:
                raise ValueError("Failed to create backfill progress record")

        except Exception as e:
            self.logger.error(f"Error starting backfill: {e}", exc_info=True)
            raise

    def update_progress(
        self,
        progress_id: int,
        last_successful_time: datetime,
        records_collected: int,
    ) -> None:
        """
        Update progress for a backfill operation

        :param progress_id: Progress record ID
        :param last_successful_time: Last successfully processed timestamp
        :param records_collected: Total number of records collected so far
        """
        try:
            # Get progress record to retrieve connector_type, symbol, start_time, end_time
            get_query = text("""
                SELECT connector_type, symbol, start_time, end_time, records_collected
                FROM backfill_progress
                WHERE id = :progress_id
            """)
            get_result = self.db.execute_with_result(
                get_query, {"progress_id": progress_id}
            )

            if not get_result or len(get_result) == 0:
                self.logger.warning(f"Progress record {progress_id} not found")
                return

            row = get_result[0]
            connector_type = row[0]
            symbol = row[1]
            start_time = row[2]
            end_time = row[3]
            previous_records_collected = row[4] or 0

            # Calculate progress percentage
            if start_time and end_time and last_successful_time:
                total_duration = (end_time - start_time).total_seconds()
                elapsed_duration = (last_successful_time - start_time).total_seconds()
                if total_duration > 0:
                    progress_pct = min(
                        100.0, max(0.0, (elapsed_duration / total_duration) * 100.0)
                    )
                else:
                    progress_pct = 0.0
            else:
                progress_pct = 0.0

            # Update database
            query = text("""
                UPDATE backfill_progress
                SET last_successful_time = :last_successful_time,
                    records_collected = :records_collected,
                    status = 'in_progress',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :progress_id
            """)

            params = {
                "progress_id": progress_id,
                "last_successful_time": last_successful_time,
                "records_collected": records_collected,
            }

            self.db.execute_with_result(query, params)

            # Emit Prometheus metrics
            try:
                data_collection_backfill_progress.labels(
                    connector_type=connector_type, symbol=symbol
                ).set(progress_pct)

                data_collection_backfill_records.labels(
                    connector_type=connector_type, symbol=symbol
                ).set(records_collected)

                backfill_progress_percent.labels(
                    symbol=symbol, data_type=connector_type
                ).set(progress_pct)

                # Increment counter for new records processed
                records_increment = records_collected - previous_records_collected
                if records_increment > 0:
                    backfill_records_processed_total.labels(
                        symbol=symbol, data_type=connector_type
                    ).inc(records_increment)
            except Exception as metric_error:
                self.logger.warning(f"Failed to emit metrics: {metric_error}")

            self.logger.debug(
                f"Updated progress {progress_id}: {records_collected} records, "
                f"last_time={last_successful_time}, progress={progress_pct:.2f}%"
            )

        except Exception as e:
            self.logger.error(f"Error updating progress: {e}", exc_info=True)
            raise

    def get_progress(
        self,
        connector_type: str,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[Dict]:
        """
        Get existing progress record

        :param connector_type: Type of connector
        :param symbol: Trading symbol
        :param start_time: Start time of backfill range
        :param end_time: End time of backfill range
        :return: Progress record dictionary or None if not found
        """
        try:
            query = text("""
                SELECT id, connector_type, symbol, start_time, end_time,
                       last_successful_time, records_collected, status, error_message,
                       created_at, updated_at
                FROM backfill_progress
                WHERE connector_type = :connector_type
                  AND symbol = :symbol
                  AND start_time = :start_time
                  AND end_time = :end_time
                ORDER BY created_at DESC
                LIMIT 1
            """)

            params = {
                "connector_type": connector_type,
                "symbol": symbol,
                "start_time": start_time,
                "end_time": end_time,
            }

            result = self.db.execute_with_result(query, params)

            if result and len(result) > 0:
                row = result[0]
                return {
                    "id": row[0],
                    "connector_type": row[1],
                    "symbol": row[2],
                    "start_time": row[3],
                    "end_time": row[4],
                    "last_successful_time": row[5],
                    "records_collected": row[6],
                    "status": row[7],
                    "error_message": row[8],
                    "created_at": row[9],
                    "updated_at": row[10],
                }
            return None

        except Exception as e:
            self.logger.error(f"Error getting progress: {e}", exc_info=True)
            return None

    def mark_completed(self, progress_id: int) -> None:
        """
        Mark backfill as completed

        :param progress_id: Progress record ID
        """
        try:
            # Get progress record to retrieve connector_type and symbol
            get_query = text("""
                SELECT connector_type, symbol
                FROM backfill_progress
                WHERE id = :progress_id
            """)
            get_result = self.db.execute_with_result(
                get_query, {"progress_id": progress_id}
            )

            query = text("""
                UPDATE backfill_progress
                SET status = 'completed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :progress_id
            """)

            params = {"progress_id": progress_id}

            self.db.execute_with_result(query, params)

            # Emit metrics - set progress to 100%
            if get_result and len(get_result) > 0:
                row = get_result[0]
                connector_type = row[0]
                symbol = row[1]
                try:
                    data_collection_backfill_progress.labels(
                        connector_type=connector_type, symbol=symbol
                    ).set(100.0)
                    backfill_progress_percent.labels(
                        symbol=symbol, data_type=connector_type
                    ).set(100.0)
                except Exception as metric_error:
                    self.logger.warning(
                        f"Failed to emit completion metrics: {metric_error}"
                    )

            self.logger.info(f"Marked backfill {progress_id} as completed")

        except Exception as e:
            self.logger.error(f"Error marking completed: {e}", exc_info=True)
            raise

    def mark_failed(self, progress_id: int, error_message: str) -> None:
        """
        Mark backfill as failed

        :param progress_id: Progress record ID
        :param error_message: Error message describing the failure
        """
        try:
            query = text("""
                UPDATE backfill_progress
                SET status = 'failed',
                    error_message = :error_message,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :progress_id
            """)

            params = {
                "progress_id": progress_id,
                "error_message": error_message[:1000],  # Limit message length
            }

            self.db.execute_with_result(query, params)
            self.logger.warning(
                f"Marked backfill {progress_id} as failed: {error_message}"
            )

        except Exception as e:
            self.logger.error(f"Error marking failed: {e}", exc_info=True)
            raise

    def get_resume_point(self, progress_id: int) -> Optional[datetime]:
        """
        Get timestamp to resume from for a failed backfill

        :param progress_id: Progress record ID
        :return: Timestamp to resume from, or None if cannot resume
        """
        try:
            query = text("""
                SELECT last_successful_time, status
                FROM backfill_progress
                WHERE id = :progress_id
            """)

            params = {"progress_id": progress_id}

            result = self.db.execute_with_result(query, params)

            if result and len(result) > 0:
                row = result[0]
                last_successful_time = row[0]
                status = row[1]

                # Only resume if status is 'failed' or 'in_progress' and we have a resume point
                if status in ("failed", "in_progress") and last_successful_time:
                    return last_successful_time

            return None

        except Exception as e:
            self.logger.error(f"Error getting resume point: {e}", exc_info=True)
            return None

    def get_failed_backfills(self, connector_type: Optional[str] = None) -> List[Dict]:
        """
        Get all failed backfills (for resuming)

        :param connector_type: Optional filter by connector type
        :return: List of failed backfill records
        """
        try:
            if connector_type:
                query = text("""
                    SELECT id, connector_type, symbol, start_time, end_time,
                           last_successful_time, records_collected, error_message
                    FROM backfill_progress
                    WHERE status = 'failed'
                      AND connector_type = :connector_type
                    ORDER BY created_at DESC
                """)
                params = {"connector_type": connector_type}
            else:
                query = text("""
                    SELECT id, connector_type, symbol, start_time, end_time,
                           last_successful_time, records_collected, error_message
                    FROM backfill_progress
                    WHERE status = 'failed'
                    ORDER BY created_at DESC
                """)
                params = {}

            result = self.db.execute_with_result(query, params)

            backfills = []
            for row in result:
                backfills.append(
                    {
                        "id": row[0],
                        "connector_type": row[1],
                        "symbol": row[2],
                        "start_time": row[3],
                        "end_time": row[4],
                        "last_successful_time": row[5],
                        "records_collected": row[6],
                        "error_message": row[7],
                    }
                )

            return backfills

        except Exception as e:
            self.logger.error(f"Error getting failed backfills: {e}", exc_info=True)
            return []
