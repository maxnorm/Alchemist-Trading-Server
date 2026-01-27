# Database Connection Troubleshooting Guide

## Quick Diagnosis

### 1. Check Database Health
```bash
# Check if database container is running
docker compose ps postgres

# Check database health via API
curl http://localhost/api/health/db

# Or check directly in the API container
docker compose exec api curl http://localhost:8000/health/db
```

### 2. Check Database Container Status
```bash
# View database logs
docker compose logs postgres

# Check if database is accepting connections
docker compose exec postgres pg_isready -U forex_user -d db_forex
```

### 3. Check API Container Logs
```bash
# View API logs for database connection errors
docker compose logs api | grep -i database
```

## Common Issues and Solutions

### Issue 1: Database Container Not Running
**Symptoms:** All API endpoints return 503

**Solution:**
```bash
# Start the database
docker compose up -d postgres

# Wait for it to be healthy
docker compose ps postgres
```

### Issue 2: Database Not Ready When API Starts
**Symptoms:** API starts but can't connect to database

**Solution:**
The API now has retry logic, but if it still fails:
```bash
# Restart the API container
docker compose restart api

# Check logs
docker compose logs api
```

### Issue 3: Wrong Connection String
**Symptoms:** Connection refused or authentication failed

**Check:**
```bash
# Verify environment variables in API container
docker compose exec api env | grep DB_

# Should show:
# DB_HOST=postgres
# DB_PORT=5432
# DB_USER=forex_user
# DB_PASSWORD=forex_password
# DB_NAME=db_forex
```

### Issue 4: Database Tables Missing
**Symptoms:** Connection works but queries fail

**Solution:**
```bash
# Check if tables exist
docker compose exec postgres psql -U forex_user -d db_forex -c "\dt"

# If tables are missing, check initialization scripts
ls -la src/database/scripts/
```

## Enhanced Error Messages

The API now provides detailed error information:

1. **Health Check Endpoint** (`/api/health/db`):
   - Shows database host, port, database name
   - Provides specific error messages
   - Indicates error type

2. **Database Connection Logs**:
   - Retry attempts are logged
   - Connection errors include full details
   - Connection string (without password) is logged

## Testing Database Connection

### From API Container
```bash
# Test connection directly
docker compose exec api python -c "
from src.api.src.services.database import init_db, check_db_health
init_db()
print('Database healthy:', check_db_health())
"
```

### From Host Machine
```bash
# Test connection using psql (if installed)
psql -h localhost -p 5432 -U forex_user -d db_forex
# Note: This won't work if postgres port is not exposed
```

## Restart Sequence

If database connection issues persist:

```bash
# 1. Stop all services
docker compose down

# 2. Start database first
docker compose up -d postgres

# 3. Wait for database to be healthy
docker compose ps postgres

# 4. Start API
docker compose up -d api

# 5. Check API logs
docker compose logs -f api
```

## Connection Retry Logic

The API now includes:
- **Startup retry**: 5 attempts with 2-second delays
- **Session retry**: 3 attempts with exponential backoff
- **Connection pooling**: Automatic reconnection via `pool_pre_ping`

## Monitoring

### Check Database Connection Status
```bash
# Via health endpoint
curl http://localhost/api/health/db | jq

# Expected healthy response:
{
  "status": "healthy",
  "service": "database",
  "host": "postgres",
  "port": 5432,
  "database": "db_forex"
}
```

### Check API Logs for Database Errors
```bash
# Real-time logs
docker compose logs -f api | grep -i "database\|error\|503"

# Historical errors
docker compose logs api | grep -i "database.*error"
```

## Next Steps After Fixing

Once the database connection is working:

1. **Verify API Endpoints**:
   ```bash
   curl http://localhost/api/v1/models
   curl http://localhost/api/v1/experiments
   curl http://localhost/api/v1/features
   ```

2. **Check Dashboard**:
   - Open http://localhost
   - Check browser console for errors
   - Verify data loads correctly

3. **Monitor Health**:
   - Set up monitoring for `/api/health/db`
   - Alert on 503 responses
