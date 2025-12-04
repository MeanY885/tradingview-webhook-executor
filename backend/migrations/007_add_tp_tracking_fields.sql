-- Add TP tracking fields to webhook_logs table
-- Migration 007: Support for multi-take-profit trade tracking

-- Add tp_level column for storing TP level (TP1, TP2, TP3, SL, PARTIAL)
ALTER TABLE webhook_logs
ADD COLUMN IF NOT EXISTS tp_level VARCHAR(10);

-- Add position_size_after column for remaining position after this action
ALTER TABLE webhook_logs
ADD COLUMN IF NOT EXISTS position_size_after FLOAT;

-- Add entry_price column for cached entry price (used for P&L calculations)
ALTER TABLE webhook_logs
ADD COLUMN IF NOT EXISTS entry_price FLOAT;

-- Add realized_pnl_percent column for P&L percentage for this specific exit
ALTER TABLE webhook_logs
ADD COLUMN IF NOT EXISTS realized_pnl_percent FLOAT;

-- Add realized_pnl_absolute column for P&L absolute value for this specific exit
ALTER TABLE webhook_logs
ADD COLUMN IF NOT EXISTS realized_pnl_absolute FLOAT;

-- Create index on tp_level for filtering queries
CREATE INDEX IF NOT EXISTS idx_webhook_logs_tp_level ON webhook_logs(tp_level);
