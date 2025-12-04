-- Add SL/TP tracking and trailing stop fields to webhook_logs table
-- Migration 008: Support for SL/TP change tracking and trailing stops

-- Add current_stop_loss column for SL value at this webhook
ALTER TABLE webhook_logs
ADD COLUMN IF NOT EXISTS current_stop_loss FLOAT;

-- Add current_take_profit column for TP value at this webhook
ALTER TABLE webhook_logs
ADD COLUMN IF NOT EXISTS current_take_profit FLOAT;

-- Add exit_trail_price column for trailing stop price
ALTER TABLE webhook_logs
ADD COLUMN IF NOT EXISTS exit_trail_price FLOAT;

-- Add exit_trail_offset column for trailing stop offset
ALTER TABLE webhook_logs
ADD COLUMN IF NOT EXISTS exit_trail_offset FLOAT;

-- Add sl_changed flag to indicate SL changed from previous webhook
ALTER TABLE webhook_logs
ADD COLUMN IF NOT EXISTS sl_changed BOOLEAN DEFAULT FALSE;

-- Add tp_changed flag to indicate TP changed from previous webhook
ALTER TABLE webhook_logs
ADD COLUMN IF NOT EXISTS tp_changed BOOLEAN DEFAULT FALSE;
