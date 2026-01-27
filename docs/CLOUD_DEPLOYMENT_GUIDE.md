# Cloud Deployment Guide for Data Collection Improvements

This guide covers cloud-specific considerations for deploying the data collection pipeline improvements.

## Overview

The three main improvements (clock sync, connection monitoring, gap detection) work in cloud environments but require some configuration adjustments.

## 1. Clock Synchronization in Cloud

### Cloud Provider NTP

Most cloud providers handle NTP synchronization automatically:

- **AWS**: EC2 instances sync with Amazon Time Sync Service
- **Azure**: VMs sync with time.windows.com
- **GCP**: Compute Engine syncs with Google's internal NTP
- **Docker/Kubernetes**: Containers inherit host time

### Configuration

#### AWS EC2

```bash
# Verify NTP is enabled
sudo timedatectl status

# If needed, configure chrony for Amazon Time Sync
sudo yum install chrony  # Amazon Linux
sudo apt-get install chrony  # Ubuntu

# Edit /etc/chrony.conf
# Add: server 169.254.169.123 prefer iburst
```

#### Azure VM

```bash
# Azure VMs automatically sync with time.windows.com
# Verify with:
w32tm /query /status
```

#### GCP Compute Engine

```bash
# GCP automatically syncs
# Verify with:
chronyc sources
```

#### Docker Containers

Docker containers inherit the host time. Ensure the host is NTP-synced:

```yaml
# docker-compose.yml
services:
  server:
    # Containers inherit host time
    # No special NTP configuration needed if host is synced
```

### Monitoring

The clock sync monitor works the same in cloud:

```bash
# Check clock sync status
curl https://your-api-domain.com/api/health/clock-sync
```

### Environment Variables

```bash
# Cloud deployment .env
CLOCK_SYNC_MONITOR_ENABLED=true
CLOCK_SYNC_CHECK_INTERVAL=300  # 5 minutes
CLOCK_SYNC_DRIFT_THRESHOLD=1.0  # 1 second
```

## 2. Connection Monitoring and Auto-Reconnect

### Cloud Network Considerations

#### Load Balancers

If using a load balancer:
- Ensure sticky sessions for WebSocket connections
- Configure health checks for connection endpoints
- Set appropriate timeout values

#### Network Latency

Cloud deployments may have higher latency:
- Adjust `CONNECTION_STALE_THRESHOLD_SECONDS` if needed
- Monitor connection health metrics
- Consider regional deployment for lower latency

### Configuration

```bash
# Connection health tracking
CONNECTION_HEALTH_CHECK_INTERVAL=30.0  # seconds
CONNECTION_STALE_THRESHOLD_SECONDS=60.0  # seconds

# Auto-reconnect
AUTO_RECONNECT=true
MAX_RECONNECT_ATTEMPTS=10
RECONNECT_BACKOFF_BASE=1.0
RECONNECT_BACKOFF_MAX=60.0
```

### Health Checks

Expose connection health via load balancer:

```yaml
# Example: AWS ALB health check
health_check:
  path: /api/health
  interval: 30
  timeout: 5
  healthy_threshold: 2
  unhealthy_threshold: 3
```

## 3. Gap Detection

### Database Connection

In cloud, database may be in a different region:

```bash
# Database connection settings
DB_HOST=your-db-host.rds.amazonaws.com  # AWS RDS
DB_HOST=your-db.postgres.database.azure.com  # Azure Database
DB_PORT=5432
DB_USER=forex_user
DB_PASSWORD=your-secure-password
DB_NAME=db_forex

# Connection pooling (important for cloud)
DB_MAX_RETRIES=5
DB_RETRY_DELAY=2.0
```

### Gap Detection Configuration

```bash
# Gap detection settings
GAP_DETECTOR_ENABLED=true
GAP_THRESHOLD_MINUTES=5.0
GAP_CHECK_INTERVAL_MINUTES=5.0
GAP_LOOKBACK_MINUTES=10.0
```

### Market Hours

Ensure timezone is correctly configured:

```bash
# Set timezone in container
TZ=UTC

# Or in docker-compose.yml
environment:
  - TZ=UTC
```

## 4. Health Check Endpoints

### Public vs Private Endpoints

#### Public Health Checks

For load balancer health checks:

```python
# /api/health endpoint (public)
@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api"}
```

#### Internal Health Checks

For internal monitoring:

```python
# /api/health/clock-sync (internal)
# /api/health/db (internal)
# /api/health/mlflow (internal)
```

### Security

Protect internal health checks:

```yaml
# nginx/gateway configuration
location /api/health/clock-sync {
    # Allow only from internal network
    allow 10.0.0.0/8;
    deny all;
    proxy_pass http://api/api/health/clock-sync;
}
```

## 5. Monitoring and Alerting

### Cloud Monitoring Integration

#### AWS CloudWatch

```python
# Example: Send clock sync metrics to CloudWatch
import boto3

cloudwatch = boto3.client('cloudwatch')

def send_clock_sync_metric(drift_seconds):
    cloudwatch.put_metric_data(
        Namespace='TradingSystem/ClockSync',
        MetricData=[{
            'MetricName': 'ClockDrift',
            'Value': drift_seconds,
            'Unit': 'Seconds'
        }]
    )
```

#### Azure Monitor

```python
# Example: Send metrics to Azure Monitor
from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor()
```

#### GCP Cloud Monitoring

```python
# Example: Send metrics to GCP
from google.cloud import monitoring_v3

client = monitoring_v3.MetricServiceClient()
```

### Prometheus in Cloud

If using Prometheus:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'trading-server'
    static_configs:
      - targets: ['server:8080']
    # In cloud, use service discovery instead
```

### Alerting

Configure alerts for:

1. **Clock Sync Drift**: Alert if drift > 1 second
2. **Connection Failures**: Alert on multiple reconnection failures
3. **Data Gaps**: Alert on system-wide gaps

## 6. Docker/Kubernetes Deployment

### Docker Compose (Cloud VM)

```yaml
# docker-compose.yml
services:
  server:
    image: your-registry/trading-server:latest
    environment:
      - CLOCK_SYNC_MONITOR_ENABLED=true
      - GAP_DETECTOR_ENABLED=true
      - TZ=UTC
    # Containers inherit host NTP sync
```

### Kubernetes

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-server
spec:
  template:
    spec:
      containers:
      - name: server
        image: your-registry/trading-server:latest
        env:
        - name: CLOCK_SYNC_MONITOR_ENABLED
          value: "true"
        - name: GAP_DETECTOR_ENABLED
          value: "true"
        - name: TZ
          value: "UTC"
        # Health checks
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
```

## 7. Security Considerations

### Secrets Management

Use cloud secrets managers:

#### AWS Secrets Manager

```python
import boto3

secrets_client = boto3.client('secretsmanager')
secret = secrets_client.get_secret_value(SecretId='trading-db-credentials')
credentials = json.loads(secret['SecretString'])
```

#### Azure Key Vault

```python
from azure.keyvault.secrets import SecretClient

client = SecretClient(vault_url="https://your-vault.vault.azure.net/", credential=credential)
password = client.get_secret("db-password").value
```

#### GCP Secret Manager

```python
from google.cloud import secretmanager

client = secretmanager.SecretManagerServiceClient()
name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
response = client.access_secret_version(request={"name": name})
password = response.payload.data.decode("UTF-8")
```

### Network Security

- Use VPC/private networks for database connections
- Restrict health check endpoints to internal networks
- Use TLS for all connections
- Implement rate limiting

## 8. Scaling Considerations

### Horizontal Scaling

If scaling multiple instances:

1. **Clock Sync**: Each instance monitors independently
2. **Connection Monitoring**: Per-instance tracking
3. **Gap Detection**: Should run on one instance only (use leader election)

```python
# Example: Leader election for gap detector
import redis

redis_client = redis.Redis(host='your-redis-host')

def is_leader():
    # Try to acquire lock
    return redis_client.set('gap_detector_leader', 'true', nx=True, ex=300)
```

### Database Connection Pooling

Configure appropriate pool sizes:

```python
# database.py
engine = create_engine(
    database_url,
    pool_size=20,  # Increase for cloud
    max_overflow=40,
    pool_pre_ping=True,
)
```

## 9. Deployment Checklist

### Pre-Deployment

- [ ] Verify cloud provider NTP configuration
- [ ] Configure database connection strings
- [ ] Set up secrets management
- [ ] Configure health check endpoints
- [ ] Set up monitoring and alerting
- [ ] Test in staging environment

### Post-Deployment

- [ ] Verify clock sync monitor is running
- [ ] Check connection health tracking
- [ ] Test gap detection
- [ ] Monitor health check endpoints
- [ ] Verify alerts are working
- [ ] Review logs for any issues

## 10. Troubleshooting

### Clock Sync Issues in Cloud

**Problem**: Large clock drift

**Solutions**:
1. Verify host NTP is enabled
2. Check cloud provider time sync service
3. Review clock sync monitor logs
4. Check firewall rules for NTP (UDP 123)

### Connection Issues

**Problem**: Frequent reconnections

**Solutions**:
1. Check network latency
2. Review connection health thresholds
3. Verify load balancer configuration
4. Check database connection pool

### Gap Detection Issues

**Problem**: Gaps not detected

**Solutions**:
1. Verify database connectivity
2. Check market hours configuration
3. Review gap detector logs
4. Verify timezone settings

## 11. Cloud-Specific Best Practices

1. **Use Managed Services**: Use managed databases (RDS, Azure Database, Cloud SQL)
2. **Implement Circuit Breakers**: For external service calls
3. **Use Health Checks**: For load balancer and orchestration
4. **Monitor Everything**: Use cloud monitoring services
5. **Automate Scaling**: Based on connection health metrics
6. **Implement Retries**: With exponential backoff
7. **Use Secrets Management**: Never hardcode credentials
8. **Enable Logging**: Centralized logging (CloudWatch, Azure Monitor, Stackdriver)

## 12. Example Cloud Configurations

### AWS ECS

```json
{
  "containerDefinitions": [{
    "name": "trading-server",
    "environment": [
      {"name": "CLOCK_SYNC_MONITOR_ENABLED", "value": "true"},
      {"name": "GAP_DETECTOR_ENABLED", "value": "true"},
      {"name": "TZ", "value": "UTC"}
    ],
    "healthCheck": {
      "command": ["CMD-SHELL", "curl -f http://localhost:8080/api/health || exit 1"],
      "interval": 30,
      "timeout": 5,
      "retries": 3
    }
  }]
}
```

### Azure Container Instances

```yaml
apiVersion: 2018-10-01
properties:
  containers:
  - name: trading-server
    properties:
      environmentVariables:
      - name: CLOCK_SYNC_MONITOR_ENABLED
        value: "true"
      - name: GAP_DETECTOR_ENABLED
        value: "true"
      - name: TZ
        value: "UTC"
```

## Summary

Cloud deployment requires:
1. ✅ Trusting cloud provider NTP (usually automatic)
2. ✅ Configuring database connections for cloud
3. ✅ Setting up health checks for load balancers
4. ✅ Using secrets management
5. ✅ Configuring monitoring and alerting
6. ✅ Handling scaling considerations

All three improvements work in cloud with proper configuration!
