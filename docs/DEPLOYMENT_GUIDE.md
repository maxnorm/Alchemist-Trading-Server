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
DB_HOST=mariadb
DB_PORT=3306
DB_NAME=db_forex
DB_USER=forex_user
DB_PASSWORD=forex_password

# Server
SERVER_IP=0.0.0.0
SERVER_PORT=1234

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
```

## Database Migrations

### Running Migrations

Migrations are in `src/database/scripts/` and should be run in order:

```bash
# Connect to database
mysql -u forex_user -p db_forex

# Run migrations
source src/database/scripts/06_features.sql
source src/database/scripts/07_experiments.sql
source src/database/scripts/08_performance_tracking.sql
source src/database/scripts/09_models.sql
```

Or use the migration script:
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

4. **Test Connection**
   - Start the server: `docker compose up server`
   - Check logs for connection status
   - Verify in dashboard

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
```

Log files are also stored in `logs/` directory.

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
   docker compose ps mariadb
   ```

2. **Check Credentials**
   - Verify `.env` file has correct credentials
   - Test connection: `mysql -u user -p -h localhost`

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
docker compose exec mariadb mysqldump -u forex_user -p db_forex > backup.sql

# Automated backup (if configured)
python scripts/backup.py
```

### Restore Database

```bash
# Restore from backup
docker compose exec -T mariadb mysql -u forex_user -p db_forex < backup.sql
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
