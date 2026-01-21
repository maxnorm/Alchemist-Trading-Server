-- Historical Data Seeding Flag Check
-- This script checks if historical data seeding should be performed
-- Called during database initialization

DO $$
BEGIN
    -- Check if seeding environment variable is set
    -- This is a marker script that signals to the entrypoint script
    -- to run the Python seeding script
    
    -- Log the check
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Historical Data Seeding Check';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'To enable historical data seeding:';
    RAISE NOTICE '  1. Set SEED_HISTORICAL_DATA=true in .env';
    RAISE NOTICE '  2. Mount data directory: -v ./data/dukascopy:/data/dukascopy:ro';
    RAISE NOTICE '  3. Run: docker compose up';
    RAISE NOTICE '========================================';
END $$;
