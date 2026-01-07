//+------------------------------------------------------------------+
//|                                            mt5-tick-streamer.mq5 |
//|                                                                  |
//| Expert Advisor for streaming real-time tick data (bid/ask prices)|
//| to the trading server via socket connection                      |
//+------------------------------------------------------------------+
#property copyright "Alchemist Capital Management"
#property link      "https://github.com/maxnorm/Alchemist-AI"
#property version   "1.00"

#include <JAson.mqh>
#include <socket_utils.mqh>

input string ip = "127.0.0.1";
input int port = 8080;
input long account_login = 0;
input string auth_token = "";

string separator = "|";

int auth_code = 1;
int successful_auth_code = 0;

int socket;

string symbol;
int digits;
//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
//---
   symbol = Symbol();
   digits = Digits();
   socket = SocketCreate();

   if (socket!=INVALID_HANDLE)
   {
      if(SocketConnect(socket, ip, port, 1000))
      {
         Print("Established connection to ",ip,":",port);
         if (!auth())
         {
            Print("Failed authentification to the server");
            Print("EA Closing");
            return(INIT_FAILED);
         }
         Print("Successful authentification to the server");
      }
      else
      {
         Print("Connection to ",ip,":",port," failed, error ",GetLastError());
         Print("EA Closing");
         return(INIT_FAILED);
      }
   }
   else
   {
      Print("Failed to create a socket, error ",GetLastError());
      Print("EA Closing");
      return(INIT_FAILED);
   }
//---
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
//---
   SocketClose(socket);
  }
//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
// Send each tick in the format [symbol, time, ask, bid]"
void OnTick()
  {
//---
   MqlTick tick;

   if(SymbolInfoTick(symbol, tick))
   {
      CJAVal json;
      json["symbol"] = symbol;
      
      // Use tick.time_msc (milliseconds since epoch) for accurate timestamp
      // This is more reliable than tick.time which can be stale
      long time_msc = tick.time_msc;
      datetime tick_time;
      int milliseconds;
      
      // If time_msc is valid (non-zero), use it; otherwise fallback to current time
      if(time_msc > 0)
      {
         // Convert milliseconds to datetime structure
         tick_time = (datetime)(time_msc / 1000);
         milliseconds = (int)(time_msc % 1000);
      }
      else
      {
         // Fallback: use current server time if tick.time_msc is invalid
         tick_time = TimeCurrent();
         milliseconds = 0;
      }
      
      // Format timestamp with milliseconds: "YYYY.MM.DD HH:MM:SS.mmm"
      string time_str = TimeToString(tick_time, TIME_DATE|TIME_SECONDS);
      json["date_time"] = StringFormat("%s.%03d", time_str, milliseconds);
      json["ask"] = tick.ask;
      json["bid"] = tick.bid;

      send_msg(socket, json, false);
   }
   else
   {
      Print("SymbolInfoTick() failed, error = ",GetLastError());
   }
  }
//+------------------------------------------------------------------+

// Authentication to the server as a terminal
bool auth()
   {
      CJAVal json;
      json["auth_code"] = auth_code;
      json["symbol"] = symbol;
      json["digits"] = digits;
      // If account_login input is not set, fall back to terminal login
      long login = account_login > 0 ? account_login : AccountInfoInteger(ACCOUNT_LOGIN);
      json["login"] = login;
      json["auth_token"] = auth_token;

      send_msg(socket, json, false);
      CJAVal msg = receive_msg(socket);
      if (msg["auth_status"] == successful_auth_code)
      {
         return true;
      }
      return false;
   }