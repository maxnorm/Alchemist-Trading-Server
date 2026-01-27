"""
NewsAPI connector for news articles
Implements IDataSourceConnector for NewsAPI (optional - free tier limited to 100 requests/day)
"""

import os
import time
import requests  # type: ignore[import-untyped]
from typing import Dict, Any, Iterator, Optional, Tuple, cast
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


class NewsAPIConnector(IDataSourceConnector):
    """
    NewsAPI connector for news articles
    Uses NewsAPI (free tier limited to 100 requests/day)
    Note: RSS feeds are preferred for free usage
    """

    API_BASE = "https://newsapi.org/v2"

    def __init__(self, config: ConnectorConfig):
        """
        Initialize NewsAPI connector

        :param config: Connector configuration
        """
        self.config = config
        self.normalizer = EventNormalizer()
        self.logger = get_logger("news_api_connector", "news_api_connector.log")

        # Get API key from environment
        api_key = os.getenv("NEWSAPI_API_KEY")
        if not api_key:
            self.logger.warning(
                "NEWSAPI_API_KEY not found in environment. NewsAPI connector will not work."
            )
            self.api_key = None
        else:
            self.api_key = api_key
            self.logger.info("NewsAPI connector initialized successfully")

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

        self._is_connected = False
        self._latest_timestamp: Optional[datetime] = None

        # Rate limiting: 100 requests/day (free tier)
        self._last_request_time = 0.0
        self._min_request_interval = 864.0  # 864 seconds = 100 requests/day
        self._request_count_today = 0
        self._last_reset_date = datetime.now().date()

    def connect(self) -> bool:
        """
        Establish connection to NewsAPI

        :return: True if connection successful, False otherwise
        """
        if not self.api_key:
            self.logger.error("NewsAPI API key not configured")
            return False

        try:
            # Test connection
            url = f"{self.API_BASE}/everything"
            params = {
                "q": "forex",
                "apiKey": self.api_key,
                "pageSize": 1,
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                self._is_connected = True
                self.logger.info("Connected to NewsAPI")
                return True
            else:
                self.logger.warning(
                    f"NewsAPI connection test returned status {response.status_code}: {response.text}"
                )
                return False
        except Exception as e:
            self.logger.error(f"Failed to connect to NewsAPI: {e}")
            return False

    def disconnect(self) -> None:
        """Close connection to NewsAPI"""
        self._is_connected = False
        self.logger.info("Disconnected from NewsAPI")

    def is_connected(self) -> bool:
        """Check if connector is currently connected"""
        return self._is_connected and self.api_key is not None

    def _rate_limit(self):
        """Enforce rate limiting (100 requests/day free tier)"""
        # Reset counter if new day
        current_date = datetime.now().date()
        if current_date != self._last_reset_date:
            self._request_count_today = 0
            self._last_reset_date = current_date

        # Check daily limit
        if self._request_count_today >= 100:
            self.logger.warning("NewsAPI daily limit reached (100 requests/day)")
            raise ConnectionError("NewsAPI daily limit reached")

        # Enforce minimum interval
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            time.sleep(sleep_time)

        self._last_request_time = time.time()
        self._request_count_today += 1

    def _fetch_articles(
        self,
        query: str = "forex",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch articles from NewsAPI

        :param query: Search query
        :param start_date: Start date (optional)
        :param end_date: End date (optional)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to NewsAPI")

        try:
            self._rate_limit()

            # Build request
            url = f"{self.API_BASE}/everything"
            params = {
                "q": query,
                "apiKey": self.api_key,
                "pageSize": 100,  # Max page size
                "sortBy": "publishedAt",
            }

            if start_date:
                params["from"] = start_date.strftime("%Y-%m-%dT%H:%M:%S")
            if end_date:
                params["to"] = end_date.strftime("%Y-%m-%dT%H:%M:%S")

            # Fetch articles
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            articles = data.get("articles", [])

            # Process articles
            for article in articles:
                # Parse timestamp
                published_at = article.get("publishedAt")
                if published_at:
                    try:
                        timestamp = datetime.fromisoformat(
                            published_at.replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        timestamp = datetime.now()
                else:
                    timestamp = datetime.now()

                timestamp_utc = normalize_to_utc(timestamp)

                # Apply sentiment analysis and entity extraction
                sentiment_score = None
                sentiment_label = None
                entities = None
                symbol = None

                title = article.get("title", "")
                content = article.get("content", "") or article.get("description", "")

                if self.sentiment_analyzer and self.sentiment_analyzer.is_available():
                    try:
                        text_to_analyze = title
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
                        text_to_extract = title + " " + (content or "")
                        extracted_entities = self.entity_extractor.extract_entities(
                            text_to_extract
                        )

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
                    "source": "newsapi",
                    "title": title,
                    "content": content,
                    "url": article.get("url", ""),
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
            self.logger.error(f"Error fetching NewsAPI articles: {e}", exc_info=True)
            raise

    def _normalize_news(self, raw_event: Dict) -> Dict[str, Any]:
        """
        Normalize news event to contract format

        :param raw_event: Raw NewsAPI event dictionary
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
        Stream latest news articles from NewsAPI

        :param start_time: Optional start time (defaults to last 24 hours)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to NewsAPI")

        if start_time is None:
            start_time = datetime.now() - timedelta(hours=24)

        # Search for forex-related news
        try:
            yield from self._fetch_articles(
                query="forex OR currency", start_date=start_time
            )
        except Exception as e:
            self.logger.error(f"Error streaming NewsAPI: {e}")
            raise

    def batch(
        self, start_time: datetime, end_time: datetime
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch historical news articles from database (not implemented for NewsAPI)

        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :return: Iterator of normalized event dictionaries
        """
        # NewsAPI connector doesn't read from database
        # Use backfill() for historical data from NewsAPI (limited by API tier)
        self.logger.warning(
            "batch() not implemented for NewsAPI. Use backfill() instead."
        )
        return iter([])

    def backfill(
        self, start_time: datetime, end_time: datetime, batch_size: int = 1000
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch historical news articles from NewsAPI (limited by API tier)

        :param start_time: Start time for historical data
        :param end_time: End time for historical data
        :param batch_size: Batch size (not used, NewsAPI handles batching)
        :return: Iterator of normalized event dictionaries
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to NewsAPI")

        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

        # NewsAPI free tier has limited historical access
        # Only fetch if within last month
        one_month_ago = datetime.now() - timedelta(days=30)
        if start_time < one_month_ago:
            self.logger.warning(
                "NewsAPI free tier limited to last month. Adjusting start_time."
            )
            start_time = one_month_ago

        try:
            yield from self._fetch_articles(
                query="forex OR currency", start_date=start_time, end_date=end_time
            )
        except Exception as e:
            self.logger.error(f"Error backfilling NewsAPI: {e}")
            raise

    def get_available_range(self) -> Tuple[datetime, datetime]:
        """
        Get the available data range from NewsAPI

        :return: Tuple of (earliest_available_time, latest_available_time)
        """
        if not self.is_connected():
            if not self.connect():
                raise ConnectionError("Failed to connect to NewsAPI")

        # NewsAPI free tier typically has data from last month
        now = datetime.now()
        one_month_ago = now - timedelta(days=30)
        return (normalize_to_utc(one_month_ago), normalize_to_utc(now))

    def get_schema(self) -> Dict[str, Any]:
        """
        Return NewsAPI connector schema definition

        :return: Schema dictionary
        """
        return {
            "source": "newsapi",
            "data_type": "news",
            "fields": {
                "timestamp": "datetime",
                "source": "string",
                "title": "string",
                "content": "string",
                "url": "string",
                "symbol": "string",
            },
            "rate_limit": "100 requests/day (free tier)",
        }

    def get_latest_timestamp(self) -> Optional[datetime]:
        """
        Get timestamp of most recent data available

        :return: Datetime of most recent data, or None if no data available
        """
        return self._latest_timestamp
