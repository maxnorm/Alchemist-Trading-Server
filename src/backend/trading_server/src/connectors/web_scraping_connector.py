"""
Web Scraping connector for news articles
Implements IDataSourceConnector for AI-assisted web scraping
"""

import time
from typing import Dict, Any, Iterator, Optional, Tuple, List
from datetime import datetime, timedelta
from utils.logging_config import get_logger
from events.normalizer import EventNormalizer
from .base import IDataSourceConnector, ConnectorConfig
from utils.time_utils import normalize_to_utc, ensure_utc_timezone
from infrastructure.scraping.website_scrapers import WebsiteScraper, create_scraper
from infrastructure.scraping.ai_scraper import LLMScraper

# Import sentiment analyzer and entity extractor (optional)
try:
    from utils.sentiment_analyzer import SentimentAnalyzer
    from utils.entity_extractor import EntityExtractor

    SENTIMENT_AVAILABLE = True
except ImportError:
    SENTIMENT_AVAILABLE = False
    SentimentAnalyzer = None
    EntityExtractor = None


class WebScrapingConnector(IDataSourceConnector):
    """
    Web scraping connector for news articles
    Orchestrates multiple website scrapers with AI-assisted extraction
    """

    # Default websites to scrape
    DEFAULT_WEBSITES = [
        "tradingeconomics",
        "investing",
        "forexfactory",
    ]

    def __init__(self, config: ConnectorConfig):
        """
        Initialize web scraping connector

        :param config: Connector configuration
        """
        self.config = config
        self.normalizer = EventNormalizer()
        self.logger = get_logger("web_scraping_connector", "web_scraping_connector.log")

        # Get websites from config
        self.websites = config.extra_config.get("websites", self.DEFAULT_WEBSITES)

        # Initialize AI scraper (optional, will work without it but less accurate)
        self.ai_scraper = None
        try:
            provider = config.extra_config.get("llm_provider", "openai")
            self.ai_scraper = LLMScraper(provider=provider)
        except Exception as e:
            self.logger.warning(f"Could not initialize AI scraper: {e}")

        # Initialize website scrapers
        self.scrapers: Dict[str, WebsiteScraper] = {}
        for website in self.websites:
            try:
                self.scrapers[website] = create_scraper(website, self.ai_scraper)
            except Exception as e:
                self.logger.warning(f"Could not create scraper for {website}: {e}")

        self._is_connected = False
        self._latest_timestamp: Optional[datetime] = None

        # Initialize sentiment analyzer and entity extractor (optional)
        self.sentiment_analyzer = None
        self.entity_extractor = None
        if SENTIMENT_AVAILABLE:
            try:
                self.sentiment_analyzer = SentimentAnalyzer()
                self.entity_extractor = EntityExtractor()
                if (
                    self.sentiment_analyzer.is_available()
                    and self.entity_extractor.is_available()
                ):
                    self.logger.info("Sentiment analysis and entity extraction enabled")
            except Exception as e:
                self.logger.warning(
                    f"Could not initialize sentiment/entity extractors: {e}"
                )

        # Rate limiting
        self._last_request_time: Dict[str, float] = {}
        self._min_request_interval = 5.0  # 5 seconds between requests per website

    def connect(self) -> bool:
        """
        Establish connection (check if scrapers are available)

        :return: True if connection successful, False otherwise
        """
        if not self.scrapers:
            self.logger.error("No website scrapers available")
            return False

        self._is_connected = True
        self.logger.info(
            f"Connected to web scraping (websites: {list(self.scrapers.keys())})"
        )
        return True

    def disconnect(self) -> None:
        """Close connection"""
        self._is_connected = False
        self.logger.info("Disconnected from web scraping")

    def is_connected(self) -> bool:
        """Check if connector is currently connected"""
        return self._is_connected

    def _rate_limit(self, website: str):
        """Enforce rate limiting per website"""
        current_time = time.time()
        last_time = self._last_request_time.get(website, 0.0)
        time_since_last = current_time - last_time
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            time.sleep(sleep_time)
        self._last_request_time[website] = time.time()

    def _scrape_website(
        self, website: str, urls: List[str]
    ) -> Iterator[Dict[str, Any]]:
        """
        Scrape articles from a website

        :param website: Website identifier
        :param urls: List of URLs to scrape
        :return: Iterator of normalized event dictionaries
        """
        if website not in self.scrapers:
            return

        scraper = self.scrapers[website]

        for url in urls:
            try:
                self._rate_limit(website)

                # Scrape article
                data = scraper.scrape(url)
                if not data:
                    continue

                # Extract timestamp
                timestamp = data.get("timestamp")
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        timestamp = datetime.now()
                elif not isinstance(timestamp, datetime):
                    timestamp = datetime.now()

                timestamp_utc = normalize_to_utc(timestamp)

                # Apply sentiment analysis and entity extraction
                sentiment_score = None
                sentiment_label = None
                entities = None
                symbol = data.get("symbol")

                if self.sentiment_analyzer and self.sentiment_analyzer.is_available():
                    try:
                        # Analyze sentiment
                        text_to_analyze = data.get("title", "")
                        content = data.get("content", "")
                        if content:
                            text_to_analyze += " " + content[:500]
                        sentiment_result = self.sentiment_analyzer.analyze_sentiment(
                            text_to_analyze
                        )
                        sentiment_score = sentiment_result.get("score")
                        sentiment_label = sentiment_result.get("label")
                    except Exception as e:
                        self.logger.warning(f"Error in sentiment analysis: {e}")

                if self.entity_extractor and self.entity_extractor.is_available():
                    try:
                        # Extract entities
                        text_to_extract = (
                            data.get("title", "")
                            + " "
                            + (data.get("content", "") or "")
                        )
                        extracted_entities = self.entity_extractor.extract_entities(
                            text_to_extract
                        )

                        # Update symbol if entity extractor found better matches
                        currency_pairs = extracted_entities.get("currency_pairs", [])
                        if currency_pairs:
                            matched_symbols = self.entity_extractor.match_symbols(
                                currency_pairs
                            )
                            if matched_symbols:
                                symbol = matched_symbols[0]

                        entities = extracted_entities
                    except Exception as e:
                        self.logger.warning(f"Error in entity extraction: {e}")

                # Create raw event
                raw_event = {
                    "timestamp": timestamp_utc,
                    "source": data.get("source", website),
                    "title": data.get("title", ""),
                    "content": data.get("content", ""),
                    "url": data.get("url", url),
                    "symbol": symbol,
                    "sentiment_score": sentiment_score,
                    "sentiment_label": sentiment_label,
                    "entities": entities,
                    "_receive_time": ensure_utc_timezone(datetime.now()),
                }

                # Normalize event
                normalized = self._normalize_news(raw_event)

                # Update latest timestamp
                if (
                    self._latest_timestamp is None
                    or timestamp_utc > self._latest_timestamp
                ):
                    self._latest_timestamp = timestamp_utc

                yield normalized

            except Exception as e:
                self.logger.error(f"Error scraping {url}: {e}")
                continue

    def _normalize_news(self, raw_event: Dict) -> Dict[str, Any]:
        """
        Normalize news event to contract format

        :param raw_event: Raw scraped event dictionary
        :return: Normalized event dictionary conforming to news contract
        """
        normalized = {
            "timestamp": raw_event["timestamp"],
            "source": raw_event["source"],
            "title": raw_event["title"],
            "content": raw_event.get("content"),
            "url": raw_event["url"],
            "symbol": raw_event.get("symbol"),
            "sentiment_score": raw_event.get("sentiment_score"),
            "sentiment_label": raw_event.get("sentiment_label"),
            "entities": raw_event.get("entities"),
            "receive_time": raw_event.get("_receive_time"),
        }
        return normalized

    def stream(self, start_time: Optional[datetime] = None) -> Iterator[Dict[str, Any]]:
        """
        Stream latest news articles from web scraping

        :param start_time: Optional start time (defaults to last 24 hours)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to web scraping")

        # For streaming, we need URLs to scrape
        # This is a simplified version - in production, you'd have a URL discovery mechanism
        # For now, we'll use a placeholder that would need to be configured
        urls_to_scrape = self.config.extra_config.get("urls", [])

        if not urls_to_scrape:
            self.logger.warning(
                "No URLs configured for web scraping. Configure 'urls' in extra_config."
            )
            return iter([])

        # Scrape all websites
        for website in self.websites:
            try:
                for article in self._scrape_website(website, urls_to_scrape):
                    # Filter by start_time if provided
                    if start_time and article["timestamp"] < start_time:
                        continue
                    yield article
            except Exception as e:
                self.logger.error(f"Error streaming from {website}: {e}")
                continue

    def batch(
        self, start_time: datetime, end_time: datetime
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch historical news articles from database (not implemented for web scraping)

        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :return: Iterator of normalized event dictionaries
        """
        # Web scraping connector doesn't read from database
        # Use backfill() for historical data from websites (limited by website retention)
        self.logger.warning(
            "batch() not implemented for web scraping. Use backfill() instead."
        )
        return iter([])

    def backfill(
        self, start_time: datetime, end_time: datetime, batch_size: int = 1000
    ) -> Iterator[Dict[str, Any]]:
        """
        Scrape historical news articles from websites (limited by website retention)

        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :param batch_size: Batch size (not used)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to web scraping")

        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

        # Similar to stream(), but filter by time range
        urls_to_scrape = self.config.extra_config.get("urls", [])

        if not urls_to_scrape:
            self.logger.warning("No URLs configured for web scraping.")
            return iter([])

        for website in self.websites:
            try:
                for article in self._scrape_website(website, urls_to_scrape):
                    # Filter by time range
                    if start_time <= article["timestamp"] <= end_time:
                        yield article
            except Exception as e:
                self.logger.error(f"Error backfilling from {website}: {e}")
                continue

    def get_available_range(self) -> Tuple[datetime, datetime]:
        """
        Get the available data range from web scraping

        :return: Tuple of (earliest_available_time, latest_available_time)
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to web scraping")

        # Web scraping typically only has recent articles
        # Return a conservative range
        now = datetime.now()
        return (normalize_to_utc(now - timedelta(days=30)), normalize_to_utc(now))

    def get_schema(self) -> Dict[str, Any]:
        """
        Return web scraping connector schema definition

        :return: Schema dictionary
        """
        return {
            "source": "web_scraping",
            "data_type": "news",
            "fields": {
                "timestamp": "datetime",
                "source": "string",
                "title": "string",
                "content": "string",
                "url": "string",
                "symbol": "string",
            },
            "websites": self.websites,
        }

    def get_latest_timestamp(self) -> Optional[datetime]:
        """
        Get timestamp of most recent data available

        :return: Datetime of most recent data, or None if no data available
        """
        return self._latest_timestamp
