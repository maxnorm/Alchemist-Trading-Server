USE db_forex;

-- Migration: Add bitemporal columns to ticks_forex table
-- This migration adds support for tracking both event_time (when event occurred)
-- and receive_time (when we received it) to enable point-in-time queries and
-- eliminate look-ahead bias in training.

-- Add bitemporal timestamp columns
ALTER TABLE ticks_forex 
ADD COLUMN receive_time DATETIME NULL COMMENT 'Transaction time (when received)',
ADD COLUMN latency_seconds INT NULL COMMENT 'Delay: receive_time - datetime',
ADD COLUMN is_stale BOOLEAN DEFAULT FALSE COMMENT 'Flag if original timestamp was stale',
ADD COLUMN stale_age_seconds INT NULL COMMENT 'Age of stale timestamp',
ADD COLUMN timestamp_source VARCHAR(20) DEFAULT 'event' COMMENT 'event, receive, estimated';

-- Add indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_receive_time ON ticks_forex(receive_time);
CREATE INDEX IF NOT EXISTS idx_latency ON ticks_forex(latency_seconds);
CREATE INDEX IF NOT EXISTS idx_is_stale ON ticks_forex(is_stale);

-- Backfill receive_time for existing data (use created_at as proxy)
-- This provides a reasonable estimate for historical data
UPDATE ticks_forex 
SET receive_time = created_at,
    latency_seconds = TIMESTAMPDIFF(SECOND, datetime, created_at),
    timestamp_source = 'estimated'
WHERE receive_time IS NULL;
