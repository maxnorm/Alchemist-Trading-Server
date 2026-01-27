---
name: Phase 1 Safety Infrastructure
overview: Complete and finalize all safety mechanisms (Kill Switch, Circuit Breaker, OMS) with database persistence and ensure full integration with TradingController. Most components are implemented; remaining work focuses on database tables and final verification.
todos:
  - id: phase1-db-migration
    content: Create database migration script (06_safety_infrastructure.sql) with orders, kill_switch_events, and circuit_breaker_events tables
    status: completed
  - id: phase1-oms-db-persistence
    content: Enhance OMS with database persistence - add _persist_to_db() and _load_from_db() methods
    status: completed
  - id: phase1-kill-switch-db-logging
    content: Add database logging to kill switch - log events to kill_switch_events table on trigger and reset
    status: completed
  - id: phase1-circuit-breaker-db-logging
    content: Add database logging to circuit breaker - log events to circuit_breaker_events table on trip and resume
    status: completed
  - id: phase1-trading-controller-db-integration
    content: Update TradingController to pass database connections to safety components and handle errors
    status: completed
  - id: phase1-db-integration-tests
    content: Add database integration tests for OMS, kill switch, and circuit breaker database operations
    status: completed
  - id: phase1-documentation
    content: Create Phase 1 documentation (PHASE1_SAFETY_INFRASTRUCTURE.md) and update README
    status: completed
---

# Phase 1: Safety Infrastructure - Implementation Plan

## Current Status Assessment

### ✅ Completed Components

1. **Kill Switch** (`src/mt5-python_server/src/risk/kill_switch.py`)

   - All trigger mechanisms implemented (File, Environment, Network, Signal)
   - Integration with TradingController complete
   - Audit logging implemented
   - API trigger deferred to Phase 4 (FastAPI integration)

2. **Circuit Breaker** (`src/mt5-python_server/src/risk/circuit_breaker.py`)

   - Full implementation with all threshold checks
   - Integration with TradingController complete
   - Checks before trades, records after trades
   - Half-open recovery state implemented

3. **Order Management System** (`src/mt5-python_server/src/risk/oms.py`)

   - Idempotency implemented (unique order IDs, duplicate detection)
   - Position reconciliation implemented
   - Order state machine complete (pending → submitted → filled/rejected)
   - File-based persistence working
   - Currently missing: Database persistence

4. **Integration Tests** (`tests/integration/test_safety_integration.py`)

   - Comprehensive test coverage exists
   - Tests for all safety components working together

### ❌ Missing Components

1. **Database Tables for Safety Infrastructure**

   - `orders` table for OMS persistence
   - `kill_switch_events` table for audit trail
   - `circuit_breaker_events` table for tracking trips

2. **OMS Database Integration**

   - OMS currently uses file-based persistence only
   - Needs database adapter for production use

3. **Final Verification**

   - End-to-end testing with database
   - Documentation updates

## Implementation Tasks

### Task 1.1: Create Database Migration Script for Orders Table

**File**: `database/scripts/06_safety_infrastructure.sql`

Create migration script with:

```sql
USE db_forex;

-- Orders table for OMS
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

-- Kill switch events table
CREATE TABLE kill_switch_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trigger_source VARCHAR(50) NOT NULL,
    reason TEXT NOT NULL,
    positions_closed INT DEFAULT 0,
    approver VARCHAR(100) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    INDEX idx_created_at (created_at)
);

-- Circuit breaker events table
CREATE TABLE circuit_breaker_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    breaker_type VARCHAR(50) NOT NULL,
    trigger_value DECIMAL(10, 4),
    threshold_value DECIMAL(10, 4),
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resumed_at TIMESTAMP NULL,
    INDEX idx_created_at (created_at)
);
```

### Task 1.2: Enhance OMS with Database Persistence

**File**: `src/mt5-python_server/src/risk/oms.py`

Add database persistence methods:

1. **Add database connection parameter** to `__init__`
2. **Implement `_persist_to_db()`** method:

   - Save orders to database
   - Update order states
   - Store fills

3. **Implement `_load_from_db()`** method:

   - Load orders on initialization
   - Restore positions from filled orders

4. **Update `submit_order()`** to persist to database
5. **Update `handle_fill()`** to persist fills
6. **Update `update_order_state()`** to persist state changes

**Integration Points**:

- Use existing database connection from `src/mt5-python_server/src/database.py`
- Maintain backward compatibility with file-based persistence
- Use database as primary, file as backup

### Task 1.3: Integrate Kill Switch with Database

**File**: `src/mt5-python_server/src/risk/kill_switch.py`

Add database logging:

1. **Add database connection parameter** to `__init__`
2. **Update `trigger()`** method:

   - Log event to `kill_switch_events` table
   - Store trigger source, reason, positions closed

3. **Update `reset()`** method:

   - Update `resolved_at` timestamp in database
   - Store approver name

### Task 1.4: Integrate Circuit Breaker with Database

**File**: `src/mt5-python_server/src/risk/circuit_breaker.py`

Add database logging:

1. **Add database connection parameter** to `__init__`
2. **Update `_trip()`** method:

   - Log event to `circuit_breaker_events` table
   - Store breaker type, trigger value, threshold, reason

3. **Update `_close()`** method:

   - Update `resumed_at` timestamp in database

### Task 1.5: Update TradingController Integration

**File**: `src/mt5-python_server/src/trading_controller.py`

Ensure proper initialization:

1. **Verify database connections** are passed to safety components
2. **Add error handling** for database failures (fallback to file-based)
3. **Add logging** for database persistence operations

### Task 1.6: Update Integration Tests

**File**: `tests/integration/test_safety_integration.py`

Add database integration tests:

1. **Test OMS database persistence**:

   - Create order, verify in database
   - Update state, verify persistence
   - Load from database on restart

2. **Test kill switch database logging**:

   - Trigger kill switch, verify event in database
   - Reset, verify resolution timestamp

3. **Test circuit breaker database logging**:

   - Trip circuit breaker, verify event in database
   - Resume, verify resolution timestamp

### Task 1.7: Create Database Migration Runner

**File**: `scripts/run-migrations.py` (if not exists)

Create script to run database migrations in order:

- Check current schema version
- Run pending migrations
- Verify migration success

### Task 1.8: Documentation Updates

**Files**:

- `docs/PHASE1_SAFETY_INFRASTRUCTURE.md` (new)
- `README.md` (update)

Document:

1. Safety infrastructure overview
2. Database schema for safety components
3. How to run migrations
4. Configuration options
5. Testing procedures

## Database Schema Dependencies

The orders table references `experiments` table which will be created in Phase 3. For Phase 1:

- Make `experiment_id` nullable (can be NULL for non-experiment orders)
- Add foreign key constraint only if experiments table exists

## Testing Strategy

1. **Unit Tests**: Verify database operations work correctly
2. **Integration Tests**: Test full workflow with database
3. **End-to-End Tests**: Test with real TradingController
4. **Failure Tests**: Test fallback to file-based persistence on DB failure

## Success Criteria

- ✅ All safety components persist to database
- ✅ Orders table stores all order lifecycle events
- ✅ Kill switch events logged to database
- ✅ Circuit breaker events logged to database
- ✅ Integration tests pass with database
- ✅ Backward compatibility maintained (file-based fallback)
- ✅ Documentation complete

## Files to Modify

1. `database/scripts/06_safety_infrastructure.sql` - New migration script
2. `src/mt5-python_server/src/risk/oms.py` - Add database persistence
3. `src/mt5-python_server/src/risk/kill_switch.py` - Add database logging
4. `src/mt5-python_server/src/risk/circuit_breaker.py` - Add database logging
5. `src/mt5-python_server/src/trading_controller.py` - Verify integration
6. `tests/integration/test_safety_integration.py` - Add DB tests
7. `docs/PHASE1_SAFETY_INFRASTRUCTURE.md` - New documentation

## Notes

- OMS currently uses file-based persistence which works but should be enhanced with database for production
- Kill switch and circuit breaker have audit logs but should also log to database for queryability
- All database operations should have error handling and fallback mechanisms
- Consider using connection pooling for database operations