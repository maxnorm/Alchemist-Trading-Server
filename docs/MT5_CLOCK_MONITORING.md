# MT5 Broker Clock Monitoring Guide

## Overview

This guide explains how MT5 broker clock monitoring works, why the broker clock cannot be controlled, and how to interpret drift metrics.

## Why MT5 Broker Clock Cannot Be Controlled

### MT5 Architecture

MT5 (MetaTrader 5) uses a client-server architecture where:

1. **MT5 Terminal** runs on Windows host
2. **MT5 Broker Server** provides market data and executes trades
3. **Tick Timestamps** come from broker server clock (`tick.time_msc`)
4. **Client Cannot Override** broker server time

### Broker Server Time

- MT5 brokers set their own server time (typically GMT+2 or GMT+3)
- This time is used for all tick timestamps (`tick.time_msc`)
- The timezone offset is often chosen to align with 5-day H4 candle close
- **Cannot be changed by the client** - it's a broker-side setting

### Code Evidence

From `mt5_zeromq_streamer.mq5`:
```mql5
long time_msc = tick.time_msc;  // Broker server time (milliseconds since epoch)
datetime tick_time;
if(time_msc > 0) {
    tick_time = (datetime)(time_msc / 1000);  // Convert to datetime
}
```

The EA receives `tick.time_msc` from the broker and uses it directly - there's no way to override or adjust this timestamp.

## How Monitoring Works

### MT5ClockMonitor

The `MT5ClockMonitor` class tracks MT5 broker clock drift by:

1. **Receiving Ticks**: Each tick includes `datetime` (derived from `tick.time_msc`)
2. **Comparing Timestamps**: Calculates drift = `tick_datetime - receive_time`
3. **Rolling Window**: Maintains last 1000 ticks for statistics
4. **Statistics**: Calculates mean, median, min, max, stddev of drift
5. **Alerting**: Alerts when persistent drift exceeds threshold

### Drift Calculation

```python
# In TickProcessor._process_tick_info()
normalized_tick_datetime = self._normalize_mt5_timestamp(date_time)
receive_time = get_utc_time()  # Server receive time

# In MT5ClockMonitor.track_tick()
drift_seconds = (tick_datetime - receive_time).total_seconds()
```

**Interpretation**:
- **Positive drift**: MT5 broker clock is ahead of server clock
- **Negative drift**: MT5 broker clock is behind server clock (causes negative latency)

### Negative Latency

Negative latency occurs when `tick_datetime > receive_time`, meaning:
- The tick timestamp is in the future relative to when we received it
- This indicates MT5 broker clock is ahead of our server clock
- Or our server clock is behind the broker clock

## Interpreting Drift Metrics

### Health Check Response

```json
{
  "mt5_broker": {
    "avg_drift_seconds": -0.045,
    "min_drift_seconds": -0.114,
    "max_drift_seconds": -0.018,
    "median_drift_seconds": -0.042,
    "stddev_drift_seconds": 0.023,
    "sample_count": 1000,
    "status": "warning"
  }
}
```

### Metrics Explained

- **avg_drift_seconds**: Average drift over rolling window
  - `-0.045s` = Broker clock is 45ms behind server clock (on average)
  - This is within threshold (< 1s) but indicates slight drift

- **min_drift_seconds**: Minimum drift (most negative)
  - `-0.114s` = Worst case: broker clock 114ms behind

- **max_drift_seconds**: Maximum drift (most positive)
  - `-0.018s` = Best case: broker clock 18ms behind

- **median_drift_seconds**: Median drift (less affected by outliers)
  - `-0.042s` = Typical drift is 42ms

- **stddev_drift_seconds**: Standard deviation
  - `0.023s` = Low variation (23ms) - drift is consistent

- **sample_count**: Number of ticks in rolling window
  - `1000` = Statistics based on last 1000 ticks

- **status**: Overall status
  - `ok`: Drift < 1s and negative latency rate < 10%
  - `warning`: Drift > 1s or negative latency rate > 10%
  - `critical`: Drift > 2s or negative latency rate > 20%

### Negative Latency Rate

```json
{
  "negative_latency_rate": 0.15
}
```

- `0.15` = 15% of ticks have negative latency
- **Warning threshold**: 10% (0.1)
- **Critical threshold**: 20% (0.2)

## When to Alert Broker

### Contact Broker Support If:

1. **Persistent Large Drift**: Average drift > 5 seconds for > 1 hour
2. **Increasing Drift**: Drift is increasing over time (clock running fast/slow)
3. **Compliance Risk**: Drift exceeds regulatory requirements
4. **High Negative Latency**: Negative latency rate > 20% consistently

### Information to Provide:

1. **Drift Statistics**: Average, min, max drift over time period
2. **Sample Count**: Number of ticks analyzed
3. **Time Period**: When the issue started/occurred
4. **Impact**: How it affects trading/data quality
5. **Server Clock Status**: Confirmation that your server is NTP-synchronized

### Example Alert to Broker

```
Subject: MT5 Broker Clock Drift Detected

We have detected persistent clock drift between your MT5 broker server 
and our trading server:

- Average drift: -2.45 seconds (broker clock behind)
- Sample size: 10,000 ticks over 1 hour
- Negative latency rate: 35%
- Our server is NTP-synchronized (verified)

This is causing negative latency warnings and may impact data quality.
Please verify your broker server clock synchronization.

Drift statistics:
- Min: -3.12s
- Max: -1.89s
- Median: -2.41s
- Stddev: 0.23s
```

## Best Practices

### 1. Continuous Monitoring

- Monitor MT5 broker clock drift continuously
- Track trends over time
- Alert on persistent issues

### 2. Baseline Establishment

- Establish baseline drift when system is working correctly
- Document expected drift range
- Alert when drift exceeds baseline significantly

### 3. Documentation

- Document MT5 broker clock drift as known limitation
- Include in system architecture documentation
- Note in compliance documentation

### 4. Compensation (Optional)

- Consider implementing clock drift compensation in latency calculations
- Only as temporary mitigation
- Document compensation logic clearly

### 5. Broker Communication

- Maintain open communication with broker support
- Report clock issues promptly
- Provide detailed metrics and evidence

## Configuration

### Environment Variables

```bash
# MT5 Clock Monitoring
MT5_CLOCK_MONITOR_ENABLED=true
MT5_CLOCK_WINDOW_SIZE=1000
MT5_CLOCK_DRIFT_THRESHOLD=1.0
MT5_CLOCK_ALERT_COOLDOWN_MINUTES=5

# Negative Latency Compliance
NEGATIVE_LATENCY_WARNING_THRESHOLD=0.1  # 10%
NEGATIVE_LATENCY_CRITICAL_THRESHOLD=0.2  # 20%
```

### Thresholds

- **Drift Threshold**: 1.0 second (configurable)
  - Alerts when average drift exceeds threshold
  - Based on regulatory requirements (MiFID II: <1s for non-HFT)

- **Negative Latency Warning**: 10% (0.1)
  - Alerts when > 10% of ticks have negative latency
  - Indicates systematic clock drift

- **Negative Latency Critical**: 20% (0.2)
  - Critical alert when > 20% of ticks have negative latency
  - Indicates severe clock synchronization issue

## Prometheus Metrics

The monitor exports the following Prometheus metrics:

- `clock_drift_seconds{source="mt5_broker"}`: Current average drift
- `negative_latency_rate`: Percentage of ticks with negative latency (0.0-1.0)
- `clock_sync_status{source="mt5_broker"}`: Health status (1=healthy, 0=unhealthy)

### Example Queries

```promql
# Average MT5 broker drift over 5 minutes
avg_over_time(clock_drift_seconds{source="mt5_broker"}[5m])

# Negative latency rate
negative_latency_rate

# MT5 clock sync health
clock_sync_status{source="mt5_broker"}
```

## Troubleshooting

### High Negative Latency Rate

**Symptoms**: Negative latency rate > 10%

**Possible Causes**:
1. MT5 broker clock ahead of server clock
2. Server clock behind NTP
3. Network latency causing timestamp issues

**Solutions**:
1. Verify server NTP synchronization
2. Check MT5 broker clock drift metrics
3. Contact broker if drift is excessive

### Persistent Drift

**Symptoms**: Average drift > 1s consistently

**Possible Causes**:
1. MT5 broker clock not synchronized
2. Server clock not synchronized
3. Timezone misconfiguration

**Solutions**:
1. Verify server NTP sync: `python scripts/verify_host_ntp.py`
2. Check MT5 broker drift: `/api/health/clock-sync`
3. Contact broker support if server is synchronized

### Increasing Drift

**Symptoms**: Drift increasing over time

**Possible Causes**:
1. Clock running at different rates (drift rate)
2. One clock not synchronized properly

**Solutions**:
1. Verify both clocks are NTP-synchronized
2. Monitor drift trend over time
3. Contact broker if trend continues

## Related Documentation

- [Clock Synchronization Setup Guide](CLOCK_SYNC_SETUP.md)
- [Deployment Checklist](DEPLOYMENT_CHECKLIST.md)
- [Host NTP Verification Script](../../scripts/verify_host_ntp.py)
