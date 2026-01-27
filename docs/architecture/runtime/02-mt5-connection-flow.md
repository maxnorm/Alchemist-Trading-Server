# Runtime Scenario: MT5 Expert Advisor Connection Flow

## Purpose
This diagram answers: **How do MT5 Expert Advisors connect to the Trading Server for tick streaming and trade execution?**

## Scope
- **Includes**: Streamer authentication, Terminal authentication, connection lifecycle
- **Excludes**: Internal MT5 operations

## Source of Truth References
| Step | Evidence Path |
|------|---------------|
| Socket Server | `src/trading_server/src/server.py:169-188` |
| Auth Socket | `src/trading_server/src/server.py:212-355` |
| Streamer Auth | `src/trading_server/src/server.py:357-465` |
| Terminal Auth | `src/trading_server/src/server.py:467-567` |
| Tick Streamer EA | `src/utils/MT5-EA/EAs/mt5_tick_streamer.mq5` |
| Trading EA | `src/utils/MT5-EA/EAs/mt5_trading_operation.mq5` |

## Sequence Diagram - Tick Streamer Connection

```mermaid
sequenceDiagram
    autonumber
    participant MT5 as MT5 Terminal
    participant EA as Tick Streamer EA
    participant Gateway as nginx Gateway
    participant Server as Trading Server
    participant Registry as Connector Registry
    participant Catalog as Feature Catalog
    participant DB as PostgreSQL

    %% Connection initiation
    MT5->>EA: OnInit() - EA starts
    EA->>EA: Read config (ip, port, symbol, streamer_token)
    
    EA->>Gateway: TCP Connect to port 8080
    Gateway->>Server: Proxy TCP connection
    Server->>Server: socket.accept()
    Server-->>EA: Connection established
    
    %% Authentication
    EA->>Server: JSON: {auth_code: 1, symbol: "EURUSD",<br/>digits: 5, streamer_token: "xxx"}
    
    Server->>Server: __auth_socket() - detect MT5 protocol
    Server->>Server: __auth_streamer()
    
    alt Token Valid
        Server->>Server: Validate streamer_token vs STREAMER_AUTH_TOKEN env
        Server-->>EA: {auth_status: 0}
        
        %% Setup connectors
        Server->>Server: Create CurrencyPair object
        Server->>Registry: Create MT5PriceConnector
        Registry->>Registry: Register connector
        Server->>Catalog: Sync with connector registry
        Catalog->>Catalog: Discover features
        
        Server->>Server: Create MT5TickStreamer
        Server->>Server: Start receive_tick thread
        
        %% Tick streaming loop
        loop Every Tick
            MT5->>EA: OnTick() event
            EA->>Server: {datetime, bid, ask, volume}\n
            Server->>Server: Parse tick data
            Server->>DB: Insert into ticks_forex
            Server->>Registry: Update MT5PriceConnector
        end
    else Token Invalid
        Server-->>EA: {auth_status: -1, message: "Authentication failed"}
        Server->>Server: Close connection
    end
```

## Sequence Diagram - Trading Terminal Connection

```mermaid
sequenceDiagram
    autonumber
    participant MT5 as MT5 Terminal
    participant EA as Trading EA
    participant Server as Trading Server
    participant DBInt as DB Integration
    participant DB as PostgreSQL
    participant Account as Account Manager

    %% Pre-requisite: Account must be registered via API
    Note over Server,DB: Account pre-registered via<br/>POST /api/mt5-accounts/register

    %% Connection initiation
    MT5->>EA: OnInit() - EA starts
    EA->>EA: Read config (ip, port, login, auth_token)
    
    EA->>Server: TCP Connect to port 8080
    Server-->>EA: Connection established
    
    %% Authentication
    EA->>Server: JSON: {auth_code: 2, login: 12345678,<br/>auth_token: "yyy", account_type: 0,<br/>broker_name: "ICMarkets"}
    
    Server->>Server: __auth_terminal()
    Server->>DBInt: get_account_from_db(login)
    DBInt->>DB: SELECT FROM mt5_accounts WHERE login = ?
    
    alt Account Exists
        DB-->>DBInt: Account data
        DBInt-->>Server: Account record
        
        Server->>DBInt: get_account_auth_token(login)
        DBInt-->>Server: Expected auth_token
        
        alt Token Matches
            Server->>Server: Create MT5Terminal
            Server-->>EA: {auth_status: 0, terminal_id: 1}
            
            Server->>Server: Create MT5BrokerAdapter
            Server->>Account: Create/Update Account with adapter
            
            Server->>DBInt: update_account_in_db()
            DBInt->>DB: UPDATE mt5_accounts SET ...
            
            Server->>DBInt: log_connection()
            DBInt->>DB: INSERT INTO mt5_connections
            
            Server->>Server: Create LiveTradingEnv
            
            %% Trading operations loop
            loop Trading Session
                Server->>EA: Trade signal: {type: "BUY", symbol, volume, ...}
                EA->>MT5: OrderSend()
                MT5-->>EA: Order result
                EA->>Server: Execution result
            end
        else Token Mismatch
            Server-->>EA: {auth_status: -1, message: "Authentication failed"}
        end
    else Account Not Found
        Server-->>EA: {auth_status: -1, message: "Account not registered"}
    end
```

## Authentication Protocol

### Streamer Authentication
| Field | Type | Description |
|-------|------|-------------|
| `auth_code` | int | Must be `1` for streamer |
| `symbol` | string | Currency pair (e.g., "EURUSD") |
| `digits` | int | Decimal precision (e.g., 5) |
| `streamer_token` | string | Must match `STREAMER_AUTH_TOKEN` env var |

### Terminal Authentication
| Field | Type | Description |
|-------|------|-------------|
| `auth_code` | int | Must be `2` for terminal |
| `login` | int | MT5 account login number |
| `auth_token` | string | Per-account token from registration |
| `account_type` | int | 0=Demo, 2=Live |
| `broker_name` | string | Optional broker identifier |

### Response Format
```json
// Success
{"auth_status": 0, "terminal_id": 1}

// Failure
{"auth_status": -1, "message": "Error description"}
```

## Connection Lifecycle

### Streamer Lifecycle
1. EA connects on chart attach
2. Server authenticates with environment token
3. Streamer thread receives ticks continuously
4. On EA removal/MT5 close: socket closes, connection cleaned up

### Terminal Lifecycle
1. Account pre-registered via API (user gets auth_token)
2. EA connects with account credentials
3. Server validates token from database
4. Terminal ready to receive trade commands
5. Connection status tracked in `mt5_connections` table

## Error Scenarios

| Scenario | Response | Recovery |
|----------|----------|----------|
| Invalid streamer token | `auth_status: -1` | Check `STREAMER_AUTH_TOKEN` env var |
| Account not registered | `auth_status: -1` | Register via API first |
| Invalid auth token | `auth_status: -1` | Verify token from registration |
| Connection timeout | Socket closed | EA auto-reconnects |
| Server unavailable | Connection refused | Check server status |

## Assumptions
- **None** - All connection flows verified in codebase
