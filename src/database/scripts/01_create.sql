-- PostgreSQL migration: Core tables
-- Note: Database should be created separately: CREATE DATABASE db_forex;

CREATE TABLE IF NOT EXISTS currency(
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    iso_code CHAR(3) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS country(
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    currency_id INT NOT NULL,
    CONSTRAINT currency_id_country
        FOREIGN KEY (currency_id)
        REFERENCES currency(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS forex_pairs(
    id SERIAL PRIMARY KEY,
    symbol CHAR(6) NOT NULL,
    base_currency_id INT NOT NULL,
    CONSTRAINT base_currency_id_ticks
        FOREIGN KEY (base_currency_id)
        REFERENCES currency(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    quote_currency_id INT NOT NULL,
    CONSTRAINT quote_currency_id_ticks
        FOREIGN KEY (quote_currency_id)
        REFERENCES currency(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS ticks_forex(
    id BIGSERIAL PRIMARY KEY,
    datetime TIMESTAMP NOT NULL,
    ask DOUBLE PRECISION NOT NULL,
    bid DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION,
    forex_pairs_id INT NOT NULL,
    CONSTRAINT forex_pairs_id_ticks
        FOREIGN KEY (forex_pairs_id)
        REFERENCES forex_pairs(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS economic_calendar(
    id BIGSERIAL PRIMARY KEY,
    datetime TIMESTAMP NOT NULL,
    event VARCHAR(250) NOT NULL,
    impact INT NOT NULL,
    previous VARCHAR(20),
    consensus VARCHAR(20),
    actual VARCHAR(20),
    country_id INT NOT NULL,
    CONSTRAINT country_id_economic_calendar
        FOREIGN KEY (country_id)
        REFERENCES country(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL
);

-- Add triggers for updated_at columns
CREATE TRIGGER update_currency_updated_at
    BEFORE UPDATE ON currency
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_country_updated_at
    BEFORE UPDATE ON country
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ticks_forex_updated_at
    BEFORE UPDATE ON ticks_forex
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_economic_calendar_updated_at
    BEFORE UPDATE ON economic_calendar
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();