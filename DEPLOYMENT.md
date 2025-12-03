# Deployment Guide

## Automatic Migrations ✅

The backend now automatically runs pending database migrations on startup!

### How It Works

1. **Migration Files**: All `.sql` files in `backend/migrations/` are tracked
2. **Tracking Table**: A `schema_migrations` table records which migrations have been applied
3. **Auto-Run**: On backend startup, pending migrations are automatically applied in order
4. **Logs**: Check backend logs to see migration status:
   ```
   Checking for pending database migrations...
   Found 1 pending migration(s)
   Applying migration: 005_add_leverage_and_metadata.sql
   ✓ Migration applied: 005_add_leverage_and_metadata.sql
   All migrations applied successfully
   ```

### Deploying Updates

**Method 1: Standard Deployment (Recommended)**

```bash
# Pull latest code
git pull origin main

# Rebuild and restart containers
docker-compose down
docker-compose build
docker-compose up -d

# Check backend logs to verify migrations ran
docker logs tradingview-webhook-backend | grep migration
```

**Method 2: Manual Migration (If needed)**

If you need to run a migration manually:

```bash
# SSH into your server, then:
docker exec -i tradingview-webhook-db psql -U webhook_user -d webhooks < backend/migrations/005_add_leverage_and_metadata.sql

# Restart backend
docker restart tradingview-webhook-backend
```

### Recent Changes

#### Migration 005: Leverage & Metadata Support
- Adds `leverage` column to webhook_logs
- Adds `metadata_json` column for TradingView strategy data
- Adds index on leverage field

#### Username-based Webhook URLs
- URLs now use username: `/blofin/chrise885` instead of `/blofin/<long-token>`
- Old token-based URLs still work (backwards compatible)
- No migration needed (uses existing username field)

### Troubleshooting

**Migration fails on startup:**
1. Check backend logs: `docker logs tradingview-webhook-backend`
2. Verify database is accessible
3. Try manual migration method above

**422 Errors in UI:**
- This means migrations haven't run yet
- Wait for backend to start fully (migrations run on startup)
- Check logs to confirm migrations completed
- If still failing, run manual migration

**To check applied migrations:**
```bash
docker exec -it tradingview-webhook-db psql -U webhook_user -d webhooks -c "SELECT * FROM schema_migrations ORDER BY version;"
```

### Adding New Migrations

1. Create new `.sql` file in `backend/migrations/`
2. Name it with next number: `006_your_migration.sql`
3. Write SQL (multiple statements OK)
4. Deploy - it will run automatically!

Example:
```sql
-- 006_add_new_field.sql
ALTER TABLE webhook_logs
ADD COLUMN IF NOT EXISTS new_field TEXT;

CREATE INDEX IF NOT EXISTS idx_new_field ON webhook_logs(new_field);
```
