-- Migration script for schema contracts and versioning
-- Blocker A2: Schema Contracts - Database schema versioning support

-- Create schema_contracts table to track contract definitions
CREATE TABLE IF NOT EXISTS schema_contracts (
    id SERIAL PRIMARY KEY,
    data_type VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- 'active', 'deprecated', 'archived'
    description TEXT,
    contract_definition JSONB NOT NULL,  -- Full contract definition (fields, constraints, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL,
    UNIQUE (data_type, version)
);

CREATE INDEX IF NOT EXISTS idx_data_type ON schema_contracts(data_type);
CREATE INDEX IF NOT EXISTS idx_status ON schema_contracts(status);

-- Add trigger for updated_at column
CREATE TRIGGER update_schema_contracts_updated_at
    BEFORE UPDATE ON schema_contracts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add comment to table
COMMENT ON TABLE schema_contracts IS 'Schema contract registry tracking all data type contract definitions and versions';

-- Add schema versioning columns to ticks_forex table
ALTER TABLE ticks_forex
ADD COLUMN IF NOT EXISTS schema_version VARCHAR(20) DEFAULT '1.0.0',
ADD COLUMN IF NOT EXISTS schema_type VARCHAR(50) DEFAULT 'tick';

-- Create index for schema version queries
CREATE INDEX IF NOT EXISTS idx_schema_version ON ticks_forex(schema_version, schema_type);

-- Add comments to columns
COMMENT ON COLUMN ticks_forex.schema_version IS 'Schema contract version used when data was ingested';
COMMENT ON COLUMN ticks_forex.schema_type IS 'Data type identifier (e.g., tick, bar, news)';

-- Insert initial contract definitions
INSERT INTO schema_contracts (data_type, version, status, description, contract_definition) VALUES
(
    'tick',
    '1.0.0',
    'active',
    'Tick data contract v1.0.0 - Real-time price tick data for currency pairs',
    jsonb_build_object(
        'data_type', 'tick',
        'version', '1.0.0',
        'required_fields', jsonb_build_array('symbol', 'datetime', 'bid', 'ask'),
        'optional_fields', jsonb_build_array('receive_time', 'latency_seconds', 'is_stale', 'stale_age_seconds', 'timestamp_source', 'volume'),
        'fields', jsonb_build_object(
            'symbol', jsonb_build_object('type', 'string', 'format', 'Uppercase 6 chars', 'required', true),
            'datetime', jsonb_build_object('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', true),
            'bid', jsonb_build_object('type', 'float', 'unit', 'Price', 'required', true, 'constraints', jsonb_build_array('bid > 0', 'bid < ask')),
            'ask', jsonb_build_object('type', 'float', 'unit', 'Price', 'required', true, 'constraints', jsonb_build_array('ask > 0', 'ask > bid')),
            'receive_time', jsonb_build_object('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', false),
            'latency_seconds', jsonb_build_object('type', 'integer', 'unit', 'Seconds', 'required', false, 'constraints', jsonb_build_array('>= 0')),
            'is_stale', jsonb_build_object('type', 'boolean', 'required', false),
            'stale_age_seconds', jsonb_build_object('type', 'integer', 'unit', 'Seconds', 'required', false, 'constraints', jsonb_build_array('>= 0')),
            'timestamp_source', jsonb_build_object('type', 'string', 'enum', jsonb_build_array('event', 'receive', 'estimated'), 'required', false),
            'volume', jsonb_build_object('type', 'float', 'unit', 'Lots', 'required', false, 'constraints', jsonb_build_array('>= 0'))
        )
    )
),
(
    'bar',
    '1.0.0',
    'active',
    'Bar/OHLCV data contract v1.0.0 - Aggregated price bars for time-series analysis',
    jsonb_build_object(
        'data_type', 'bar',
        'version', '1.0.0',
        'required_fields', jsonb_build_array('symbol', 'datetime', 'open', 'high', 'low', 'close', 'timeframe'),
        'optional_fields', jsonb_build_array('volume', 'receive_time'),
        'fields', jsonb_build_object(
            'symbol', jsonb_build_object('type', 'string', 'format', 'Uppercase 6 chars', 'required', true),
            'datetime', jsonb_build_object('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', true),
            'open', jsonb_build_object('type', 'float', 'unit', 'Price', 'required', true, 'constraints', jsonb_build_array('open > 0')),
            'high', jsonb_build_object('type', 'float', 'unit', 'Price', 'required', true, 'constraints', jsonb_build_array('high >= open', 'high >= low', 'high >= close')),
            'low', jsonb_build_object('type', 'float', 'unit', 'Price', 'required', true, 'constraints', jsonb_build_array('low > 0', 'low <= open', 'low <= high', 'low <= close')),
            'close', jsonb_build_object('type', 'float', 'unit', 'Price', 'required', true, 'constraints', jsonb_build_array('close > 0')),
            'timeframe', jsonb_build_object('type', 'string', 'enum', jsonb_build_array('M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'), 'required', true),
            'volume', jsonb_build_object('type', 'float', 'unit', 'Lots', 'required', false, 'constraints', jsonb_build_array('>= 0')),
            'receive_time', jsonb_build_object('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', false)
        )
    )
),
(
    'news',
    '1.0.0',
    'active',
    'News data contract v1.0.0 - News events and announcements affecting markets',
    jsonb_build_object(
        'data_type', 'news',
        'version', '1.0.0',
        'required_fields', jsonb_build_array('symbol', 'datetime', 'title', 'source'),
        'optional_fields', jsonb_build_array('content', 'impact', 'category', 'receive_time'),
        'fields', jsonb_build_object(
            'symbol', jsonb_build_object('type', 'string', 'format', 'Uppercase 6 chars or "*"', 'required', true),
            'datetime', jsonb_build_object('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', true),
            'title', jsonb_build_object('type', 'string', 'required', true, 'max_length', 500),
            'content', jsonb_build_object('type', 'string', 'required', false, 'max_length', 10000),
            'source', jsonb_build_object('type', 'string', 'required', true, 'max_length', 100),
            'impact', jsonb_build_object('type', 'string', 'enum', jsonb_build_array('low', 'medium', 'high'), 'required', false),
            'category', jsonb_build_object('type', 'string', 'required', false),
            'receive_time', jsonb_build_object('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', false)
        )
    )
),
(
    'economic',
    '1.0.0',
    'active',
    'Economic calendar data contract v1.0.0 - Economic calendar events and indicators',
    jsonb_build_object(
        'data_type', 'economic',
        'version', '1.0.0',
        'required_fields', jsonb_build_array('datetime', 'country', 'event', 'impact'),
        'optional_fields', jsonb_build_array('previous', 'consensus', 'actual', 'receive_time'),
        'fields', jsonb_build_object(
            'datetime', jsonb_build_object('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', true),
            'country', jsonb_build_object('type', 'string', 'format', 'ISO country code', 'required', true, 'length', '2-3 chars'),
            'event', jsonb_build_object('type', 'string', 'required', true, 'max_length', 250),
            'impact', jsonb_build_object('type', 'integer', 'required', true, 'range', jsonb_build_array(0, 3)),
            'previous', jsonb_build_object('type', 'string', 'format', 'Decimal string', 'required', false),
            'consensus', jsonb_build_object('type', 'string', 'format', 'Decimal string', 'required', false),
            'actual', jsonb_build_object('type', 'string', 'format', 'Decimal string', 'required', false),
            'receive_time', jsonb_build_object('type', 'datetime', 'unit', 'UTC', 'format', 'ISO 8601', 'required', false)
        )
    )
)
ON CONFLICT (data_type, version) DO UPDATE
    SET updated_at = CURRENT_TIMESTAMP;
