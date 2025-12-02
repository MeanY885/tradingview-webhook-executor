-- Add IP whitelist columns to users table
ALTER TABLE users
ADD COLUMN IF NOT EXISTS webhook_ip_whitelist_enabled BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS webhook_ip_whitelist TEXT DEFAULT '[]';

-- Add comment for documentation
COMMENT ON COLUMN users.webhook_ip_whitelist_enabled IS 'Enable IP whitelist restriction for webhooks';
COMMENT ON COLUMN users.webhook_ip_whitelist IS 'JSON array of allowed IP addresses (supports CIDR notation)';
