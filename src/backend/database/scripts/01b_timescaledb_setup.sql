-- Converts time-series tables to hypertables for optimized performance
-- Note: For hypertables, unique indexes must include the partitioning column
-- Since id is BIGSERIAL, it will be unique anyway, but we create composite
-- unique indexes (id, datetime) to satisfy TimescaleDB constraints

-- Convert ticks_forex to hypertable
SELECT create_hypertable('ticks_forex', 'datetime', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Create composite unique index (id, datetime) for TimescaleDB compatibility
-- BIGSERIAL ensures id is unique, but TimescaleDB requires partitioning column in unique indexes
CREATE UNIQUE INDEX IF NOT EXISTS ticks_forex_id_datetime_unique ON ticks_forex(id, datetime);

-- Convert economic_calendar to hypertable
SELECT create_hypertable('economic_calendar', 'datetime',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE);

-- Create composite unique index (id, datetime) for TimescaleDB compatibility
CREATE UNIQUE INDEX IF NOT EXISTS economic_calendar_id_datetime_unique ON economic_calendar(id, datetime);

-- Convert equity_curve to hypertable (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'equity_curve') THEN
        PERFORM create_hypertable('equity_curve', 'timestamp',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE);
        
        -- Create composite unique index (id, timestamp) for TimescaleDB compatibility
        CREATE UNIQUE INDEX IF NOT EXISTS equity_curve_id_timestamp_unique ON equity_curve(id, timestamp);
    END IF;
END $$;
