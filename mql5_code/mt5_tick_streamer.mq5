//+------------------------------------------------------------------+
//|                                                 python_conn2.mq5 |
//|                                                 Maxime Normandin |
//|                                                                  |
//+------------------------------------------------------------------+
#property copyright "Maxime Normandin"
#property link      ""
#property version   "1.00"

input string ip = "127.0.0.1";
input int port = 1234;

int Socket;
//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
//---
   Socket = SocketCreate();
   if (Socket!=INVALID_HANDLE) 
   {
      if(SocketConnect(Socket, ip, port, 1000)) 
      {
         Print("Established connection to ",ip,":",port);
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
   SocketClose(Socket);
  }
//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
//---
   string symbol = Symbol();
   MqlTick tick;
    
   if(SymbolInfoTick(symbol, tick))
   {
      string request = StringFormat(
         "%s|%s|%s|%s",
         symbol, TimeToString(tick.time,TIME_DATE|TIME_SECONDS), DoubleToString(tick.ask,5), DoubleToString(tick.bid,5)
      );
      Print(request);
      
      char req[];
      int len=StringToCharArray(request, req)-1;
      SocketSend(Socket,req,len);
      
   } 
   else 
   {
      Print("SymbolInfoTick() failed, error = ",GetLastError());
   }
  }
//+------------------------------------------------------------------+
