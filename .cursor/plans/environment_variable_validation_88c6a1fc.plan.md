---
name: Environment Variable Validation
overview: Add fail-fast environment variable validation at startup for both API and Trading Server services, with a reusable validation script and Docker entrypoint integration.
todos:
  - id: create-validate-script
    content: Create scripts/validate-env.sh that validates required environment variables per service (api, server, all)
    status: pending
  - id: enhance-api-config
    content: Enhance src/api/src/config.py to wrap Settings() instantiation with clear validation error handling
    status: pending
  - id: add-trading-server-validation
    content: Add validate_environment() function to src/trading_server/src/app.py and call it at startup
    status: pending
  - id: create-api-entrypoint
    content: Create src/api/entrypoint.sh that calls validate-env.sh before starting uvicorn
    status: pending
  - id: create-server-entrypoint
    content: Create src/trading_server/entrypoint.sh that calls validate-env.sh before starting Python app
    status: pending
  - id: update-api-dockerfile
    content: Update src/api/Dockerfile to copy and use entrypoint script
    status: pending
  - id: update-server-dockerfile
    content: Update src/trading_server/Dockerfile to copy and use entrypoint script
    status: pending
isProject: false
---

# Environment Variable Validation Implementation Plan

## Overview

Add comprehensive environment variable validation to ensure services fail fast with clear error messages when required configuration is missing. This will prevent runtime errors and improve deployment reliability.

## Current State Analysis

### API Service (`src/api/src/config.py`)

- Uses `pydantic-settings` with `BaseSettings`
- Required fields without defaults: `db_host`, `db_port`, `db_user`, `db_password`, `db_name`, `mlflow_tracking_uri`
- Settings instantiated at module level (`settings = Settings()`)
- Pydantic will raise `ValidationError` on missing required fields, but error messages could be clearer

### Trading Server (`src/trading_server/src/app.py`)

- Uses `os.getenv()` with defaults for most variables
- No validation - services start even if required vars are missing
- Uses `load_dotenv()` to load environment variables
- Database connection uses defaults if env vars missing (in `src/trading_server/src/database/config.py`)

### Docker Compose

- Services depend on environment variables from `.env` file
- No validation before container startup
- Multiple services require DB_* variables

## Implementation Strategy

### 1. Create Validation Script (`scripts/validate-env.sh`)

Create a reusable shell script that validates required environment variables:

- Accept service name as argument (`api`, `server`, `all`)
- Define required variables per service
- Check each variable and collect missing ones
- Exit with non-zero code and clear error message listing missing variables
- Support both shell and Docker environments

**Required Variables by Service:**

**API Service:**

- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `MLFLOW_TRACKING_URI`
- `API_HOST`, `API_PORT` (have defaults but validate they're set)

**Trading Server:**

- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `SERVER_IP`, `SERVER_PORT`
- `STREAMER_AUTH_TOKEN` (if using tick streaming)

**Common:**

- Database variables are shared across services

### 2. Enhance API Service Validation (`src/api/src/config.py`)

- Wrap `Settings()` instantiation in try-except to catch `ValidationError`
- Parse pydantic validation errors to extract missing field names
- Format clear error message: "Missing required environment variable(s): VAR1, VAR2, ..."
- Exit with code 1 if validation fails
- Create `validate_settings()` function that can be called explicitly

### 3. Add Trading Server Validation (`src/trading_server/src/app.py`)

- Create `validate_environment()` function that checks required variables
- Call before `create_composition_root()` in `start()` function
- Use `os.getenv()` without defaults to detect missing variables
- Exit with code 1 and clear error message if validation fails

### 4. Create Docker Entrypoint Scripts

**API Entrypoint (`src/api/entrypoint.sh`):**

- Call `validate-env.sh api` before starting uvicorn
- Exit if validation fails
- Otherwise proceed with `uvicorn main:app`

**Trading Server Entrypoint (`src/trading_server/entrypoint.sh`):**

- Call `validate-env.sh server` before starting Python app
- Exit if validation fails
- Otherwise proceed with `python src/app.py`

### 5. Update Dockerfiles

`**src/api/Dockerfile`:**

- Copy `scripts/validate-env.sh` into image
- Copy `src/api/entrypoint.sh` into image
- Make entrypoint script executable
- Change `CMD` to use entrypoint script

`**src/trading_server/Dockerfile`:**

- Copy `scripts/validate-env.sh` into image
- Copy `src/trading_server/entrypoint.sh` into image
- Make entrypoint script executable
- Change `CMD` to use entrypoint script

### 6. Update docker-compose.yml (Optional Enhancement)

- Add healthcheck that validates env vars are set (or rely on startup validation)
- Consider adding init containers that validate before dependent services start

## File Changes

### New Files

1. `scripts/validate-env.sh` - Main validation script
2. `src/api/entrypoint.sh` - API Docker entrypoint
3. `src/trading_server/entrypoint.sh` - Trading server Docker entrypoint

### Modified Files

1. `src/api/src/config.py` - Add validation error handling
2. `src/trading_server/src/app.py` - Add `validate_environment()` function
3. `src/api/Dockerfile` - Add entrypoint script and validation
4. `src/trading_server/Dockerfile` - Add entrypoint script and validation

## Validation Logic

The validation script will:

1. Accept service name: `api`, `server`, or `all`
2. Define required variables per service
3. Check each variable using `[ -z "${VAR}" ]` test
4. Collect missing variables in an array
5. If any missing, print error message and exit 1
6. If all present, exit 0

## Error Message Format

```
ERROR: Missing required environment variable(s) for service 'api':
  - DB_PASSWORD
  - MLFLOW_TRACKING_URI

Please set these variables in your .env file or environment.
```

## Testing Strategy

1. **Test validation script directly:**
  ```bash
   # Remove a required var
   unset DB_PASSWORD
   ./scripts/validate-env.sh api
   # Should exit 1 with error message
  ```
2. **Test API service:**
  ```bash
   # Remove required var
   unset DB_PASSWORD
   docker compose up api
   # Should fail to start with clear error
  ```
3. **Test Trading Server:**
  ```bash
   # Remove required var
   unset DB_PASSWORD
   docker compose up server
   # Should fail to start with clear error
  ```
4. **Test with all vars set:**
  ```bash
   # All vars present
   docker compose up api server
   # Should start successfully
  ```

## Acceptance Criteria Verification

✅ `scripts/validate-env.sh` validates all required vars

- Script checks all required variables per service
- Exits with non-zero code if any missing
- Provides clear error messages

✅ Services fail to start if required vars missing

- API service fails before uvicorn starts
- Trading server fails before Python app starts
- Docker containers exit with error code

✅ Clear error messages indicate which vars are missing

- Error message lists all missing variables
- Error message indicates which service is affected
- Error message provides guidance (check .env file)

## Implementation Notes

- Use bash for maximum compatibility (works in Docker alpine/debian images)
- Make scripts executable (`chmod +x`)
- Ensure scripts work both in local shell and Docker containers
- Consider making validation script work with `.env` file directly (using `source` or parsing)
- Validation happens before any service initialization to fail fast
- Python validation complements shell script for programmatic access

