USE db_forex;

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
