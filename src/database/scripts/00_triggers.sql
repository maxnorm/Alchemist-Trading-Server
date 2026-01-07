-- Trigger function for updating updated_at timestamp columns
-- This replaces MariaDB's ON UPDATE CURRENT_TIMESTAMP functionality

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
