-- PostgreSQL migration: Add gold (XAU) support
-- Adds XAU currency and XAUUSD/XAUEUR trading pairs

-- Add XAU (Gold) to currency table (if it doesn't exist)
INSERT INTO currency(nom, iso_code)
SELECT 'Gold', 'XAU'
WHERE NOT EXISTS (
    SELECT 1 FROM currency WHERE iso_code = 'XAU'
);

-- Get currency IDs (assuming they exist from seed data)
-- Note: This assumes USD=1, EUR=2, XAU will be the next ID
-- In production, you should query the IDs dynamically

-- Add XAUUSD pair (Gold vs US Dollar)
-- XAU is base currency (10), USD is quote currency (1)
INSERT INTO forex_pairs(symbol, base_currency_id, quote_currency_id)
SELECT 'XAUUSD', 
       (SELECT id FROM currency WHERE iso_code = 'XAU'),
       (SELECT id FROM currency WHERE iso_code = 'USD')
WHERE NOT EXISTS (
    SELECT 1 FROM forex_pairs WHERE symbol = 'XAUUSD'
);

-- Add XAUEUR pair (Gold vs Euro)
-- XAU is base currency (10), EUR is quote currency (2)
INSERT INTO forex_pairs(symbol, base_currency_id, quote_currency_id)
SELECT 'XAUEUR',
       (SELECT id FROM currency WHERE iso_code = 'XAU'),
       (SELECT id FROM currency WHERE iso_code = 'EUR')
WHERE NOT EXISTS (
    SELECT 1 FROM forex_pairs WHERE symbol = 'XAUEUR'
);
