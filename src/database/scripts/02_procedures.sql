-- PostgreSQL functions (converted from MariaDB stored procedures)

-- Insert Tick Forex
CREATE OR REPLACE FUNCTION insert_tick_forex(
    p_datetime TIMESTAMP,
    p_ask DOUBLE PRECISION,
    p_bid DOUBLE PRECISION,
    p_base_currency CHAR(3),
    p_quoted_currency CHAR(3)
)
RETURNS VOID AS $$
DECLARE
    base_id INT;
    quoted_id INT;
    pair_id INT;
BEGIN
    SELECT id INTO base_id
    FROM currency WHERE iso_code = p_base_currency;

    SELECT id INTO quoted_id
    FROM currency WHERE iso_code = p_quoted_currency;

    SELECT id INTO pair_id
    FROM forex_pairs
    WHERE base_currency_id = base_id AND quote_currency_id = quoted_id;

    IF pair_id IS NOT NULL THEN
        INSERT INTO ticks_forex(datetime, ask, bid, forex_pairs_id)
        VALUES (p_datetime, p_ask, p_bid, pair_id);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Insert Economic Calendar Data
CREATE OR REPLACE FUNCTION insert_economic_calendar_data(
    p_datetime TIMESTAMP,
    p_country VARCHAR(100),
    p_event VARCHAR(250),
    p_impact INT,
    p_previous VARCHAR(20),
    p_consensus VARCHAR(20),
    p_actual VARCHAR(20)
)
RETURNS VOID AS $$
DECLARE
    id_country INT;
BEGIN
    SELECT id INTO id_country
    FROM country WHERE nom = p_country;

    IF id_country IS NOT NULL THEN
        INSERT INTO economic_calendar(datetime, event, impact, previous, consensus, actual, country_id)
        VALUES (p_datetime, p_event, p_impact, p_previous, p_consensus, p_actual, id_country);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Optimized single tick insert with cached lookups (improved version)
CREATE OR REPLACE FUNCTION insert_tick_forex_optimized(
    p_datetime TIMESTAMP,
    p_ask DOUBLE PRECISION,
    p_bid DOUBLE PRECISION,
    p_base_currency CHAR(3),
    p_quoted_currency CHAR(3)
)
RETURNS VOID AS $$
DECLARE
    base_id INT;
    quoted_id INT;
    pair_id INT;
BEGIN
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
END;
$$ LANGUAGE plpgsql;