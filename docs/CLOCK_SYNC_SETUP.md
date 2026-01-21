# Clock Synchronization Setup Guide

## Overview

Clock synchronization is critical for accurate latency measurements in the tick data collection pipeline. This guide explains how to configure and monitor NTP synchronization.

**Note**: For cloud deployments, see [CLOUD_DEPLOYMENT_GUIDE.md](CLOUD_DEPLOYMENT_GUIDE.md) for cloud-specific instructions.

## Problem

Negative latency (receive_time < event_time) occurs when clocks are not properly synchronized. This can be caused by:

1. **Server clock not synchronized with NTP** - Server clock drifts from UTC
2. **MT5 broker clock drift** - MT5 broker server clock differs from our server clock (cannot be controlled)
3. **Clock drift over time** - Clocks naturally drift without synchronization
4. **Timezone misconfiguration** - Incorrect timezone settings

**Important**: MT5 broker clock cannot be controlled by the client. We can only monitor drift and alert when it exceeds thresholds.

## Solution

### Docker Container Configuration

**Important**: Docker containers inherit the host kernel clock via VDSO (Virtual Dynamic Shared Object). We do NOT run NTP synchronization inside containers - the host system must be NTP-synchronized.

1. **NTP Client Installation**: The Dockerfile installs `ntpsec-ntpdate` for verification scripts only (not for sync)
2. **Host Time Sync**: Docker containers automatically inherit host system time - ensure host is NTP-synchronized
3. **Best Practice**: Sync the host, not the container (industry standard)

### Host System Configuration

**CRITICAL**: The host system must be NTP-synchronized before deploying the trading server. Docker containers inherit the host kernel clock, so host NTP sync is essential.

#### Pre-Deployment Verification

Before deploying, verify host NTP synchronization:

```bash
# Run host NTP verification script
python scripts/verify_host_ntp.py
```

This script checks:
- NTP service status (Linux: systemd-timesyncd/chronyd, Windows: w32tm)
- NTP server connectivity
- Current clock drift
- Docker container time inheritance
- Provides remediation steps if issues found

#### Linux (systemd)

```bash
# Enable NTP synchronization
sudo timedatectl set-ntp true

# Verify status
timedatectl status

# Check NTP synchronization
ntpq -p

# Alternative: Use chronyd
sudo systemctl enable chronyd
sudo systemctl start chronyd
chronyc sources
```

#### Windows

1. Open "Date and Time" settings
2. Enable "Set time automatically"
3. Select time server (e.g., `time.windows.com`)

Or via command line:
```powershell
# Configure Windows Time service
w32tm /config /manualpeerlist:time.windows.com /syncfromflags:manual /reliable:yes /update

# Start Windows Time service
net start w32time

# Verify status
w32tm /query /status
```

### Monitoring

The trading server includes comprehensive clock synchronization monitoring:

#### Server-NTP Monitoring

1. **Automatic Monitoring**: Checks server clock vs NTP every 5 minutes
2. **Drift Detection**: Alerts if drift exceeds threshold (default: 1 second)
3. **Health Check**: Available via API endpoint `/api/health/clock-sync`

#### MT5 Broker Clock Monitoring

1. **Continuous Tracking**: Monitors MT5 broker clock drift vs server clock on every tick
2. **Rolling Window**: Uses last 1000 ticks for statistics
3. **Alerting**: Alerts on persistent drift > 1 second
4. **Negative Latency Tracking**: Tracks percentage of ticks with negative latency
5. **Compliance**: Monitors for regulatory compliance (MiFID II: <1s, FINRA: <50ms)

**Note**: MT5 broker clock cannot be controlled - we can only monitor and alert.

### Configuration

#### Server-NTP Monitoring

Environment variables for server-NTP clock sync monitoring:

- `CLOCK_SYNC_MONITOR_ENABLED`: Enable/disable monitoring (default: `true`)
- `CLOCK_SYNC_CHECK_INTERVAL`: Check interval in seconds (default: `300`)
- `CLOCK_SYNC_DRIFT_THRESHOLD`: Maximum acceptable drift in seconds (default: `1.0`)

#### MT5 Broker Clock Monitoring

Environment variables for MT5 broker clock monitoring:

- `MT5_CLOCK_MONITOR_ENABLED`: Enable/disable MT5 clock monitoring (default: `true`)
- `MT5_CLOCK_WINDOW_SIZE`: Rolling window size for drift statistics (default: `1000`)
- `MT5_CLOCK_DRIFT_THRESHOLD`: Maximum acceptable drift in seconds (default: `1.0`)
- `MT5_CLOCK_ALERT_COOLDOWN_MINUTES`: Minutes between alerts for same issue (default: `5`)

#### Negative Latency Compliance

Environment variables for negative latency compliance monitoring:

- `NEGATIVE_LATENCY_WARNING_THRESHOLD`: Warning threshold for negative latency rate 0.0-1.0 (default: `0.1` = 10%)
- `NEGATIVE_LATENCY_CRITICAL_THRESHOLD`: Critical threshold for negative latency rate 0.0-1.0 (default: `0.2` = 20%)

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
  "server_ntp": {
    "last_drift_seconds": -0.158,
    "last_status": "ok",
    "check_count": 42
  },
  "mt5_broker": {
    "avg_drift_seconds": -0.045,
    "min_drift_seconds": -0.114,
    "max_drift_seconds": -0.018,
    "median_drift_seconds": -0.042,
    "stddev_drift_seconds": 0.023,
    "sample_count": 1000,
    "status": "warning"
  },
  "negative_latency_rate": 0.15
}
```

**Response Fields**:
- `server_ntp`: Server clock vs NTP drift information
- `mt5_broker`: MT5 broker clock vs server drift statistics
- `negative_latency_rate`: Percentage of ticks with negative latency (0.0-1.0)

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

### Manual Verification

#### Host NTP Verification

Run the host NTP verification script (recommended before deployment):

```bash
python scripts/verify_host_ntp.py
```

This will:
1. Check NTP service status (Linux: systemd-timesyncd/chronyd, Windows: w32tm)
2. Verify NTP server connectivity
3. Report current clock drift
4. Verify Docker container time inheritance
5. Provide remediation steps

#### Application-Level Clock Sync Check

Run the application-level clock sync check:

```bash
python scripts/check_clock_sync.py
```

This will:
1. Check server time
2. Compare with NTP servers
3. Report drift and recommendations
4. Generate report in `docs/generated/CLOCK_SYNC_CHECK.md`

### Best Practices

1. **Host NTP Sync**: Always ensure host system is NTP-synchronized (containers inherit host time)
2. **Pre-Deployment Verification**: Run `scripts/verify_host_ntp.py` before deployment
3. **Regular Monitoring**: Monitor clock sync health checks via `/api/health/clock-sync`
4. **MT5 Broker Monitoring**: Monitor MT5 broker clock drift (cannot be controlled, only monitored)
5. **Alerting**: Set up alerts for clock drift warnings (> 1s) and negative latency rate (> 10%)
6. **Compliance**: Ensure drift stays within regulatory requirements (MiFID II: <1s, FINRA: <50ms)
7. **Documentation**: Document NTP server configuration

### Compliance Requirements

#### MiFID II (EU)
- **Non-HFT**: Clock synchronization within 1 second of UTC
- **HFT**: Clock synchronization within 100 microseconds of UTC

#### FINRA (US)
- **General**: Clock synchronization within 50 milliseconds of NIST UTC
- **CAT**: Millisecond-resolution timestamps with 100ms tolerance

**Note**: Our system targets non-HFT requirements (1 second threshold). For HFT, consider PTP (Precision Time Protocol) instead of NTP.

### Production Deployment

For production:

1. Use reliable NTP servers (e.g., `pool.ntp.org`, `time.google.com`)
2. Configure multiple NTP servers for redundancy
3. Monitor clock sync health checks
4. Set up alerts for drift > 1 second
5. Document NTP configuration in deployment guide

### Troubleshooting MT5 Clock Drift

**Symptoms**:
- Persistent negative latency warnings
- MT5 broker drift > 1 second in health check
- High negative latency rate (> 10%)

**Root Cause**:
MT5 broker clock cannot be controlled by the client. The broker sets its own server time (typically GMT+2 or GMT+3).

**Solutions**:
1. **Monitor and Alert**: Use MT5 clock monitoring to track drift
2. **Contact Broker**: If drift is excessive (> 5s), contact MT5 broker support
3. **Compensation**: Consider implementing clock drift compensation in latency calculations (temporary mitigation)
4. **Documentation**: Document MT5 broker clock drift as known limitation

**See**: [MT5 Clock Monitoring Guide](MT5_CLOCK_MONITORING.md) for detailed information.

## Related Documentation

- [MT5 Clock Monitoring Guide](MT5_CLOCK_MONITORING.md) - Detailed guide on MT5 broker clock monitoring
- [Data Collection Investigation](../generated/DATA_ISSUES_INVESTIGATION.md)
- [Negative Latency Root Cause](../generated/NEGATIVE_LATENCY_ROOT_CAUSE.md)
- [Clock Sync Check Script](../../scripts/check_clock_sync.py)
- [Host NTP Verification Script](../../scripts/verify_host_ntp.py)
