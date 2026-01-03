# Safety Mechanisms Documentation

## Overview

The Alchemist trading platform implements comprehensive safety mechanisms to protect capital and ensure reliable trading operations. All safety components are integrated with database persistence for audit trails and historical analysis.

## Components

### 1. Kill Switch

The kill switch provides an emergency stop mechanism that immediately halts all trading operations and closes all open positions.

#### Features

- **Multiple Trigger Mechanisms**:
  - File-based trigger (watches for kill file on disk)
  - Environment variable trigger (`TRADING_KILL`)
  - Network trigger (UDP listener on port 9999)
  - Signal trigger (SIGUSR1 on Unix systems)
  - API trigger (deferred to Phase 4)

- **Database Persistence**:
  - All kill switch events are logged to `kill_switch_events` table
  - Tracks trigger source, reason, positions closed, approver, and timestamps
  - Supports querying historical kill switch activations

#### Usage

```python
from risk import KillSwitch
from database import Database

# Initialize with database for persistence
db = Database()
kill_switch = KillSwitch(
    broker_adapter=broker,
    on_kill_callback=handle_emergency,
    database=db
)

# Arm the kill switch
kill_switch.arm()

# In trading loop
if kill_switch.is_active():
    # Halt trading immediately
    break

# Manually trigger
kill_switch.trigger("Emergency stop", "Manual")

# Reset (requires approver name)
kill_switch.reset("admin")
```

#### Database Schema

```sql
CREATE TABLE kill_switch_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trigger_source VARCHAR(50) NOT NULL,
    reason TEXT NOT NULL,
    positions_closed INT DEFAULT 0,
    approver VARCHAR(100) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    INDEX idx_created_at (created_at),
    INDEX idx_resolved_at (resolved_at)
);
```

### 2. Circuit Breaker

The circuit breaker automatically halts trading when certain thresholds are exceeded (losses, volatility, errors, latency).

#### Features

- **Threshold Monitoring**:
  - Hourly loss percentage
  - Daily loss percentage
  - Volatility spikes (calculated from price history)
  - Error rate
  - Operation latency

- **States**:
  - **CLOSED**: Normal operation, trading allowed
  - **OPEN**: Trading halted due to threshold breach
  - **HALF_OPEN**: Testing recovery, limited trading allowed

- **Volatility Integration**:
  - Automatically calculates volatility from price history if available
  - Can use price history provider for real-time volatility calculation
  - Falls back to manually recorded volatility if price history unavailable

- **Database Persistence**:
  - All circuit breaker trips are logged to `circuit_breaker_events` table
  - Tracks breaker type, trigger value, threshold value, reason, and timestamps
  - Supports querying historical circuit breaker activations

#### Usage

```python
from risk import CircuitBreaker, CircuitBreakerConfig
from database import Database

# Initialize with database for persistence
db = Database()
config = CircuitBreakerConfig(
    max_loss_per_hour_pct=0.03,  # 3% per hour
    max_loss_per_day_pct=0.05,   # 5% per day
    max_volatility_multiple=3.0,
    max_error_rate=0.10,
    max_latency_ms=1000
)
circuit_breaker = CircuitBreaker(config, database=db)

# Optionally provide price history provider for automatic volatility calculation
def get_price_histories():
    return env.price_history_manager.get_all_histories()
circuit_breaker.price_history_provider = get_price_histories

circuit_breaker.initialize(starting_balance=10000.0)

# Before each trade
can_trade, reason = circuit_breaker.check()
if not can_trade:
    # Trading blocked
    print(f"Trading blocked: {reason}")
    return

# After each trade
circuit_breaker.record_trade(pnl=50.0)

# On errors
circuit_breaker.record_error(exception)

# On latency
circuit_breaker.record_latency(latency_ms=500)

# Record volatility (optional - can be calculated automatically)
circuit_breaker.record_volatility(volatility=0.015)

# Or calculate from price history
circuit_breaker.record_volatility(price_history=[1.0850, 1.0855, 1.0860, ...])

# Manual reset
circuit_breaker.reset(manual=True)

# Daily/hourly resets (called automatically by TradingController)
circuit_breaker.reset_daily(balance=10000.0)
circuit_breaker.reset_hourly(balance=10000.0)
```

#### Database Schema

```sql
CREATE TABLE circuit_breaker_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    breaker_type VARCHAR(50) NOT NULL,  -- 'loss', 'volatility', 'error', 'latency'
    trigger_value DECIMAL(10, 4) NOT NULL,
    threshold_value DECIMAL(10, 4) NOT NULL,
    trip_reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resumed_at TIMESTAMP NULL,
    INDEX idx_created_at (created_at),
    INDEX idx_resumed_at (resumed_at)
);
```

### 3. Order Management System (OMS)

The OMS provides order tracking, idempotency, state management, position reconciliation, and alerting.

#### Features

- **Idempotency**: Prevents duplicate orders using `client_order_id`
- **State Machine**: Tracks orders through lifecycle (pending → submitted → filled/rejected)
- **Position Tracking**: Maintains local position state
- **Reconciliation**: Detects discrepancies between local and broker positions
- **Alert System**: Triggers alerts on position mismatches exceeding threshold
- **Database Persistence**: All orders are persisted to `orders` table

#### Usage

```python
from risk import OrderManagementSystem, Order
from database import Database

# Initialize with database for persistence
db = Database()

def handle_alert(alert_type, alert_data):
    print(f"Alert: {alert_type} - {alert_data}")
    # Can trigger kill switch for critical alerts
    if alert_data.get('discrepancy_pct', 0) > 0.50:
        kill_switch.trigger("Critical position mismatch", "OMS Alert")

oms = OrderManagementSystem(
    database=db,
    persistence_path="oms_state.json",  # File fallback
    on_alert=handle_alert,
    alert_threshold_pct=0.10  # Alert if discrepancy > 10%
)

# Submit order (idempotent)
order = Order(
    client_order_id="unique-order-123",
    symbol="EURUSD",
    side="BUY",
    quantity=0.1
)
order_id = oms.submit_order(order)

# Handle fill from broker
oms.handle_fill({
    'order_id': order_id,
    'quantity': 0.1,
    'price': 1.0850
})

# Reconcile positions (triggers alerts if discrepancies found)
broker_positions = broker.get_positions()
discrepancies = oms.reconcile(broker_positions)

# Sync positions if needed (overwrites local with broker)
oms.sync_positions(broker_positions)
```

#### Database Schema

```sql
CREATE TABLE orders (
    id VARCHAR(64) PRIMARY KEY,
    client_order_id VARCHAR(100),
    experiment_id INT NULL,
    account_login INT NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    side ENUM('BUY', 'SELL') NOT NULL,
    order_type ENUM('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT') DEFAULT 'MARKET',
    quantity DECIMAL(15, 6) NOT NULL,
    price DECIMAL(15, 6) NULL,
    stop_loss DECIMAL(15, 6) NULL,
    take_profit DECIMAL(15, 6) NULL,
    state ENUM('PENDING_NEW', 'NEW', 'PARTIALLY_FILLED', 'FILLED', 
               'PENDING_CANCEL', 'CANCELLED', 'REJECTED', 'EXPIRED') DEFAULT 'PENDING_NEW',
    filled_quantity DECIMAL(15, 6) DEFAULT 0,
    average_fill_price DECIMAL(15, 6) DEFAULT 0,
    broker_order_id VARCHAR(100) NULL,
    reject_reason TEXT NULL,
    metadata JSON NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_experiment (experiment_id),
    INDEX idx_account (account_login),
    INDEX idx_client_order_id (client_order_id),
    INDEX idx_state (state),
    INDEX idx_symbol (symbol)
);
```

## Integration with TradingController

The `TradingController` integrates all three safety components with automatic reset hooks and reconciliation:

```python
from trading_controller import TradingController
from risk import KillSwitch, CircuitBreaker, OrderManagementSystem
from database import Database

# Initialize database
db = Database()

# Create safety components with database
kill_switch = KillSwitch(
    broker_adapter=broker,
    database=db
)
circuit_breaker = CircuitBreaker(
    config=CircuitBreakerConfig(),
    database=db
)
oms = OrderManagementSystem(
    database=db,
    on_alert=lambda alert_type, data: handle_alert(alert_type, data)
)

# Create trading controller
controller = TradingController(
    agent=agent,
    environment=env,
    account=account,
    risk_manager=risk_manager,
    kill_switch=kill_switch,
    circuit_breaker=circuit_breaker,
    oms=oms,
    database=db
)

# Start trading - automatic resets and reconciliation are handled
controller.start()
```

### Automatic Features

The TradingController automatically:

1. **Circuit Breaker Resets**:
   - Daily reset at start of trading day (00:00 UTC)
   - Hourly reset at start of each hour
   - Resets are performed automatically based on time

2. **Position Reconciliation**:
   - Periodic reconciliation every 5 minutes (configurable via `reconciliation_interval`)
   - Compares local OMS positions with broker positions
   - Triggers alerts on discrepancies exceeding threshold

3. **Trade Recording**:
   - Records P&L to circuit breaker after each trade
   - Records errors to circuit breaker
   - Records volatility from environment metrics

4. **Volatility Calculation**:
   - Automatically calculates volatility from price history if available
   - Uses environment's price history manager
   - Falls back to manually recorded volatility

## Database Migration

To set up the database tables, run the migration script:

```bash
mysql -u root -p db_forex < database/scripts/06_safety_infrastructure.sql
```

Or use the migration runner (if available):

```bash
python scripts/run-migrations.py
```

## Configuration

### Kill Switch Configuration

- **File Trigger**: Create file at `logs/kill_switch.trigger` (or default paths)
- **Environment Trigger**: Set `TRADING_KILL=1`
- **Network Trigger**: Send UDP packet to port 9999: `echo "KILL:reason" | nc -u localhost 9999`
- **Signal Trigger**: Send SIGUSR1 signal to process: `kill -USR1 <pid>`

### Circuit Breaker Configuration

Default thresholds (configurable via `CircuitBreakerConfig`):

- `max_loss_per_hour_pct`: 3% (0.03)
- `max_loss_per_day_pct`: 5% (0.05)
- `max_volatility_multiple`: 3.0x normal
- `max_error_rate`: 10% (0.10)
- `max_latency_ms`: 1000ms
- `cooldown_minutes`: 30 minutes
- `auto_reset`: False (requires manual reset by default)
- `half_open_max_trades`: 3 trades

### OMS Configuration

- **Persistence**: Database (primary) + File (fallback)
- **Reconciliation**: Periodic sync with broker positions (every 5 minutes)
- **Idempotency**: Enabled by default using `client_order_id`
- **Alert Threshold**: Default 10% discrepancy triggers alert

## Error Handling

All safety components are designed to degrade gracefully:

- **Database Failures**: Components fall back to file-based persistence
- **Connection Issues**: Operations continue with in-memory state
- **Broker Failures**: Kill switch attempts to close positions, logs errors
- **Price History Unavailable**: Circuit breaker uses manually recorded volatility

## Testing

Run integration tests:

```bash
# All safety integration tests
pytest tests/integration/test_safety_integration.py -v

# Database persistence tests
pytest tests/unit/test_kill_switch_db.py -v
pytest tests/unit/test_circuit_breaker_db.py -v
pytest tests/unit/test_oms_db.py -v
```

## Monitoring

### Query Kill Switch Events

```sql
SELECT * FROM kill_switch_events 
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY created_at DESC;
```

### Query Circuit Breaker Events

```sql
SELECT * FROM circuit_breaker_events 
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY created_at DESC;
```

### Query Recent Orders

```sql
SELECT * FROM orders 
WHERE account_login = 12345 
AND created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY created_at DESC;
```

### Query Active Orders

```sql
SELECT * FROM orders 
WHERE state NOT IN ('FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED')
ORDER BY created_at DESC;
```

## Troubleshooting

### Kill Switch Not Triggering

1. Check if kill switch is armed: `kill_switch.state == KillSwitchState.ARMED`
2. Verify trigger file exists (if using file trigger)
3. Check audit log: `kill_switch.get_audit_log()`
4. Check database events: Query `kill_switch_events` table
5. Verify network trigger: Check UDP port 9999 is accessible

### Circuit Breaker Tripping Too Often

1. Review threshold configuration
2. Check metrics: `circuit_breaker.get_metrics()`
3. Adjust thresholds in `CircuitBreakerConfig`
4. Review historical events in database
5. Check if volatility calculation is accurate

### OMS Position Mismatches

1. Run reconciliation: `oms.reconcile(broker_positions)`
2. Check for discrepancies in logs
3. Sync positions if needed: `oms.sync_positions(broker_positions)`
4. Review order history in database
5. Check alert threshold configuration

### Volatility Not Being Calculated

1. Verify price history provider is set: `circuit_breaker.price_history_provider`
2. Check if environment has price history manager
3. Verify price history has sufficient data (at least 2 prices)
4. Check logs for volatility calculation errors

## Best Practices

1. **Always Initialize with Database**: Pass database connection to all safety components for persistence
2. **Monitor Events**: Regularly query database tables for safety events
3. **Test Regularly**: Run integration tests before deploying
4. **Document Resets**: Always provide approver name when resetting kill switch
5. **Review Thresholds**: Periodically review and adjust circuit breaker thresholds based on trading performance
6. **Set Alert Thresholds**: Configure OMS alert thresholds based on risk tolerance
7. **Monitor Reconciliation**: Review reconciliation logs regularly for position mismatches
8. **Test Failures**: Test database failure scenarios to ensure graceful degradation

## Future Enhancements

- API trigger for kill switch (Phase 4)
- Dashboard integration for monitoring (Phase 5)
- Automated alerting on safety events (email, SMS, webhooks)
- Historical analysis and reporting tools
- Machine learning-based threshold adjustment
- Multi-account safety coordination
