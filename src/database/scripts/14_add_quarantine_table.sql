USE db_forex;

-- Migration: Add quarantine_ticks table for storing rejected ticks
-- This migration creates a table to capture all ticks rejected by quality gates
-- for review and analysis, enabling data quality monitoring and improvement.

-- Create quarantine_ticks table
CREATE TABLE IF NOT EXISTS quarantine_ticks (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    symbol VARCHAR(6) NOT NULL COMMENT 'Currency pair symbol (e.g., EURUSD)',
    datetime DATETIME(6) NOT NULL COMMENT 'Event time with microsecond precision',
    receive_time DATETIME(6) NULL COMMENT 'When tick was received (transaction time)',
    bid DOUBLE NOT NULL COMMENT 'Bid price',
    ask DOUBLE NOT NULL COMMENT 'Ask price',
    rejection_reason TEXT NOT NULL COMMENT 'Detailed reason for rejection',
    rejection_category VARCHAR(50) NOT NULL COMMENT 'Categorized reason: outlier, duplicate, stale, missing_data, invalid_spread',
    quarantined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'When tick was quarantined',
    INDEX idx_symbol (symbol),
    INDEX idx_datetime (datetime),
    INDEX idx_rejection_category (rejection_category),
    INDEX idx_quarantined_at (quarantined_at),
    INDEX idx_symbol_datetime (symbol, datetime)
) COMMENT='Quarantine table for ticks rejected by quality gates';
