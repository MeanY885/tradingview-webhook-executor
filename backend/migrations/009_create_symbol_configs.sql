-- Migration: Create symbol_configs table
-- Description: User-defined TP/SL configuration per symbol

CREATE TABLE IF NOT EXISTS symbol_configs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Symbol identification
    symbol VARCHAR(20) NOT NULL,           -- e.g., 'EUR_USD', 'BTCUSDT'
    broker VARCHAR(20) NOT NULL,           -- 'oanda', 'blofin'
    
    -- TP/SL configuration
    tp_count INTEGER DEFAULT 1,            -- Number of TP levels (1, 2, or 3)
    sl_count INTEGER DEFAULT 1,            -- Number of SL levels (1, 2, or 3)
    
    -- Optional display name
    display_name VARCHAR(50),              -- e.g., 'Euro/USD'
    
    -- Metadata
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint: one config per user/symbol/broker
    CONSTRAINT uq_user_symbol_broker UNIQUE (user_id, symbol, broker)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_symbol_configs_user_broker 
ON symbol_configs(user_id, broker);

CREATE INDEX IF NOT EXISTS idx_symbol_configs_symbol 
ON symbol_configs(symbol);
