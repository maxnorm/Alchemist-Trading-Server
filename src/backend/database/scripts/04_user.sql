-- PostgreSQL migration: User privileges
-- 
-- Context: This script runs in the database initialization context where the database user
-- is created via POSTGRES_USER environment variable in docker-compose.yml (defaults to DB_USER from .env).
-- The user referenced below (user) is the database owner created by Docker Compose.
--
-- Note: The hardcoded 'user' here is acceptable because:
-- 1. This script runs during database initialization in the Docker container
-- 2. The database user is created by Docker Compose using POSTGRES_USER (from DB_USER env var)
-- 3. This script must match the user created by Docker Compose
-- 4. For custom database users, ensure DB_USER in .env matches the user referenced here
--
-- Since the database user is the database owner, it already has all privileges on the database.
-- This script ensures schema-level privileges are set for future objects.
--
-- This script is conditional - it only grants privileges if the "user" role exists.
-- This allows it to work in both production (where "user" exists) and test environments
-- (where testcontainers may use different user names).

DO $$
BEGIN
    -- Check if the "user" role exists before granting privileges
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'user') THEN
        -- Grant all privileges on existing tables and sequences
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "user";
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "user";

        -- Set default privileges for future objects
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "user";
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO "user";
    END IF;
END $$;