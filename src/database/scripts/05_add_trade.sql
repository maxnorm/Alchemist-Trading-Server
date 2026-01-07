-- PostgreSQL migration: Trade table

CREATE TABLE IF NOT EXISTS trade(
    id SERIAL PRIMARY KEY,
    ticket INT NOT NULL,
    ordertype INT NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    openprice DOUBLE PRECISION NOT NULL,
    closeprice DOUBLE PRECISION NULL,
    stoploss DOUBLE PRECISION NULL,
    takeprofit DOUBLE PRECISION NULL,
    profit DECIMAL NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add trigger for updated_at column
CREATE TRIGGER update_trade_updated_at
    BEFORE UPDATE ON trade
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();