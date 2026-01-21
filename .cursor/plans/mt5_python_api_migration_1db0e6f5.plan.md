---
name: MT5 Python API Migration
overview: Migrate all trading operations from socket-based EA to MT5 Python API while preserving socket connections for tick streaming. This eliminates connection reliability issues and simplifies user onboarding.
todos:
  - id: security-infra
    content: Create CredentialManager for password encryption/decryption using Fernet
    status: pending
  - id: db-migration
    content: Create database migration script to add mt5_password_encrypted and mt5_server fields
    status: pending
  - id: python-api-adapter
    content: Implement MT5PythonAPIBrokerAdapter class using MetaTrader5 Python package, implementing all IBrokerAdapter methods
    status: pending
  - id: adapter-factory
    content: Update broker adapter factory to support creating Python API adapters from encrypted credentials
    status: pending
  - id: update-models
    content: Update SQLAlchemy models to include mt5_password_encrypted and mt5_server fields
    status: pending
  - id: update-schemas
    content: Update Pydantic schemas to require password/server in account creation, remove auth_token requirement
    status: pending
  - id: update-service
    content: Update mt5_accounts_service to encrypt passwords and store credentials
    status: pending
  - id: update-api
    content: Update API endpoints to require password/server collection, remove auth_token generation
    status: pending
  - id: update-frontend-types
    content: Update TypeScript types to include mt5_password and mt5_server in MT5AccountCreatePayload, remove auth_token from response
    status: pending
  - id: update-frontend-form
    content: Update MT5Accounts registration form to collect password and server fields, remove EA config display
    status: pending
  - id: update-frontend-api
    content: Update API service to send password/server in registration request
    status: pending
  - id: server-init
    content: Add server method to initialize Python API accounts from database on startup
    status: pending
  - id: add-dependencies
    content: Add cryptography and MetaTrader5 packages to requirements.txt
    status: pending
  - id: env-config
    content: Add MT5_ENCRYPTION_KEY to .env.example with generation instructions
    status: pending
  - id: unit-tests
    content: Write unit tests for CredentialManager and MT5PythonAPIBrokerAdapter
    status: pending
  - id: integration-tests
    content: Write integration tests for end-to-end Python API trading operations
    status: pending
isProject: false
---

# MT5 Python API Migration Plan

## Architecture Overview

### Current State

- Trading operations: Socket-based EA (`mt5_trading_operation.mq5`) → Server socket → `MT5Terminal` → `MT5BrokerAdapter`
- Tick streaming: Socket-based EA (`mt5_tick_streamer.mq5`) → Server socket → `MT5TickStreamer` → `MT5TickConnector`

### Target State

- Trading operations: MT5 Python API → `MT5PythonAPIBrokerAdapter` (new)
- Tick streaming: **UNCHANGED** - Socket-based EA → `MT5TickStreamer` → `MT5TickConnector`

## Affected Components

### Core Components Requiring Changes

1. **`MT5BrokerAdapter`** (`src/trading_server/src/trading/brokers/mt5_adapter.py`)

   - Currently wraps `MT5Terminal` (socket-based)
   - **Action**: Create new `MT5PythonAPIBrokerAdapter` class implementing `IBrokerAdapter`
   - Old `MT5BrokerAdapter` can be deprecated (EA code kept but not used for trading)

2. **`TerminalManager`** (`src/trading_server/src/infrastructure/connections/terminal_manager.py`)

   - Currently manages socket connections and heartbeats for trading
   - **Action**: No changes needed - Python API accounts don't use TerminalManager
   - Keep socket management for tick streaming EA only

3. **`Server`** (`src/trading_server/src/server.py`)

   - Socket server for EA connections
   - **Action**: Keep socket server for tick streaming, but trading operations bypass socket

4. **`Account`** (`src/trading_server/src/models/account.py`)

   - Currently requires `MT5Terminal` or `IBrokerAdapter`
   - **Action**: Minimal changes - works with new adapter via `IBrokerAdapter` interface

5. **Database Schema** (`src/database/scripts/17_mt5_accounts.sql`)

   - Currently stores `auth_token` for EA authentication
   - **Action**: Add encrypted password and server fields (auth_token can remain for reference but not used)

6. **API Endpoints** (`src/api/src/routers/mt5_accounts.py`)

   - Registration endpoint
   - **Action**: Add password collection, update schemas

7. **Schemas** (`src/api/src/schemas/mt5_accounts.py`)

   - Account creation/response schemas
   - **Action**: Require password and server fields (write-only password, never returned)

8. **Frontend Types** (`src/dashboard/src/types/mt5.ts`)

   - TypeScript interfaces for MT5 accounts
   - **Action**: Add `mt5_password` and `mt5_server` to `MT5AccountCreatePayload`, remove `auth_token` from `MT5AccountSecret` response

9. **Frontend Registration Form** (`src/dashboard/src/pages/MT5Accounts.tsx`)

   - Account registration UI
   - **Action**: Add password and server input fields, remove EA config display, update success message

10. **Frontend API Service** (`src/dashboard/src/services/api.ts`)

    - API client methods
    - **Action**: Update `postMt5AccountRegister` to send password/server, update response type

## Implementation Details

### Phase 1: Security Infrastructure

#### 1.1 Credential Encryption Service

**New File**: `src/trading_server/src/infrastructure/security/credential_manager.py`

```python
from cryptography.fernet import Fernet
import os
import base64

class CredentialManager:
    """Manages encryption/decryption of MT5 credentials"""
    
    def __init__(self):
        key = os.getenv("MT5_ENCRYPTION_KEY")
        if not key:
            raise ValueError("MT5_ENCRYPTION_KEY environment variable required")
        # Support both base64-encoded key or generate from string
        try:
            self.cipher = Fernet(key.encode())
        except:
            # If key is not valid Fernet key, derive from it
            key_bytes = key.encode()
            key_hash = hashlib.sha256(key_bytes).digest()
            self.cipher = Fernet(base64.urlsafe_b64encode(key_hash))
    
    def encrypt_password(self, password: str) -> bytes:
        return self.cipher.encrypt(password.encode())
    
    def decrypt_password(self, encrypted: bytes) -> str:
        return self.cipher.decrypt(encrypted).decode()
```

**Dependencies**: Add `cryptography>=41.0.0` to `requirements.txt`

#### 1.2 Database Migration

**New File**: `src/database/scripts/19_mt5_python_api_migration.sql`

```sql
-- Add fields for Python API connection (simplified - no connection_method needed)
ALTER TABLE mt5_accounts 
ADD COLUMN IF NOT EXISTS mt5_password_encrypted BYTEA,
ADD COLUMN IF NOT EXISTS mt5_server VARCHAR(100);

-- Index for server filtering
CREATE INDEX IF NOT EXISTS idx_mt5_accounts_server 
    ON mt5_accounts(mt5_server);
```

### Phase 2: New Broker Adapter Implementation

#### 2.1 MT5 Python API Broker Adapter

**New File**: `src/trading_server/src/trading/brokers/mt5_python_api_adapter.py`

```python
import MetaTrader5 as mt5
from typing import Dict, List, Optional
from datetime import datetime
from risk.oms import Order, Position, Discrepancy, OrderState
from trading.brokers.base import IBrokerAdapter, OrderStatus
from domain.entities.account_info import AccountInfo
from infrastructure.security.credential_manager import CredentialManager
from utils.logging_config import get_logger

class MT5PythonAPIBrokerAdapter(IBrokerAdapter):
    """MT5 broker adapter using Python API (no EA required)"""
    
    def __init__(self, login: int, password: str, server: str, credential_manager: CredentialManager):
        self.login = login
        self.password = password  # Decrypted password
        self.server = server
        self.credential_manager = credential_manager
        self.logger = get_logger("mt5_python_api_adapter", "mt5_python_api_adapter.log")
        self._idempotency_map: Dict[str, str] = {}
        self._order_id_map: Dict[str, Order] = {}
        self._initialized = False
        self._connection_id = None  # Track connection for cleanup
    
    def _ensure_connected(self):
        """Ensure MT5 connection is established"""
        if not self._initialized:
            if not mt5.initialize():
                raise ConnectionError(f"Failed to initialize MT5: {mt5.last_error()}")
            self._initialized = True
        
        # Login if not already logged in
        if not mt5.login(self.login, password=self.password, server=self.server):
            raise ConnectionError(f"Failed to login to MT5: {mt5.last_error()}")
    
    def submit_order(self, order: Order, idempotency_key: str) -> OrderStatus:
        """Submit order via MT5 Python API"""
        # Implementation using mt5.order_send()
        # Convert Order to MqlTradeRequest structure
        # Handle idempotency
        # Return OrderStatus
        pass
    
    def get_account_info(self) -> AccountInfo:
        """Get account info via mt5.account_info()"""
        self._ensure_connected()
        account_info = mt5.account_info()
        # Convert to AccountInfo
        pass
    
    # Implement other IBrokerAdapter methods...
    
    def __del__(self):
        """Cleanup: logout and shutdown"""
        if self._initialized:
            mt5.logout()
            mt5.shutdown()
```

**Key Implementation Notes**:

- Use `mt5.initialize()`, `mt5.login()`, `mt5.order_send()`, `mt5.account_info()`
- Handle connection pooling (one connection per account)
- Implement proper error handling for MT5 API errors
- Map MT5 error codes to `OrderStatus` states

#### 2.2 Broker Adapter Factory Update

**File**: `src/trading_server/src/trading/brokers/factory.py`

Add method to create Python API adapter:

```python
@staticmethod
def create_mt5_python_api_adapter(
    login: int, 
    encrypted_password: bytes, 
    server: str,
    credential_manager: CredentialManager
) -> MT5PythonAPIBrokerAdapter:
    """Create MT5 Python API adapter from credentials"""
    password = credential_manager.decrypt_password(encrypted_password)
    return MT5PythonAPIBrokerAdapter(login, password, server, credential_manager)
```

### Phase 3: Account Creation & Management

#### 3.1 Update Account Model

**File**: `src/api/src/models/mt5_accounts.py`

Add fields:

```python
mt5_password_encrypted = Column(LargeBinary, nullable=True)
mt5_server = Column(String(100), nullable=True)
```

Note: `auth_token` field remains in schema but is not used for new accounts.

#### 3.2 Update Schemas

**File**: `src/api/src/schemas/mt5_accounts.py`

Update `MT5AccountCreateRequest` to require:

```python
mt5_password: str = Field(..., description="MT5 account password (required)")
mt5_server: str = Field(..., description="MT5 broker server name (required)")
```

Remove `auth_token` requirement (no longer needed).

**Security**: Password should never be returned in response schemas.

#### 3.3 Update Service Layer

**File**: `src/api/src/services/mt5_accounts_service.py`

Update `create_account_for_user()`:

- Require password and server (no optional)
- Encrypt password using `CredentialManager`
- Store encrypted password and server
- No `connection_method` field needed (always Python API)

#### 3.4 Update API Endpoints

**File**: `src/api/src/routers/mt5_accounts.py`

Update `register_account_with_secret()`:

- Require `mt5_password` and `mt5_server` (always Python API)
- Remove `auth_token` generation and return (no longer needed)
- Return account info without auth_token, server_host, or server_port

### Phase 4: Frontend Updates

#### 4.1 Update TypeScript Types

**File**: `src/dashboard/src/types/mt5.ts`

Update `MT5AccountCreatePayload` to include required fields:

```typescript
export interface MT5AccountCreatePayload {
  account_login: number
  account_type: AccountType
  broker_name?: string
  broker_server?: string
  account_currency?: string
  account_leverage?: number
  account_name?: string
  mt5_password: string  // NEW: Required
  mt5_server: string    // NEW: Required
}
```

Update `MT5AccountSecret` interface (or remove if not needed):

```typescript
export interface MT5AccountSecret extends MT5Account {
  // Remove: auth_token, server_host, server_port
  // Response no longer includes these fields
}
```

#### 4.2 Update Registration Form

**File**: `src/dashboard/src/pages/MT5Accounts.tsx`

Update registration form state to include password and server:

```typescript
const [registerForm, setRegisterForm] = useState<{
  account_login: string
  account_name: string
  account_type: AccountType
  mt5_password: string      // NEW
  mt5_server: string        // NEW
}>({
  account_login: '',
  account_name: '',
  account_type: 'live',
  mt5_password: '',         // NEW
  mt5_server: '',           // NEW
})
```

Add password and server input fields in the form (after account_type field):

```tsx
<div>
  <label className="block text-sm font-medium mb-1">MT5 Password</label>
  <Input
    type="password"
    value={registerForm.mt5_password}
    onChange={(e) =>
      setRegisterForm((f) => ({ ...f, mt5_password: e.target.value }))
    }
    required
    placeholder="Your MT5 account password"
  />
</div>
<div>
  <label className="block text-sm font-medium mb-1">MT5 Server</label>
  <Input
    value={registerForm.mt5_server}
    onChange={(e) =>
      setRegisterForm((f) => ({ ...f, mt5_server: e.target.value }))
    }
    required
    placeholder="e.g., ICMarkets-Demo, FXCM-Demo"
  />
</div>
```

Update registration payload in `registerMutation`:

```typescript
const payload = {
  account_login: Number(registerForm.account_login),
  account_type: registerForm.account_type,
  account_name: registerForm.account_name || undefined,
  mt5_password: registerForm.mt5_password,  // NEW
  mt5_server: registerForm.mt5_server,      // NEW
}
```

Remove EA config display section:

- Remove `registrationResult` state that stores `auth_token`, `server_host`, `server_port`
- Remove the EA configuration snippet display (lines 212-223)
- Update success message to just confirm registration (no EA config needed)

Update button text from "Generate EA token" to "Register Account".

#### 4.3 Update API Service

**File**: `src/dashboard/src/services/api.ts`

Update `postMt5AccountRegister` method:

```typescript
async postMt5AccountRegister(payload: MT5AccountCreatePayload): Promise<MT5Account> {
  // Response no longer includes auth_token, server_host, server_port
  const response = await this.client.post<MT5Account>(
    `${API_ENDPOINTS.mt5Accounts}/register`,
    payload
  )
  return response.data
}
```

Change return type from `MT5AccountSecret` to `MT5Account`.

### Phase 5: Server-Side Account Initialization

#### 5.1 Update Server Account Management

**File**: `src/trading_server/src/server.py`

Add method to initialize accounts from database:

```python
def initialize_accounts_from_db(self):
    """Initialize accounts with Python API connection from database"""
    # Query all accounts with mt5_password_encrypted and mt5_server
    # Decrypt password using CredentialManager
    # Create MT5PythonAPIBrokerAdapter
    # Create Account instances
    # Add to __accounts list
    # No TerminalManager needed (no socket connections)
    pass
```

Call this during server startup.

### Phase 6: Environment Variable Configuration

**File**: `.env.example`

Add:

```bash
MT5 Credential Encryption
MT5_ENCRYPTION_KEY=your-base64-encoded-fernet-key-here
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Phase 7: Cleanup (Optional)

Since no production deployments exist, we can optionally:

- Keep `MT5BrokerAdapter` and `MT5Terminal` code for reference (EA files remain)
- Remove socket server trading code (keep tick streaming)
- Simplify `TerminalManager` to only handle tick streaming connections

**Note**: EA code files (`.mq5`) are kept but not used for trading operations.

## Testing Strategy

### Unit Tests

1. `CredentialManager` encryption/decryption
2. `MT5PythonAPIBrokerAdapter` methods (mock MT5 API)
3. Account creation with Python API credentials

### Integration Tests

1. End-to-end order execution via Python API
2. Account info retrieval
3. Position management
4. Migration from EA to Python API

### Manual Testing Checklist

- [ ] Register new account via frontend with password/server
- [ ] Verify password is not displayed/returned in UI
- [ ] Execute market order via Python API
- [ ] Get account info via Python API
- [ ] Close position via Python API
- [ ] Verify tick streaming still works (socket-based EA)

## Deployment Strategy

Since no production exists, this is a clean implementation:

### Step 1: Deploy Infrastructure

- Deploy database migration
- Deploy credential manager
- Deploy Python API adapter
- Deploy API changes (require password/server)

### Step 2: Test

- Register test account with password/server
- Test order execution
- Verify tick streaming (separate EA)

### Step 3: Cleanup (Optional)

- Remove unused socket trading code (keep tick streamer)
- Keep EA files for reference but mark as unused

## Risk Mitigation

1. **Credential Security**: 

   - Encrypt at rest using Fernet
   - Master key from environment variable
   - Never log passwords
   - Use secrets manager in production

2. **Connection Reliability**:

   - Implement connection retry logic
   - Handle MT5 API disconnections
   - Connection pooling per account

3. **Clean Implementation**:

   - Python API only (no dual-mode complexity)
   - Simpler codebase
   - No migration needed

4. **Error Handling**:

   - Map MT5 error codes to user-friendly messages
   - Log all API errors
   - Graceful degradation

## Files to Create/Modify

### New Files

- `src/trading_server/src/infrastructure/security/credential_manager.py`
- `src/trading_server/src/trading/brokers/mt5_python_api_adapter.py`
- `src/database/scripts/19_mt5_python_api_migration.sql`

### Modified Files

- `src/trading_server/src/trading/brokers/factory.py` (add Python API factory method)
- `src/trading_server/src/server.py` (add account initialization from DB)
- `src/api/src/models/mt5_accounts.py` (add password/server fields)
- `src/api/src/schemas/mt5_accounts.py` (require password/server, remove auth_token)
- `src/api/src/services/mt5_accounts_service.py` (encrypt passwords)
- `src/api/src/routers/mt5_accounts.py` (update registration to require password/server)
- `src/dashboard/src/types/mt5.ts` (add password/server to payload, remove auth_token from response)
- `src/dashboard/src/pages/MT5Accounts.tsx` (add password/server fields, remove EA config display)
- `src/dashboard/src/services/api.ts` (update registration API call)
- `requirements.txt` (add `cryptography` and `MetaTrader5`)
- `.env.example` (add `MT5_ENCRYPTION_KEY`)

**Note**: `TerminalManager` unchanged (only used for tick streaming EA)

### Unchanged (Tick Streaming)

- `src/utils/MT5-EA/EAs/mt5_tick_streamer.mq5`
- `src/trading_server/src/mt5_connection/tick_streamer.py`
- `src/trading_server/src/connectors/mt5_tick_connector.py`
- Socket server code (for tick streaming only)