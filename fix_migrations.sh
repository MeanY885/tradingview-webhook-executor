#!/bin/bash
# Fix missing database columns
# Run this if migrations failed and columns are missing

set -e

echo "🔧 Applying missing database columns..."

docker-compose exec -T db psql -U postgres -d tradingview <<EOF
-- Migration 007: Add TP tracking fields
ALTER TABLE webhook_logs ADD COLUMN IF NOT EXISTS tp_level VARCHAR(20);
ALTER TABLE webhook_logs ADD COLUMN IF NOT EXISTS position_size_after FLOAT;
ALTER TABLE webhook_logs ADD COLUMN IF NOT EXISTS entry_price FLOAT;
ALTER TABLE webhook_logs ADD COLUMN IF NOT EXISTS realized_pnl_percent FLOAT;
ALTER TABLE webhook_logs ADD COLUMN IF NOT EXISTS realized_pnl_absolute FLOAT;

-- Migration 008: Add SL/TP tracking fields
ALTER TABLE webhook_logs ADD COLUMN IF NOT EXISTS current_stop_loss FLOAT;
ALTER TABLE webhook_logs ADD COLUMN IF NOT EXISTS current_take_profit FLOAT;
ALTER TABLE webhook_logs ADD COLUMN IF NOT EXISTS exit_trail_price FLOAT;
ALTER TABLE webhook_logs ADD COLUMN IF NOT EXISTS exit_trail_offset FLOAT;
ALTER TABLE webhook_logs ADD COLUMN IF NOT EXISTS sl_changed BOOLEAN DEFAULT FALSE;
ALTER TABLE webhook_logs ADD COLUMN IF NOT EXISTS tp_changed BOOLEAN DEFAULT FALSE;
EOF

echo "✅ Columns added successfully!"

echo "🔄 Restarting backend..."
docker-compose restart backend

echo "✅ Done! Backend restarted."
