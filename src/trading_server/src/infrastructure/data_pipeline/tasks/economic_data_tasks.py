"""
Economic Data Collection Tasks
Economic indicator collection Celery tasks for Phase 3
"""

from datetime import datetime, timedelta
from infrastructure.data_pipeline.celery_app import celery_app
import logging

from ....connectors.fred_connector import FREDConnector
from ....connectors.world_bank_connector import WorldBankConnector
from ....connectors.ecb_connector import ECBConnector
from ....connectors.base import ConnectorConfig
from ....database import Database

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def collect_fred_indicators(self):
    """
    Collect FRED economic indicators

    :return: Collection result
    """
    try:
        logger.info("Collecting FRED economic indicators")

        # Initialize database
        db = Database()

        # Create FRED connector
        config = ConnectorConfig(
            source="FRED", symbol="US", extra_config={}
        )  # US indicators
        connector = FREDConnector(config)

        if not connector.connect():
            logger.warning("FRED connector not available (check FRED_API_KEY)")
            return {"status": "skipped", "reason": "Connector not available"}

        # Stream latest indicators
        start_time = datetime.now() - timedelta(days=1)
        indicators_collected = 0

        for indicator in connector.stream(start_time=start_time):
            try:
                # Insert indicator to database
                success = db.insert_economic_indicator(
                    series_id=indicator["series_id"],
                    timestamp=indicator["timestamp"],
                    value=indicator["value"],
                    source=indicator["source"],
                    country=indicator.get("country"),
                    frequency=indicator.get("frequency"),
                    receive_time=indicator.get("receive_time"),
                )
                if success:
                    indicators_collected += 1
            except Exception as e:
                logger.warning(f"Error inserting indicator: {e}")
                continue

        connector.disconnect()

        logger.info(f"Collected {indicators_collected} FRED indicators")
        return {"status": "success", "indicators_collected": indicators_collected}

    except Exception as exc:
        logger.error(f"FRED indicator collection failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def collect_world_bank_indicators(self):
    """
    Collect World Bank economic indicators

    :return: Collection result
    """
    try:
        logger.info("Collecting World Bank economic indicators")

        # Initialize database
        db = Database()

        # Create World Bank connector
        config = ConnectorConfig(
            source="WORLD_BANK", symbol="*", extra_config={}
        )  # Global indicators
        connector = WorldBankConnector(config)

        if not connector.connect():
            logger.warning("World Bank connector not available")
            return {"status": "skipped", "reason": "Connector not available"}

        # Stream latest indicators (monthly updates, so check last month)
        start_time = datetime.now() - timedelta(days=30)
        indicators_collected = 0

        for indicator in connector.stream(start_time=start_time):
            try:
                # Insert indicator to database
                success = db.insert_economic_indicator(
                    series_id=indicator["series_id"],
                    timestamp=indicator["timestamp"],
                    value=indicator["value"],
                    source=indicator["source"],
                    country=indicator.get("country"),
                    frequency=indicator.get("frequency"),
                    receive_time=indicator.get("receive_time"),
                )
                if success:
                    indicators_collected += 1
            except Exception as e:
                logger.warning(f"Error inserting indicator: {e}")
                continue

        connector.disconnect()

        logger.info(f"Collected {indicators_collected} World Bank indicators")
        return {"status": "success", "indicators_collected": indicators_collected}

    except Exception as exc:
        logger.error(f"World Bank indicator collection failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def collect_ecb_indicators(self):
    """
    Collect ECB economic indicators

    :return: Collection result
    """
    try:
        logger.info("Collecting ECB economic indicators")

        # Initialize database
        db = Database()

        # Create ECB connector
        config = ConnectorConfig(
            source="ECB", symbol="EU", extra_config={}
        )  # Eurozone indicators
        connector = ECBConnector(config)

        if not connector.connect():
            logger.warning("ECB connector not available")
            return {"status": "skipped", "reason": "Connector not available"}

        # Stream latest indicators
        start_time = datetime.now() - timedelta(days=3)
        indicators_collected = 0

        for indicator in connector.stream(start_time=start_time):
            try:
                # Insert indicator to database
                success = db.insert_economic_indicator(
                    series_id=indicator["series_id"],
                    timestamp=indicator["timestamp"],
                    value=indicator["value"],
                    source=indicator["source"],
                    country=indicator.get("country"),
                    frequency=indicator.get("frequency"),
                    receive_time=indicator.get("receive_time"),
                )
                if success:
                    indicators_collected += 1
            except Exception as e:
                logger.warning(f"Error inserting indicator: {e}")
                continue

        connector.disconnect()

        logger.info(f"Collected {indicators_collected} ECB indicators")
        return {"status": "success", "indicators_collected": indicators_collected}

    except Exception as exc:
        logger.error(f"ECB indicator collection failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)
