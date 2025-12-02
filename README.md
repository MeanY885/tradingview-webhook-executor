# TradingView Webhook Executor

A full-stack application for automatically executing trades from TradingView alerts on multiple brokers (Blofin for crypto, Oanda for forex).

## Features

- **Multi-Broker Support**: Trade on Blofin (crypto) and Oanda (forex)
- **Real-Time Monitoring**: WebSocket-based live webhook feed on dashboard
- **Secure Credential Storage**: Encrypted API credentials using Fernet symmetric encryption
- **Multi-User System**: Isolated webhook URLs and credentials per user
- **Alert Template Generator**: Easy setup of TradingView alerts with copy-paste templates
- **Trade History**: Comprehensive filtering and pagination
- **Multiple Alert Formats**: Supports JSON and text-based alerts, including strategy-generated messages

## Tech Stack

### Backend
- Flask 3.x with Flask-SocketIO for real-time updates
- PostgreSQL database with SQLAlchemy ORM
- JWT authentication
- Fernet encryption for sensitive data
- Python 3.11+

### Frontend
- React 18+ with Vite
- Material-UI v5 (dark theme)
- Socket.IO client for real-time updates
- React Router v6
- Axios for API calls

### Deployment
- Docker + Docker Compose
- Nginx reverse proxy (ports 80/443)
- PostgreSQL database

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Node.js 18+ (for local development)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd tradingview-webhook-executor
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```

3. **Generate encryption key**
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Copy the output and paste it into `.env` as `ENCRYPTION_KEY`

4. **Update `.env` file**
   - Set `SECRET_KEY` and `JWT_SECRET_KEY` to random strings
   - Set `DB_PASSWORD` to a secure password
   - Set `BASE_URL` to your domain (e.g., `https://your-domain.com`)
   - Set `ENCRYPTION_KEY` to the generated Fernet key

### Running with Docker

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

The application will be available at:
- Frontend: http://localhost (or your domain)
- Backend API: http://localhost/api

### Local Development

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up database (PostgreSQL must be running)
# Update DATABASE_URI in .env to point to your local PostgreSQL

# Run Flask development server
python app.py
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

The frontend will be available at http://localhost:3000

## Configuration

### Database Setup

The application requires PostgreSQL. When using Docker, the database is automatically created. For local development:

```sql
CREATE DATABASE webhooks;
CREATE USER webhook_user WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE webhooks TO webhook_user;
```

Then run migrations (SQL files in `backend/migrations/`)

### Broker API Credentials

#### Blofin (Crypto)
1. Log in to your Blofin account
2. Navigate to API Management
3. Create a new API key
4. Copy the API Key, Secret Key, and Passphrase
5. Enter these in the Settings page of the application

#### Oanda (Forex)
1. Log in to your Oanda account
2. Navigate to Manage API Access
3. Generate a Personal Access Token
4. Copy the token and your account ID
5. Enter these in the Settings page of the application

## Usage

### Setting Up TradingView Alerts

1. **Login to the application** and navigate to Settings
2. **Add your broker credentials** (Blofin or Oanda)
3. **Generate webhook URL and message template**:
   - Select your broker
   - Choose template type (Strategy-driven, Simple Buy/Sell, or with SL/TP)
   - Copy the webhook URL
   - Copy the message template (JSON or text format)

4. **In TradingView**:
   - Create an alert on your chart
   - Go to "Notifications" tab → Enable "Webhook URL" → Paste your webhook URL
   - Go to "Message" tab → Clear existing text → Paste the message template
   - Adjust parameters (quantity, price, stop loss, take profit) as needed
   - Create the alert!

### Alert Message Formats

**JSON Format (Recommended)**:
```json
{
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "order_type": "market",
  "quantity": "{{strategy.order.contracts}}",
  "stop_loss": 40000,
  "take_profit": 50000
}
```

**Text Format**:
```
{{strategy.order.action}} {{ticker}} QTY:{{strategy.order.contracts}} SL:40000 TP:50000
```

### Supported Parameters

- `symbol`: Trading pair (e.g., BTCUSDT, EURUSD)
- `action`: "buy" or "sell"
- `order_type`: "market", "limit", "stop", "trailing"
- `quantity`: Order size
- `price`: Limit/stop price (optional)
- `stop_loss`: Stop loss price (optional)
- `take_profit`: Take profit price (optional)
- `trailing_stop_pct`: Trailing stop percentage (optional)

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get JWT tokens
- `GET /api/auth/me` - Get current user info with webhook URLs
- `POST /api/auth/regenerate-webhook-token` - Regenerate webhook token

### Webhooks
- `POST /blofin/<webhook_token>` - Receive TradingView webhook for Blofin
- `POST /oanda/<webhook_token>` - Receive TradingView webhook for Oanda

### Webhook Logs
- `GET /api/webhook-logs` - Get webhook logs (paginated, filterable)
- `GET /api/webhook-logs/stats` - Get webhook statistics

### Credentials
- `GET /api/credentials` - Get user's credentials
- `POST /api/credentials` - Create new credential set
- `PUT /api/credentials/<id>` - Update credentials
- `DELETE /api/credentials/<id>` - Delete credentials

## Security

- **Webhook Authentication**: Each user has a unique webhook token in their URL
- **API Key Encryption**: All broker API keys are encrypted using Fernet symmetric encryption
- **JWT Authentication**: Secure token-based authentication for API access
- **HTTPS**: Use SSL/TLS certificates in production (configure in nginx/nginx.conf)
- **Environment Variables**: Sensitive data stored in environment variables

## Deployment

### Production Deployment with Nginx

1. **Set up SSL certificates**:
   ```bash
   # Using Let's Encrypt (recommended)
   sudo certbot certonly --standalone -d your-domain.com

   # Copy certificates
   sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/cert.pem
   sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/key.pem
   ```

2. **Update nginx/nginx.conf**:
   - Replace `your-domain.com` with your actual domain
   - Configure SSL certificate paths

3. **Deploy with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

4. **Set up auto-renewal for SSL certificates** (if using Let's Encrypt)

## Troubleshooting

### Webhook not executing
- Check that credentials are active in Settings
- Verify webhook URL is correct in TradingView
- Check webhook logs in Dashboard for errors
- Ensure symbol format is correct (will be auto-converted)

### WebSocket not connecting
- Check browser console for errors
- Verify JWT token is valid
- Ensure SocketIO is properly configured in backend

### Database connection errors
- Verify DATABASE_URI is correct
- Ensure PostgreSQL is running
- Check database credentials

## License

MIT License

## Support

For issues and questions, please open an issue on GitHub.
