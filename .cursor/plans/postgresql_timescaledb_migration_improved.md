# PostgreSQL + TimescaleDB Migration Plan (Improved)

## Critical Issues Found & Solutions

After deep codebase analysis, the following critical issues were identified that must be addressed:

### 1. Connection Pool API Differences (CRITICAL)

**Issue**: MariaDB uses `pool.get_connection()` and `conn.close()` to return connections. PostgreSQL psycopg2 uses `pool.getconn()` and `pool.putconn(conn)`.

**Impact**: All files using `conn.close()` need to be updated to use `pool.putconn(conn)`.

**Files Affected** (15+ files):
- `src/mt5-python_server/src/database.py` - Core database class
- `src/mt5-python_server/src/risk/oms.py`
- `src/mt5-python_server/src/risk/kill_switch.py`
- `src/mt5-python_server/src/risk/circuit_breaker.py`
- `src/mt5-python_server/src/performance/metrics_calculator.py`
- `src/mt5-python_server/src/performance/trade_logger.py`
- `src/mt5-python_server/src/performance/session_manager.py`
- `src/mt5-python_server/src/mlops/paper_session_manager.py`
- `src/mt5-python_server/src/mlops/model_registry.py`
- `src/mt5-python_server/src/experiments/optuna_tuner.py`
- `src/mt5-python_server/src/mlops/feature_registry.py`
- `src/mt5-python_server/src/features/catalog.py`
- And more...

**Solution**: 
1. Update `Database` class to store pool reference
2. Create helper method `return_connection(conn)` that calls `pool.putconn(conn)`
3. Replace all `conn.close()` with `self.return_connection(conn)`

### 2. lastrowid Usage (CRITICAL)

**Issue**: Many files use `cursor.lastrowid` to get inserted ID. PostgreSQL doesn't support `lastrowid` - need to use `RETURNING id` clause.

**Files Affected**:
- `src/mt5-python_server/src/mlops/paper_session_manager.py` (line 94)
- `src/mt5-python_server/src/performance/session_manager.py` (line 49)
- `src/mt5-python_server/src/performance/trade_logger.py` (line 79)
- `src/mt5-python_server/src/mlops/model_registry.py` (line 187)
- `src/mt5-python_server/src/experiments/optuna_tuner.py` (lines 84, 512)
- `src/mt5-python_server/src/mlops/feature_registry.py` (line 139)
- `src/mt5-python_server/src/risk/circuit_breaker.py` (line 693)

**Solution**: 
```python
# Replace
cursor.execute("INSERT INTO table (...) VALUES (...)")
id = cursor.lastrowid

# With
cursor.execute("INSERT INTO table (...) VALUES (...) RETURNING id")
id = cursor.fetchone()[0]
```

### 3. SQL Function Differences

**Issue**: MariaDB-specific SQL functions need conversion.

**Functions to Convert**:
- `DATE_SUB(NOW(), INTERVAL %s HOUR)` → `NOW() - INTERVAL '%s hours'`
- `DATE_ADD(NOW(), INTERVAL %s HOUR)` → `NOW() + INTERVAL '%s hours'`
- `TIMESTAMPDIFF(SECOND, a, b)` → `EXTRACT(EPOCH FROM (b - a))::INTEGER`
- `NOW()` → `NOW()` (same, but verify timezone handling)

**Files Affected**:
- `src/mt5-python_server/src/database.py` (lines 794, 843-844)
- `src/database/scripts/07_add_bitemporal_columns.sql` (line 25)
- `src/api/src/services/*.py` (multiple files using NOW())

### 4. Error Code Mapping

**Issue**: MariaDB error codes (2006, 2013, 2003, 2002) need PostgreSQL equivalents.

**Solution**: Map to PostgreSQL error codes:
- 2006 (Connection lost) → 08003 (connection_does_not_exist)
- 2013 (Lost connection) → 08006 (connection_failure)
- 2003 (Can't connect) → 08001 (sqlclient_unable_to_establish_sqlconnection)
- 2002 (Can't connect) → 08001

**File**: `src/mt5-python_server/src/database.py` (lines 177-182)

### 5. Connection Arguments

**Issue**: API service uses MySQL-specific connection arguments.

**File**: `src/api/src/services/database.py` (lines 34-39)

**Solution**:
```python
# Replace
connect_args = {
    "connect_timeout": 10,
    "read_timeout": 30,
    "write_timeout": 60,
    "charset": "utf8mb4",
}

# With
connect_args = {
    "connect_timeout": 10,
    "options": "-c statement_timeout=30000 -c client_encoding=utf8"
}
```

### 6. Default Port Update

**Issue**: Config defaults to MariaDB port 3306.

**File**: `src/api/src/config.py` (line 16)

**Solution**: Change default port from 3306 to 5432.

## Updated Migration Plan

### Phase 3.1: Update Database Class (CRITICAL - Must be done first)

**File**: `src/mt5-python_server/src/database.py`

**Changes**:

1. **Connection Pool**:
```python
# Replace
import mariadb
pool = mariadb.ConnectionPool(...)
conn = self.__pool.get_connection()

# With
import psycopg2.pool
pool = psycopg2.pool.ThreadedConnectionPool(...)
conn = self.__pool.getconn()
```

2. **Add Helper Method**:
```python
def return_connection(self, conn):
    """Return connection to pool"""
    if conn:
        try:
            self.__pool.putconn(conn)
        except Exception as e:
            print_with_datetime(f"Error returning connection to pool: {e}")
```

3. **Replace all `conn.close()`** with `self.return_connection(conn)`

4. **Error Code Mapping**:
```python
# Replace
transient_errors = (2006, 2013, 2003, 2002)

# With
transient_errors = ('08003', '08006', '08001')  # PostgreSQL error codes
error_code = getattr(e, 'pgcode', None)  # Instead of errno
```

5. **SQL Function Updates**:
```python
# Replace
AND {time_column} >= DATE_SUB(NOW(), INTERVAL %s HOUR)

# With
AND {time_column} >= NOW() - INTERVAL '%s hours'
```

### Phase 3.2: Update All Files Using Database Connections

**Strategy**: Update files in dependency order (core first, then dependent modules).

**Files to Update** (in order):

1. **Core Database** (`src/mt5-python_server/src/database.py`) - Already covered above

2. **Feature Registry** (`src/mt5-python_server/src/features/catalog.py`)
   - Replace `mariadb` imports
   - Update error handling
   - Replace `conn.close()` with `self.db.return_connection(conn)`
   - Update any `lastrowid` usage

3. **MLOps Feature Registry** (`src/mt5-python_server/src/mlops/feature_registry.py`)
   - Same as above

4. **All Other Files** (15+ files):
   - Replace `conn.close()` with `self.db.return_connection(conn)` or `database.return_connection(conn)`
   - Update `lastrowid` to use `RETURNING id`
   - Update error handling

**Pattern for lastrowid**:
```python
# Before
cursor.execute(
    "INSERT INTO table (col1, col2) VALUES (%s, %s)",
    (val1, val2)
)
id = cursor.lastrowid

# After
cursor.execute(
    "INSERT INTO table (col1, col2) VALUES (%s, %s) RETURNING id",
    (val1, val2)
)
id = cursor.fetchone()[0]
```

### Phase 3.3: Update API Service

**File**: `src/api/src/services/database.py`

**Changes**:
1. Update connection string format
2. Update connection arguments (remove charset, update timeouts)
3. Verify SQLAlchemy compatibility

**File**: `src/api/src/config.py`

**Changes**:
1. Update default port from 3306 to 5432
2. Update default host from "mariadb" to "postgres" (optional, can use env var)

### Phase 3.4: Update SQL Queries with NOW()

**Files**:
- `src/api/src/services/optuna_service.py` (line 119)
- `src/api/src/services/model_service.py` (lines 182, 299, 353)
- `src/api/src/services/experiment_service.py` (lines 115, 117)
- `src/api/src/services/trading_service.py` (line 157)

**Note**: `NOW()` works in both, but verify timezone handling is consistent.

### Phase 3.5: Update Migration Scripts

**File**: `src/database/scripts/07_add_bitemporal_columns.sql`

**Change**:
```sql
-- Replace
latency_seconds = TIMESTAMPDIFF(SECOND, datetime, created_at)

-- With
latency_seconds = EXTRACT(EPOCH FROM (created_at - datetime))::INTEGER
```

## Testing Strategy Updates

### Critical Test Cases

1. **Connection Pool Test**:
   - Verify connections are properly returned to pool
   - Test connection pool exhaustion
   - Test connection retry logic

2. **lastrowid Replacement Test**:
   - Verify all INSERT operations return correct IDs
   - Test in all affected files

3. **SQL Function Test**:
   - Test DATE_SUB/DATE_ADD replacements
   - Test TIMESTAMPDIFF replacement
   - Verify timezone handling

4. **Error Handling Test**:
   - Test transient error detection
   - Test error code mapping
   - Test retry logic

5. **Transaction Test**:
   - Verify commit/rollback work correctly
   - Test connection cleanup on errors

## Additional Considerations

### 1. Connection Pool Size

PostgreSQL connection pools work differently. Consider:
- Current: pool_size=20
- PostgreSQL: minconn=1, maxconn=20
- May need adjustment based on workload

### 2. Autocommit Behavior

PostgreSQL has different autocommit defaults. Verify:
- Explicit commits are working
- Rollbacks work correctly
- No unexpected autocommit behavior

### 3. Timezone Handling

PostgreSQL timezone handling is stricter. Ensure:
- All timestamps stored in UTC
- Queries use appropriate timezone
- NOW() returns correct timezone

### 4. JSON/JSONB Queries

JSONB is more efficient but has different query syntax. Verify:
- JSON queries work correctly
- Index usage is optimal
- Query performance is acceptable

## Updated Timeline

| Phase | Duration | Key Changes |
|-------|----------|-------------|
| Phase 1: Schema | 3 days | Same as before |
| Phase 2: Infrastructure | 2 days | Same as before |
| Phase 3: Code Migration | **6 days** | **Increased due to 15+ files** |
| Phase 4: Testing | **5 days** | **Increased for critical tests** |
| Phase 5: Production Ready | 3 days | Same as before |

**Total Duration**: 19-21 days (3-4 weeks)

## Risk Assessment Update

### High Risk Areas

1. **Connection Pool API Changes** - HIGH RISK
   - Impact: All database operations
   - Mitigation: Comprehensive testing, code review
   - Testing: Connection pool stress tests

2. **lastrowid Replacement** - HIGH RISK
   - Impact: All INSERT operations
   - Mitigation: Test all affected files
   - Testing: Verify IDs returned correctly

3. **Error Code Mapping** - MEDIUM RISK
   - Impact: Error handling, retries
   - Mitigation: Test error scenarios
   - Testing: Simulate connection failures

4. **SQL Function Differences** - MEDIUM RISK
   - Impact: Time-based queries
   - Mitigation: Test all time-based queries
   - Testing: Verify query results match

## Success Criteria (Updated)

### Critical Must-Pass Tests

- [ ] All connection pool operations work correctly
- [ ] All INSERT operations return correct IDs
- [ ] All time-based queries work correctly
- [ ] Error handling and retries work correctly
- [ ] No connection leaks (verify with monitoring)
- [ ] All 15+ files updated and tested
- [ ] Performance equal or better than MariaDB

## Files Modified Summary (Updated)

### Critical Files (Must Update)

1. `src/mt5-python_server/src/database.py` - Core database class
2. `src/mt5-python_server/src/features/catalog.py`
3. `src/mt5-python_server/src/mlops/feature_registry.py`
4. `src/mt5-python_server/src/risk/oms.py`
5. `src/mt5-python_server/src/risk/kill_switch.py`
6. `src/mt5-python_server/src/risk/circuit_breaker.py`
7. `src/mt5-python_server/src/performance/metrics_calculator.py`
8. `src/mt5-python_server/src/performance/trade_logger.py`
9. `src/mt5-python_server/src/performance/session_manager.py`
10. `src/mt5-python_server/src/mlops/paper_session_manager.py`
11. `src/mt5-python_server/src/mlops/model_registry.py`
12. `src/mt5-python_server/src/experiments/optuna_tuner.py`
13. `src/api/src/services/database.py`
14. `src/api/src/config.py`
15. All SQL migration files

**Total**: 15+ Python files + 15 SQL files
