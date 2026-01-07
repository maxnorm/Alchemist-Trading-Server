-- TimescaleDB setup script
-- Converts time-series tables to hypertables for optimized performance

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Convert ticks_forex to hypertable
SELECT create_hypertable('ticks_forex', 'datetime', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Convert economic_calendar to hypertable
SELECT create_hypertable('economic_calendar', 'datetime',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE);

-- Convert equity_curve to hypertable (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'equity_curve') THEN
        PERFORM create_hypertable('equity_curve', 'timestamp',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE);
    END IF;
END $$;
