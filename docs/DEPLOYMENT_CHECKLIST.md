# Data Collection Improvements - Deployment Checklist

Use this checklist when deploying the data collection pipeline improvements to production (cloud or on-premise).

## Pre-Deployment

### Clock Synchronization

- [ ] Verify host system NTP is enabled and synchronized
  - [ ] Linux: `timedatectl status` shows "NTP service: active"
  - [ ] Windows: Time sync is enabled in settings
  - [ ] Cloud: Verify cloud provider time sync (usually automatic)
- [ ] Run host NTP verification: `python scripts/verify_host_ntp.py`
  - [ ] Verify NTP service status
  - [ ] Verify NTP server connectivity
  - [ ] Verify clock drift < 1 second
  - [ ] Verify Docker container time inheritance (if using Docker)
- [ ] Test clock sync monitor: `python scripts/check_clock_sync.py`
- [ ] Verify server-NTP drift is < 1 second
- [ ] Configure server-NTP monitoring environment variables:
  - [ ] `CLOCK_SYNC_MONITOR_ENABLED=true`
  - [ ] `CLOCK_SYNC_CHECK_INTERVAL=300`
  - [ ] `CLOCK_SYNC_DRIFT_THRESHOLD=1.0`
- [ ] Configure MT5 clock monitoring environment variables:
  - [ ] `MT5_CLOCK_MONITOR_ENABLED=true`
  - [ ] `MT5_CLOCK_WINDOW_SIZE=1000`
  - [ ] `MT5_CLOCK_DRIFT_THRESHOLD=1.0`
  - [ ] `MT5_CLOCK_ALERT_COOLDOWN_MINUTES=5`
- [ ] Configure negative latency compliance thresholds:
  - [ ] `NEGATIVE_LATENCY_WARNING_THRESHOLD=0.1` (10%)
  - [ ] `NEGATIVE_LATENCY_CRITICAL_THRESHOLD=0.2` (20%)
- [ ] Verify MT5 clock monitoring is active after deployment
- [ ] Test health check endpoint: `curl http://localhost:8000/api/health/clock-sync`
  - [ ] Verify response includes `server_ntp` and `mt5_broker` sections
  - [ ] Verify negative latency rate is reported

### Connection Monitoring

- [ ] Configure connection health settings:
  - [ ] `CONNECTION_HEALTH_CHECK_INTERVAL=30.0`
  - [ ] `CONNECTION_STALE_THRESHOLD_SECONDS=60.0`
- [ ] Configure auto-reconnect settings:
  - [ ] `AUTO_RECONNECT=true`
  - [ ] `MAX_RECONNECT_ATTEMPTS=10`
  - [ ] `RECONNECT_BACKOFF_BASE=1.0`
  - [ ] `RECONNECT_BACKOFF_MAX=60.0`
- [ ] Test connection state manager
- [ ] Verify connection health tracking is enabled

### Gap Detection

- [ ] Configure gap detection settings:
  - [ ] `GAP_DETECTOR_ENABLED=true`
  - [ ] `GAP_THRESHOLD_MINUTES=5.0`
  - [ ] `GAP_CHECK_INTERVAL_MINUTES=5.0`
  - [ ] `GAP_LOOKBACK_MINUTES=10.0`
- [ ] Verify database connection for gap detection
- [ ] Test gap detector: `python scripts/test_data_collection_improvements.py`
- [ ] Configure Prometheus alerts (if using Prometheus)

### Database

- [ ] Verify database connection settings:
  - [ ] `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- [ ] Test database connectivity
- [ ] Verify connection pooling settings
- [ ] Check database timezone is UTC

### Health Checks

- [ ] Verify health check endpoints are accessible:
  - [ ] `/api/health` (basic)
  - [ ] `/api/health/clock-sync` (clock sync)
  - [ ] `/api/health/db` (database)
- [ ] Configure load balancer health checks (if applicable)
- [ ] Test health check endpoints

### Monitoring and Alerting

- [ ] Set up monitoring dashboards:
  - [ ] Server-NTP clock sync drift (`clock_drift_seconds{source="server_ntp"}`)
  - [ ] MT5 broker clock drift (`clock_drift_seconds{source="mt5_broker"}`)
  - [ ] Negative latency rate (`negative_latency_rate`)
  - [ ] Clock sync health status (`clock_sync_status`)
  - [ ] Connection health
  - [ ] Gap detection metrics
- [ ] Configure alerts:
  - [ ] Server-NTP clock drift > 1 second
  - [ ] MT5 broker clock drift > 1 second (persistent)
  - [ ] Negative latency rate > 10% (warning) or > 20% (critical)
  - [ ] Clock sync status unhealthy
  - [ ] Connection failures
  - [ ] System-wide gaps
  - [ ] Prolonged gaps (>30 minutes)
- [ ] Test alert delivery (WebSocket, email, etc.)

### Security

- [ ] Use secrets management (no hardcoded credentials)
- [ ] Restrict health check endpoints to internal networks
- [ ] Enable TLS for all connections
- [ ] Configure firewall rules

### Cloud-Specific (if applicable)

- [ ] Verify cloud provider NTP/time sync
- [ ] Configure VPC/private networks
- [ ] Set up cloud monitoring integration
- [ ] Configure auto-scaling (if needed)
- [ ] Set up leader election for gap detector (if multiple instances)

## Deployment

### Step 1: Deploy Code

- [ ] Build Docker images (if using Docker)
- [ ] Push images to registry
- [ ] Update deployment configuration
- [ ] Deploy to staging environment first

### Step 2: Verify Services

- [ ] All containers/services are running
- [ ] Health checks are passing
- [ ] No errors in logs

### Step 3: Test Components

- [ ] Run test suite: `python scripts/test_data_collection_improvements.py`
- [ ] Verify clock sync monitor is running
- [ ] Check connection health tracking
- [ ] Test gap detection
- [ ] Verify alerts are working

### Step 4: Monitor

- [ ] Watch logs for first 30 minutes
- [ ] Check clock sync status
- [ ] Monitor connection health
- [ ] Verify gap detection is working
- [ ] Check alert delivery

## Post-Deployment

### Immediate (First Hour)

- [ ] Verify clock sync: `curl /api/health/clock-sync`
- [ ] Check connection health logs
- [ ] Verify gap detection is running
- [ ] Test alert delivery
- [ ] Monitor error rates

### Short Term (First Day)

- [ ] Review clock sync drift trends
- [ ] Check connection reconnection rates
- [ ] Analyze gap detection results
- [ ] Verify alert accuracy
- [ ] Review performance metrics

### Ongoing

- [ ] Weekly review of clock sync status
- [ ] Monthly review of connection health metrics
- [ ] Quarterly review of gap detection effectiveness
- [ ] Update thresholds based on actual data

## Rollback Plan

If issues occur:

1. **Clock Sync Issues**:
   - Disable clock sync monitor: `CLOCK_SYNC_MONITOR_ENABLED=false`
   - Manually sync host clock
   - Re-enable monitor

2. **Connection Issues**:
   - Disable auto-reconnect: `AUTO_RECONNECT=false`
   - Review connection logs
   - Adjust thresholds

3. **Gap Detection Issues**:
   - Disable gap detector: `GAP_DETECTOR_ENABLED=false`
   - Review database connectivity
   - Check query performance

## Success Criteria

Deployment is successful when:

- [ ] Clock sync drift < 1 second
- [ ] Connection health tracking working
- [ ] Auto-reconnect functioning
- [ ] Gap detection running
- [ ] Alerts being delivered
- [ ] No increase in error rates
- [ ] Performance metrics stable

## Documentation

- [ ] Update deployment documentation
- [ ] Document any custom configurations
- [ ] Record any issues and resolutions
- [ ] Update runbooks

## Support

If issues arise:

1. Check logs: `docker-compose logs server`
2. Review health checks: `/api/health/*`
3. Run diagnostics: `python scripts/check_clock_sync.py`
4. Review monitoring dashboards
5. Check alert history

## Notes

- Record any deviations from standard configuration
- Document any cloud-specific settings
- Note any performance observations
- Record any issues encountered
