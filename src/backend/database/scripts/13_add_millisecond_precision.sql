-- Migration: Add fractional seconds precision to datetime columns in ticks_forex
-- This migration changes TIMESTAMP to TIMESTAMP(6) to preserve microseconds
-- from Python datetime objects, enabling millisecond-level precision for tick data.

-- Modify datetime column to support microseconds (6 fractional digits)
-- TIMESTAMP(6) can store: YYYY-MM-DD HH:MM:SS.ffffff
ALTER TABLE ticks_forex 
ALTER COLUMN datetime TYPE TIMESTAMP(6);

-- Modify receive_time column to support microseconds (6 fractional digits) if it exists
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'ticks_forex' AND column_name = 'receive_time') THEN
        ALTER TABLE ticks_forex 
        ALTER COLUMN receive_time TYPE TIMESTAMP(6);
    END IF;
END $$;

-- Add comments to columns
COMMENT ON COLUMN ticks_forex.datetime IS 'Event time with microsecond precision';
COMMENT ON COLUMN ticks_forex.receive_time IS 'Transaction time (when received) with microsecond precision';

-- Note: Existing data will be preserved, but fractional seconds will remain NULL/0
-- New inserts will now preserve microsecond precision from Python datetime objects
