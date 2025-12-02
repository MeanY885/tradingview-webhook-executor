-- Create user_credentials table
CREATE TABLE IF NOT EXISTS user_credentials (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    broker VARCHAR(20) NOT NULL,

    -- Encrypted fields
    api_key_encrypted TEXT NOT NULL,
    secret_key_encrypted TEXT,
    passphrase_encrypted TEXT,
    account_id_encrypted TEXT,

    -- Metadata
    is_active BOOLEAN DEFAULT true,
    label VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(user_id, broker, label)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_credentials_user_broker ON user_credentials(user_id, broker);

-- Trigger to automatically update updated_at
CREATE TRIGGER update_user_credentials_updated_at BEFORE UPDATE ON user_credentials
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
