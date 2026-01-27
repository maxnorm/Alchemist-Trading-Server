---
name: EA-to-Server Ping Keepalive Implementation
overview: Implement periodic ping messages from EA to server to keep connection alive, with proper protocol handling to avoid conflicts with server requests.
todos:
  - id: ea-ping-function
    content: Add send_ping_to_server() function to EA that sends ACCOUNT_INFO request and waits for response with timeout
    status: pending
  - id: ea-ping-loop
    content: Modify start_listenning() loop to send periodic pings (every 15s) before entering receive_msg()
    status: pending
  - id: ea-ping-timeout
    content: Implement ping response timeout handling (5 seconds max) in send_ping_to_server()
    status: pending
  - id: ea-ping-error-handling
    content: Add error handling for ping failures (reconnection logic) in start_listenning()
    status: pending
  - id: test-ping-flow
    content: "Test ping flow: EA sends ping, server responds, EA continues normally"
    status: pending
  - id: test-ping-order-interaction
    content: Test order execution after ping to verify no protocol conflicts
    status: pending
  - id: test-ping-failure
    content: "Test ping failure scenario: EA detects failure and reconnects"
    status: pending
isProject: false
---

# EA-to-Server Ping Keepalive Implementation Plan

## Problem Analysis

### Current Architecture

**EA Side:**

- EA blocks on `receive_msg()` waiting for server requests
- `receive_msg()` uses `SocketRead()` with 1-second timeout per read
- EA processes requests and sends responses synchronously
- No mechanism to send unsolicited messages to server

**Server Side:**

- Server sends requests via `send_msg()` and waits for responses via `get_response()`
- `get_response()` calls `_receive_response()` which blocks on `socket.recv()`
- Server expects responses to match requests it sent
- No mechanism to handle unsolicited messages from EA

### Critical Issue: Protocol Conflict

If EA sends an unsolicited ping while:

- Server is waiting for order response → Server receives ping instead of order response → Protocol mismatch
- EA is waiting for server request → EA receives ping response instead of server request → Protocol mismatch

### Solution Strategy

**Key Insight:** EA should only send pings when it's idle (waiting for server requests), not when processing requests or when server is waiting for responses.

## Implementation Approach

### Option 1: Pre-Receive Ping (Recommended)

Send ping **before** entering the blocking `receive_msg()` call. This ensures:

- EA is idle (not processing a request)
- Server is not waiting for a response (EA hasn't sent one)
- Ping happens at predictable times
- No interference with request/response flow

### Option 2: Non-Blocking Receive with Timeout

Modify EA's receive loop to use non-blocking receive with timeout, allowing periodic ping checks. More complex but more flexible.

**Decision: Use Option 1** - Simpler, safer, and sufficient for keepalive needs.

## Detailed Implementation

### 1. EA Changes: `src/utils/MT5-EA/EAs/mt5_trading_operation.mq5`

#### Add Ping Function

Add before `start_listenning()`:

```mql5
// Send a ping/keepalive message to the server
bool send_ping_to_server()
   {
      Print("[EA] send_ping_to_server: Sending keepalive ping to server...");
      
      // Create ping message (ACCOUNT_INFO request acts as ping)
      CJAVal ping_msg;
      ping_msg["request"] = ACCOUNT_INFOS;
      
      // Send ping
      send_msg(socket, ping_msg);
      
      // Wait for response with timeout
      // Use a shorter timeout for ping (5 seconds max)
      Print("[EA] send_ping_to_server: Waiting for ping response...");
      datetime ping_start = TimeCurrent();
      const int PING_TIMEOUT_SECONDS = 5;
      
      CJAVal response;
      bool got_response = false;
      
      // Try to receive response with timeout
      // We'll use a modified receive that times out faster
      string result = "";
      int consecutive_zeros = 0;
      const int MAX_PING_TIMEOUTS = 5; // 5 seconds max
      
      while (!got_response && (TimeCurrent() - ping_start) < PING_TIMEOUT_SECONDS)
      {
         uchar c[1];
         uint rsp_len = SocketRead(socket, c, 1, 1000);
         
         if (rsp_len > 0)
         {
            result += CharArrayToString(c, 0, (int)rsp_len);
            if (CharArrayToString(c, 0, (int)rsp_len) == "\n")
            {
               StringReplace(result, "\n", "");
               if (response.Deserialize(result))
               {
                  got_response = true;
               }
            }
         }
         else if (rsp_len == 0)
         {
            consecutive_zeros++;
            if (consecutive_zeros >= MAX_PING_TIMEOUTS)
            {
               Print("[EA] send_ping_to_server: Ping timeout - no response received");
               return false;
            }
         }
         else
         {
            int error = GetLastError();
            if (error == 10054 || error == 10053 || error == 10058)
            {
               PrintFormat("[EA] send_ping_to_server: Connection error: %d", error);
               return false;
            }
         }
      }
      
      if (!got_response)
      {
         Print("[EA] send_ping_to_server: Ping timeout - no response within timeout period");
         return false;
      }
      
      // Check if we got a valid response
      if (response.HasKey("_disconnected"))
      {
         Print("[EA] send_ping_to_server: ERROR - Disconnection detected during ping!");
         return false;
      }
      
      // Check if response has account info (indicates successful ping)
      if (response.HasKey("currency") || response.HasKey("balance"))
      {
         Print("[EA] send_ping_to_server: Ping successful - server responded with account info");
         return true;
      }
      
      Print("[EA] send_ping_to_server: WARNING - Ping response unexpected format");
      return false;
   }
```

#### Modify `start_listenning()` Loop

Replace the health check section (lines 233-252) with ping logic:

```mql5
datetime last_ping = 0;
const int PING_INTERVAL = 15;  // Send ping every 15 seconds

while (true)
{
   datetime now = TimeCurrent();
   
   // Send periodic ping to server BEFORE waiting for server requests
   // This keeps connection alive and verifies server is responsive
   if (now - last_ping >= PING_INTERVAL)
   {
      Print("[EA] start_listenning: Sending keepalive ping to server...");
      if (!send_ping_to_server())
      {
         Print("[EA] start_listenning: Ping failed - connection may be lost!");
         if (!SocketIsConnected(socket))
         {
            Print("[EA] start_listenning: Socket disconnected! Attempting reconnect...");
            if (!reconnect())
            {
               Print("[EA] start_listenning: Reconnection failed. EA will exit.");
               ExpertRemove();
               return;
            }
            reconnect_attempts = 0;
            last_ping = now;
            continue;
         }
         // Socket appears connected but ping failed - might be temporary
         Print("[EA] start_listenning: Ping failed but socket appears connected. Continuing...");
      }
      else
      {
         Print("[EA] start_listenning: Keepalive ping successful - connection is alive.");
      }
      last_ping = now;
   }
   
   // Now wait for server requests (normal operation)
   PrintFormat("[EA] Waiting for message from server (request #%d)...", request_count);
   CJAVal infos = receive_msg(socket);
   // ... rest of loop unchanged
}
```

### 2. Server-Side: No Changes Required

The server already handles ACCOUNT_INFO requests (code 100) in `handle_request()`. When EA sends a ping:

- Server receives `{"request": 100}`
- Server calls `handle_request()` which processes ACCOUNT_INFO
- Server responds with account info
- EA receives response

**No server code changes needed** - existing request handling works for pings.

### 3. Protocol Flow

```
Normal Flow (No Ping):
  Server → EA: {"request": 101} (order)
  EA → Server: {"return_code": 10009, ...} (response)

Ping Flow (EA Initiated):
  EA → Server: {"request": 100} (ping)
  Server → EA: {"currency": "USD", "balance": 10000, ...} (response)
  [EA continues to wait for server requests]

Order Flow (After Ping):
  Server → EA: {"request": 101} (order)
  EA → Server: {"return_code": 10009, ...} (response)
```

### 4. Timing Considerations

**Ping Interval: 15 seconds**

- Frequent enough to keep connection alive
- Not too frequent to avoid network overhead
- Matches server heartbeat interval (15s)

**Ping Timeout: 5 seconds**

- Fast failure detection
- Doesn't block too long if server is unresponsive
- Allows EA to continue or reconnect quickly

**Ping Position: Before `receive_msg()`**

- EA is idle (not processing request)
- Server is not waiting for response
- No protocol conflicts

## Potential Issues & Mitigations

### Issue 1: Race Condition

**Problem:** Server sends request right after EA sends ping

**Mitigation:**

- EA sends ping, waits for response, then enters `receive_msg()`
- Server's request will be received in the next `receive_msg()` call
- No conflict because ping completes before EA waits for next message

### Issue 2: Server Waiting for Response

**Problem:** Server sends order, EA sends ping before responding

**Mitigation:**

- EA only sends ping when idle (before `receive_msg()`)
- If EA is processing a request, it won't send ping
- Ping happens between requests, not during request processing

### Issue 3: Ping Response Interference

**Problem:** EA receives ping response when expecting server request

**Mitigation:**

- EA sends ping and waits for response with timeout
- After receiving ping response, EA enters `receive_msg()` for next server request
- Clear separation: ping completes, then wait for server request

### Issue 4: Server Receives Ping During Order Wait

**Problem:** Server waiting for order response, EA sends ping

**Mitigation:**

- EA only sends ping when idle (before `receive_msg()`)
- If server sent an order, EA is processing it (not idle)
- EA won't send ping while processing a request
- **However:** If server sends order right after EA sends ping, server might receive ping response instead of order response

**Additional Mitigation Needed:**

- Server's `get_response()` should handle unexpected messages
- If server receives ACCOUNT_INFO response when expecting order response, it should:
  - Log the unexpected message
  - Continue waiting for the actual order response
  - Or handle the ping and retry the order request

**Better Solution:** Make server's `_receive_response()` smarter to handle unsolicited pings.

## Enhanced Server Handling (Optional but Recommended)

### Server-Side Enhancement: Handle Unsolicited Pings

**File:** `src/trading_server/src/mt5_connection/conn.py`

Add logic to `_receive_response()` to handle unsolicited ACCOUNT_INFO responses:

```python
async def _receive_response(self, expected_request_type=None):
    """
    Receive response, optionally filtering by expected request type
    """
    while True:
        raw_data = await loop.run_in_executor(None, self.__socket.recv, 1024)
        # ... parse message ...
        
        # If we're expecting a specific response type and got something else
        if expected_request_type:
            if parsed.get("request") == Terminal.ACCOUNT_INFO.value:
                # This is a ping response - handle it and continue waiting
                self.__last_recv_ts = time.time()  # Update last receive time
                continue  # Keep waiting for expected response
        
        return parsed
```

**However:** This requires tracking what request was sent, which adds complexity.

**Simpler Approach:** Accept that pings might occasionally interfere, but they're rare because:

- EA only pings when idle (every 15 seconds)
- Most of the time, EA is waiting for requests (not processing)
- Server requests are infrequent compared to ping interval
- If interference occurs, server can retry the request

## Testing Strategy

### Test Cases

1. **Normal Ping Flow**

   - EA sends ping → Server responds → EA continues waiting
   - Verify connection stays alive

2. **Ping During Idle**

   - EA idle for 15+ seconds → EA sends ping → Server responds
   - Verify no interference

3. **Order After Ping**

   - EA sends ping → Server responds → Server sends order → EA processes
   - Verify order works correctly

4. **Ping Failure**

   - EA sends ping → No response → EA detects failure → EA reconnects
   - Verify reconnection works

5. **Concurrent Operations**

   - Server sends order → EA processes → EA sends ping (shouldn't happen, but test)
   - Verify no protocol corruption

## Files to Modify

1. **`src/utils/MT5-EA/EAs/mt5_trading_operation.mq5`**

   - Add `send_ping_to_server()` function
   - Modify `start_listenning()` to send periodic pings
   - Change `HEALTH_CHECK_INTERVAL` to `PING_INTERVAL` (15s)

2. **No server-side changes required** (existing ACCOUNT_INFO handling works)

## Benefits

1. **Connection Keepalive**: Regular pings prevent timeout
2. **Early Failure Detection**: Ping failures detected within 5 seconds
3. **Bidirectional Health Checks**: Both EA and server verify connection
4. **No Server Changes**: Uses existing request/response mechanism
5. **Simple Implementation**: Minimal code changes

## Risks & Considerations

1. **Protocol Interference**: Low risk due to ping timing (only when EA idle)
2. **Network Overhead**: Minimal (ping every 15s, small JSON message)
3. **EA Complexity**: Slight increase in EA code complexity
4. **Testing Required**: Need to verify no edge cases cause issues

## Alternative: Simpler Approach

If the ping implementation is too complex, we could:

- Keep server-side heartbeat (already implemented)
- Improve TCP keep-alive settings (already done)
- Add connection health check before orders (already done)
- Skip EA-side ping for now

**Recommendation:** Implement EA ping as it provides the most reliable keepalive mechanism.