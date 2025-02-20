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