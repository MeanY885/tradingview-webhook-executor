#!/bin/bash
# Remote server deployment script
# Usage: ./deploy.sh

set -e  # Exit on error

echo "🚀 Starting deployment..."

# Pull latest code
echo "📥 Pulling latest code from GitHub..."
git pull origin main

# Stop containers
echo "🛑 Stopping containers..."
docker-compose down

# Remove old images and clear cache
echo "🗑️  Removing old images and clearing cache..."
docker rmi tradingview-webhook-executor-frontend 2>/dev/null || true
docker rmi tradingview-webhook-executor-backend 2>/dev/null || true
docker builder prune -f

# Rebuild and start
echo "🔨 Rebuilding services..."
docker-compose build --no-cache frontend backend
docker-compose up -d

# Wait and show status
echo "⏳ Waiting for services..."
sleep 5

# Run database migrations
echo "🗄️  Running database migrations..."
docker compose exec -T backend python -c "from app import create_app; app = create_app(); app.app_context().push(); from app.migrations import run_migrations; run_migrations()"

echo ""
echo "✅ Deployment complete!"
docker-compose ps
echo ""
echo "🌐 https://webhook.eddisford.co.uk"
echo "💡 Hard refresh browser: Cmd+Shift+R or Ctrl+Shift+F5"
