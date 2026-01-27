# Testing Data Collection Pipeline Improvements

This guide explains how to test the three main improvements:
1. Clock Synchronization
2. Connection Monitoring and Auto-Reconnect
3. Gap Detection Alerts

**Note**: For cloud deployment testing, see [CLOUD_DEPLOYMENT_GUIDE.md](CLOUD_DEPLOYMENT_GUIDE.md).

## Prerequisites

1. **Database running**: PostgreSQL/TimescaleDB must be running
2. **Python environment**: Install required packages
3. **API server** (optional): For testing health check endpoints

## Quick Test

Run the comprehensive test script:

```bash
python scripts/test_data_collection_improvements.py
```

This will test all components and provide a summary.

## Individual Component Tests

### 1. Clock Synchronization

#### Test Clock Sync Monitor

```bash
python -c "
import sys
sys.path.insert(0, 'src/trading_server/src')
from monitoring.clock_sync_monitor import ClockSyncMonitor

monitor = ClockSyncMonitor(check_interval_seconds=10)
result = monitor.check_clock_sync()
print(f'Status: {result[\"status\"]}')
print(f'Drift: {result.get(\"drift_seconds\", \"N/A\")} seconds')
"
```

#### Test Health Check Endpoint

```bash
# Start API server first
curl http://localhost:8000/api/health/clock-sync
```

Expected response:
```json
{
  "status": "healthy",
  "service": "clock_sync",
  "last_drift_seconds": 0.123,
  "last_status": "ok"
}
```

#### Manual Clock Sync Check

```bash
python scripts/check_clock_sync.py
```

This will:
- Check server time
- Compare with NTP servers
- Report drift and recommendations

### 2. Connection Monitoring and Auto-Reconnect

#### Test Connection State Manager

```bash
python -c "
import sys
sys.path.insert(0, 'src/trading_server/src')
from mt5_connection.connection_state import ConnectionStateManager, ConnectionState

manager = ConnectionStateManager('EURUSD')
manager.transition_to(ConnectionState.CONNECTING, 'Test')
manager.transition_to(ConnectionState.CONNECTED, 'Test')
metrics = manager.get_metrics()
print(f'State: {metrics[\"current_state\"]}')
print(f'Reconnection attempts: {metrics[\"reconnection_attempts\"]}')
"
```

#### Test Connection Health Tracking

The connection health tracking is integrated into the tick streamer. To test:

1. **Start tick streamer** with a symbol
2. **Monitor logs** for connection health messages:
   - Look for "connection_stale" events
   - Check for periodic health check logs

```bash
# In tick streamer logs, look for:
# - "Connection health check" messages
# - "Connection stale" warnings
# - "No ticks received" warnings
```

#### Test Auto-Reconnect

To test auto-reconnect:

1. **Start tick streamer** with a symbol
2. **Simulate connection loss**:
   - Stop MT5 EA
   - Disconnect network
   - Close socket connection
3. **Observe reconnection attempts**:
   - Check logs for reconnection messages
   - Verify exponential backoff
   - Confirm successful reconnection

```bash
# Monitor logs for:
# - "Connection lost" messages
# - "Reconnecting" state transitions
# - "Reconnected" success messages
```

### 3. Gap Detection

#### Test Gap Detector

```bash
python -c "
import sys
import os
sys.path.insert(0, 'src/trading_server/src')
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '5432'
os.environ['DB_USER'] = 'forex_user'
os.environ['DB_PASSWORD'] = 'forex_password'
os.environ['DB_NAME'] = 'db_forex'

from monitoring.gap_detector import GapDetector

detector = GapDetector(
    gap_threshold_minutes=5.0,
    check_interval_minutes=1.0,
    lookback_minutes=10.0
)

gaps = detector.detect_gaps()
print(f'Detected {len(gaps)} gaps')
for gap in gaps[:5]:
    print(f\"  {gap['symbol']}: {gap['gap_seconds']/60:.1f} minutes\")
"
```

#### Test Gap Detection Alerts

1. **Start gap detector** (runs automatically with server)
2. **Create a test gap** in the database (optional):
   ```sql
   -- Insert a gap by deleting some ticks
   DELETE FROM ticks_forex 
   WHERE symbol = 'EURUSD' 
   AND datetime BETWEEN '2026-01-09 10:00:00' AND '2026-01-09 10:10:00';
   ```
3. **Monitor for alerts**:
   - Check logs for "data_gap_detected" events
   - Check WebSocket alerts channel
   - Check Prometheus metrics

#### Test System-Wide Gap Detection

The gap detector automatically detects when 3+ symbols gap simultaneously:

1. **Monitor logs** for "system_wide_gap" events
2. **Check Prometheus** for `system_wide_gap_active` metric
3. **Verify alerts** are sent via WebSocket

## Integration Testing

### Test Full Pipeline

1. **Start all services**:
   ```bash
   docker-compose up -d
   ```

2. **Start tick streamer** with multiple symbols

3. **Monitor all components**:
   - Clock sync: Check `/api/health/clock-sync`
   - Connection health: Monitor tick streamer logs
   - Gap detection: Check gap detector logs

4. **Simulate issues**:
   - Clock drift: Change system time
   - Connection loss: Stop MT5 EA
   - Data gaps: Create gaps in database

5. **Verify responses**:
   - Clock sync warnings logged
   - Auto-reconnect attempts
   - Gap detection alerts

## Monitoring Tests

### Check Clock Sync Status

```bash
# Via API
curl http://localhost:8000/api/health/clock-sync

# Via script
python scripts/check_clock_sync.py
```

### Check Connection Health

Monitor tick streamer logs for:
- Connection health check messages (every 30 seconds)
- Connection stale warnings
- Reconnection attempts

### Check Gap Detection

Monitor gap detector logs for:
- Gap detection messages (every 5 minutes during market hours)
- System-wide gap alerts
- Prolonged gap alerts

## Prometheus Metrics

Check Prometheus for new metrics:

```bash
# Clock sync metrics (if exposed)
curl http://localhost:9090/api/v1/query?query=clock_sync_drift_seconds

# Gap detection metrics
curl http://localhost:9090/api/v1/query?query=data_gap_duration_seconds
curl http://localhost:9090/api/v1/query?query=system_wide_gap_active
```

## WebSocket Alerts

Test WebSocket alert delivery:

1. **Connect to WebSocket**:
   ```javascript
   const ws = new WebSocket('ws://localhost:8000/ws/alerts');
   ws.onmessage = (event) => {
     const alert = JSON.parse(event.data);
     console.log('Alert:', alert);
   };
   ```

2. **Trigger alerts**:
   - Create a data gap
   - Wait for gap detection
   - Verify alert received

## Troubleshooting

### Clock Sync Not Working

- Check NTP server connectivity
- Verify host system is NTP-synced
- Check firewall allows UDP port 123
- Review clock sync monitor logs

### Auto-Reconnect Not Working

- Check connection state manager logs
- Verify reconnection is enabled in config
- Check socket connection status
- Review tick streamer logs

### Gap Detection Not Working

- Verify database connection
- Check market hours (only runs during trading hours)
- Review gap detector logs
- Verify gap threshold configuration

## Success Criteria

All tests should verify:

1. **Clock Sync**:
   - ✓ Clock sync monitor runs and checks NTP
   - ✓ Health check endpoint returns status
   - ✓ Drift warnings logged when threshold exceeded

2. **Connection Monitoring**:
   - ✓ Connection health tracked
   - ✓ Stale connection warnings logged
   - ✓ Auto-reconnect attempts on connection loss

3. **Gap Detection**:
   - ✓ Gaps detected during market hours
   - ✓ System-wide gaps identified
   - ✓ Alerts sent via WebSocket
   - ✓ Prometheus metrics updated

## Next Steps

After testing:

1. **Monitor in production**: Watch logs and metrics
2. **Tune thresholds**: Adjust based on actual data
3. **Set up alerting**: Configure alerts for critical issues
4. **Document findings**: Record any issues or improvements needed
