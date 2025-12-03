-- Initialize schema_migrations table with already-applied migrations
-- Run this ONCE on existing databases to mark old migrations as applied

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Mark existing migrations as applied (since they ran via docker-entrypoint-initdb.d)
INSERT INTO schema_migrations (version) VALUES ('001_create_users') ON CONFLICT DO NOTHING;
INSERT INTO schema_migrations (version) VALUES ('002_create_user_credentials') ON CONFLICT DO NOTHING;
INSERT INTO schema_migrations (version) VALUES ('003_create_webhook_logs') ON CONFLICT DO NOTHING;
INSERT INTO schema_migrations (version) VALUES ('004_add_ip_whitelist') ON CONFLICT DO NOTHING;
