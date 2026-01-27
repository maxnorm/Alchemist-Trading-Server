# Runtime Scenario: WebSocket Real-Time Updates

## Purpose
This diagram answers: **How do real-time updates flow from the backend services to the dashboard?**

## Scope
- **Includes**: WebSocket channels, subscription, broadcasting, alert consumption
- **Excludes**: REST API calls

## Source of Truth References
| Step | Evidence Path |
|------|---------------|
| WebSocket Manager | `src/api/src/websocket/manager.py` |
| Channel Handlers | `src/api/src/websocket/channels.py` |
| WebSocket Endpoints | `src/api/src/main.py:180-253` |
| Alert Consumer | `src/api/src/infrastructure/messaging/alert_consumer.py` |
| Alert Publisher | `src/trading_server/src/infrastructure/messaging/alert_publisher.py` |
| Dashboard WebSocket | `src/dashboard/src/services/websocket.ts` |
| WebSocket Context | `src/dashboard/src/contexts/WebSocketContext.tsx` |

## WebSocket Architecture

```mermaid
flowchart TB
    subgraph Dashboard["🖥️ React Dashboard"]
        WSContext["WebSocketContext"]
        WSService["WebSocket Service"]
        Hooks["useWebSocket Hooks"]
        Components["React Components"]
    end

    subgraph API["⚙️ FastAPI API"]
        WSEndpoints["WebSocket Endpoints"]
        WSManager["Connection Manager"]
        Channels["Channel Registry"]
        AlertConsumer["Alert Consumer"]
    end

    subgraph MessageBus["📨 Redis"]
        PubSub["Pub/Sub Channels"]
    end

    subgraph TradingServer["🖥️ Trading Server"]
        AlertPublisher["Alert Publisher"]
        TrainingLoop["Training Loop"]
        TradingController["Trading Controller"]
    end

    Components --> Hooks
    Hooks --> WSContext
    WSContext --> WSService
    WSService <-->|"WebSocket"| WSEndpoints

    WSEndpoints --> WSManager
    WSManager --> Channels

    AlertConsumer -->|"Subscribe"| PubSub
    AlertConsumer -->|"Broadcast"| WSManager

    AlertPublisher -->|"Publish"| PubSub
    TrainingLoop -->|"Metrics"| AlertPublisher
    TradingController -->|"Trades"| AlertPublisher

    style WSManager fill:#00b894,stroke:#00997b,color:#fff
    style PubSub fill:#dc382d,stroke:#a91d1d,color:#fff
```

## Connection Sequence

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant Dashboard
    participant WSService as WebSocket Service
    participant API as FastAPI
    participant Manager as Connection Manager
    participant Channels as Channel Registry

    %% Initial connection
    User->>Dashboard: Load application
    Dashboard->>WSService: Initialize WebSocket service
    WSService->>API: Connect to /ws
    API->>API: websocket.accept()
    API->>Manager: connect(websocket, "generic")
    Manager->>Channels: Add to channel set
    API-->>WSService: Connection established

    %% Subscribe to channels
    WSService->>API: Send: {action: "subscribe", channels: ["training", "alerts"]}
    API->>Manager: Add websocket to channels
    Manager-->>WSService: Subscribed to: training, alerts

    %% Keep-alive
    loop Heartbeat
        WSService->>API: Ping
        API-->>WSService: Pong
    end
```

## Broadcasting Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Server as Trading Server
    participant Publisher as Alert Publisher
    participant Redis as Redis Pub/Sub
    participant Consumer as Alert Consumer
    participant Manager as Connection Manager
    participant WSService as WebSocket Service
    participant Dashboard

    %% Training metrics broadcast
    Server->>Server: Training step completed
    Server->>Publisher: publish_training_metrics(metrics)
    Publisher->>Redis: PUBLISH alchemist:training {metrics}
    
    Redis->>Consumer: Message received
    Consumer->>Consumer: Parse message
    Consumer->>Manager: broadcast_to_channel("training", metrics)
    
    Manager->>Manager: Get channel subscribers
    
    loop Each subscriber
        Manager->>WSService: send_json({channel, data})
    end
    
    WSService->>Dashboard: onMessage callback
    Dashboard->>Dashboard: Update UI state
    Dashboard-->>User: Display new metrics
```

## WebSocket Channels

| Channel | Path | Purpose | Publisher |
|---------|------|---------|-----------|
| `ticks` | `/ws/ticks` | Real-time tick data | Trading Server |
| `training` | `/ws/training` | Training progress | Experiment Runner |
| `optuna` | `/ws/optuna` | Hyperparameter search | Optuna Tuner |
| `positions` | `/ws/positions` | Open positions | Trading Controller |
| `alerts` | `/ws/alerts` | System alerts | Various |
| `mt5_accounts` | `/ws/accounts/mt5` | Connection status | Trading Server |
| `performance` | `/ws/performance` | Performance updates | Performance Service |
| `trades` | `/ws/trades` | Trade execution | Trading Controller |
| `models` | `/ws/models` | Model lifecycle | Model Service |
| `models/{id}/status` | `/ws/models/{id}/status` | Specific model status | Model Service |
| `models/{id}/paper-session` | `/ws/models/{id}/paper-session` | Paper trading | Paper Session |
| `models/{id}/validation` | `/ws/models/{id}/validation` | Validation status | Validation Service |

## Message Format

### Client → Server (Subscription)
```json
{
  "action": "subscribe",
  "channels": ["training", "alerts", "positions"]
}
```

### Server → Client (Broadcast)
```json
{
  "channel": "/ws/training/metrics",
  "data": {
    "experiment_id": 1,
    "episode": 42,
    "step": 1000,
    "reward": 0.05,
    "loss": 0.012,
    "epsilon": 0.3
  }
}
```

### Alert Message Types
```json
// Training progress
{
  "type": "training_progress",
  "experiment_id": 1,
  "metrics": {...}
}

// Trade executed
{
  "type": "trade_executed",
  "ticket": 12345,
  "symbol": "EURUSD",
  "action": "BUY",
  "volume": 0.05
}

// System alert
{
  "type": "alert",
  "severity": "warning",
  "message": "High drawdown detected"
}

// MT5 connection status
{
  "type": "connection_status",
  "account_id": 1,
  "connected": true
}
```

## Dashboard WebSocket Hooks

| Hook | Channel | Usage |
|------|---------|-------|
| `useExperimentProgress` | training | Training monitor page |
| `useTradingPositions` | positions | Live trading page |
| `useOptunaTrials` | optuna | Hyperparameter search page |
| `useWebSocket` | generic | Base hook for any channel |

## Connection Management

### Reconnection Strategy
```typescript
// From websocket.ts
const RECONNECT_DELAYS = [1000, 2000, 5000, 10000, 30000]
```

1. Immediate reconnect attempt
2. Exponential backoff with jitter
3. Max 5 retry attempts before alert

### Heartbeat
- Ping every 30 seconds
- Disconnect if no pong within 10 seconds
- Auto-reconnect on disconnect

## Redis Pub/Sub Channels

| Redis Channel | API Channel | Purpose |
|---------------|-------------|---------|
| `alchemist:training` | training | Training metrics |
| `alchemist:alerts` | alerts | System alerts |
| `alchemist:trades` | trades | Trade events |
| `alchemist:positions` | positions | Position updates |
| `alchemist:mt5` | mt5_accounts | MT5 status |

## Error Handling

| Scenario | Action |
|----------|--------|
| Connection failed | Retry with backoff |
| Message parse error | Log and continue |
| Channel not found | Ignore subscription |
| Client disconnect | Clean up subscriptions |
| Redis down | API continues, no broadcasts |

## Assumptions
- **None** - All WebSocket flows verified in codebase
