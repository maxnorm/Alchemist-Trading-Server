"""
News Data Collection Tasks
News collection Celery tasks for Phase 3
"""

from datetime import datetime, timedelta
from infrastructure.data_pipeline.celery_app import celery_app
import logging

from ....connectors.rss_feed_connector import RSSFeedConnector
from ....connectors.web_scraping_connector import WebScrapingConnector
from ....connectors.base import ConnectorConfig
from ....database import Database

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def collect_rss_news(self):
    """
    Collect news from RSS feeds

    :return: Collection result
    """
    try:
        logger.info("Collecting news from RSS feeds")

        # Initialize database
        db = Database()

        # Create RSS connector
        config = ConnectorConfig(
            source="rss", symbol="*", extra_config={}
        )  # General news
        connector = RSSFeedConnector(config)

        if not connector.connect():
            raise ConnectionError("Failed to connect to RSS feeds")

        # Stream latest news
        start_time = datetime.now() - timedelta(hours=24)
        articles_collected = 0

        for article in connector.stream(start_time=start_time):
            try:
                # Insert article to database
                success = db.insert_news_article(
                    timestamp=article["timestamp"],
                    source=article["source"],
                    title=article["title"],
                    url=article["url"],
                    content=article.get("content"),
                    symbol=article.get("symbol"),
                    sentiment_score=article.get("sentiment_score"),
                    sentiment_label=article.get("sentiment_label"),
                    entities=article.get("entities"),
                    receive_time=article.get("receive_time"),
                )
                if success:
                    articles_collected += 1
            except Exception as e:
                logger.warning(f"Error inserting article: {e}")
                continue

        connector.disconnect()

        logger.info(f"Collected {articles_collected} articles from RSS feeds")
        return {"status": "success", "articles_collected": articles_collected}

    except Exception as exc:
        logger.error(f"RSS news collection failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def collect_web_scraping_news(self):
    """
    Collect news from web scraping

    :return: Collection result
    """
    try:
        logger.info("Collecting news from web scraping")

        # Initialize database
        db = Database()

        # Create web scraping connector
        config = ConnectorConfig(
            source="web_scraping",
            symbol="*",
            extra_config={
                "websites": ["tradingeconomics", "investing", "forexfactory"],
                "urls": [],  # URLs should be configured or discovered
            },
        )
        connector = WebScrapingConnector(config)

        if not connector.connect():
            logger.warning("Web scraping connector not available (may need API keys)")
            return {"status": "skipped", "reason": "Connector not available"}

        # Stream latest news
        start_time = datetime.now() - timedelta(hours=24)
        articles_collected = 0

        for article in connector.stream(start_time=start_time):
            try:
                # Insert article to database
                success = db.insert_news_article(
                    timestamp=article["timestamp"],
                    source=article["source"],
                    title=article["title"],
                    url=article["url"],
                    content=article.get("content"),
                    symbol=article.get("symbol"),
                    sentiment_score=article.get("sentiment_score"),
                    sentiment_label=article.get("sentiment_label"),
                    entities=article.get("entities"),
                    receive_time=article.get("receive_time"),
                )
                if success:
                    articles_collected += 1
            except Exception as e:
                logger.warning(f"Error inserting article: {e}")
                continue

        connector.disconnect()

        logger.info(f"Collected {articles_collected} articles from web scraping")
        return {"status": "success", "articles_collected": articles_collected}

    except Exception as exc:
        logger.error(f"Web scraping news collection failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)
