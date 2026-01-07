-- PostgreSQL migration: User creation
-- Note: In PostgreSQL, users are created at the database cluster level
-- This script should be run as a superuser (postgres)

-- Drop existing user if exists
DROP USER IF EXISTS forex_user;

-- Create user
CREATE USER forex_user WITH PASSWORD 'forex_password';

-- Grant all privileges on database
GRANT ALL PRIVILEGES ON DATABASE db_forex TO forex_user;

-- Grant all privileges on schema (run after connecting to db_forex)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO forex_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO forex_user;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO forex_user;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO forex_user;