USE db_forex;

-- Migration: Add fractional seconds precision to datetime columns in ticks_forex
-- This migration changes DATETIME to DATETIME(6) to preserve microseconds
-- from Python datetime objects, enabling millisecond-level precision for tick data.

-- Modify datetime column to support microseconds (6 fractional digits)
-- DATETIME(6) can store: YYYY-MM-DD HH:MM:SS.ffffff
ALTER TABLE ticks_forex 
MODIFY COLUMN datetime DATETIME(6) NOT NULL COMMENT 'Event time with microsecond precision';

-- Modify receive_time column to support microseconds (6 fractional digits)
ALTER TABLE ticks_forex 
MODIFY COLUMN receive_time DATETIME(6) NULL COMMENT 'Transaction time (when received) with microsecond precision';

-- Note: Existing data will be preserved, but fractional seconds will remain NULL/0
-- New inserts will now preserve microsecond precision from Python datetime objects
