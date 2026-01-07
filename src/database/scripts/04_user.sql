-- PostgreSQL migration: User privileges
-- Note: The user 'forex_user' is already created via POSTGRES_USER environment variable in docker-compose.yml
-- Since forex_user is the database owner, it already has all privileges on the database
-- This script ensures schema-level privileges are set for future objects

-- Grant all privileges on existing tables and sequences
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO forex_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO forex_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO forex_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO forex_user;