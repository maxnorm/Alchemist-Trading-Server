"""
RSS Feed connector for news articles
Implements IDataSourceConnector for multiple RSS feeds (completely free, no API key)
"""

import time
from typing import Dict, Any, Iterator, Optional, Tuple, Set, cast
from datetime import datetime, timedelta
from utils.logging_config import get_logger
from events.normalizer import EventNormalizer
from .base import IDataSourceConnector, ConnectorConfig
from utils.time_utils import normalize_to_utc, ensure_utc_timezone

# Import sentiment analyzer and entity extractor (optional)
try:
    from utils.sentiment_analyzer import SentimentAnalyzer
    from utils.entity_extractor import EntityExtractor

    SENTIMENT_AVAILABLE = True
except ImportError:
    SENTIMENT_AVAILABLE = False
    SentimentAnalyzer = cast(Any, None)  # type: ignore[misc]
    EntityExtractor = cast(Any, None)  # type: ignore[misc]

try:
    import feedparser
except ImportError:
    feedparser = None


class RSSFeedConnector(IDataSourceConnector):
    """
    RSS Feed connector for news articles
    Supports multiple RSS feeds (Reuters, Bloomberg, FT, ForexFactory)
    Completely free, no API key required
    """

    # Default RSS feed URLs
    DEFAULT_FEEDS = {
        "reuters_finance": "https://www.reuters.com/finance",
        "bloomberg": "https://www.bloomberg.com/feeds",
        "ft": "https://www.ft.com/?format=rss",
        "forexfactory": "https://www.forexfactory.com/calendar.php?week=today",
    }

    def __init__(self, config: ConnectorConfig):
        """
        Initialize RSS Feed connector

        :param config: Connector configuration
        """
        self.config = config
        self.normalizer = EventNormalizer()
        self.logger = get_logger("rss_feed_connector", "rss_feed_connector.log")

        if feedparser is None:
            self.logger.error(
                "feedparser library not installed. Install with: pip install feedparser"
            )
            self._available = False
        else:
            self._available = True
            self.logger.info("RSS Feed connector initialized successfully")

        # Get feed URLs from config or use defaults
        self.feed_urls = config.extra_config.get("feed_urls", self.DEFAULT_FEEDS)

        self._is_connected = False
        self._latest_timestamp: Optional[datetime] = None
        self._seen_urls: Set[str] = set()  # For deduplication

        # Initialize lineage service
        try:
            from infrastructure.lineage.lineage_service import LineageService

            self.lineage_service: Optional[LineageService] = LineageService()
            self.current_run_id: Optional[str] = None
        except Exception as e:
            self.logger.warning(f"Failed to initialize lineage service: {e}")
            self.lineage_service = None
            self.current_run_id = None

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

        # Rate limiting: be respectful to RSS feeds
        self._last_request_time: Dict[str, float] = {}
        self._min_request_interval = 2.0  # 2 seconds between requests per feed

    def connect(self) -> bool:
        """
        Establish connection to RSS feeds

        :return: True if connection successful, False otherwise
        """
        if not self._available:
            self.logger.error(
                "RSS Feed connector not available. Install feedparser library."
            )
            return False

        try:
            # Test connection by fetching first feed
            test_feed_name = list(self.feed_urls.keys())[0]
            test_feed_url = self.feed_urls[test_feed_name]
            feed = feedparser.parse(test_feed_url)
            if feed.bozo == 0 and len(feed.entries) > 0:
                self._is_connected = True
                self.logger.info("Connected to RSS feeds")
                return True
            else:
                self.logger.warning(
                    f"RSS feed connection test returned no valid entries for {test_feed_name}"
                )
                return False
        except Exception as e:
            self.logger.error(f"Failed to connect to RSS feeds: {e}")
            return False

    def disconnect(self) -> None:
        """Close connection to RSS feeds"""
        self._is_connected = False
        self.logger.info("Disconnected from RSS feeds")

    def is_connected(self) -> bool:
        """Check if connector is currently connected"""
        return self._is_connected and self._available

    def _rate_limit(self, feed_name: str):
        """Enforce rate limiting per feed"""
        current_time = time.time()
        last_time = self._last_request_time.get(feed_name, 0.0)
        time_since_last = current_time - last_time
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            time.sleep(sleep_time)
        self._last_request_time[feed_name] = time.time()

    def _parse_feed_entry(
        self, entry: Any, source: str, feed_url: str
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a single RSS feed entry

        :param entry: Feedparser entry object
        :param source: Source identifier
        :param feed_url: Feed URL
        :return: Normalized event dictionary or None if invalid
        """
        try:
            # Extract URL (for deduplication)
            url = entry.get("link", "")
            if not url:
                return None

            # Check if we've seen this URL
            if url in self._seen_urls:
                return None

            # Extract title
            title = entry.get("title", "")
            if not title:
                return None

            # Extract content/description
            content = entry.get("summary", "") or entry.get("description", "")

            # Extract timestamp
            timestamp = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                timestamp = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                timestamp = datetime(*entry.updated_parsed[:6])
            else:
                # Use current time as fallback
                timestamp = datetime.now()

            # Normalize timestamp to UTC
            timestamp_utc = normalize_to_utc(timestamp)

            # Extract symbol from title/content (basic extraction)
            symbol = self._extract_symbol(title + " " + content)

            # Apply sentiment analysis and entity extraction
            sentiment_score = None
            sentiment_label = None
            entities = None

            if self.sentiment_analyzer and self.sentiment_analyzer.is_available():
                try:
                    # Analyze sentiment (use title + content)
                    text_to_analyze = title
                    if content:
                        text_to_analyze += " " + content[:500]  # Limit content length
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
                    text_to_extract = title + " " + (content or "")
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
                            symbol = matched_symbols[0]  # Use first matched symbol

                    entities = extracted_entities
                except Exception as e:
                    self.logger.warning(f"Error in entity extraction: {e}")

            # Create raw event
            raw_event = {
                "timestamp": timestamp_utc,
                "source": source,
                "title": title,
                "content": content,
                "url": url,
                "symbol": symbol,
                "sentiment_score": sentiment_score,
                "sentiment_label": sentiment_label,
                "entities": entities,
                "_receive_time": ensure_utc_timezone(datetime.now()),
            }

            # Normalize event
            normalized = self._normalize_news(raw_event)

            # Mark URL as seen
            self._seen_urls.add(url)

            # Update latest timestamp
            if self._latest_timestamp is None or timestamp_utc > self._latest_timestamp:
                self._latest_timestamp = timestamp_utc

            return normalized

        except Exception as e:
            self.logger.warning(f"Error parsing RSS entry: {e}")
            return None

    def _extract_symbol(self, text: str) -> Optional[str]:
        """
        Extract currency pair symbol from text (basic extraction)

        :param text: Text to search
        :return: Symbol if found, None otherwise
        """
        # Common currency pairs
        currency_pairs = [
            "EURUSD",
            "GBPUSD",
            "USDJPY",
            "USDCHF",
            "AUDUSD",
            "USDCAD",
            "NZDUSD",
            "EURGBP",
            "EURJPY",
            "GBPJPY",
            "AUDNZD",
            "EURAUD",
            "EURCHF",
        ]

        text_upper = text.upper()
        for pair in currency_pairs:
            if pair in text_upper:
                return pair

        return None

    def _normalize_news(self, raw_event: Dict) -> Dict[str, Any]:
        """
        Normalize news event to contract format

        :param raw_event: Raw RSS event dictionary
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

    def _fetch_feed(self, feed_name: str, feed_url: str) -> Iterator[Dict[str, Any]]:
        """
        Fetch and parse a single RSS feed

        :param feed_name: Feed name identifier
        :param feed_url: Feed URL
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to RSS feeds")

        try:
            self._rate_limit(feed_name)

            # Parse RSS feed
            feed = feedparser.parse(feed_url)

            # Check for parsing errors
            if feed.bozo != 0:
                self.logger.warning(
                    f"RSS feed {feed_name} has parsing errors: {feed.bozo_exception}"
                )

            # Process entries
            for entry in feed.entries:
                normalized = self._parse_feed_entry(entry, feed_name, feed_url)
                if normalized:
                    yield normalized

        except Exception as e:
            self.logger.error(
                f"Error fetching RSS feed {feed_name}: {e}", exc_info=True
            )
            raise

    def stream(self, start_time: Optional[datetime] = None) -> Iterator[Dict[str, Any]]:
        """
        Stream latest news articles from RSS feeds

        :param start_time: Optional start time (defaults to last 24 hours)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to RSS feeds")

        # Start lineage run
        run_id = None
        if self.lineage_service:
            try:
                job_name = "rss_news_collection"
                run_id = self.lineage_service.start_run(
                    job_name=job_name,
                    namespace="trading_data",
                    inputs=[],
                    metadata={
                        "source": "rss",
                        "data_type": "news",
                        "mode": "stream",
                        "feed_count": len(self.feed_urls),
                    },
                )
                self.current_run_id = run_id
            except Exception as e:
                self.logger.warning(f"Failed to start lineage run: {e}")

        event_count = 0
        try:
            # For streaming, fetch all feeds
            for feed_name, feed_url in self.feed_urls.items():
                try:
                    for article in self._fetch_feed(feed_name, feed_url):
                        # Filter by start_time if provided
                        if start_time and article["timestamp"] < start_time:
                            continue
                        event_count += 1
                        yield article
                except Exception as e:
                    self.logger.error(f"Error streaming feed {feed_name}: {e}")
                    continue

            # Emit output dataset and complete lineage run
            if self.lineage_service and run_id:
                try:
                    dataset_name = "news_articles_rss"
                    self.lineage_service.emit_dataset(
                        dataset_name=dataset_name,
                        namespace="trading_data",
                        schema=self.get_schema(),
                    )
                    self.lineage_service.complete_run(
                        run_id=run_id,
                        outputs=[
                            {
                                "dataset_id": f"trading_data:{dataset_name}",
                                "namespace": "trading_data",
                            }
                        ],
                        metadata={"event_count": event_count},
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to complete lineage run: {e}")

        except Exception as e:
            # Fail lineage run on error
            if self.lineage_service and run_id:
                try:
                    self.lineage_service.fail_run(run_id, str(e))
                except Exception as lineage_error:
                    self.logger.warning(f"Failed to fail lineage run: {lineage_error}")
            raise

    def batch(
        self, start_time: datetime, end_time: datetime
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch historical news articles from database (not implemented for RSS)

        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :return: Iterator of normalized event dictionaries
        """
        if start_time >= end_time:
            raise ValueError("start_time must be < end_time")

        # Start lineage run
        run_id = None
        if self.lineage_service:
            try:
                job_name = "rss_news_batch"
                run_id = self.lineage_service.start_run(
                    job_name=job_name,
                    namespace="trading_data",
                    inputs=[],
                    metadata={
                        "source": "rss",
                        "data_type": "news",
                        "mode": "batch",
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                    },
                )
                self.current_run_id = run_id
            except Exception as e:
                self.logger.warning(f"Failed to start lineage run: {e}")

        event_count = 0
        try:
            # RSS feeds don't support historical queries, so return empty
            # In a real implementation, this would query the database
            self.logger.warning(
                "RSS batch() not implemented - RSS feeds don't support historical queries"
            )

            # Complete lineage run
            if self.lineage_service and run_id:
                try:
                    dataset_name = "news_articles_rss"
                    self.lineage_service.emit_dataset(
                        dataset_name=dataset_name,
                        namespace="trading_data",
                        schema=self.get_schema(),
                    )
                    self.lineage_service.complete_run(
                        run_id=run_id,
                        outputs=[
                            {
                                "dataset_id": f"trading_data:{dataset_name}",
                                "namespace": "trading_data",
                            }
                        ],
                        metadata={"event_count": event_count},
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to complete lineage run: {e}")

        except Exception as e:
            # Fail lineage run on error
            if self.lineage_service and run_id:
                try:
                    self.lineage_service.fail_run(run_id, str(e))
                except Exception as lineage_error:
                    self.logger.warning(f"Failed to fail lineage run: {lineage_error}")
            raise
        # RSS connector doesn't read from database
        # Use backfill() for historical data from RSS feeds (limited by feed retention)
        self.logger.warning("batch() not implemented for RSS. Use backfill() instead.")
        return iter([])

    def backfill(
        self, start_time: datetime, end_time: datetime, batch_size: int = 1000
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch historical news articles from RSS feeds (limited by feed retention)

        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :param batch_size: Batch size (not used)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to RSS feeds")

        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

        # RSS feeds typically only retain recent articles (last 10-50)
        # We fetch all available and filter by time range
        for feed_name, feed_url in self.feed_urls.items():
            try:
                for article in self._fetch_feed(feed_name, feed_url):
                    # Filter by time range
                    if start_time <= article["timestamp"] <= end_time:
                        yield article
            except Exception as e:
                self.logger.error(f"Error backfilling feed {feed_name}: {e}")
                continue

    def get_available_range(self) -> Tuple[datetime, datetime]:
        """
        Get the available data range from RSS feeds

        :return: Tuple of (earliest_available_time, latest_available_time)
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to RSS feeds")

        try:
            # RSS feeds typically only have recent articles
            # Fetch first feed to get date range
            feed_name = list(self.feed_urls.keys())[0]
            feed_url = self.feed_urls[feed_name]

            self._rate_limit(feed_name)
            feed = feedparser.parse(feed_url)

            if not feed.entries:
                raise ValueError("No entries found in RSS feed")

            # Get earliest and latest dates from entries
            dates = []
            for entry in feed.entries:
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    dates.append(datetime(*entry.published_parsed[:6]))
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    dates.append(datetime(*entry.updated_parsed[:6]))

            if not dates:
                # Fallback to current time
                now = datetime.now()
                return (
                    normalize_to_utc(now - timedelta(days=30)),
                    normalize_to_utc(now),
                )

            earliest = min(dates)
            latest = max(dates)

            return (normalize_to_utc(earliest), normalize_to_utc(latest))

        except Exception as e:
            self.logger.error(f"Error getting available range from RSS feeds: {e}")
            raise ConnectionError(f"Failed to get available range: {e}")

    def get_schema(self) -> Dict[str, Any]:
        """
        Return RSS Feed connector schema definition

        :return: Schema dictionary
        """
        return {
            "source": "RSS",
            "data_type": "news",
            "fields": {
                "timestamp": "datetime",
                "source": "string",
                "title": "string",
                "content": "string",
                "url": "string",
                "symbol": "string",
            },
            "feeds": list(self.feed_urls.keys()),
        }

    def get_latest_timestamp(self) -> Optional[datetime]:
        """
        Get timestamp of most recent data available

        :return: Datetime of most recent data, or None if no data available
        """
        return self._latest_timestamp
