USE db_forex;

DELIMITER |
CREATE OR REPLACE PROCEDURE insert_tick_forex(
    IN p_datetime DATETIME, IN p_ask double, IN p_bid double,
    IN p_base_currency CHAR(3), IN p_quoted_currency CHAR(3))
BEGIN
    DECLARE base_id INT DEFAULT -1;
    DECLARE quoted_id INT DEFAULT -1;

    SELECT id
    INTO base_id
    FROM currency WHERE iso_code = p_base_currency;

    SELECT id
    INTO quoted_id
    FROM currency WHERE iso_code = p_quoted_currency;

    INSERT INTO ticks_forex(datetime, ask, bid, base_currency_id, quote_currency_id)
    VALUES (p_datetime, p_ask, p_bid, base_id, quoted_id);
END |
DELIMITER ;