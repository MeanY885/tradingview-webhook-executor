#!/bin/bash
set -e  # Exit on any error

# Configuration
DOMAIN="webhook.eddisford.co.uk"
EMAIL="chris@eddisford.co.uk"
PROJECT_DIR="$HOME/tradingview-webhook-executor"
CERT_DIR="/etc/letsencrypt/live/$DOMAIN"

echo "=== Let's Encrypt SSL Setup for TradingView Webhooks ==="
echo ""

# Step 1: Verify DNS resolution
echo "[1/9] Verifying DNS resolution..."
RESOLVED_IP=$(dig +short $DOMAIN | tail -n1)
if [ "$RESOLVED_IP" != "46.65.75.120" ]; then
    echo "❌ ERROR: Domain $DOMAIN does not resolve to 46.65.75.120"
    echo "   Current resolution: $RESOLVED_IP"
    echo "   Please wait for DNS propagation and try again."
    exit 1
fi
echo "✓ DNS resolves correctly to 46.65.75.120"
echo ""

# Step 2: Backup current configuration
echo "[2/9] Backing up current configuration..."
cd $PROJECT_DIR
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
cp docker-compose.yml docker-compose.yml.backup.$(date +%Y%m%d_%H%M%S)
echo "✓ Backup created"
echo ""

# Step 3: Update .env file
echo "[3/9] Updating .env file..."
sed -i "s|BASE_URL=.*|BASE_URL=https://$DOMAIN|g" .env
sed -i "s|FRONTEND_URL=.*|FRONTEND_URL=https://$DOMAIN|g" .env
sed -i "s|VITE_API_URL=.*|VITE_API_URL=https://$DOMAIN|g" .env
echo "✓ .env updated with domain"
echo ""

# Step 4: Update docker-compose.yml ports
echo "[4/9] Updating docker-compose.yml ports..."
sed -i 's/"8888:443"/"443:443"/g' docker-compose.yml
sed -i 's/"8887:80"/"80:80"/g' docker-compose.yml
echo "✓ Ports updated to 443:443 and 80:80"
echo ""

# Step 5: Install certbot (using snap - recommended method)
echo "[5/9] Installing certbot..."
if ! command -v certbot &> /dev/null; then
    # Remove old apt-based certbot if it exists
    sudo apt remove certbot -y 2>/dev/null || true

    # Install snapd if not present
    if ! command -v snap &> /dev/null; then
        sudo apt update
        sudo apt install snapd -y
        sudo systemctl enable --now snapd.socket
        sleep 2
    fi

    # Install certbot via snap
    sudo snap install --classic certbot
    sudo ln -sf /snap/bin/certbot /usr/bin/certbot
    echo "✓ Certbot installed via snap"
else
    # Check if it's the old apt version
    CERTBOT_VERSION=$(certbot --version 2>&1 | grep -oP '\d+\.\d+\.\d+' | head -1)
    if [[ "$CERTBOT_VERSION" < "1.0.0" ]]; then
        echo "Old certbot version detected, upgrading..."
        sudo apt remove certbot -y
        sudo snap install --classic certbot
        sudo ln -sf /snap/bin/certbot /usr/bin/certbot
        echo "✓ Certbot upgraded via snap"
    else
        echo "✓ Certbot already installed"
    fi
fi
echo ""

# Step 6: Stop nginx and generate certificate
echo "[6/9] Stopping nginx and generating certificate..."
docker-compose stop nginx
echo "Waiting for port 80 to be free..."
sleep 3

sudo certbot certonly --standalone \
    -d $DOMAIN \
    --agree-tos \
    --email $EMAIL \
    --non-interactive

if [ ! -f "$CERT_DIR/fullchain.pem" ]; then
    echo "❌ ERROR: Certificate generation failed"
    echo "   Restarting nginx..."
    docker-compose start nginx
    exit 1
fi
echo "✓ Certificate generated successfully"
echo ""

# Step 7: Copy certificates to nginx directory
echo "[7/9] Copying certificates to nginx directory..."
sudo cp $CERT_DIR/fullchain.pem $PROJECT_DIR/nginx/ssl/cert.pem
sudo cp $CERT_DIR/privkey.pem $PROJECT_DIR/nginx/ssl/key.pem
sudo chmod 644 $PROJECT_DIR/nginx/ssl/cert.pem
sudo chmod 600 $PROJECT_DIR/nginx/ssl/key.pem
sudo chown $USER:$USER $PROJECT_DIR/nginx/ssl/*.pem
echo "✓ Certificates copied and permissions set"
echo ""

# Step 8: Rebuild and restart services
echo "[8/9] Rebuilding frontend and restarting services..."
docker-compose build frontend
docker-compose down
docker-compose up -d
echo "Waiting for services to start..."
sleep 10
echo "✓ Services restarted"
echo ""

# Step 9: Set up auto-renewal
echo "[9/9] Setting up auto-renewal cron job..."
CRON_CMD="0 2 * * * certbot renew --quiet --post-hook \"cp $CERT_DIR/fullchain.pem $PROJECT_DIR/nginx/ssl/cert.pem && cp $CERT_DIR/privkey.pem $PROJECT_DIR/nginx/ssl/key.pem && cd $PROJECT_DIR && docker-compose restart nginx\""

# Check if cron job already exists
if sudo crontab -l 2>/dev/null | grep -q "certbot renew"; then
    echo "✓ Auto-renewal cron job already exists"
else
    (sudo crontab -l 2>/dev/null; echo "$CRON_CMD") | sudo crontab -
    echo "✓ Auto-renewal cron job added"
fi
echo ""

# Verification
echo "=== Setup Complete ==="
echo ""
echo "Running verification tests..."
echo ""

# Test 1: Check services
echo "Services status:"
docker-compose ps
echo ""

# Test 2: Test HTTPS connection
echo "Testing HTTPS connection..."
sleep 5
if curl -s -o /dev/null -w "%{http_code}" https://$DOMAIN/api/auth/me | grep -q "401\|422"; then
    echo "✓ HTTPS endpoint responding"
else
    echo "⚠ HTTPS endpoint check inconclusive (may need to wait for propagation)"
fi
echo ""

# Test 3: Check certificate
echo "Certificate info:"
echo "Issuer: $(openssl s_client -connect $DOMAIN:443 -servername $DOMAIN </dev/null 2>/dev/null | openssl x509 -noout -issuer 2>/dev/null | grep -o "O = .*")"
echo "Valid until: $(openssl s_client -connect $DOMAIN:443 -servername $DOMAIN </dev/null 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null)"
echo ""

echo "=== Next Steps ==="
echo "1. Visit https://$DOMAIN in your browser (should show valid certificate)"
echo "2. Update TradingView webhook URLs:"
echo "   - Blofin: https://$DOMAIN/blofin/chrise885"
echo "   - Oanda: https://$DOMAIN/oanda/chrise885"
echo "3. Test with a TradingView alert (use test_mode: true first)"
echo "4. Check webhook logs in the dashboard"
echo ""
echo "Rollback: Restore from .env.backup.* and docker-compose.yml.backup.* if needed"
