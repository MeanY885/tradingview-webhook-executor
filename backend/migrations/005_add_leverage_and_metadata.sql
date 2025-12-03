-- Add leverage and metadata_json columns to webhook_logs table
-- Migration 005: Support for TradingView strategy webhooks with leverage and additional metadata

-- Add leverage column for storing trading leverage (e.g., 5x, 10x)
ALTER TABLE webhook_logs
ADD COLUMN IF NOT EXISTS leverage FLOAT;

-- Add metadata_json column for storing additional TradingView metadata as JSON
ALTER TABLE webhook_logs
ADD COLUMN IF NOT EXISTS metadata_json TEXT;

-- Create index on leverage for potential queries
CREATE INDEX IF NOT EXISTS idx_webhook_leverage ON webhook_logs(leverage);
