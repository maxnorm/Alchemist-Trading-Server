-- Migration: Create news_articles table for news article data
-- This table stores news articles from multiple sources (RSS, web scraping, NewsAPI)

CREATE TABLE IF NOT EXISTS news_articles(
    id BIGSERIAL NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    source VARCHAR(100) NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    url VARCHAR(1000) NOT NULL,
    symbol VARCHAR(6),
    sentiment_score DOUBLE PRECISION,
    sentiment_label VARCHAR(20),
    entities JSONB,
    receive_time TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL,
    CONSTRAINT sentiment_label_check CHECK (sentiment_label IN ('positive', 'negative', 'neutral', NULL)),
    CONSTRAINT url_length_check CHECK (LENGTH(url) > 0 AND LENGTH(url) <= 1000),
    CONSTRAINT title_length_check CHECK (LENGTH(title) > 0 AND LENGTH(title) <= 500)
);

-- Add bitemporal columns (for consistency with other tables)
ALTER TABLE news_articles
ADD COLUMN IF NOT EXISTS latency_seconds INT NULL,
ADD COLUMN IF NOT EXISTS is_stale BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS stale_age_seconds INT NULL,
ADD COLUMN IF NOT EXISTS timestamp_source VARCHAR(20) DEFAULT 'event';

-- Add schema versioning columns (for consistency with Phase 1)
ALTER TABLE news_articles
ADD COLUMN IF NOT EXISTS schema_version VARCHAR(20) DEFAULT '1.0.0',
ADD COLUMN IF NOT EXISTS schema_type VARCHAR(50) DEFAULT 'news';

-- Add indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_news_articles_timestamp 
    ON news_articles(timestamp);
CREATE INDEX IF NOT EXISTS idx_news_articles_symbol_timestamp 
    ON news_articles(symbol, timestamp) WHERE symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_news_articles_source_timestamp 
    ON news_articles(source, timestamp);
CREATE INDEX IF NOT EXISTS idx_news_articles_url 
    ON news_articles(url);
CREATE INDEX IF NOT EXISTS idx_news_articles_receive_time 
    ON news_articles(receive_time);
CREATE INDEX IF NOT EXISTS idx_news_articles_schema_version 
    ON news_articles(schema_version, schema_type);
CREATE INDEX IF NOT EXISTS idx_news_articles_sentiment 
    ON news_articles(sentiment_label, timestamp) WHERE sentiment_label IS NOT NULL;

-- Add trigger for updated_at column
CREATE TRIGGER update_news_articles_updated_at
    BEFORE UPDATE ON news_articles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments
COMMENT ON TABLE news_articles IS 'News articles from multiple sources (RSS, web scraping, NewsAPI)';
COMMENT ON COLUMN news_articles.timestamp IS 'Event time (article publication time)';
COMMENT ON COLUMN news_articles.source IS 'News source identifier (e.g., "reuters", "bloomberg", "rss")';
COMMENT ON COLUMN news_articles.title IS 'Article headline (max 500 characters)';
COMMENT ON COLUMN news_articles.content IS 'Full article content (optional, max 10000 characters)';
COMMENT ON COLUMN news_articles.url IS 'Article URL (unique for deduplication)';
COMMENT ON COLUMN news_articles.symbol IS 'Trading symbol if article is symbol-specific (nullable)';
COMMENT ON COLUMN news_articles.sentiment_score IS 'Sentiment score (-1 to 1)';
COMMENT ON COLUMN news_articles.sentiment_label IS 'Sentiment label: positive, negative, neutral';
COMMENT ON COLUMN news_articles.entities IS 'Extracted entities (currency pairs, events) as JSONB';
COMMENT ON COLUMN news_articles.receive_time IS 'Transaction time (when received)';
COMMENT ON COLUMN news_articles.latency_seconds IS 'Delay: receive_time - timestamp';
COMMENT ON COLUMN news_articles.is_stale IS 'Flag if original timestamp was stale';
COMMENT ON COLUMN news_articles.stale_age_seconds IS 'Age of stale timestamp';
COMMENT ON COLUMN news_articles.timestamp_source IS 'event, receive, estimated';
COMMENT ON COLUMN news_articles.schema_version IS 'Schema contract version used when data was ingested';
COMMENT ON COLUMN news_articles.schema_type IS 'Data type identifier (news)';

-- Convert to TimescaleDB hypertable (1-day chunk interval)
SELECT create_hypertable('news_articles', 'timestamp', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Create composite unique index (id, timestamp) for TimescaleDB compatibility
CREATE UNIQUE INDEX IF NOT EXISTS news_articles_id_timestamp_unique 
    ON news_articles(id, timestamp);

-- Note: Cannot create unique index on URL alone for TimescaleDB hypertables
-- Unique indexes on hypertables must include the partitioning column (timestamp)
-- URL deduplication is handled in application code (see database.py insert_news_article)
-- The regular index on url (line 42-43) is sufficient for fast lookups

-- Add foreign key to forex_pairs if symbol is provided (nullable)
ALTER TABLE news_articles
ADD COLUMN IF NOT EXISTS forex_pairs_id INT NULL,
ADD CONSTRAINT forex_pairs_id_news
    FOREIGN KEY (forex_pairs_id)
    REFERENCES forex_pairs(id)
    ON UPDATE CASCADE ON DELETE RESTRICT;

-- Add index for foreign key
CREATE INDEX IF NOT EXISTS idx_news_articles_forex_pairs_id 
    ON news_articles(forex_pairs_id) WHERE forex_pairs_id IS NOT NULL;
