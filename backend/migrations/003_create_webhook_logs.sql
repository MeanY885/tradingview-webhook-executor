-- Create webhook_logs table
CREATE TABLE IF NOT EXISTS webhook_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Request data
    raw_payload TEXT NOT NULL,
    source_ip VARCHAR(50),
    broker VARCHAR(20) NOT NULL,

    -- Parsed data
    symbol VARCHAR(20),
    original_symbol VARCHAR(20),
    action VARCHAR(10),
    order_type VARCHAR(20),
    quantity FLOAT,
    price FLOAT,
    stop_loss FLOAT,
    take_profit FLOAT,
    trailing_stop_pct FLOAT,

    -- Execution status
    status VARCHAR(20) NOT NULL,
    broker_order_id VARCHAR(50),
    client_order_id VARCHAR(32),
    error_message TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_webhook_timestamp ON webhook_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_webhook_user ON webhook_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_webhook_status ON webhook_logs(status);
CREATE INDEX IF NOT EXISTS idx_webhook_broker ON webhook_logs(broker);
CREATE INDEX IF NOT EXISTS idx_webhook_symbol ON webhook_logs(symbol);
CREATE INDEX IF NOT EXISTS idx_webhook_action ON webhook_logs(action);
