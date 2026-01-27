# Runtime Scenario: Trade Execution Flow

## Purpose
This diagram answers: **How does a trade signal from a trained model result in an executed order on MT5?**

## Scope
- **Includes**: Signal generation, risk validation, order execution, result handling
- **Excludes**: Model training, account registration

## Source of Truth References
| Step | Evidence Path |
|------|---------------|
| Trading Controller | `src/trading_server/src/trading_controller.py` |
| Risk Manager | `src/trading_server/src/risk/risk_manager.py` |
| Kill Switch | `src/trading_server/src/risk/kill_switch.py` |
| Circuit Breaker | `src/trading_server/src/risk/circuit_breaker.py` |
| Position Sizer | `src/trading_server/src/risk/position_sizer.py` |
| Broker Adapter | `src/trading_server/src/trading/brokers/mt5_adapter.py` |
| MT5 Terminal | `src/trading_server/src/mt5_connection/terminal.py` |
| Trading EA | `src/utils/MT5-EA/EAs/mt5_trading_operation.mq5` |

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant Model as DRL Model
    participant Controller as Trading Controller
    participant Risk as Risk Manager
    participant Kill as Kill Switch
    participant CB as Circuit Breaker
    participant Sizer as Position Sizer
    participant Adapter as MT5 Broker Adapter
    participant Terminal as MT5 Terminal
    participant EA as Trading EA
    participant MT5 as MetaTrader 5
    participant DB as PostgreSQL

    %% Signal Generation
    Model->>Controller: Trade signal<br/>{action: BUY, symbol: EURUSD, confidence: 0.85}
    
    %% Kill Switch Check
    Controller->>Kill: is_active()
    
    alt Kill Switch Active
        Kill-->>Controller: True
        Controller->>Controller: Log blocked signal
        Controller-->>Model: Signal blocked (kill switch)
    else Kill Switch Inactive
        Kill-->>Controller: False
        
        %% Circuit Breaker Check
        Controller->>CB: can_trade()
        
        alt Circuit Breaker Tripped
            CB-->>Controller: False (loss limit exceeded)
            Controller->>Controller: Log blocked signal
            Controller-->>Model: Signal blocked (circuit breaker)
        else Circuit Breaker OK
            CB-->>Controller: True
            
            %% Risk Validation
            Controller->>Risk: validate_signal(signal)
            Risk->>DB: Get current positions
            DB-->>Risk: Open positions
            
            Risk->>Risk: Check exposure limits
            Risk->>Risk: Check correlation limits
            Risk->>Risk: Check max positions
            
            alt Risk Check Failed
                Risk-->>Controller: {valid: false, reason: "Max exposure exceeded"}
                Controller-->>Model: Signal rejected (risk)
            else Risk Check Passed
                Risk-->>Controller: {valid: true}
                
                %% Position Sizing
                Controller->>Sizer: calculate_size(signal, account)
                Sizer->>DB: Get account balance
                DB-->>Sizer: Balance, equity
                Sizer->>Sizer: Apply risk percentage
                Sizer->>Sizer: Apply max lot limits
                Sizer-->>Controller: lot_size = 0.05
                
                %% Build Order Request
                Controller->>Controller: Create TradeRequest<br/>{symbol, type, volume, sl, tp}
                
                %% Execute via Adapter
                Controller->>Adapter: execute_order(request)
                Adapter->>Adapter: Format for MT5 protocol
                Adapter->>Terminal: send_order(order_data)
                
                %% Send to MT5 via EA
                Terminal->>EA: JSON: {cmd: "ORDER",<br/>symbol, action, volume, sl, tp}
                EA->>MT5: OrderSend()
                
                alt Order Executed
                    MT5-->>EA: Ticket #12345
                    EA-->>Terminal: {status: "OK", ticket: 12345}
                    Terminal-->>Adapter: Execution result
                    Adapter-->>Controller: {success: true, ticket: 12345}
                    
                    %% Log Trade
                    Controller->>DB: INSERT INTO trades<br/>{ticket, symbol, type, volume, ...}
                    
                    %% Update Circuit Breaker
                    Controller->>CB: record_trade(trade)
                    
                    %% WebSocket Broadcast
                    Controller->>Controller: Broadcast trade event
                    Note over Controller: WebSocket /ws/trades
                    
                    Controller-->>Model: Order executed (ticket: 12345)
                    
                else Order Failed
                    MT5-->>EA: Error code
                    EA-->>Terminal: {status: "ERROR", code: 10019}
                    Terminal-->>Adapter: Execution error
                    Adapter-->>Controller: {success: false, error: "Insufficient margin"}
                    
                    Controller->>DB: Log failed order attempt
                    Controller-->>Model: Order failed
                end
            end
        end
    end
```

## Risk Management Checks

### Kill Switch
| Check | Trigger | Effect |
|-------|---------|--------|
| File-based | `/app/logs/kill_switch.flag` exists | All trading halted |
| Environment | `KILL_SWITCH_ACTIVE=true` | All trading halted |
| API trigger | `POST /api/trading/kill` | Creates flag file |
| Signal | SIGTERM/SIGINT | Graceful shutdown |

### Circuit Breaker
| Check | Configuration | Action |
|-------|---------------|--------|
| Daily loss limit | e.g., -5% | Halt trading for day |
| Weekly loss limit | e.g., -10% | Halt trading for week |
| Consecutive losses | e.g., 5 in a row | Halt and alert |
| Drawdown limit | e.g., -15% from peak | Halt trading |

### Risk Manager
| Validation | Description |
|------------|-------------|
| Max exposure | Total position size limit |
| Max positions | Maximum concurrent trades |
| Correlation | Limit correlated positions |
| Symbol exposure | Per-symbol limits |

### Position Sizing
| Method | Description |
|--------|-------------|
| Fixed percentage | Risk % of balance per trade |
| ATR-based | Size based on volatility |
| Max lot cap | Upper limit on lot size |
| Min lot floor | Minimum tradeable size |

## Order Flow Details

### TradeRequest Structure
```python
@dataclass
class TradeRequest:
    symbol: str          # "EURUSD"
    action: ActionType   # BUY, SELL
    volume: float        # Lot size
    price: float         # Entry price (0 for market)
    sl: float           # Stop loss
    tp: float           # Take profit
    magic: int          # EA magic number
    comment: str        # Trade comment
```

### MT5 EA Protocol
```json
// Order command
{
  "cmd": "ORDER",
  "symbol": "EURUSD",
  "action": 0,       // 0=BUY, 1=SELL
  "volume": 0.05,
  "sl": 1.0800,
  "tp": 1.0900,
  "magic": 123456,
  "comment": "model_v1.2.3"
}

// Response
{
  "status": "OK",
  "ticket": 12345678,
  "open_price": 1.0850,
  "open_time": 1704067200
}
```

## Safety Infrastructure

### Multi-Layer Protection
1. **Kill Switch** (Immediate halt - manual or automated)
2. **Circuit Breaker** (Automatic halt on loss thresholds)
3. **Risk Manager** (Pre-trade validation)
4. **Position Sizer** (Appropriate sizing)

### Emergency Stop Sequence
```mermaid
flowchart LR
    A[Kill Signal] --> B[Set Kill Flag]
    B --> C[Cancel Pending Orders]
    C --> D[Close All Positions]
    D --> E[Notify Operator]
    E --> F[Log Event]
```

## Trade Logging

| Table | Purpose |
|-------|---------|
| `trades` | All executed trades |
| `orders` | Order attempts (success/fail) |
| `kill_switch_events` | Kill switch activations |
| `circuit_breaker_events` | Circuit breaker trips |

## Error Codes

| MT5 Error | Description | Handling |
|-----------|-------------|----------|
| 10004 | Requote | Retry with new price |
| 10006 | Request rejected | Log and notify |
| 10014 | Invalid volume | Adjust to limits |
| 10019 | Not enough money | Reduce size or skip |
| 10025 | Server busy | Retry with backoff |

## Assumptions
- **None** - All execution flows verified in codebase
