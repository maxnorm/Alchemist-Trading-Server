# Schema Contracts

## Overview

Schema contracts define the structure, types, units, formats, and validation rules for all data types in the system. This document serves as the authoritative specification for data schemas and enables modular addition of new data types.

## Design Principles

1. **Modularity**: Each data type has its own contract definition that can be added independently
2. **Versioning**: Contracts are versioned to track schema evolution over time
3. **Extensibility**: New data types can be added by creating new contract definitions
4. **Validation**: Contracts provide both structural and semantic validation rules
5. **Documentation**: Contracts serve as both specification and documentation

## Contract Structure

Each schema contract defines:

- **Data Type**: The canonical data type identifier (e.g., "tick", "bar", "news")
- **Version**: Semantic version (e.g., "1.0.0")
- **Fields**: Field definitions with types, units, formats, constraints
- **Required Fields**: List of mandatory fields
- **Optional Fields**: List of optional fields with defaults
- **Validation Rules**: Custom validation logic
- **Database Mapping**: How fields map to database columns

## Current Schema Contracts

### 1. Tick Data Contract

**Data Type**: `tick`  
**Current Version**: `1.0.0`  
**Description**: Real-time price tick data for currency pairs

#### Fields

| Field Name | Type | Unit | Format | Required | Constraints | Description |
|------------|------|------|--------|----------|-------------|-------------|
| `symbol` | string | - | Uppercase, 6 chars (e.g., "EURUSD") | Yes | Must match regex: `^[A-Z]{6}$` | Currency pair symbol |
| `datetime` | datetime | UTC | ISO 8601 with timezone | Yes | Timezone-aware, UTC normalized | Event timestamp (event_time) |
| `bid` | float | Price | Decimal (e.g., 1.12345) | Yes | `bid > 0`, `bid < ask` | Bid price |
| `ask` | float | Price | Decimal (e.g., 1.12350) | Yes | `ask > 0`, `ask > bid` | Ask price |
| `receive_time` | datetime | UTC | ISO 8601 with timezone | No | Timezone-aware, UTC normalized | Transaction timestamp |
| `latency_seconds` | integer | Seconds | Integer | No | `>= 0` | Latency in seconds |
| `is_stale` | boolean | - | true/false | No | - | Flag indicating stale timestamp |
| `stale_age_seconds` | integer | Seconds | Integer | No | `>= 0` | Age of stale timestamp |
| `timestamp_source` | string | - | Enum: "event", "receive", "estimated" | No | - | Source of timestamp |
| `volume` | float | Lots | Decimal | No | `>= 0` | Trading volume (if available) |

#### Validation Rules

1. **Spread Validation**: `ask - bid > 0` and `ask - bid < 0.01` (100 pips max for forex)
2. **Price Range**: Prices must be positive and within reasonable bounds for the currency pair
3. **Timestamp Ordering**: `receive_time >= datetime` (if both present)
4. **Symbol Format**: Must be exactly 6 uppercase characters

#### Database Mapping

- Table: `ticks_forex`
- Mapping:
  - `symbol` → Resolved via `forex_pairs` table (base_currency + quote_currency)
  - `datetime` → `datetime` column
  - `bid` → `bid` column
  - `ask` → `ask` column
  - `receive_time` → `receive_time` column
  - `latency_seconds` → `latency_seconds` column
  - `is_stale` → `is_stale` column
  - `stale_age_seconds` → `stale_age_seconds` column
  - `timestamp_source` → `timestamp_source` column
  - `volume` → `volume` column

---

### 2. Bar/OHLCV Data Contract

**Data Type**: `bar`  
**Current Version**: `1.0.0`  
**Description**: Aggregated price bars (OHLCV) for time-series analysis

#### Fields

| Field Name | Type | Unit | Format | Required | Constraints | Description |
|------------|------|------|--------|----------|-------------|-------------|
| `symbol` | string | - | Uppercase, 6 chars | Yes | Must match regex: `^[A-Z]{6}$` | Currency pair symbol |
| `datetime` | datetime | UTC | ISO 8601 with timezone | Yes | Timezone-aware, UTC normalized | Bar start timestamp |
| `open` | float | Price | Decimal | Yes | `open > 0` | Opening price |
| `high` | float | Price | Decimal | Yes | `high >= open`, `high >= low`, `high >= close` | Highest price |
| `low` | float | Price | Decimal | Yes | `low > 0`, `low <= open`, `low <= high`, `low <= close` | Lowest price |
| `close` | float | Price | Decimal | Yes | `close > 0` | Closing price |
| `volume` | float | Lots | Decimal | No | `>= 0` | Trading volume |
| `timeframe` | string | - | Enum: "M1", "M5", "M15", "M30", "H1", "H4", "D1" | Yes | - | Bar timeframe |
| `receive_time` | datetime | UTC | ISO 8601 with timezone | No | Timezone-aware, UTC normalized | Transaction timestamp |

#### Validation Rules

1. **OHLC Consistency**: `high >= max(open, close)` and `low <= min(open, close)`
2. **Price Ordering**: `high >= low` (always true by definition)
3. **Timeframe Validation**: Must be a valid timeframe enum value
4. **Symbol Format**: Must be exactly 6 uppercase characters

#### Database Mapping

- Table: `bars_forex` (to be created)
- Mapping: Direct field-to-column mapping

---

### 3. News Data Contract

**Data Type**: `news`  
**Current Version**: `1.0.0`  
**Description**: News events and announcements affecting markets

#### Fields

| Field Name | Type | Unit | Format | Required | Constraints | Description |
|------------|------|------|--------|----------|-------------|-------------|
| `symbol` | string | - | Uppercase, 6 chars or "*" | Yes | - | Affected currency pair or "*" for general news |
| `datetime` | datetime | UTC | ISO 8601 with timezone | Yes | Timezone-aware, UTC normalized | News publication timestamp |
| `title` | string | - | UTF-8 text | Yes | Length: 1-500 chars | News headline |
| `content` | string | - | UTF-8 text | No | Length: 0-10000 chars | Full news content |
| `source` | string | - | String | Yes | Length: 1-100 chars | News source identifier |
| `impact` | string | - | Enum: "low", "medium", "high" | No | - | Expected market impact |
| `category` | string | - | String | No | - | News category |
| `receive_time` | datetime | UTC | ISO 8601 with timezone | No | Timezone-aware, UTC normalized | Transaction timestamp |

#### Validation Rules

1. **Content Length**: Title and content must not exceed maximum lengths
2. **Impact Validation**: Impact must be valid enum value if provided
3. **Symbol Validation**: Symbol must be valid format or "*"

#### Database Mapping

- Table: `news_events` (to be created)
- Mapping: Direct field-to-column mapping

---

### 4. Economic Calendar Data Contract

**Data Type**: `economic`  
**Current Version**: `1.0.0`  
**Description**: Economic calendar events and indicators

#### Fields

| Field Name | Type | Unit | Format | Required | Constraints | Description |
|------------|------|------|--------|----------|-------------|-------------|
| `datetime` | datetime | UTC | ISO 8601 with timezone | Yes | Timezone-aware, UTC normalized | Event scheduled time |
| `country` | string | - | ISO country code | Yes | Length: 2-3 chars | Country code |
| `event` | string | - | UTF-8 text | Yes | Length: 1-250 chars | Event name |
| `impact` | integer | - | Integer | Yes | Range: 0-3 | Impact level (0=low, 3=high) |
| `previous` | string | - | Decimal string | No | - | Previous value |
| `consensus` | string | - | Decimal string | No | - | Consensus forecast |
| `actual` | string | - | Decimal string | No | - | Actual value |
| `receive_time` | datetime | UTC | ISO 8601 with timezone | No | Timezone-aware, UTC normalized | Transaction timestamp |

#### Validation Rules

1. **Impact Range**: Impact must be between 0 and 3
2. **Country Code**: Must be valid ISO country code
3. **Value Format**: Previous, consensus, actual must be parseable as numbers if provided

#### Database Mapping

- Table: `economic_calendar`
- Mapping: Direct field-to-column mapping

---

## Schema Versioning

### Version Format

Schema versions follow semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes (field removal, type changes)
- **MINOR**: Non-breaking additions (new optional fields)
- **PATCH**: Bug fixes, clarifications

### Version Tracking

Each data record stores:
- `schema_version`: The schema contract version used when the data was ingested
- `schema_type`: The data type identifier (e.g., "tick", "bar")

This enables:
- **Backward Compatibility**: Query data by schema version
- **Migration Planning**: Identify which records need migration
- **Audit Trail**: Track when schema changes were applied

### Database Schema Versioning

The database tracks schema versions in:

1. **`schema_contracts` table**: Registry of all contract definitions
2. **Data tables**: Each table has `schema_version` and `schema_type` columns

---

## Adding New Data Types

To add a new data type:

1. **Define Contract**: Add a new section in this document following the template
2. **Register Contract**: Add contract definition to `schema_contracts` table
3. **Implement Validator**: Create validator class in `src/trading_server/src/data/contracts/`
4. **Update Quality Gates**: Register validator in `quality_gates.py`
5. **Database Migration**: Create table and add schema version columns
6. **Update Documentation**: Add examples and usage patterns

### Contract Template

```markdown
### N. [Data Type Name] Data Contract

**Data Type**: `[type_identifier]`  
**Current Version**: `1.0.0`  
**Description**: [Brief description]

#### Fields

[Table of fields with types, units, formats, constraints]

#### Validation Rules

[Custom validation logic]

#### Database Mapping

[Table name and field mappings]
```

---

## Validation Architecture

### Contract Validator Interface

All contract validators implement:

```python
class IContractValidator(ABC):
    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate data against contract"""
        pass
    
    @abstractmethod
    def get_contract_version(self) -> str:
        """Return contract version"""
        pass
    
    @abstractmethod
    def get_data_type(self) -> str:
        """Return data type identifier"""
        pass
```

### Integration with Quality Gates

Contract validation is integrated into the quality gate pipeline:

1. **Schema Contract Check**: Validates structure, types, formats
2. **Business Logic Check**: Validates ranges, relationships, constraints
3. **Data Quality Check**: Validates outliers, duplicates, staleness

---

## Migration Strategy

When a schema contract changes:

1. **Create New Version**: Define new contract version (e.g., `1.1.0`)
2. **Backward Compatibility**: Ensure old data can still be read
3. **Migration Script**: Create migration to transform old data (if needed)
4. **Gradual Rollout**: Update validators to use new version
5. **Data Migration**: Migrate existing data to new schema (optional)

---

## Examples

### Valid Tick Data

```json
{
  "symbol": "EURUSD",
  "datetime": "2024-01-15T10:30:45.123456+00:00",
  "bid": 1.12345,
  "ask": 1.12350,
  "receive_time": "2024-01-15T10:30:45.200000+00:00",
  "latency_seconds": 0,
  "is_stale": false,
  "timestamp_source": "event"
}
```

### Invalid Tick Data (Missing Required Field)

```json
{
  "symbol": "EURUSD",
  "datetime": "2024-01-15T10:30:45.123456+00:00",
  "bid": 1.12345
  // Missing "ask" - validation will fail
}
```

### Invalid Tick Data (Type Mismatch)

```json
{
  "symbol": "EURUSD",
  "datetime": "2024-01-15T10:30:45.123456+00:00",
  "bid": "1.12345",  // String instead of float - validation will fail
  "ask": 1.12350
}
```

---

## Contract Registry

The system maintains a registry of all active contracts in the `schema_contracts` database table:

| Contract ID | Data Type | Version | Status | Created At | Description |
|-------------|-----------|---------|--------|------------|-------------|
| 1 | tick | 1.0.0 | active | 2024-01-01 | Tick data contract |
| 2 | bar | 1.0.0 | active | 2024-01-01 | OHLCV bar data contract |
| 3 | news | 1.0.0 | active | 2024-01-01 | News data contract |
| 4 | economic | 1.0.0 | active | 2024-01-01 | Economic calendar contract |

---

## References

- [Canonical Event Schema](../src/trading_server/src/events/schema_registry.py)
- [Quality Gates](../src/trading_server/src/data/quality_gates.py)
- [Database Schema](../src/database/scripts/)
