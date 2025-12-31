USE db_forex;

-- Insert Tick Forex
DELIMITER |
CREATE OR REPLACE PROCEDURE insert_tick_forex(
    IN p_datetime DATETIME, IN p_ask double, IN p_bid double,
    IN p_base_currency CHAR(3), IN p_quoted_currency CHAR(3))
BEGIN
    DECLARE base_id INT DEFAULT -1;
    DECLARE quoted_id INT DEFAULT -1;
    DECLARE pair_id INT DEFAULT -1;

    SELECT id
    INTO base_id
    FROM currency WHERE iso_code = p_base_currency;

    SELECT id
    INTO quoted_id
    FROM currency WHERE iso_code = p_quoted_currency;

    SELECT id
    INTO pair_id
    FROM forex_pairs
    WHERE base_currency_id = base_id AND quote_currency_id = quoted_id;

    IF pair_id <> -1 THEN
        INSERT ticks_forex(datetime, ask, bid, forex_pairs_id)
        VALUES (p_datetime, p_ask, p_bid, pair_id);
    END IF;
END |
DELIMITER ;

-- Insert Economic Calendar Data
DELIMITER |
CREATE OR REPLACE PROCEDURE insert_economic_calendar_data(
    IN p_datetime DATETIME, IN p_country VARCHAR(100), IN p_event VARCHAR(250),
    IN p_impact INT, IN p_previous VARCHAR(20),
     IN p_consesus VARCHAR(20), IN p_actual VARCHAR(20))
BEGIN
    DECLARE id_country INT DEFAULT -1;

    SELECT id
    INTO id_country
    FROM country WHERE nom = p_country;

    IF id_country <> -1 THEN
        INSERT INTO economic_calendar(datetime, event, impact, previous, consensus, actual, country_id)
        VALUES (p_datetime, p_event, p_impact, p_previous, p_consesus, p_actual, id_country);
    END IF;
END |
DELIMITER ;

-- Batch Insert Tick Forex (optimized for bulk inserts)
-- This procedure uses a temporary table to batch insert multiple ticks efficiently
DELIMITER |
CREATE OR REPLACE PROCEDURE insert_tick_forex_batch(
    IN p_tick_data TEXT)
BEGIN
    DECLARE done INT DEFAULT 0;
    DECLARE v_datetime DATETIME;
    DECLARE v_ask DOUBLE;
    DECLARE v_bid DOUBLE;
    DECLARE v_base_currency CHAR(3);
    DECLARE v_quoted_currency CHAR(3);
    DECLARE v_base_id INT;
    DECLARE v_quoted_id INT;
    DECLARE v_pair_id INT;
    DECLARE v_row_count INT DEFAULT 0;
    
    -- Create temporary table for batch processing
    CREATE TEMPORARY TABLE IF NOT EXISTS temp_ticks_batch (
        datetime_val DATETIME,
        ask_val DOUBLE,
        bid_val DOUBLE,
        base_currency_val CHAR(3),
        quoted_currency_val CHAR(3),
        pair_id_val INT DEFAULT NULL
    ) ENGINE=MEMORY;
    
    -- Parse and insert into temp table (format: datetime|ask|bid|base|quoted;...)
    -- For now, we'll use a simpler approach: direct INSERT with multiple VALUES
    -- The Python code will format the data appropriately
    
    -- Note: MariaDB doesn't support table-valued parameters natively
    -- The actual batch insert will be done via Python using executemany or bulk INSERT
    -- This procedure is kept for potential future use or as a template
    
    DROP TEMPORARY TABLE IF EXISTS temp_ticks_batch;
END |
DELIMITER ;

-- Optimized single tick insert with cached lookups (improved version)
-- Note: For true caching, we'd need to use a different approach
-- This version is optimized but still does lookups each time
DELIMITER |
CREATE OR REPLACE PROCEDURE insert_tick_forex_optimized(
    IN p_datetime DATETIME, IN p_ask double, IN p_bid double,
    IN p_base_currency CHAR(3), IN p_quoted_currency CHAR(3))
BEGIN
    DECLARE base_id INT DEFAULT NULL;
    DECLARE quoted_id INT DEFAULT NULL;
    DECLARE pair_id INT DEFAULT NULL;

    -- Use single query with JOINs to get all IDs at once (more efficient)
    SELECT 
        c1.id AS base_id,
        c2.id AS quoted_id,
        fp.id AS pair_id
    INTO base_id, quoted_id, pair_id
    FROM currency c1
    CROSS JOIN currency c2
    LEFT JOIN forex_pairs fp ON fp.base_currency_id = c1.id AND fp.quote_currency_id = c2.id
    WHERE c1.iso_code = p_base_currency AND c2.iso_code = p_quoted_currency
    LIMIT 1;

    IF pair_id IS NOT NULL THEN
        INSERT INTO ticks_forex(datetime, ask, bid, forex_pairs_id)
        VALUES (p_datetime, p_ask, p_bid, pair_id);
    END IF;
END |
DELIMITER ;