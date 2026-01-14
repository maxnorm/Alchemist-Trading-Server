# Deployment Guide

## Local Setup

### Prerequisites

- Docker and Docker Compose installed
- MT5 terminal installed (for trading)
- 8GB+ RAM recommended
- 100GB+ disk space

### Quick Start

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd alchemist-platform
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Start Services**
   ```bash
   docker compose up -d
   ```

4. **Wait for Services**
   ```bash
   # Check service status
   docker compose ps
   
   # View logs
   docker compose logs -f
   ```

5. **Access Services**
   - Dashboard: http://localhost:3000
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - MLflow: http://localhost:5000

## Environment Variables

### Required Variables

```env
# Database
DB_HOST=postgres
DB_PORT=5432
DB_NAME=db_forex
DB_USER=forex_user
DB_PASSWORD=forex_password

# Server
SERVER_IP=0.0.0.0
SERVER_PORT=8080

# MLflow
MLFLOW_TRACKING_URI=http://mlflow:5000

# Redis
REDIS_URL=redis://redis:6379
```

### Optional Variables

```env
# Risk Management
CIRCUIT_BREAKER_DAILY_LOSS_PCT=5.0
CIRCUIT_BREAKER_MAX_CONSECUTIVE_LOSSES=5
CIRCUIT_BREAKER_MAX_DRAWDOWN_PCT=20.0

# MyFxBook (optional)
MYFXBOOK_EMAIL=your_email@example.com
MYFXBOOK_PASSWORD=your_password

# Streamer Authentication (Required for tick streamers)
# Generate a secure random token (minimum 32 characters)
# Example: openssl rand -hex 32
# Never commit this to git!
STREAMER_AUTH_TOKEN=your_secure_random_token_here
```

## Database Migrations

### Running Migrations

Migrations are in `src/database/scripts/` and should be run in order using the migration script:

```bash
# Run all migrations
python scripts/run-migrations.py
```

Or connect to PostgreSQL directly:
```bash
# Connect to database
psql -h localhost -U forex_user -d db_forex

# Run migrations manually (in order)
\i src/database/scripts/00_triggers.sql
\i src/database/scripts/01_create.sql
\i src/database/scripts/02_procedures.sql
# ... continue with other scripts in order
\i src/database/scripts/16_timescaledb_setup.sql
```

The migration script:
```bash
python scripts/run-migrations.py
```

## MT5 Configuration

### Setting Up MT5 Connection

1. **Install MT5 Terminal**
   - Download from broker
   - Install and login

2. **Configure Account**
   - Use demo account for testing
   - Note account login and password
   - Set server address

3. **Enable Algorithmic Trading**
   - Tools → Options → Expert Advisors
   - Enable "Allow algorithmic trading"

4. **Configure MT5 Gateway Connection**

   The MT5 EAs connect to the server through the gateway on port 8080. You have three connection options:

   **Option 1: Direct IP Connection (Simplest, No DNS Required)**
   - In EA inputs, set:
     - `ip`: Your server's IP address (e.g., `192.168.1.100` or your public IP)
     - `port`: `8080`
   - Works immediately, no DNS setup needed
   - Recommended for development and testing

   **Option 2: Subdomain with DNS (Production)**
   - Configure DNS A record: `mt5.yourdomain.com` → Your server's public IP address
   - In EA inputs, set:
     - `ip`: `mt5.yourdomain.com`
     - `port`: `8080`
   - Free DNS options: Cloudflare (free tier), DuckDNS, No-IP
   - Recommended for production deployments

   **Option 3: Local Testing with /etc/hosts**
   - Add entry to hosts file:
     - Linux/Mac: `/etc/hosts`: `127.0.0.1 mt5.yourdomain.com`
     - Windows: `C:\Windows\System32\drivers\etc\hosts`: `127.0.0.1 mt5.yourdomain.com`
   - In EA inputs, set:
     - `ip`: `mt5.yourdomain.com`
     - `port`: `8080`
   - Useful for local development

5. **Configure Streamer Authentication**

   **For Tick Streamers (mt5_tick_streamer.mq5):**
   - Generate a secure token: `openssl rand -hex 32` or `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   - Set `STREAMER_AUTH_TOKEN` in your `.env` file (see Environment Variables section)
   - In EA inputs, set:
     - `streamer_token`: The token from your `.env` file
   - No account registration needed for streamers
   - Same token works for all tick streamers (28+ pairs)

   **For Trading Operations (mt5_trading_operation.mq5):**
   - Still uses account-based authentication
   - Register account via API to get `auth_token`
   - In EA inputs, set:
     - `auth_token`: Account auth token from API

6. **Connection Limits and Rate Limiting**
   - Gateway supports up to 100 concurrent connections per IP
   - Sufficient for 28+ tick streamers (major currency pairs) + additional exotic pairs + trading operation EAs
   - Rate limiting: 5 authentication attempts per minute (burst: 5)
   - Limits can be adjusted in `src/gateway/conf.d/stream/mt5.conf` if needed

7. **Test Connection**
   - Start the services: `docker compose up -d`
   - Check gateway logs: `./logs/gateway/mt5_access.log` and `./logs/gateway/mt5_error.log`
   - Verify connection in trading server logs
   - Monitor connection status in dashboard

### MT5 Gateway Logs

Gateway logs are accessible in the codebase:
- Access logs: `./logs/gateway/mt5_access.log` - All connection attempts
- Error logs: `./logs/gateway/mt5_error.log` - Failed connections and errors

View logs in real-time:
```bash
# Access logs
tail -f logs/gateway/mt5_access.log

# Error logs
tail -f logs/gateway/mt5_error.log
```

## Monitoring

### Health Checks

All services provide health endpoints:
- API: `GET /api/v1/health`
- Server: Check logs for "Server started"

### Logs

View logs for each service:
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f server
docker compose logs -f api
docker compose logs -f gateway
```

Log files are also stored in `logs/` directory:
- Trading server logs: `logs/` (tick_streamer.log, mt5_price_connector.log, etc.)
- Gateway logs: `logs/gateway/` (mt5_access.log, mt5_error.log, gateway_access.log, gateway_error.log)
- API logs: Check container logs or application logs

### Metrics

- MLflow: Track experiment metrics at http://localhost:5000
- Database: Monitor query performance
- API: Check response times in logs

## Troubleshooting

### Services Won't Start

1. **Check Docker**
   ```bash
   docker --version
   docker compose version
   ```

2. **Check Ports**
   ```bash
   # Check if ports are in use
   netstat -an | grep 8000
   netstat -an | grep 3000
   ```

3. **Check Logs**
   ```bash
   docker compose logs
   ```

### Database Connection Errors

1. **Verify Database is Running**
   ```bash
   docker compose ps postgres
   ```

2. **Check Credentials**
   - Verify `.env` file has correct credentials
   - Test connection: `psql -h localhost -U forex_user -d db_forex`

3. **Check Network**
   - Ensure services are on same Docker network
   - Check `docker-compose.yml` network configuration

### MT5 Connection Issues

1. **Verify MT5 Terminal is Running**
   - Check MT5 is logged in
   - Verify account is active

2. **Check Server Logs**
   ```bash
   docker compose logs server | grep -i mt5
   ```

3. **Test Connection Manually**
   - Use MT5's built-in connection test
   - Verify firewall allows connections

## Backup and Restore

### Database Backup

```bash
# Manual backup
docker compose exec postgres pg_dump -U forex_user db_forex --format=custom > backup.dump

# Automated backup (if configured)
python src/database/backup.py
```

### Restore Database

```bash
# Restore from backup
docker compose exec -T postgres pg_restore -U forex_user -d db_forex < backup.dump
```

## Updates

### Updating Services

1. **Pull Latest Code**
   ```bash
   git pull
   ```

2. **Rebuild Images**
   ```bash
   docker compose build
   ```

3. **Restart Services**
   ```bash
   docker compose up -d
   ```

4. **Run Migrations** (if schema changed)
   ```bash
   python scripts/run-migrations.py
   ```

## Security Considerations

### Local Deployment

- No authentication required (single-user)
- All services on localhost
- Database credentials in `.env` (never commit)

### Production Deployment (Future)

- Enable authentication
- Use HTTPS
- Secure database credentials
- Enable firewall rules
- Regular security updates

## Performance Tuning

### Database

- Add indexes for frequently queried columns
- Monitor slow queries
- Adjust connection pool size

### API

- Enable response caching
- Optimize database queries
- Use connection pooling

### Training

- Adjust batch sizes
- Use GPU if available
- Monitor memory usage
