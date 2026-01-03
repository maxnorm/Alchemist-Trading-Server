-- Drop existing users if they exist (in case created by environment variables)
DROP USER IF EXISTS 'forex_user'@'%';
DROP USER IF EXISTS 'forex_user'@'localhost';

-- Create users with proper host access
CREATE USER 'forex_user'@'%' IDENTIFIED BY 'forex_password';
CREATE USER 'forex_user'@'localhost' IDENTIFIED BY 'forex_password';

-- Grant all privileges
GRANT ALL PRIVILEGES ON db_forex.* TO 'forex_user'@'%';
GRANT ALL PRIVILEGES ON db_forex.* TO 'forex_user'@'localhost';

FLUSH PRIVILEGES;