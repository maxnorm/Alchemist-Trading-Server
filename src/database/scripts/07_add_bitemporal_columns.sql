-- Migration: Add bitemporal columns to ticks_forex table
-- This migration adds support for tracking both event_time (when event occurred)
-- and receive_time (when we received it) to enable point-in-time queries and
-- eliminate look-ahead bias in training.

-- Add bitemporal timestamp columns
ALTER TABLE ticks_forex 
ADD COLUMN IF NOT EXISTS receive_time TIMESTAMP NULL,
ADD COLUMN IF NOT EXISTS latency_seconds INT NULL,
ADD COLUMN IF NOT EXISTS is_stale BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS stale_age_seconds INT NULL,
ADD COLUMN IF NOT EXISTS timestamp_source VARCHAR(20) DEFAULT 'event';

-- Add indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_receive_time ON ticks_forex(receive_time);
CREATE INDEX IF NOT EXISTS idx_latency ON ticks_forex(latency_seconds);
CREATE INDEX IF NOT EXISTS idx_is_stale ON ticks_forex(is_stale);

-- Add comments to columns
COMMENT ON COLUMN ticks_forex.receive_time IS 'Transaction time (when received)';
COMMENT ON COLUMN ticks_forex.latency_seconds IS 'Delay: receive_time - datetime';
COMMENT ON COLUMN ticks_forex.is_stale IS 'Flag if original timestamp was stale';
COMMENT ON COLUMN ticks_forex.stale_age_seconds IS 'Age of stale timestamp';
COMMENT ON COLUMN ticks_forex.timestamp_source IS 'event, receive, estimated';

-- Backfill receive_time for existing data (use created_at as proxy)
-- This provides a reasonable estimate for historical data
UPDATE ticks_forex 
SET receive_time = created_at,
    latency_seconds = EXTRACT(EPOCH FROM (created_at - datetime))::INTEGER,
    timestamp_source = 'estimated'
WHERE receive_time IS NULL;
