-- Diagnostic SQL Queries for Data Collection Pipeline Investigation
-- These queries help analyze negative latency and data gap issues

-- ============================================================================
-- NEGATIVE LATENCY QUERIES
-- ============================================================================

-- 1. Find all negative latency samples with full context
SELECT 
    fp.symbol,
    tf.datetime as event_time,
    tf.receive_time,
    tf.latency_seconds,
    tf.ask,
    tf.bid,
    EXTRACT(HOUR FROM tf.datetime) as hour_of_day,
    EXTRACT(DOW FROM tf.datetime) as day_of_week,
    EXTRACT(EPOCH FROM (tf.receive_time - tf.datetime)) as calculated_latency,
    tf.timestamp_source
FROM ticks_forex tf
JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
WHERE tf.datetime >= NOW() - INTERVAL '48 hours'
AND tf.latency_seconds < 0
ORDER BY tf.latency_seconds ASC, tf.datetime DESC
LIMIT 100;

-- 2. Negative latency statistics by symbol
SELECT 
    fp.symbol,
    COUNT(*) as negative_count,
    MIN(tf.latency_seconds) as min_latency,
    MAX(tf.latency_seconds) as max_latency,
    AVG(tf.latency_seconds) as avg_latency,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tf.latency_seconds) as median_latency
FROM ticks_forex tf
JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
WHERE tf.datetime >= NOW() - INTERVAL '48 hours'
AND tf.latency_seconds < 0
GROUP BY fp.symbol
ORDER BY negative_count DESC;

-- 3. Negative latency by hour of day
SELECT 
    EXTRACT(HOUR FROM tf.datetime) as hour_of_day,
    COUNT(*) as negative_count,
    AVG(tf.latency_seconds) as avg_latency
FROM ticks_forex tf
WHERE tf.datetime >= NOW() - INTERVAL '48 hours'
AND tf.latency_seconds < 0
GROUP BY EXTRACT(HOUR FROM tf.datetime)
ORDER BY hour_of_day;

-- 4. Check if negative latency is systematic (affects all symbols)
SELECT 
    COUNT(DISTINCT fp.symbol) as affected_symbols,
    COUNT(DISTINCT (SELECT COUNT(DISTINCT fp2.symbol) FROM ticks_forex tf2 JOIN forex_pairs fp2 ON tf2.forex_pairs_id = fp2.id WHERE tf2.datetime >= NOW() - INTERVAL '48 hours')) as total_symbols,
    COUNT(DISTINCT fp.symbol)::FLOAT / NULLIF((SELECT COUNT(DISTINCT fp2.symbol) FROM ticks_forex tf2 JOIN forex_pairs fp2 ON tf2.forex_pairs_id = fp2.id WHERE tf2.datetime >= NOW() - INTERVAL '48 hours'), 0) as affected_ratio
FROM ticks_forex tf
JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
WHERE tf.datetime >= NOW() - INTERVAL '48 hours'
AND tf.latency_seconds < 0;

-- 5. Timestamp source distribution for negative latency
SELECT 
    tf.timestamp_source,
    COUNT(*) as total_count,
    COUNT(CASE WHEN tf.latency_seconds < 0 THEN 1 END) as negative_count,
    AVG(tf.latency_seconds) as avg_latency,
    MIN(tf.latency_seconds) as min_latency,
    MAX(tf.latency_seconds) as max_latency
FROM ticks_forex tf
WHERE tf.datetime >= NOW() - INTERVAL '48 hours'
AND tf.receive_time IS NOT NULL
GROUP BY tf.timestamp_source;

-- ============================================================================
-- DATA GAP QUERIES
-- ============================================================================

-- 6. Find all significant gaps (>5 minutes)
WITH tick_intervals AS (
    SELECT 
        fp.symbol,
        tf.datetime,
        LAG(tf.datetime) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime) as prev_datetime,
        EXTRACT(EPOCH FROM (tf.datetime - LAG(tf.datetime) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime))) as gap_seconds,
        EXTRACT(DOW FROM tf.datetime) as day_of_week,
        EXTRACT(HOUR FROM tf.datetime) as hour
    FROM ticks_forex tf
    JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
    WHERE tf.datetime >= NOW() - INTERVAL '48 hours'
)
SELECT 
    symbol,
    prev_datetime,
    datetime,
    gap_seconds,
    gap_seconds / 3600.0 as gap_hours,
    day_of_week,
    hour
FROM tick_intervals
WHERE gap_seconds > 300  -- 5 minutes
ORDER BY gap_seconds DESC;

-- 7. Gap statistics by symbol
WITH tick_intervals AS (
    SELECT 
        fp.symbol,
        EXTRACT(EPOCH FROM (tf.datetime - LAG(tf.datetime) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime))) as gap_seconds
    FROM ticks_forex tf
    JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
    WHERE tf.datetime >= NOW() - INTERVAL '48 hours'
)
SELECT 
    symbol,
    COUNT(*) as gap_count,
    MIN(gap_seconds) as min_gap_seconds,
    MAX(gap_seconds) as max_gap_seconds,
    AVG(gap_seconds) as avg_gap_seconds,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY gap_seconds) as p95_gap_seconds
FROM tick_intervals
WHERE gap_seconds > 300  -- 5 minutes
GROUP BY symbol
ORDER BY gap_count DESC;

-- 8. Gap analysis by day of week (to detect market hours correlation)
WITH tick_intervals AS (
    SELECT 
        fp.symbol,
        tf.datetime,
        LAG(tf.datetime) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime) as prev_datetime,
        EXTRACT(EPOCH FROM (tf.datetime - LAG(tf.datetime) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime))) as gap_seconds,
        EXTRACT(DOW FROM tf.datetime) as day_of_week
    FROM ticks_forex tf
    JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
    WHERE tf.datetime >= NOW() - INTERVAL '48 hours'
)
SELECT 
    day_of_week,
    COUNT(*) as gap_count,
    AVG(gap_seconds / 3600.0) as avg_gap_hours,
    MAX(gap_seconds / 3600.0) as max_gap_hours
FROM tick_intervals
WHERE gap_seconds > 300  -- 5 minutes
GROUP BY day_of_week
ORDER BY day_of_week;

-- 9. Check for simultaneous gaps (system-wide issues)
WITH tick_intervals AS (
    SELECT 
        fp.symbol,
        tf.datetime,
        LAG(tf.datetime) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime) as prev_datetime,
        EXTRACT(EPOCH FROM (tf.datetime - LAG(tf.datetime) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime))) as gap_seconds
    FROM ticks_forex tf
    JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
    WHERE tf.datetime >= NOW() - INTERVAL '48 hours'
),
gap_times AS (
    SELECT 
        symbol,
        prev_datetime,
        datetime,
        gap_seconds,
        DATE_TRUNC('hour', prev_datetime) as gap_hour
    FROM tick_intervals
    WHERE gap_seconds > 300  -- 5 minutes
)
SELECT 
    gap_hour,
    COUNT(DISTINCT symbol) as symbols_affected,
    AVG(gap_seconds / 3600.0) as avg_gap_hours
FROM gap_times
GROUP BY gap_hour
HAVING COUNT(DISTINCT symbol) >= 3  -- 3+ symbols gap simultaneously
ORDER BY gap_hour DESC;

-- 10. Market hours correlation (check if gaps align with market close)
WITH tick_intervals AS (
    SELECT 
        fp.symbol,
        tf.datetime,
        LAG(tf.datetime) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime) as prev_datetime,
        EXTRACT(EPOCH FROM (tf.datetime - LAG(tf.datetime) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime))) as gap_seconds,
        EXTRACT(DOW FROM tf.datetime) as day_of_week,
        EXTRACT(HOUR FROM tf.datetime) as hour
    FROM ticks_forex tf
    JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
    WHERE tf.datetime >= NOW() - INTERVAL '48 hours'
)
SELECT 
    COUNT(*) as total_gaps,
    COUNT(CASE WHEN day_of_week IN (5, 6, 0) OR (day_of_week = 4 AND hour >= 17) THEN 1 END) as market_close_gaps,
    COUNT(CASE WHEN day_of_week IN (5, 6, 0) OR (day_of_week = 4 AND hour >= 17) THEN 1 END)::FLOAT / NULLIF(COUNT(*), 0) as market_close_ratio
FROM tick_intervals
WHERE gap_seconds > 300;  -- 5 minutes

-- ============================================================================
-- TIMESTAMP VALIDATION QUERIES
-- ============================================================================

-- 11. Check for future timestamps (event_time > receive_time)
SELECT 
    fp.symbol,
    tf.datetime as event_time,
    tf.receive_time,
    EXTRACT(EPOCH FROM (tf.datetime - tf.receive_time)) as future_offset_seconds
FROM ticks_forex tf
JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
WHERE tf.datetime >= NOW() - INTERVAL '48 hours'
AND tf.receive_time IS NOT NULL
AND tf.datetime > tf.receive_time + INTERVAL '1 minute'
ORDER BY future_offset_seconds DESC
LIMIT 50;

-- 12. Latency distribution analysis
SELECT 
    CASE 
        WHEN tf.latency_seconds < 0 THEN 'Negative'
        WHEN tf.latency_seconds < 1 THEN '<1s'
        WHEN tf.latency_seconds < 5 THEN '1-5s'
        WHEN tf.latency_seconds < 60 THEN '5-60s'
        ELSE '>60s'
    END as latency_category,
    COUNT(*) as count,
    AVG(tf.latency_seconds) as avg_latency,
    MIN(tf.latency_seconds) as min_latency,
    MAX(tf.latency_seconds) as max_latency
FROM ticks_forex tf
WHERE tf.datetime >= NOW() - INTERVAL '48 hours'
AND tf.receive_time IS NOT NULL
GROUP BY latency_category
ORDER BY 
    CASE latency_category
        WHEN 'Negative' THEN 1
        WHEN '<1s' THEN 2
        WHEN '1-5s' THEN 3
        WHEN '5-60s' THEN 4
        WHEN '>60s' THEN 5
    END;
