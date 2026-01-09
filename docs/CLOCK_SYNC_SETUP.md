# Clock Synchronization Setup Guide

## Overview

Clock synchronization is critical for accurate latency measurements in the tick data collection pipeline. This guide explains how to configure and monitor NTP synchronization.

**Note**: For cloud deployments, see [CLOUD_DEPLOYMENT_GUIDE.md](CLOUD_DEPLOYMENT_GUIDE.md) for cloud-specific instructions.

## Problem

Negative latency (receive_time < event_time) occurs when the server clock is ahead of the MT5 terminal clock. This is typically caused by:

1. Server clock not synchronized with NTP
2. Clock drift over time
3. Timezone misconfiguration

## Solution

### Docker Container Configuration

The trading server Docker container is configured to use NTP synchronization:

1. **NTP Client Installation**: The Dockerfile installs `ntpdate` for NTP synchronization
2. **Host Time Sync**: Docker containers inherit the host system time, so the host must be NTP-synchronized

### Host System Configuration

For production deployments, ensure the host system is NTP-synchronized:

#### Linux (systemd)

```bash
# Enable NTP synchronization
sudo timedatectl set-ntp true

# Verify status
timedatectl status

# Check NTP synchronization
ntpq -p
```

#### Windows

1. Open "Date and Time" settings
2. Enable "Set time automatically"
3. Select time server (e.g., `time.windows.com`)

### Monitoring

The clock sync monitor runs automatically in the trading server:

1. **Automatic Monitoring**: Checks clock sync every 5 minutes
2. **Drift Detection**: Alerts if drift exceeds threshold (default: 1 second)
3. **Health Check**: Available via API endpoint `/api/health/clock-sync`

### Configuration

Environment variables for clock sync monitoring:

- `CLOCK_SYNC_MONITOR_ENABLED`: Enable/disable monitoring (default: `true`)
- `CLOCK_SYNC_CHECK_INTERVAL`: Check interval in seconds (default: `300`)
- `CLOCK_SYNC_DRIFT_THRESHOLD`: Maximum acceptable drift in seconds (default: `1.0`)

### Health Check Endpoint

Check clock sync status via API:

```bash
curl http://localhost:8000/api/health/clock-sync
```

Response:
```json
{
  "status": "healthy",
  "service": "clock_sync",
  "last_drift_seconds": 0.123,
  "last_status": "ok",
  "check_count": 42
}
```

### Troubleshooting

#### Server Clock Ahead of NTP

**Symptoms:**
- Negative latency in tick data
- Clock sync status shows "warning" or "critical"

**Solution:**
1. Synchronize host system clock with NTP
2. Restart Docker containers to pick up new time
3. Verify with `scripts/check_clock_sync.py`

#### Clock Sync Monitor Not Running

**Symptoms:**
- Health check returns "unknown" status
- No clock sync logs

**Solution:**
1. Check environment variable `CLOCK_SYNC_MONITOR_ENABLED=true`
2. Check server logs for clock sync monitor errors
3. Verify monitoring module is available

#### Large Clock Drift

**Symptoms:**
- Clock drift > 5 seconds
- Frequent negative latency

**Solution:**
1. Check NTP server connectivity
2. Verify firewall allows NTP traffic (UDP port 123)
3. Consider using local NTP server for better accuracy

### Manual Clock Sync Check

Run the clock sync check script:

```bash
python scripts/check_clock_sync.py
```

This will:
1. Check server time
2. Compare with NTP servers
3. Report drift and recommendations

### Best Practices

1. **Host NTP Sync**: Always ensure host system is NTP-synchronized
2. **Regular Monitoring**: Monitor clock sync health checks
3. **Alerting**: Set up alerts for clock drift warnings
4. **Documentation**: Document NTP server configuration

### Production Deployment

For production:

1. Use reliable NTP servers (e.g., `pool.ntp.org`, `time.google.com`)
2. Configure multiple NTP servers for redundancy
3. Monitor clock sync health checks
4. Set up alerts for drift > 1 second
5. Document NTP configuration in deployment guide

## Related Documentation

- [Data Collection Investigation](../generated/DATA_ISSUES_INVESTIGATION.md)
- [Negative Latency Root Cause](../generated/NEGATIVE_LATENCY_ROOT_CAUSE.md)
- [Clock Sync Check Script](../../scripts/check_clock_sync.py)
