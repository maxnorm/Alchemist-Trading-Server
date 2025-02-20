CREATE USER IF NOT EXISTS 'forex_user'@'%' IDENTIFIED BY 'forex_password';
CREATE USER IF NOT EXISTS 'forex_user'@'localhost' IDENTIFIED BY 'forex_password';

GRANT ALL PRIVILEGES ON db_forex.* TO 'forex_user'@'%';
GRANT ALL PRIVILEGES ON db_forex.* TO 'forex_user'@'localhost';

FLUSH PRIVILEGES;