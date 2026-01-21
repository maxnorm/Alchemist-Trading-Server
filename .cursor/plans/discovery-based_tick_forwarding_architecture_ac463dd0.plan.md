---
name: Discovery-based tick forwarding architecture
overview: Refactor tick streaming so discovery service consumes all messages from broker and forwards them to registered streamers via queues, removing SUB sockets from streamers entirely. This enables auto-registration for all symbols while ensuring streamers receive all their ticks.
todos: []
isProject: false
---

# Discovery-Based Tick Forwarding Architecture

## Current Architecture Problem

- Discovery service and streamers both subscribe to broker (PUB/SUB)
- ZeroMQ distributes messages in round-robin, causing discovery to consume messages
- Streamers miss ticks when discovery receives them

## New Architecture

Discovery service acts as a central message router:

- Discovery subscribes to `""` (all topics) and consumes ALL messages
- Discovery forwards each tick to the appropriate registered streamer via a queue
- Streamers no longer use SUB sockets - they read from internal queues
- Enables auto-registration for all symbols without message loss

## Architecture Flow

```
EA (PUSH) → Broker (PUB) → Discovery (SUB to "") → Queue per Symbol → Streamer (reads from queue)
```

## Implementation Plan

### 1. Add Queue-Based Message Reading to ZeroMQTickStreamer

**File**: `src/trading_server/src/mt5_connection/zeromq_tick_streamer.py`

- Add a `queue.Queue` for receiving ticks from discovery
- Modify `_read_message()` to read from queue instead of SUB socket
- Add `put_tick()` method for discovery to push ticks
- Keep `receive_tick()` signature but change internal implementation

**Changes**:

```python
import queue

class ZeroMQTickStreamer:
    def __init__(self, ...):
        self._tick_queue = queue.Queue(maxsize=1000)  # Buffer for ticks from discovery
        # Remove zmq_conn dependency or keep for backward compatibility
    
    def put_tick(self, tick_data: dict):
        """Called by discovery service to forward a tick"""
        try:
            self._tick_queue.put_nowait(tick_data)
        except queue.Full:
            # Log warning, drop tick
            pass
    
    def _read_message(self):
        """Read from queue instead of SUB socket"""
        try:
            tick_timeout = float(os.getenv("TICK_STREAMING_TIMEOUT", "1.0"))
            return self._tick_queue.get(timeout=tick_timeout)
        except queue.Empty:
            raise TimeoutError("No tick available in queue")
```

### 2. Modify Discovery Service to Forward Ticks

**File**: `src/trading_server/src/infrastructure/connections/streamer_discovery_service.py`

- Remove socket closing logic after registration
- In `_discover_streamers()` loop, forward ticks to registered streamers
- Keep discovery running continuously to auto-register new symbols

**Changes**:

```python
def _discover_streamers(self):
    while self._running:
        # Receive message from broker
        parts = self._discovery_socket.recv_multipart(zmq.NOBLOCK)
        
        if len(parts) == 2:
            topic_bytes, message_bytes = parts
            topic = topic_bytes.decode('utf-8', errors='ignore')
            tick_data = json.loads(message_bytes.decode('utf-8'))
            symbol = tick_data.get("symbol") or topic
            
            # Check if registered
            with self._registration_lock:
                is_registered = symbol in self._registered_streamers
                
                if is_registered:
                    # Forward to registered streamer
                    streamer_info = self._registered_streamers[symbol]
                    streamer = streamer_info.get("streamer")
                    if streamer and hasattr(streamer, "put_tick"):
                        streamer.put_tick(tick_data)
                else:
                    # Auto-register new symbol
                    self._process_tick_message(tick_data, topic)
```

### 3. Remove SUB Socket Creation from Connection Manager

**File**: `src/trading_server/src/infrastructure/zeromq/zeromq_connection_manager.py`

- Modify `connect_streamer_by_symbol()` to NOT create SUB socket
- Create ZeroMQTickStreamer without ZeroMQConnection
- Pass None or a dummy connection object

**Changes**:

```python
def connect_streamer_by_symbol(self, symbol: str, ...):
    # Don't create SUB socket - streamer will receive from discovery queue
    # Create streamer without ZeroMQ connection
    from mt5_connection.zeromq_tick_streamer import ZeroMQTickStreamer
    from models.currency_pair import CurrencyPair
    
    pair = CurrencyPair(symbol, digits)
    # Pass None for zmq_conn - streamer uses queue instead
    streamer = ZeroMQTickStreamer(None, pair, db=db)
    return streamer
```

### 4. Update ZeroMQTickStreamer Constructor

**File**: `src/trading_server/src/mt5_connection/zeromq_tick_streamer.py`

- Make `zmq_conn` optional (can be None)
- Only use `zmq_conn` if provided (backward compatibility)
- Default to queue-based reading

**Changes**:

```python
def __init__(self, zmq_conn: Optional[ZeroMQConnection], ...):
    self._zmq_conn = zmq_conn  # Can be None for discovery-based forwarding
    self._tick_queue = queue.Queue(maxsize=1000)
    
def _read_message(self):
    # If queue-based (zmq_conn is None), read from queue
    if self._zmq_conn is None:
        tick_timeout = float(os.getenv("TICK_STREAMING_TIMEOUT", "1.0"))
        return self._tick_queue.get(timeout=tick_timeout)
    else:
        # Legacy: read from SUB socket
        return asyncio.run(self._zmq_conn.get_response(timeout=tick_timeout))
```

### 5. Remove Thread Start from Discovery Registration

**File**: `src/trading_server/src/infrastructure/connections/streamer_discovery_service.py`

- In `_auto_register_streamer()`, still start the `receive_tick()` thread
- Thread will now read from queue instead of SUB socket
- Remove socket closing logic

### 6. Handle Initial Tick Processing

**File**: `src/trading_server/src/infrastructure/connections/streamer_discovery_service.py`

- After registration, forward the triggering tick to the streamer's queue
- Streamer's `receive_tick()` thread will process it

## Benefits

- Auto-registration works for all symbols
- No message loss - discovery forwards all ticks
- Streamers receive all their ticks via queue
- Discovery continues running for new symbol discovery
- Cleaner architecture - single point of message consumption

## Testing Considerations

- Verify queue doesn't fill up under high tick rates
- Ensure thread safety when discovery forwards ticks
- Test auto-registration of multiple symbols
- Verify no ticks are lost during registration
- Check performance with queue-based forwarding