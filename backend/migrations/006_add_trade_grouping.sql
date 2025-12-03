-- Add trade grouping fields to webhook_logs table
ALTER TABLE webhook_logs
ADD COLUMN IF NOT EXISTS trade_group_id VARCHAR(50),
ADD COLUMN IF NOT EXISTS trade_direction VARCHAR(10);

-- Add index for faster grouping queries
CREATE INDEX IF NOT EXISTS idx_webhook_logs_trade_group_id ON webhook_logs(trade_group_id);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_user_symbol_timestamp ON webhook_logs(user_id, symbol, timestamp);
