---
name: Phase 3 Alternative Data Integration
overview: Integrate alternative data sources including news APIs, sentiment analysis, social media connectors, and macroeconomic indicators to enrich RL state space with contextual signals beyond price data.
todos:
  - id: create-news-table
    content: Create news_articles database table migration with TimescaleDB hypertable conversion
    status: pending
  - id: add-news-db-methods
    content: Add insert_news_article() and insert_news_articles_batch() methods to Database class
    status: pending
    dependencies:
      - create-news-table
  - id: create-news-api-connector
    content: Create NewsAPIConnector implementing IDataSourceConnector for NewsAPI integration
    status: pending
    dependencies:
      - add-news-db-methods
  - id: create-rss-connector
    content: Create RSSFeedConnector for financial news RSS feeds (Reuters, Bloomberg, FT)
    status: pending
    dependencies:
      - add-news-db-methods
  - id: create-sentiment-analyzer
    content: Create sentiment_analyzer.py module with FinBERT-based sentiment analysis pipeline
    status: pending
  - id: create-entity-extractor
    content: Create entity_extractor.py module for extracting currency pairs, companies, and events from news
    status: pending
  - id: integrate-sentiment-news
    content: Integrate sentiment analysis into news connectors (real-time and batch processing)
    status: pending
    dependencies:
      - create-sentiment-analyzer
      - create-entity-extractor
      - create-news-api-connector
      - create-rss-connector
  - id: enhance-economic-calendar
    content: Enhance economic calendar collector with historical backfill and multiple sources
    status: pending
  - id: create-economic-indicators-table
    content: Create economic_indicators database table migration with TimescaleDB hypertable
    status: pending
  - id: add-economic-indicators-db-methods
    content: Add insert_economic_indicator() and insert_economic_indicators_batch() methods to Database class
    status: pending
    dependencies:
      - create-economic-indicators-table
  - id: create-fred-connector
    content: Create FREDConnector implementing IDataSourceConnector for US economic indicators
    status: pending
    dependencies:
      - add-economic-indicators-db-methods
  - id: create-world-bank-connector
    content: Create WorldBankConnector for global economic indicators
    status: pending
    dependencies:
      - add-economic-indicators-db-methods
  - id: create-ecb-connector
    content: Create ECBConnector for European Central Bank data
    status: pending
    dependencies:
      - add-economic-indicators-db-methods
  - id: create-reddit-connector
    content: Create RedditConnector using PRAW for Reddit sentiment collection
    status: pending
    dependencies:
      - create-sentiment-analyzer
  - id: create-twitter-connector
    content: Create TwitterConnector for social media sentiment collection (optional, requires API access)
    status: pending
    dependencies:
      - create-sentiment-analyzer
  - id: create-sentiment-aggregator
    content: Create sentiment_aggregator.py module to aggregate sentiment across sources and time windows
    status: pending
    dependencies:
      - integrate-sentiment-news
      - create-reddit-connector
  - id: integrate-alternative-features
    content: Integrate news sentiment, social media sentiment, and macro indicators into FeatureEngine
    status: pending
    dependencies:
      - create-sentiment-aggregator
      - create-fred-connector
      - create-world-bank-connector
      - create-ecb-connector
  - id: create-airflow-dag-alternative
    content: Create Airflow DAG for alternative data collection (news, economic indicators, social media)
    status: pending
    dependencies:
      - integrate-alternative-features
  - id: add-alternative-data-tests
    content: Add unit and integration tests for all new connectors and sentiment analysis
    status: pending
    dependencies:
      - integrate-alternative-features
---

# Phase 3: Alternative Data Integration (Weeks 9-12)

## Overview

Phase 3 builds on Phases 1-2 infrastructure to integrate alternative data sources that provide contextual signals beyond price data. This phase focuses on news sentiment, social media sentiment, and macroeconomic indicators to enrich the RL state space with market context.

## Week 9-10: News & Sentiment Data

### 3.1 News Data Collection Infrastructure

**Current State:**

- ✅ `EventNormalizer` has `_normalize_news()` method for news event normalization
- ✅ `NewsContractValidator` exists for news data contract validation
- ✅ Schema contract defined for news data in `15_schema_contracts.sql`
- ❌ No `news_articles` database table exists yet
- ❌ No news data connectors implemented
- ❌ No sentiment analysis pipeline

**Implementation Tasks:**

1. **Create news_articles database table**

- Create migration script: `src/database/scripts/19_news_articles_table.sql`
- Table structure:
  - `id` (BIGSERIAL)
  - `timestamp` (TIMESTAMPTZ) - publication time
  - `source` (VARCHAR) - news source identifier
  - `title` (TEXT) - news headline
  - `content` (TEXT) - full article content (nullable)
  - `url` (VARCHAR) - article URL
  - `symbol` (VARCHAR) - affected currency pair or "*" for general news
  - `sentiment_score` (FLOAT) - sentiment score (-1 to 1)
  - `sentiment_label` (VARCHAR) - sentiment label (positive, negative, neutral)
  - `entities` (JSONB) - extracted entities (currencies, companies, events)
  - `receive_time` (TIMESTAMPTZ) - when data was received (bitemporal)
  - `created_at` (TIMESTAMPTZ) - record creation time
- Convert to TimescaleDB hypertable with 1-day chunk interval
- Add indexes: `(timestamp)`, `(symbol, timestamp)`, `(source, timestamp)`
- Foreign key to `forex_pairs` table (nullable, for symbol matching)

2. **Add database methods for news data**

- Enhance `src/trading_server/src/database.py`:
  - `insert_news_article(article: Dict[str, Any]) -> bool` - Insert single news article
  - `insert_news_articles_batch(articles: List[Dict[str, Any]]) -> int` - Batch insert with transaction
  - `get_recent_news(symbol: Optional[str] = None, hours: int = 24, limit: int = 100) -> List[Dict]` - Query recent news
  - `get_news_by_timeframe(start_time: datetime, end_time: datetime, symbol: Optional[str] = None) -> List[Dict]` - Historical news query
- Support bitemporal queries (event_time vs receive_time)
- Use existing connection pooling and retry logic

3. **Create NewsAPI connector**

- Create `src/trading_server/src/connectors/news_api_connector.py`
- Implement `IDataSourceConnector` interface:
  - `stream()` - Poll NewsAPI for real-time news (every 15-30 minutes)
  - `batch()` - Fetch historical news from database (for backfill)
  - `backfill()` - Use NewsAPI paid tier or web scraping for historical data
- Configuration:
  - API key from environment variables
  - Query keywords: "forex OR currency OR trading OR central bank"
  - Rate limiting: 100 requests/day (free tier), respect API limits
  - Language filter: English only
- Normalize events using `EventNormalizer._normalize_news()`
- Handle API errors gracefully with retry logic

4. **Create RSS feed connector**

- Create `src/trading_server/src/connectors/rss_feed_connector.py`
- Implement `IDataSourceConnector` interface
- Support multiple RSS feeds:
  - Reuters Forex RSS
  - Bloomberg Markets RSS
  - Financial Times Markets RSS
  - ForexFactory News RSS
- Use `feedparser` library for RSS parsing
- Poll feeds every 15-30 minutes
- Normalize RSS items to news event format
- Deduplicate articles by URL

### 3.2 Sentiment Analysis Pipeline

**Implementation Tasks:**

1. **Create sentiment analyzer module**

- Create `src/trading_server/src/utils/sentiment_analyzer.py`
- Implement `SentimentAnalyzer` class:
  - Use `transformers` library with FinBERT model (`ProsusAI/finbert`)
  - Alternative: `yiyanghkust/finbert-tone` for financial sentiment
  - Batch processing for efficiency
  - Support both title-only and full-content analysis
- Methods:
  - `analyze_sentiment(text: str) -> Dict[str, Any]` - Analyze single text
  - `analyze_batch(texts: List[str]) -> List[Dict[str, Any]]` - Batch analysis
  - Returns: `{"score": float, "label": str, "confidence": float}`
- Cache model loading (singleton pattern)
- Handle model loading errors gracefully

2. **Create entity extractor module**

- Create `src/trading_server/src/utils/entity_extractor.py`
- Implement `EntityExtractor` class:
  - Use spaCy NER or `flair` library for named entity recognition
  - Extract: currency pairs (EUR, USD, GBP, etc.), company names, economic events
  - Match currency pairs to trading symbols
  - Extract event types (rate decisions, GDP, employment, etc.)
- Methods:
  - `extract_entities(text: str) -> Dict[str, List[str]]` - Extract entities
  - `extract_currency_pairs(text: str) -> List[str]` - Extract currency mentions
  - `extract_events(text: str) -> List[str]` - Extract economic event types
- Store entities as JSONB in database

3. **Integrate sentiment into news connectors**

- Enhance `NewsAPIConnector` and `RSSFeedConnector`:
  - Analyze sentiment for each article (title + description/content)
  - Extract entities for each article
  - Include sentiment and entities in normalized events
  - Store in database with sentiment scores
- Use batch processing for efficiency (analyze multiple articles at once)
- Handle sentiment analysis failures gracefully (store article without sentiment if analysis fails)

### 3.3 Economic Calendar Enhancement

**Current State:**

- ✅ `EconomicCalendarCollector` exists using MyFXBook scraper
- ✅ `economic_calendar` table exists with TimescaleDB hypertable
- ✅ `insert_economic_calendar_data()` method exists
- ✅ `FeatureEngine.extract_economic_features()` uses economic calendar data
- ❌ No FRED API integration
- ❌ No historical backfill capability

**Implementation Tasks:**

1. **Enhance economic calendar collector**

- Enhance `src/trading_server/src/infrastructure/collectors/economic_calendar_collector.py`:
  - Add historical backfill capability
  - Support multiple sources (MyFXBook, ForexFactory, Investing.com)
  - Add event impact scoring (high, medium, low)
  - Store event metadata (country, currency affected)

2. **Create FRED API connector (placeholder for now)**

- Create `src/trading_server/src/connectors/fred_connector.py` (structure only)
- Will be fully implemented in Week 11-12
- Prepare for US economic indicators integration

## Week 11-12: Social Media & Macro Data

### 3.4 Macroeconomic Indicators

**Implementation Tasks:**

1. **Create FRED API connector**

- Create `src/trading_server/src/connectors/fred_connector.py`
- Implement `IDataSourceConnector` interface
- Use `pandas_datareader` or `fredapi` library for FRED API access
- Key indicators to collect:
  - **Interest Rates**: FEDFUNDS (Federal Funds Rate), DFF (Daily Federal Funds Rate)
  - **Employment**: UNRATE (Unemployment Rate), PAYEMS (Nonfarm Payrolls)
  - **Inflation**: CPIAUCSL (CPI), PCEPI (PCE Price Index)
  - **GDP**: GDP (Gross Domestic Product), GDPC1 (Real GDP)
  - **Manufacturing**: INDPRO (Industrial Production Index)
  - **Consumer**: UMCSENT (Consumer Sentiment Index)
- Methods:
  - `stream()` - Poll FRED API for latest data (daily)
  - `backfill()` - Fetch historical data (decades available)
  - `get_available_range()` - Query available date range per series
- Rate limiting: FRED API allows 120 requests/minute (free tier)
- Normalize to economic indicator event format

2. **Create World Bank API connector**

- Create `src/trading_server/src/connectors/world_bank_connector.py`
- Implement `IDataSourceConnector` interface
- Use `wbdata` or `pandas_datareader` library
- Key indicators:
  - GDP growth rates by country
  - Inflation rates by country
  - Trade balance data
  - Currency exchange rates (official)
- Support multiple countries (US, EU, UK, Japan, etc.)
- Historical data: 50+ years for many indicators
- Normalize to economic indicator event format

3. **Create ECB SDW connector**

- Create `src/trading_server/src/connectors/ecb_connector.py`
- Implement `IDataSourceConnector` interface
- Use ECB Statistical Data Warehouse (SDW) API
- Key indicators:
  - ECB interest rates (DF, MRO, MLF)
  - Eurozone inflation (HICP)
  - Eurozone GDP
  - Eurozone unemployment
- Historical data: 20+ years
- Normalize to economic indicator event format

4. **Create economic_indicators database table**

- Create migration script: `src/database/scripts/20_economic_indicators_table.sql`
- Table structure:
  - `id` (BIGSERIAL)
  - `timestamp` (TIMESTAMPTZ) - indicator publication/reference time
  - `series_id` (VARCHAR) - indicator series identifier (e.g., "FEDFUNDS", "UNRATE")
  - `value` (DECIMAL) - indicator value
  - `source` (VARCHAR) - data source (FRED, WorldBank, ECB)
  - `country` (VARCHAR) - country code (US, EU, etc.)
  - `frequency` (VARCHAR) - data frequency (daily, monthly, quarterly)
  - `receive_time` (TIMESTAMPTZ) - when data was received (bitemporal)
  - `created_at` (TIMESTAMPTZ) - record creation time
- Convert to TimescaleDB hypertable with 1-month chunk interval
- Add indexes: `(series_id, timestamp)`, `(source, timestamp)`, `(country, timestamp)`

5. **Add database methods for economic indicators**

- Enhance `src/trading_server/src/database.py`:
  - `insert_economic_indicator(indicator: Dict[str, Any]) -> bool`
  - `insert_economic_indicators_batch(indicators: List[Dict[str, Any]]) -> int`
  - `get_economic_indicators(series_id: Optional[str] = None, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[Dict]`
  - `get_latest_indicator(series_id: str) -> Optional[Dict]`

### 3.5 Social Media Sentiment (Optional)

**Implementation Tasks:**

1. **Create Reddit connector**

- Create `src/trading_server/src/connectors/reddit_connector.py`
- Implement `IDataSourceConnector` interface
- Use PRAW (Python Reddit API Wrapper)
- Monitor subreddits:
  - r/Forex
  - r/wallstreetbets (for general market sentiment)
  - r/investing
- Collect: post titles, comments, upvotes, timestamps
- Apply sentiment analysis to posts/comments
- Rate limiting: Reddit API allows 60 requests/minute
- Historical data: Limited (can backfill recent posts via API)

2. **Create Twitter/X connector (optional, requires API access)**

- Create `src/trading_server/src/connectors/twitter_connector.py`
- Implement `IDataSourceConnector` interface
- Use Twitter API v2 (requires API key)
- Monitor keywords: "forex", "currency", "EURUSD", "GBPUSD", etc.
- Collect: tweets, retweets, likes, timestamps
- Apply sentiment analysis
- Rate limiting: Depends on API tier
- Historical data: Limited (7 days free tier, more with paid)

3. **Create sentiment aggregator**

- Create `src/trading_server/src/utils/sentiment_aggregator.py`
- Implement `SentimentAggregator` class:
  - Aggregate sentiment across sources (news, Reddit, Twitter)
  - Time-window aggregation (1h, 4h, 24h)
  - Weighted aggregation (news > social media)
  - Per-symbol sentiment aggregation
- Methods:
  - `aggregate_sentiment(symbol: str, time_window: timedelta) -> Dict[str, float]`
  - `get_sentiment_timeseries(symbol: str, start_time: datetime, end_time: datetime) -> pd.DataFrame`
- Store aggregated sentiment in Redis for real-time access

### 3.6 Feature Engineering Integration

**Implementation Tasks:**

1. **Integrate alternative data into FeatureEngine**

- Enhance `src/trading_server/src/application/environment/feature_engine.py`:
  - Add `extract_news_features(symbol: str, current_time: datetime) -> Dict[str, float]`:
    - `news_sentiment_1h` - Average sentiment in last hour
    - `news_sentiment_24h` - Average sentiment in last 24 hours
    - `news_volume_24h` - Number of news articles in last 24 hours
    - `high_impact_news_count_24h` - Count of high-impact news
    - `news_sentiment_momentum` - Change in sentiment over time
  - Add `extract_social_sentiment_features(symbol: str, current_time: datetime) -> Dict[str, float]`:
    - `reddit_sentiment_24h` - Reddit sentiment (if available)
    - `twitter_sentiment_24h` - Twitter sentiment (if available)
    - `social_mention_velocity` - Rate of social media mentions
  - Add `extract_macro_features(symbol: str, current_time: datetime) -> Dict[str, float]`:
    - `fed_funds_rate` - Current Federal Funds Rate
    - `unemployment_rate` - Latest unemployment rate
    - `cpi_yoy` - Year-over-year CPI
    - `gdp_growth_rate` - Latest GDP growth rate
    - `interest_rate_differential` - Rate differential between base/quote currencies
  - Ensure point-in-time computation (no lookahead bias)
  - Use latency buffers for real-time data

2. **Update FeatureCatalog**

- Add new features to `FeatureCatalog`:
  - News sentiment features
  - Social media sentiment features
  - Macroeconomic indicator features
- Update feature metadata (source, category, description)

## Implementation Details

### Database Schema

**news_articles table:**

```sql
CREATE TABLE IF NOT EXISTS news_articles (
    id BIGSERIAL NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    source VARCHAR(100) NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    url VARCHAR(500),
    symbol VARCHAR(10),
    sentiment_score FLOAT,
    sentiment_label VARCHAR(20),
    entities JSONB,
    receive_time TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, timestamp)
);

SELECT create_hypertable('news_articles', 'timestamp', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

CREATE INDEX idx_news_timestamp ON news_articles(timestamp);
CREATE INDEX idx_news_symbol_timestamp ON news_articles(symbol, timestamp);
CREATE INDEX idx_news_source_timestamp ON news_articles(source, timestamp);
```

**economic_indicators table:**

```sql
CREATE TABLE IF NOT EXISTS economic_indicators (
    id BIGSERIAL NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    series_id VARCHAR(50) NOT NULL,
    value DECIMAL(18, 6) NOT NULL,
    source VARCHAR(50) NOT NULL,
    country VARCHAR(10),
    frequency VARCHAR(20),
    receive_time TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, timestamp)
);

SELECT create_hypertable('economic_indicators', 'timestamp',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE);

CREATE INDEX idx_econ_series_timestamp ON economic_indicators(series_id, timestamp);
CREATE INDEX idx_econ_source_timestamp ON economic_indicators(source, timestamp);
CREATE INDEX idx_econ_country_timestamp ON economic_indicators(country, timestamp);
```

### Connector Structure

```
src/trading_server/src/connectors/
├── news_api_connector.py      # NewsAPI integration
├── rss_feed_connector.py       # RSS feed integration
├── fred_connector.py           # FRED API integration
├── world_bank_connector.py     # World Bank API integration
├── ecb_connector.py            # ECB SDW integration
├── reddit_connector.py         # Reddit API integration
└── twitter_connector.py        # Twitter API integration (optional)
```

### Sentiment Analysis Structure

```
src/trading_server/src/utils/
├── sentiment_analyzer.py       # FinBERT-based sentiment analysis
├── entity_extractor.py         # NER for currency pairs and events
└── sentiment_aggregator.py     # Multi-source sentiment aggregation
```

### Requirements Updates

Add to `src/trading_server/requirements.txt`:

- `transformers==4.35.0` - For FinBERT sentiment analysis
- `torch==2.1.0` - PyTorch for transformers
- `feedparser==6.0.10` - RSS feed parsing
- `pandas-datareader==0.10.0` - FRED API access
- `fredapi==0.5.1` - Alternative FRED API client
- `wbdata==0.3.0` - World Bank API client
- `praw==7.7.1` - Reddit API wrapper
- `tweepy==4.14.0` - Twitter API wrapper (optional)
- `spacy==3.7.0` - Named entity recognition
- `flair==0.13.0` - Alternative NER library

### Airflow DAG Integration

Create `src/trading_server/src/infrastructure/data_pipeline/airflow/dags/alternative_data_collection.py`:

- Hourly news collection task
- Daily economic indicators collection task
- Weekly social media sentiment collection task (if enabled)
- Historical backfill tasks for all sources

## Success Criteria

- [ ] `news_articles` table created and converted to TimescaleDB hypertable
- [ ] `economic_indicators` table created and converted to TimescaleDB hypertable
- [ ] NewsAPI connector streaming news in real-time
- [ ] RSS feed connector collecting from multiple sources
- [ ] Sentiment analysis pipeline operational (FinBERT)
- [ ] Entity extraction working (currency pairs, events)
- [ ] FRED connector collecting US economic indicators
- [ ] World Bank connector collecting global indicators
- [ ] ECB connector collecting Eurozone indicators
- [ ] Reddit connector collecting social sentiment (optional)
- [ ] Twitter connector collecting social sentiment (optional)
- [ ] Sentiment aggregator combining multiple sources
- [ ] Alternative data features integrated into FeatureEngine
- [ ] Point-in-time computation verified for all features
- [ ] Historical backfill working for all API-based sources
- [ ] Unit tests for all connectors and utilities
- [ ] Integration tests for end-to-end data flow

## Dependencies

- Phase 1 infrastructure (Airflow, Celery, Redis) must be operational
- Phase 2 market data collection should be stable
- Database connection pool from Phase 1
- Existing `EventNormalizer` for news normalization
- Existing `FeatureEngine` for feature integration

## Testing Strategy

- **Unit Tests:**
  - Test sentiment analyzer with sample financial texts
  - Test entity extractor with news articles
  - Test each connector's normalization logic
  - Test database insertion methods

- **Integration Tests:**
  - Test end-to-end news collection → sentiment analysis → database storage
  - Test economic indicator collection → database storage
  - Test feature extraction with alternative data
  - Test point-in-time constraints (no lookahead bias)

- **API Tests:**
  - Mock API responses for connectors
  - Test rate limiting and retry logic
  - Test error handling for API failures

- **Data Quality Tests:**
  - Verify sentiment scores are in valid range (-1 to 1)
  - Verify entity extraction accuracy
  - Verify economic indicator values are reasonable
  - Check for data gaps and missing values

## Risk Mitigation

1. **API Rate Limits:**

   - Implement aggressive caching in Redis
   - Use multiple API keys where possible
   - Respect rate limits with exponential backoff

2. **Sentiment Analysis Performance:**

   - Use batch processing for efficiency
   - Cache model loading (singleton)
   - Consider GPU acceleration for large batches

3. **Data Quality:**

   - Validate sentiment scores before storage
   - Handle missing data gracefully
   - Monitor data freshness

4. **Cost Management:**

   - NewsAPI free tier: 100 requests/day (upgrade if needed)
   - Twitter API: Requires paid tier for production use
   - Monitor API usage and costs

## Implementation Examples

### NewsAPI Connector Example

```python
# src/trading_server/src/connectors/news_api_connector.py

from typing import Iterator, Dict, Any, Optional
from datetime import datetime, timedelta
import requests
import time
from .base import IDataSourceConnector, ConnectorConfig
from events.normalizer import EventNormalizer
from utils.sentiment_analyzer import SentimentAnalyzer
from utils.entity_extractor import EntityExtractor

class NewsAPIConnector(IDataSourceConnector):
    """NewsAPI connector with sentiment analysis"""
    
    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.api_key = config.extra_config.get("api_key")
        self.normalizer = EventNormalizer()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.entity_extractor = EntityExtractor()
        self._is_connected = False
    
    def connect(self) -> bool:
        """Connect to NewsAPI"""
        try:
            # Test API key
            response = requests.get(
                "https://newsapi.org/v2/top-headlines",
                params={"apiKey": self.api_key, "country": "us", "pageSize": 1},
                timeout=self.config.timeout
            )
            response.raise_for_status()
            self._is_connected = True
            return True
        except Exception as e:
            return False
    
    def stream(self, start_time: Optional[datetime] = None) -> Iterator[Dict[str, Any]]:
        """Stream real-time news"""
        if not self._is_connected:
            raise ConnectionError("Not connected to NewsAPI")
        
        url = "https://newsapi.org/v2/everything"
        params = {
            "apiKey": self.api_key,
            "q": "forex OR currency OR trading OR central bank",
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": 100
        }
        
        while True:
            try:
                response = requests.get(url, params=params, timeout=self.config.timeout)
                response.raise_for_status()
                data = response.json()
                
                for article in data.get("articles", []):
                    # Analyze sentiment
                    text = f"{article.get('title', '')} {article.get('description', '')}"
                    sentiment = self.sentiment_analyzer.analyze_sentiment(text)
                    
                    # Extract entities
                    entities = self.entity_extractor.extract_entities(text)
                    currency_pairs = self.entity_extractor.extract_currency_pairs(text)
                    
                    # Normalize event
                    event = {
                        "timestamp": datetime.fromisoformat(article["publishedAt"].replace("Z", "+00:00")),
                        "source": "newsapi",
                        "title": article.get("title", ""),
                        "content": article.get("description", ""),
                        "url": article.get("url", ""),
                        "symbol": currency_pairs[0] if currency_pairs else "*",
                        "sentiment_score": sentiment["score"],
                        "sentiment_label": sentiment["label"],
                        "entities": entities
                    }
                    
                    normalized = self.normalizer.normalize(event, source="news")
                    yield normalized
                
                # Rate limiting: wait 15 minutes between requests (free tier: 100/day)
                time.sleep(900)
                
            except Exception as e:
                # Log error and retry
                time.sleep(60)
                continue
    
    def batch(self, start_time: datetime, end_time: datetime) -> Iterator[Dict[str, Any]]:
        """Fetch historical news from database"""
        # Implementation would query database for news in time range
        pass
    
    def backfill(self, start_time: datetime, end_time: datetime) -> Iterator[Dict[str, Any]]:
        """Backfill historical news (requires paid tier)"""
        # NewsAPI free tier doesn't support historical data
        # Would need paid tier or web scraping alternative
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """Return news data schema"""
        return {
            "data_type": "news",
            "fields": ["timestamp", "source", "title", "content", "url", "symbol", 
                      "sentiment_score", "sentiment_label", "entities"]
        }
    
    def get_latest_timestamp(self) -> Optional[datetime]:
        """Get latest news timestamp"""
        # Query database for latest news article timestamp
        pass
    
    def disconnect(self) -> None:
        """Disconnect from NewsAPI"""
        self._is_connected = False
    
    def is_connected(self) -> bool:
        """Check connection status"""
        return self._is_connected
```

### Sentiment Analyzer Example

```python
# src/trading_server/src/utils/sentiment_analyzer.py

from typing import Dict, Any, List
from transformers import pipeline
import logging

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """FinBERT-based sentiment analyzer for financial text"""
    
    _instance = None
    _model = None
    
    def __new__(cls):
        """Singleton pattern for model loading"""
        if cls._instance is None:
            cls._instance = super(SentimentAnalyzer, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize sentiment analyzer"""
        if self._model is None:
            try:
                # Use FinBERT model for financial sentiment
                self._model = pipeline(
                    "sentiment-analysis",
                    model="ProsusAI/finbert",
                    device=-1  # CPU, use 0 for GPU if available
                )
                logger.info("FinBERT model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load FinBERT model: {e}")
                raise
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of financial text
        
        :param text: Text to analyze
        :return: Dict with score, label, and confidence
        """
        if not text or len(text.strip()) == 0:
            return {"score": 0.0, "label": "neutral", "confidence": 0.0}
        
        try:
            result = self._model(text[:512])  # Limit to 512 tokens
            label = result[0]["label"].upper()
            score = result[0]["score"]
            
            # Convert to -1 to 1 scale
            if label == "POSITIVE":
                normalized_score = score
            elif label == "NEGATIVE":
                normalized_score = -score
            else:
                normalized_score = 0.0
            
            return {
                "score": normalized_score,
                "label": label.lower(),
                "confidence": score
            }
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return {"score": 0.0, "label": "neutral", "confidence": 0.0}
    
    def analyze_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Analyze sentiment for multiple texts (batch processing)
        
        :param texts: List of texts to analyze
        :return: List of sentiment results
        """
        results = []
        for text in texts:
            results.append(self.analyze_sentiment(text))
        return results
```

### FRED Connector Example

```python
# src/trading_server/src/connectors/fred_connector.py

from typing import Iterator, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas_datareader.data as web
import logging
from .base import IDataSourceConnector, ConnectorConfig
from events.normalizer import EventNormalizer

logger = logging.getLogger(__name__)

class FREDConnector(IDataSourceConnector):
    """FRED API connector for US economic indicators"""
    
    # Key FRED series IDs
    SERIES_IDS = {
        "FEDFUNDS": "Federal Funds Rate",
        "UNRATE": "Unemployment Rate",
        "CPIAUCSL": "Consumer Price Index",
        "GDP": "Gross Domestic Product",
        "PAYEMS": "Nonfarm Payrolls",
        "INDPRO": "Industrial Production Index"
    }
    
    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.api_key = config.extra_config.get("api_key")  # Optional for FRED
        self.normalizer = EventNormalizer()
        self._is_connected = True  # FRED doesn't require connection
    
    def connect(self) -> bool:
        """FRED API doesn't require explicit connection"""
        return True
    
    def stream(self, start_time: Optional[datetime] = None) -> Iterator[Dict[str, Any]]:
        """Stream latest economic indicators (daily)"""
        for series_id, description in self.SERIES_IDS.items():
            try:
                # Fetch latest data
                data = web.DataReader(series_id, "fred", start=datetime.now() - timedelta(days=365))
                
                if data.empty:
                    continue
                
                # Get latest value
                latest = data.iloc[-1]
                latest_date = data.index[-1]
                
                # Normalize event
                event = {
                    "timestamp": latest_date.to_pydatetime(),
                    "series_id": series_id,
                    "value": float(latest),
                    "source": "FRED",
                    "country": "US",
                    "frequency": "daily" if series_id == "DFF" else "monthly"
                }
                
                normalized = self.normalizer.normalize(event, source="fred")
                yield normalized
                
            except Exception as e:
                logger.error(f"Error fetching {series_id}: {e}")
                continue
    
    def backfill(self, start_time: datetime, end_time: datetime) -> Iterator[Dict[str, Any]]:
        """Backfill historical economic indicators"""
        for series_id, description in self.SERIES_IDS.items():
            try:
                data = web.DataReader(series_id, "fred", start=start_time, end=end_time)
                
                for date, value in data.iterrows():
                    event = {
                        "timestamp": date.to_pydatetime(),
                        "series_id": series_id,
                        "value": float(value.iloc[0]),
                        "source": "FRED",
                        "country": "US",
                        "frequency": "daily" if series_id == "DFF" else "monthly"
                    }
                    
                    normalized = self.normalizer.normalize(event, source="fred")
                    yield normalized
                    
            except Exception as e:
                logger.error(f"Error backfilling {series_id}: {e}")
                continue
    
    def get_available_range(self) -> Tuple[datetime, datetime]:
        """Get available date range for FRED data"""
        # FRED has decades of historical data
        return datetime(1950, 1, 1), datetime.now()
    
    def get_schema(self) -> Dict[str, Any]:
        """Return economic indicator schema"""
        return {
            "data_type": "economic_indicator",
            "fields": ["timestamp", "series_id", "value", "source", "country", "frequency"]
        }
    
    def get_latest_timestamp(self) -> Optional[datetime]:
        """Get latest indicator timestamp"""
        # Query database for latest FRED data timestamp
        pass
    
    def disconnect(self) -> None:
        """No-op for FRED"""
        pass
    
    def is_connected(self) -> bool:
        """FRED is always available"""
        return True
```

## Next Steps After Phase 3

- **Phase 4: Historical Data Backfill (Weeks 13-16)**
  - Backfill historical news (where available via paid APIs or web scraping)
  - Backfill historical economic indicators (decades available from FRED, World Bank, ECB)
  - Backfill historical social media (limited, consider purchasing datasets)
  - Create comprehensive backfill orchestration scripts
  - Validate historical data quality and completeness

- **Phase 5: AI-Powered Data Extraction (Weeks 17-20)**
  - Web crawling infrastructure for unstructured data
  - Document analysis (PDF, OCR) for financial reports
  - NLP pipelines for earnings call transcripts
  - Central bank statement analysis

- **Phase 6: Scale & Optimization (Weeks 21-24)**
  - Performance optimization for sentiment analysis
  - Horizontal scaling for data collection
  - Advanced caching strategies
  - Cost optimization for API usage