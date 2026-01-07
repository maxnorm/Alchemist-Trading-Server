# Browser Error Analysis

This document maps each browser console error to its source in the codebase.

## Summary

The dashboard is experiencing two main types of errors:
1. **WebSocket Connection Failures** - Frontend trying to connect to non-existent generic `/ws` endpoint
2. **HTTP 500 Errors** - Backend API endpoints returning internal server errors

---

## 1. WebSocket Connection Errors

### Error: `WebSocket connection to 'ws://localhost/ws' failed`

**Source Location:**
- **File**: `src/dashboard/src/services/websocket.ts`
- **Line**: 31
- **Code**:
```31:31:src/dashboard/src/services/websocket.ts
      this.ws = new WebSocket(WS_BASE_URL)
```

**Root Cause:**
- The frontend WebSocket service connects to `WS_BASE_URL` which resolves to `ws://localhost/ws`
- The backend **does not have** a generic `/ws` endpoint
- The backend has specific WebSocket endpoints like:
  - `/ws/positions`
  - `/ws/training`
  - `/ws/optuna`
  - `/ws/metrics`
  - `/ws/alerts`
  - `/ws/performance`
  - `/ws/trades`
  - `/ws/models`
  - `/ws/accounts/mt5`

**Call Chain:**
1. `WebSocketContext.tsx:17` - Calls `wsService.connect()` on mount
2. `websocket.ts:24` - `connect()` method creates new WebSocket
3. `websocket.ts:31` - Attempts connection to `WS_BASE_URL` (`ws://localhost/ws`)

**Related Errors:**
- `websocket.ts:50` - `ws.onerror` handler logs the error
- `websocket.ts:55` - `ws.onclose` handler logs disconnection
- `websocket.ts:73` - Reconnection logic attempts to reconnect with exponential backoff

### Error: `WebSocket error: Event {...}`

**Source Location:**
- **File**: `src/dashboard/src/services/websocket.ts`
- **Line**: 49-52
- **Code**:
```49:52:src/dashboard/src/services/websocket.ts
      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        this.isConnecting = false
      }
```

**Triggered By:**
- Failed WebSocket connection attempt (line 31)

### Error: `WebSocket disconnected`

**Source Location:**
- **File**: `src/dashboard/src/services/websocket.ts`
- **Line**: 54-60
- **Code**:
```54:60:src/dashboard/src/services/websocket.ts
      this.ws.onclose = () => {
        console.log('WebSocket disconnected')
        this.isConnecting = false
        if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect()
        }
      }
```

**Triggered By:**
- Connection failure triggers `onclose` event

### Error: `Reconnecting in Xms (attempt N)`

**Source Location:**
- **File**: `src/dashboard/src/services/websocket.ts`
- **Line**: 70-79
- **Code**:
```70:79:src/dashboard/src/services/websocket.ts
  private scheduleReconnect(): void {
    this.reconnectAttempts++
    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000)
    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
    setTimeout(() => {
      if (this.shouldReconnect) {
        this.connect()
      }
    }, delay)
  }
```

**Triggered By:**
- `onclose` handler calls `scheduleReconnect()` when reconnection is enabled

### Error: `subscribe @ websocket.ts:103`

**Source Location:**
- **File**: `src/dashboard/src/services/websocket.ts`
- **Line**: 95-104
- **Code**:
```95:104:src/dashboard/src/services/websocket.ts
  subscribe(channel: string, handler: MessageHandler): () => void {
    if (!this.subscribers.has(channel)) {
      this.subscribers.set(channel, new Set())
    }
    this.subscribers.get(channel)!.add(handler)

    // Ensure connection is open
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.connect()
    }
```

**Call Chain:**
1. `useTradingPositions.ts:11` - Calls `subscribe(WS_CHANNELS.tradingPositions, ...)`
2. `WebSocketContext.tsx:36` - Calls `wsService.subscribe(channel, handler)`
3. `websocket.ts:103` - Attempts to connect if not already connected

---

## 2. HTTP 500 Errors

All API errors follow the same pattern: the frontend makes a request, and the backend returns a 500 Internal Server Error.

### Error: `GET http://localhost/api/v1/models 500 (Internal Server Error)`

**Frontend Source:**
- **File**: `src/dashboard/src/services/api.ts`
- **Line**: 133-143
- **Code**:
```133:143:src/dashboard/src/services/api.ts
  async getModels(): Promise<Model[]> {
    const response = await this.client.get<{ models: Model[]; total: number } | Model[]>(API_ENDPOINTS.models)
    // Handle both response formats: { models: [], total: number } or Model[]
    if (Array.isArray(response.data)) {
      return response.data
    }
    if (response.data && typeof response.data === 'object' && 'models' in response.data) {
      return Array.isArray(response.data.models) ? response.data.models : []
    }
    return []
  }
```

**Call Chain:**
1. `useDashboardStats.ts:44` - `queryFn: () => api.getModels()`
2. `api.ts:134` - Makes GET request to `/api/v1/models`

**Backend Source:**
- **File**: `src/api/src/routers/models.py`
- **Line**: 23-36
- **Code**:
```23:36:src/api/src/routers/models.py
@router.get("", response_model=ModelListResponse)
async def list_models(
    stage: Optional[str] = Query(None, description="Filter by stage"),
    experiment_id: Optional[int] = Query(None, description="Filter by experiment ID"),
    db: Session = Depends(get_db),
):
    """List all models with optional filters"""
    try:
        models = model_service.get_all_models(
            db, stage=stage, experiment_id=experiment_id
        )
        return ModelListResponse(models=models, total=len(models))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch models: {str(e)}")
```

**Possible Causes:**
- Database connection failure
- Exception in `model_service.get_all_models()`
- Missing database tables or schema issues

---

### Error: `GET http://localhost/api/v1/experiments 500 (Internal Server Error)`

**Frontend Source:**
- **File**: `src/dashboard/src/services/api.ts`
- **Line**: 70-73
- **Code**:
```70:73:src/dashboard/src/services/api.ts
  async getExperiments(): Promise<Experiment[]> {
    const response = await this.client.get<Experiment[]>(API_ENDPOINTS.experiments)
    return Array.isArray(response.data) ? response.data : []
  }
```

**Call Chain:**
1. `useDashboardStats.ts:49` - `queryFn: () => api.getExperiments()`
2. `api.ts:71` - Makes GET request to `/api/v1/experiments`

**Backend Source:**
- **File**: `src/api/src/routers/experiments.py`
- **Line**: 20-32
- **Code**:
```20:32:src/api/src/routers/experiments.py
@router.get("/experiments", response_model=ExperimentListResponse)
async def list_experiments(
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    """List all experiments"""
    try:
        experiments = experiment_service.get_all_experiments(db, status=status)
        return ExperimentListResponse(experiments=experiments, total=len(experiments))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch experiments: {str(e)}"
        )
```

**Possible Causes:**
- Database connection failure
- Exception in `experiment_service.get_all_experiments()`
- Missing database tables or schema issues

---

### Error: `GET http://localhost/api/v1/features 500 (Internal Server Error)`

**Frontend Source:**
- **File**: `src/dashboard/src/services/api.ts`
- **Line**: 59-62
- **Code**:
```59:62:src/dashboard/src/services/api.ts
  async getFeatures(filters?: FeatureFilters): Promise<Feature[]> {
    const response = await this.client.get<Feature[]>(API_ENDPOINTS.features, { params: filters })
    return Array.isArray(response.data) ? response.data : []
  }
```

**Call Chain:**
1. `useDashboardStats.ts:61` - `queryFn: () => api.getFeatures()`
2. `api.ts:60` - Makes GET request to `/api/v1/features`

**Backend Source:**
- **File**: `src/api/src/routers/features.py`
- **Line**: 19-34 (approximate, based on search results)
- The endpoint likely follows the same pattern as others with try/except returning 500 on error

**Possible Causes:**
- Database connection failure
- Exception in feature service
- Missing database tables or schema issues

---

### Error: `GET http://localhost/api/v1/accounts/mt5 500 (Internal Server Error)`

**Frontend Source:**
- **File**: `src/dashboard/src/services/api.ts`
- **Line**: 230-233
- **Code**:
```230:233:src/dashboard/src/services/api.ts
  async getMT5Accounts(): Promise<MT5Account[]> {
    const response = await this.client.get<MT5Account[]>(API_ENDPOINTS.mt5Accounts)
    return Array.isArray(response.data) ? response.data : []
  }
```

**Call Chain:**
1. `useDashboardStats.ts:66` - `queryFn: () => api.getMT5Accounts()`
2. `api.ts:231` - Makes GET request to `/api/v1/accounts/mt5`

**Backend Source:**
- **File**: `src/api/src/routers/mt5_accounts.py`
- **Line**: 45-56
- **Code**:
```45:56:src/api/src/routers/mt5_accounts.py
@router.get("", response_model=MT5AccountListResponse)
async def list_accounts(
    connected_only: bool = Query(False, description="Show only connected accounts"),
    account_type: Optional[str] = Query(None, description="Filter by account type (demo/live)"),
    db: Session = Depends(get_db),
):
    """List all MT5 accounts"""
    try:
        accounts = get_all_accounts(db, connected_only=connected_only, account_type=account_type)
        return MT5AccountListResponse(accounts=accounts, total=len(accounts))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list accounts: {str(e)}")
```

**Possible Causes:**
- Database connection failure
- Exception in `get_all_accounts()`
- Missing database tables or schema issues

---

## Architecture Mismatch: WebSocket Design

### Frontend Design
The frontend WebSocket service (`websocket.ts`) is designed to:
1. Connect to a **single WebSocket endpoint** (`WS_BASE_URL`)
2. Subscribe to **multiple channels** via the same connection
3. Route messages based on channel names in the message payload

### Backend Design
The backend WebSocket implementation:
1. Has **separate WebSocket endpoints** for each channel type
2. Each endpoint connects to a specific channel in the manager
3. Messages are broadcast to all connections in a channel

### The Problem
- Frontend expects: `ws://localhost/ws` with channel-based routing
- Backend provides: `ws://localhost/ws/positions`, `ws://localhost/ws/training`, etc.

### Solution Options

**Option 1: Add Generic WebSocket Endpoint (Recommended)**
- Add a generic `/ws` endpoint in the backend that accepts channel subscriptions via messages
- Modify the WebSocket manager to handle channel subscriptions from client messages

**Option 2: Update Frontend to Use Multiple Connections**
- Modify the frontend to create separate WebSocket connections for each channel
- Update `WebSocketContext` to manage multiple connections

**Option 3: Use a WebSocket Gateway/Proxy**
- Add a WebSocket gateway that accepts a single connection and routes to backend endpoints

---

## Recommendations

1. **Immediate Fix**: Check backend logs to identify the root cause of 500 errors (likely database connection issues)

2. **WebSocket Fix**: Implement Option 1 (generic endpoint) or Option 2 (multiple connections) to align frontend and backend architectures

3. **Error Handling**: Add better error messages in the backend to help diagnose 500 errors

4. **Health Checks**: Verify database connectivity and API health before dashboard loads
