USE db_forex;

DELIMITER |
CREATE OR REPLACE PROCEDURE insert_tick_forex(
    IN timestamp DATETIME, IN p_adresse VARCHAR(200))
BEGIN
    DECLARE i_id INT DEFAULT -1;

    SELECT id
    INTO i_id
    FROM coureur WHERE nom = p_nom;
    START TRANSACTION;
        IF i_id = -1 THEN
            INSERT INTO coureur(nom, adresse)
            VALUES (p_nom, SHA2(CONCAT(SHA2('salt_secret', 224), p_adresse), 256));

            SELECT 'Coureur enregistré' AS Message;
        ELSE
            UPDATE coureur
            SET adresse = SHA2(CONCAT(SHA2('salt_secret', 224), p_adresse), 256)
            WHERE id = i_id;

            SELECT 'Coureur déjà existant. Changement de adresse' AS Message;
        END IF;
    COMMIT;
END |
DELIMITER ;