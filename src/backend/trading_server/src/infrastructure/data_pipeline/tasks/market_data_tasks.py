"""
Market Data Collection Tasks
MT5 data collection Celery tasks
"""

from datetime import datetime, timedelta
from typing import Optional
from infrastructure.data_pipeline.celery_app import celery_app
import logging
import time

from ....connectors.mt5_tick_connector import MT5TickConnector
from ....connectors.base import ConnectorConfig
from ....database import Database
from ....data.quality_gates import QualityGate

logger = logging.getLogger(__name__)

# Import metrics if available
try:
    from monitoring.metrics import (
        data_collection_tasks_total,
        data_collection_records_collected,
        data_collection_duration_seconds,
        data_collection_errors_total,
        data_collection_last_success_time,
    )

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("Prometheus metrics not available")


@celery_app.task(bind=True, max_retries=3)
def collect_mt5_data(
    self,
    symbol: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
):
    """
    Collect MT5 market data using MT5TickConnector

    :param symbol: Currency pair symbol
    :param start_time: Start time for data collection (defaults to 1 hour ago)
    :param end_time: End time for data collection (defaults to now)
    :return: Collection result
    """
    start_timestamp = time.time()
    try:
        # Set default time range if not provided
        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            start_time = end_time - timedelta(hours=1)

        logger.info(f"Collecting MT5 data for {symbol} from {start_time} to {end_time}")

        # Record task start
        if METRICS_AVAILABLE:
            data_collection_tasks_total.labels(
                task_type="mt5", source="mt5", status="started"
            ).inc()

        # Initialize database
        db = Database()

        # Initialize quality gate
        quality_gate = QualityGate()

        # Create connector config
        config = ConnectorConfig(
            source="mt5",
            symbol=symbol,
            extra_config={
                "digits": 5,  # Default digits for forex
                "auto_reconnect": False,  # Not needed for backfill
            },
        )

        # Create a minimal socket-like object for connector initialization
        # The backfill method doesn't actually use the socket
        class DummySocket:
            pass

        dummy_socket = DummySocket()

        # Create connector instance
        connector = MT5TickConnector(
            socket=dummy_socket,
            symbol=symbol,
            config=config,
            streamer=None,
        )

        # Use backfill method to collect historical data
        records_collected = 0
        batch = []
        batch_size = 1000

        try:
            for tick_event in connector.backfill(
                start_time=start_time, end_time=end_time, batch_size=batch_size
            ):
                # Validate data through quality gate
                is_valid, error_msg = quality_gate.validate_tick(
                    symbol=tick_event.get("symbol", symbol),
                    tick_datetime=tick_event.get("timestamp")
                    or tick_event.get("datetime"),
                    bid=tick_event.get("bid", 0.0),
                    ask=tick_event.get("ask", 0.0),
                    volume=tick_event.get("volume"),
                )

                if is_valid:
                    # Prepare tick data for batch insert
                    batch.append(
                        {
                            "symbol": tick_event.get("symbol", symbol),
                            "datetime": tick_event.get("timestamp")
                            or tick_event.get("datetime"),
                            "bid": tick_event.get("bid", 0.0),
                            "ask": tick_event.get("ask", 0.0),
                            "volume": tick_event.get("volume"),
                            "receive_time": tick_event.get("receive_time"),
                        }
                    )

                    # Insert in batches for efficiency
                    if len(batch) >= batch_size:
                        try:
                            db.insert_forex_ticks_batch(batch)
                            records_collected += len(batch)
                            batch = []
                        except Exception as e:
                            logger.warning(f"Error inserting batch: {e}")
                            batch = []
                else:
                    logger.warning(f"Tick validation failed: {error_msg}")

            # Insert remaining batch
            if batch:
                try:
                    db.insert_forex_ticks_batch(batch)
                    records_collected += len(batch)
                except Exception as e:
                    logger.warning(f"Error inserting final batch: {e}")

        except Exception as e:
            logger.error(f"Error during MT5 data collection: {e}", exc_info=True)
            raise

        finally:
            # Clean up connector
            try:
                connector.disconnect()
            except Exception:
                pass

        logger.info(f"Collected {records_collected} MT5 ticks for {symbol}")

        # Record metrics
        if METRICS_AVAILABLE:
            duration = time.time() - start_timestamp
            data_collection_tasks_total.labels(
                task_type="mt5", source="mt5", status="success"
            ).inc()
            data_collection_records_collected.labels(
                task_type="tick", source="mt5"
            ).inc(records_collected)
            data_collection_duration_seconds.labels(
                task_type="mt5", source="mt5"
            ).observe(duration)
            data_collection_last_success_time.labels(task_type="mt5", source="mt5").set(
                time.time()
            )

        return {
            "status": "success",
            "symbol": symbol,
            "records_collected": records_collected,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }

    except Exception as exc:
        logger.error(f"MT5 data collection failed for {symbol}: {exc}", exc_info=True)

        # Record error metrics
        if METRICS_AVAILABLE:
            error_type = "connection" if "connection" in str(exc).lower() else "other"
            data_collection_tasks_total.labels(
                task_type="mt5", source="mt5", status="failed"
            ).inc()
            data_collection_errors_total.labels(
                task_type="mt5", source="mt5", error_type=error_type
            ).inc()

        raise self.retry(exc=exc, countdown=60)  # Retry after 60 seconds


@celery_app.task(bind=True, max_retries=3)
def collect_mt5_data_batch(self, symbols: list[str]):
    """
    Collect MT5 data for multiple symbols

    :param symbols: List of currency pair symbols
    :return: Collection results
    """
    results = []
    for symbol in symbols:
        try:
            result = collect_mt5_data.delay(symbol)
            results.append({"symbol": symbol, "task_id": result.id})
        except Exception as e:
            logger.error(f"Failed to queue MT5 data collection for {symbol}: {e}")
            results.append({"symbol": symbol, "error": str(e)})
    return results
