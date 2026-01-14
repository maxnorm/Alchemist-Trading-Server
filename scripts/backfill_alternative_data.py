#!/usr/bin/env python3
"""
Alternative Data Backfill Script
Backfills news and economic indicator data from various sources
"""

import argparse
import sys
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List

# Add src/trading_server/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "trading_server", "src"))

from database import Database
from connectors.rss_feed_connector import RSSFeedConnector
from connectors.web_scraping_connector import WebScrapingConnector
from connectors.fred_connector import FREDConnector
from connectors.world_bank_connector import WorldBankConnector
from connectors.ecb_connector import ECBConnector
from connectors.base import ConnectorConfig
from infrastructure.backfill.progress_tracker import BackfillProgressTracker
from utils.logging_config import get_logger


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Backfill alternative data (news, economic indicators)")
    parser.add_argument(
        "--source",
        type=str,
        required=True,
        choices=["news", "economic", "all"],
        help="Data source to backfill: news, economic, or all",
    )
    parser.add_argument(
        "--start-time",
        type=str,
        required=True,
        help="Start time (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        required=True,
        help="End time (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last successful checkpoint",
    )
    parser.add_argument(
        "--connector",
        type=str,
        choices=["rss", "web_scraping", "fred", "world_bank", "ecb", "all"],
        default="all",
        help="Specific connector to use (default: all)",
    )
    return parser.parse_args()


def parse_datetime(dt_str: str) -> datetime:
    """Parse datetime string to datetime object"""
    try:
        # Try ISO format first
        if "T" in dt_str:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        else:
            # Date only - assume start of day UTC
            return datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise ValueError(f"Invalid datetime format: {dt_str}. Use YYYY-MM-DD or ISO format.") from e


def backfill_news(
    connector_type: str,
    start_time: datetime,
    end_time: datetime,
    progress_tracker: BackfillProgressTracker,
    progress_id: int,
    db: Database,
) -> int:
    """
    Backfill news data from specified connector
    
    :param connector_type: Type of connector (rss, web_scraping)
    :param start_time: Start time
    :param end_time: End time
    :param progress_tracker: Progress tracker
    :param progress_id: Progress record ID
    :param db: Database instance
    :return: Number of articles collected
    """
    logger = get_logger("backfill_alternative_data", "backfill_alternative_data.log")
    logger.info(f"Starting news backfill from {connector_type} from {start_time} to {end_time}")

    articles_collected = 0
    last_successful_time = start_time
    batch_size = 100

    article_batch = []

    try:
        # Create connector
        if connector_type == "rss":
            config = ConnectorConfig(
                source="rss",
                symbol="*",
                extra_config={}
            )
            connector = RSSFeedConnector(config)
        elif connector_type == "web_scraping":
            config = ConnectorConfig(
                source="web_scraping",
                symbol="*",
                extra_config={
                    "websites": ["tradingeconomics", "investing", "forexfactory"],
                }
            )
            connector = WebScrapingConnector(config)
        else:
            raise ValueError(f"Unknown news connector type: {connector_type}")

        if not connector.connect():
            raise ConnectionError(f"Failed to connect to {connector_type} connector")

        # Backfill news
        for article in connector.backfill(start_time, end_time):
            # Store article
            timestamp = article.get("timestamp") or article.get("datetime")
            if not timestamp:
                continue

            # Convert timestamp to datetime if needed
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

            # Add to batch
            article_batch.append({
                "timestamp": timestamp,
                "source": article.get("source", connector_type),
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "content": article.get("content"),
                "symbol": article.get("symbol"),
                "sentiment_score": article.get("sentiment_score"),
                "sentiment_label": article.get("sentiment_label"),
                "entities": article.get("entities"),
                "receive_time": article.get("receive_time"),
            })

            # Store batch when it reaches size
            if len(article_batch) >= batch_size:
                inserted = db.insert_news_articles_batch(article_batch)
                articles_collected += inserted
                article_batch = []

                # Update progress
                last_successful_time = timestamp
                progress_tracker.update_progress(
                    progress_id, last_successful_time, articles_collected
                )

                logger.debug(f"Collected {articles_collected} articles so far...")

        # Store remaining articles
        if article_batch:
            inserted = db.insert_news_articles_batch(article_batch)
            articles_collected += inserted
            if article_batch:
                last_successful_time = article_batch[-1]["timestamp"]
            progress_tracker.update_progress(
                progress_id, last_successful_time, articles_collected
            )

        connector.disconnect()
        logger.info(f"News backfill completed: {articles_collected} articles collected")
        return articles_collected

    except Exception as e:
        logger.error(f"Error during news backfill: {e}", exc_info=True)
        progress_tracker.mark_failed(progress_id, str(e))
        raise


def backfill_economic(
    connector_type: str,
    start_time: datetime,
    end_time: datetime,
    progress_tracker: BackfillProgressTracker,
    progress_id: int,
    db: Database,
) -> int:
    """
    Backfill economic indicator data from specified connector
    
    :param connector_type: Type of connector (fred, world_bank, ecb)
    :param start_time: Start time
    :param end_time: End time
    :param progress_tracker: Progress tracker
    :param progress_id: Progress record ID
    :param db: Database instance
    :return: Number of indicators collected
    """
    logger = get_logger("backfill_alternative_data", "backfill_alternative_data.log")
    logger.info(f"Starting economic backfill from {connector_type} from {start_time} to {end_time}")

    indicators_collected = 0
    last_successful_time = start_time
    batch_size = 100

    indicator_batch = []

    try:
        # Create connector
        if connector_type == "fred":
            config = ConnectorConfig(
                source="FRED",
                symbol="US",
                extra_config={}
            )
            connector = FREDConnector(config)
        elif connector_type == "world_bank":
            config = ConnectorConfig(
                source="WORLD_BANK",
                symbol="*",
                extra_config={}
            )
            connector = WorldBankConnector(config)
        elif connector_type == "ecb":
            config = ConnectorConfig(
                source="ECB",
                symbol="EU",
                extra_config={}
            )
            connector = ECBConnector(config)
        else:
            raise ValueError(f"Unknown economic connector type: {connector_type}")

        if not connector.connect():
            logger.warning(f"{connector_type} connector not available (may need API keys)")
            return 0

        # Backfill indicators
        for indicator in connector.backfill(start_time, end_time):
            # Store indicator
            timestamp = indicator.get("timestamp") or indicator.get("datetime")
            if not timestamp:
                continue

            # Convert timestamp to datetime if needed
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

            # Add to batch
            indicator_batch.append({
                "timestamp": timestamp,
                "series_id": indicator.get("series_id", ""),
                "value": indicator.get("value"),
                "source": indicator.get("source", connector_type),
                "country": indicator.get("country"),
                "frequency": indicator.get("frequency"),
                "receive_time": indicator.get("receive_time"),
            })

            # Store batch when it reaches size
            if len(indicator_batch) >= batch_size:
                inserted = db.insert_economic_indicators_batch(indicator_batch)
                indicators_collected += inserted
                indicator_batch = []

                # Update progress
                last_successful_time = timestamp
                progress_tracker.update_progress(
                    progress_id, last_successful_time, indicators_collected
                )

                logger.debug(f"Collected {indicators_collected} indicators so far...")

        # Store remaining indicators
        if indicator_batch:
            inserted = db.insert_economic_indicators_batch(indicator_batch)
            indicators_collected += inserted
            if indicator_batch:
                last_successful_time = indicator_batch[-1]["timestamp"]
            progress_tracker.update_progress(
                progress_id, last_successful_time, indicators_collected
            )

        connector.disconnect()
        logger.info(f"Economic backfill completed: {indicators_collected} indicators collected")
        return indicators_collected

    except Exception as e:
        logger.error(f"Error during economic backfill: {e}", exc_info=True)
        progress_tracker.mark_failed(progress_id, str(e))
        raise


def main():
    """Main backfill function"""
    args = parse_args()
    logger = get_logger("backfill_alternative_data", "backfill_alternative_data.log")

    # Parse times
    start_time = parse_datetime(args.start_time)
    end_time = parse_datetime(args.end_time)

    if start_time >= end_time:
        logger.error("start_time must be < end_time")
        sys.exit(1)

    logger.info(
        f"Starting alternative data backfill for {args.source} from {start_time} to {end_time}"
    )

    # Initialize components
    db = Database()
    progress_tracker = BackfillProgressTracker(db)

    # Determine connectors to use
    if args.source == "news":
        connectors = ["rss", "web_scraping"] if args.connector == "all" else [args.connector]
    elif args.source == "economic":
        connectors = ["fred", "world_bank", "ecb"] if args.connector == "all" else [args.connector]
    else:  # all
        if args.connector == "all":
            connectors = ["rss", "web_scraping", "fred", "world_bank", "ecb"]
        else:
            connectors = [args.connector]

    total_collected = 0

    for connector_type in connectors:
        # Determine connector category
        if connector_type in ["rss", "web_scraping"]:
            category = "news"
        else:
            category = "economic"

        # Check for existing progress
        existing_progress = progress_tracker.get_progress(
            f"{connector_type}_{category}", "*", start_time, end_time
        )

        if args.resume and existing_progress:
            progress_id = existing_progress["id"]
            resume_point = progress_tracker.get_resume_point(progress_id)
            if resume_point:
                logger.info(f"Resuming {connector_type} from {resume_point}")
                actual_start_time = resume_point
            else:
                actual_start_time = start_time
        else:
            # Create new progress record
            progress_id = progress_tracker.start_backfill(
                f"{connector_type}_{category}", "*", start_time, end_time
            )
            actual_start_time = start_time

        try:
            # Backfill based on category
            if category == "news":
                collected = backfill_news(
                    connector_type, actual_start_time, end_time, progress_tracker, progress_id, db
                )
            else:
                collected = backfill_economic(
                    connector_type, actual_start_time, end_time, progress_tracker, progress_id, db
                )

            # Mark as completed
            progress_tracker.mark_completed(progress_id)
            total_collected += collected

            logger.info(
                f"{connector_type} backfill completed successfully: {collected} records collected"
            )

        except Exception as e:
            logger.error(f"{connector_type} backfill failed: {e}", exc_info=True)
            progress_tracker.mark_failed(progress_id, str(e))
            # Continue with other connectors
            continue

    logger.info(f"Alternative data backfill completed: {total_collected} total records collected")


if __name__ == "__main__":
    main()
