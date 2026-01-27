//+------------------------------------------------------------------------------------------------+
//| mt5_zeromq_streamer.mq5                                                                       |
//| ZeroMQ-based tick streamer EA                                                                 |
//+------------------------------------------------------------------------------------------------+
#property copyright "Alchemist Capital Management"
#property link      "https://github.com/maxnorm/Alchemist-AI"
#property version   "2.00"

#include <Zmq/Zmq.mqh>
#include <JAson.mqh>

input string broker_host = "127.0.0.1";
input int broker_port = 5557;
input string token = "";

Context context;
Socket pushSocket(context, ZMQ_PUSH);

string symbol;
int digits;
int tick_count = 0;  // Counter for debugging
bool debug_logging = true;  // Enable/disable debug logs

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   symbol = Symbol();
   digits = Digits();

   string broker_endpoint = StringFormat("tcp://%s:%d", broker_host, broker_port);
   if(!pushSocket.connect(broker_endpoint))
     {
      PrintFormat("Failed to connect PUSH socket to broker at %s", broker_endpoint);
      return(INIT_FAILED);
     }

   PrintFormat("ZeroMQ PUSH socket connected to broker at %s", broker_endpoint);
   PrintFormat("[INFO] Streamer initialized for symbol: %s (digits: %d)", symbol, digits);
   
   // Validate token is provided
   if(StringLen(token) == 0)
     {
      Print("[WARNING] Streamer token is empty - connection may be rejected by server");
     }
   else
     {
      PrintFormat("[DEBUG] Token configured: YES (length: %d)", StringLen(token));
     }
   
   PrintFormat("[INFO] Debug logging: %s", debug_logging ? "ENABLED" : "DISABLED");
   PrintFormat("[INFO] Ready to stream ticks for %s", symbol);
   
   // Send a test/heartbeat message to verify connection
   // This helps diagnose if the connection is actually working
   CJAVal test_json;
   test_json["symbol"] = symbol;
   test_json["token"] = token;
   test_json["digits"] = digits;
   test_json["datetime"] = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);
   test_json["ask"] = SymbolInfoDouble(symbol, SYMBOL_ASK);
   test_json["bid"] = SymbolInfoDouble(symbol, SYMBOL_BID);
   test_json["heartbeat"] = true;  // Mark as heartbeat
   
   string test_message;
   test_json.Serialize(test_message);
   ZmqMsg test_msg(test_message);
   bool test_sent = pushSocket.send(test_msg);
   
   if(test_sent)
     {
      PrintFormat("[INFO] Heartbeat test message sent successfully - connection verified");
     }
   else
     {
      PrintFormat("[WARNING] Heartbeat test message failed to send, error: %d", GetLastError());
      PrintFormat("[WARNING] Connection may not be working - check broker_host and network");
     }
   
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   PrintFormat("[INFO] Streamer shutting down for %s", symbol);
   PrintFormat("[INFO] Total ticks processed: %d", tick_count);
   string broker_endpoint = StringFormat("tcp://%s:%d", broker_host, broker_port);
   pushSocket.disconnect(broker_endpoint);
   PrintFormat("[INFO] ZeroMQ PUSH socket disconnected from broker at %s", broker_endpoint);
  }

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   // Log that OnTick() was called (ALWAYS log first 10, then every 100th)
   static int on_tick_call_count = 0;
   on_tick_call_count++;
   if(on_tick_call_count <= 10 || on_tick_call_count % 100 == 0)
     {
      PrintFormat("[DEBUG] OnTick() called #%d for %s", on_tick_call_count, symbol);
     }
   
   MqlTick tick;
   bool tick_ok = SymbolInfoTick(symbol, tick);
   
   // Log SymbolInfoTick result for debugging
   if(!tick_ok && (on_tick_call_count <= 10 || on_tick_call_count % 100 == 0))
     {
      int error_code = GetLastError();
      PrintFormat("[ERROR] SymbolInfoTick() failed for %s, error = %d (OnTick call #%d)", 
                 symbol, error_code, on_tick_call_count);
     }
   
   if(tick_ok)
     {
      CJAVal json;
      json["symbol"] = symbol;
      json["token"] = token;  // Include authentication token
      json["digits"] = digits;  // Include digits for accurate pip calculation

      long time_msc = tick.time_msc;
      datetime tick_time;
      int milliseconds;
      if(time_msc > 0)
        {
         tick_time = (datetime)(time_msc / 1000);
         milliseconds = (int)(time_msc % 1000);
        }
      else
        {
         tick_time = TimeCurrent();
         milliseconds = 0;
        }

      string time_str = TimeToString(tick_time, TIME_DATE|TIME_SECONDS);
      json["datetime"] = StringFormat("%s.%03d", time_str, milliseconds);
      json["ask"] = tick.ask;
      json["bid"] = tick.bid;

      string message;
      json.Serialize(message);
      
      // Debug logging - ALWAYS log first 10 ticks
      tick_count++;
      if(tick_count <= 10 || tick_count % 100 == 0)
        {
         PrintFormat("[DEBUG] Tick #%d: Symbol=%s, Message length=%d, bid=%.5f, ask=%.5f", 
                    tick_count, symbol, StringLen(message), tick.bid, tick.ask);
         // Log message preview (first 150 chars)
         string preview = StringSubstr(message, 0, 150);
         PrintFormat("[DEBUG] Message preview: %s", preview);
        }
      
      // Validate message is not empty before sending
      if(StringLen(message) == 0)
        {
         PrintFormat("[ERROR] Attempted to send empty message for %s (tick #%d)", 
                    symbol, tick_count);
         return;  // Skip empty messages
        }
      
      // Validate symbol is not empty
      if(StringLen(symbol) == 0)
        {
         PrintFormat("[ERROR] Symbol is empty (tick #%d)", tick_count);
         return;
        }

      // Send message to broker via PUSH socket
      // Broker will extract symbol from JSON and republish with topic
      // We can send as single message (broker handles topic extraction)
      ZmqMsg msg(message);
      
      // ALWAYS log send attempts for first 10 ticks
      if(tick_count <= 10)
        {
         PrintFormat("[DEBUG] Attempting to send tick #%d to broker (length: %d)", 
                    tick_count, StringLen(message));
        }
      
      bool msg_sent = pushSocket.send(msg);
      if(!msg_sent)
        {
         int send_error = GetLastError();
         PrintFormat("[ERROR] Failed to send message for '%s' (tick #%d), error: %d", 
                    symbol, tick_count, send_error);
         PrintFormat("[ERROR] Socket state check - connection may be lost");
         return;
        }
      
      // ALWAYS log successful sends for first 10 ticks
      if(tick_count <= 10 || tick_count % 100 == 0)
        {
         PrintFormat("[DEBUG] ✓ Message sent successfully to broker for '%s' (tick #%d, length: %d)", 
                    symbol, tick_count, StringLen(message));
        }
     }
   else
     {
      // This error is already logged above, but keep this for completeness
      // (The error logging was moved up to catch it earlier)
     }
  }
