//+------------------------------------------------------------------+
//|                                        mt5_trading_operation.mq5 |
//|                                                 Maxime Normandin |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Maxime Normandin"
#property link      "https://www.mql5.com"
#property version   "1.00"

#include <JAson.mqh>

input string ip = "127.0.0.1";
input int port = 1234;

string separator = "|";

string auth_code = "2";
string successful_auth_code = "0";
string deconnection_code = "-2";

int socket;
string terminal_id;
//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
//---
   socket = SocketCreate();
   int elapsedSecond = 0;
   
   if (socket!=INVALID_HANDLE) 
   {
      if(SocketConnect(socket, ip, port, 1000)) 
      {
         Print("Established connection to ",ip,":",port);
         if (auth()) 
         {
            Print("Successful authentification to the server");
            start_listenning();
         }
         else 
         {
            Print("Failed authentification to the server");
            Print("EA Closing");
            return(INIT_FAILED);
         }
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

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
//---
   send_msg(deconnection_code);
   SocketClose(socket);
  }
  

//+------------------------------------------------------------------+
//| Functions                                                        |
//+------------------------------------------------------------------+
   
// Authentication to the server as a terminal
bool auth()
   {
      send_msg(auth_code);
      string msg = receive_msg();
      string msg_infos[];
      parse_msg(msg, msg_infos);
      Print(msg_infos[0]);
      Print(msg_infos[1]);
      if (msg_infos[0] == successful_auth_code)
      {
         terminal_id = msg_infos[1];
         return true;
      }
      return false;
   }
   
// Listen from the server
void start_listenning()
   {
      while (true)
      {
         string msg = receive_msg();
      }
   }
   
 // Send a message to the server
void send_msg(string& msg)
   {
      string request = msg + "\n";
      char req[];
      int len=StringToCharArray(request, req)-1;
      SocketSend(socket,req,len);
   }

// Receive message from server
string receive_msg()
   {
      string result = "";
      bool line_complete = false;
      
      while (!line_complete)
      {
         char c[1];
         int rsp_len;
         
         rsp_len = SocketRead(socket, c, 1, 1000);
         
         if (rsp_len > 0)
         {
            result += CharArrayToString(c, 0, rsp_len);
            
            if (CharArrayToString(c, 0, rsp_len) == "\n")
            {
               StringReplace(result, "\n", "");
               line_complete = true;   
            }
         }
      }
      
      return result;
   }
   
void parse_msg(const string msg, string& split_msg[])
   {
      StringSplit(msg, StringGetCharacter(separator,0), split_msg);
   }