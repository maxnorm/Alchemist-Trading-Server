-- Migration script for schema contracts and versioning
-- Blocker A2: Schema Contracts - Database schema versioning support

-- Create schema_contracts table to track contract definitions
CREATE TABLE IF NOT EXISTS schema_contracts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    data_type VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- 'active', 'deprecated', 'archived'
    description TEXT,
    contract_definition JSON NOT NULL,  -- Full contract definition (fields, constraints, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_type_version (data_type, version),
    INDEX idx_data_type (data_type),
    INDEX idx_status (status)
);

-- Add comment to table
ALTER TABLE schema_contracts COMMENT = 'Schema contract registry tracking all data type contract definitions and versions';

-- Add schema versioning columns to ticks_forex table
ALTER TABLE ticks_forex
ADD COLUMN IF NOT EXISTS schema_version VARCHAR(20) DEFAULT '1.0.0',
ADD COLUMN IF NOT EXISTS schema_type VARCHAR(50) DEFAULT 'tick';

-- Create index for schema version queries
CREATE INDEX IF NOT EXISTS idx_schema_version ON ticks_forex(schema_version, schema_type);

-- Add comments to columns
ALTER TABLE ticks_forex MODIFY COLUMN schema_version VARCHAR(20) COMMENT 'Schema contract version used when data was ingested';
ALTER TABLE ticks_forex MODIFY COLUMN schema_type VARCHAR(50) COMMENT 'Data type identifier (e.g., tick, bar, news)';

-- Insert initial contract definitions
INSERT INTO schema_contracts (data_type, version, status, description, contract_definition) VALUES
(
    'tick',
    '1.0.0',
    'active',
    'Tick data contract v1.0.0 - Real-time price tick data for currency pairs',
    JSON_OBJECT(
        'data_type', 'tick',
        'version', '1.0.0',
        'required_fields', JSON_ARRAY('symbol', 'datetime', 'bid', 'ask'),
        'optional_fields', JSON_ARRAY('receive_time', 'latency_seconds', 'is_stale', 'stale_age_seconds', 'timestamp_source', 'volume'),
        'fields', JSON_OBJECT(
            'symbol', JSON_OBJECT('type', 'string', 'format', 'Uppercase 6 chars', 'required', true),
            'datetime', JSON_OBJECT('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', true),
            'bid', JSON_OBJECT('type', 'float', 'unit', 'Price', 'required', true, 'constraints', JSON_ARRAY('bid > 0', 'bid < ask')),
            'ask', JSON_OBJECT('type', 'float', 'unit', 'Price', 'required', true, 'constraints', JSON_ARRAY('ask > 0', 'ask > bid')),
            'receive_time', JSON_OBJECT('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', false),
            'latency_seconds', JSON_OBJECT('type', 'integer', 'unit', 'Seconds', 'required', false, 'constraints', JSON_ARRAY('>= 0')),
            'is_stale', JSON_OBJECT('type', 'boolean', 'required', false),
            'stale_age_seconds', JSON_OBJECT('type', 'integer', 'unit', 'Seconds', 'required', false, 'constraints', JSON_ARRAY('>= 0')),
            'timestamp_source', JSON_OBJECT('type', 'string', 'enum', JSON_ARRAY('event', 'receive', 'estimated'), 'required', false),
            'volume', JSON_OBJECT('type', 'float', 'unit', 'Lots', 'required', false, 'constraints', JSON_ARRAY('>= 0'))
        )
    )
),
(
    'bar',
    '1.0.0',
    'active',
    'Bar/OHLCV data contract v1.0.0 - Aggregated price bars for time-series analysis',
    JSON_OBJECT(
        'data_type', 'bar',
        'version', '1.0.0',
        'required_fields', JSON_ARRAY('symbol', 'datetime', 'open', 'high', 'low', 'close', 'timeframe'),
        'optional_fields', JSON_ARRAY('volume', 'receive_time'),
        'fields', JSON_OBJECT(
            'symbol', JSON_OBJECT('type', 'string', 'format', 'Uppercase 6 chars', 'required', true),
            'datetime', JSON_OBJECT('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', true),
            'open', JSON_OBJECT('type', 'float', 'unit', 'Price', 'required', true, 'constraints', JSON_ARRAY('open > 0')),
            'high', JSON_OBJECT('type', 'float', 'unit', 'Price', 'required', true, 'constraints', JSON_ARRAY('high >= open', 'high >= low', 'high >= close')),
            'low', JSON_OBJECT('type', 'float', 'unit', 'Price', 'required', true, 'constraints', JSON_ARRAY('low > 0', 'low <= open', 'low <= high', 'low <= close')),
            'close', JSON_OBJECT('type', 'float', 'unit', 'Price', 'required', true, 'constraints', JSON_ARRAY('close > 0')),
            'timeframe', JSON_OBJECT('type', 'string', 'enum', JSON_ARRAY('M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'), 'required', true),
            'volume', JSON_OBJECT('type', 'float', 'unit', 'Lots', 'required', false, 'constraints', JSON_ARRAY('>= 0')),
            'receive_time', JSON_OBJECT('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', false)
        )
    )
),
(
    'news',
    '1.0.0',
    'active',
    'News data contract v1.0.0 - News events and announcements affecting markets',
    JSON_OBJECT(
        'data_type', 'news',
        'version', '1.0.0',
        'required_fields', JSON_ARRAY('symbol', 'datetime', 'title', 'source'),
        'optional_fields', JSON_ARRAY('content', 'impact', 'category', 'receive_time'),
        'fields', JSON_OBJECT(
            'symbol', JSON_OBJECT('type', 'string', 'format', 'Uppercase 6 chars or "*"', 'required', true),
            'datetime', JSON_OBJECT('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', true),
            'title', JSON_OBJECT('type', 'string', 'required', true, 'max_length', 500),
            'content', JSON_OBJECT('type', 'string', 'required', false, 'max_length', 10000),
            'source', JSON_OBJECT('type', 'string', 'required', true, 'max_length', 100),
            'impact', JSON_OBJECT('type', 'string', 'enum', JSON_ARRAY('low', 'medium', 'high'), 'required', false),
            'category', JSON_OBJECT('type', 'string', 'required', false),
            'receive_time', JSON_OBJECT('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', false)
        )
    )
),
(
    'economic',
    '1.0.0',
    'active',
    'Economic calendar data contract v1.0.0 - Economic calendar events and indicators',
    JSON_OBJECT(
        'data_type', 'economic',
        'version', '1.0.0',
        'required_fields', JSON_ARRAY('datetime', 'country', 'event', 'impact'),
        'optional_fields', JSON_ARRAY('previous', 'consensus', 'actual', 'receive_time'),
        'fields', JSON_OBJECT(
            'datetime', JSON_OBJECT('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', true),
            'country', JSON_OBJECT('type', 'string', 'format', 'ISO country code', 'required', true, 'length', '2-3 chars'),
            'event', JSON_OBJECT('type', 'string', 'required', true, 'max_length', 250),
            'impact', JSON_OBJECT('type', 'integer', 'required', true, 'range', JSON_ARRAY(0, 3)),
            'previous', JSON_OBJECT('type', 'string', 'format', 'Decimal string', 'required', false),
            'consensus', JSON_OBJECT('type', 'string', 'format', 'Decimal string', 'required', false),
            'actual', JSON_OBJECT('type', 'string', 'format', 'Decimal string', 'required', false),
            'receive_time', JSON_OBJECT('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', false)
        )
    )
)
ON DUPLICATE KEY UPDATE
    updated_at = CURRENT_TIMESTAMP;
