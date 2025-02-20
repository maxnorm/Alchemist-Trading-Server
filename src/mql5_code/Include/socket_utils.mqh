//+------------------------------------------------------------------+
//|                                                 socket_utils.mqh |
//|                                                 Maxime Normandin |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Maxime Normandin"
#property link      "https://www.mql5.com"

#include <JAson.mqh>

// Send a message to the server
void send_msg(int s, CJAVal& json)
   {
      string out = "";
      json.Serialize(out);
      string request = out + "\n";
      char req[];
      int len=StringToCharArray(request, req);
      SocketSend(s,req,len);
   }
   
// Receive message from server
CJAVal receive_msg(int s)
   {
      string result = "";
      CJAVal json;
      bool line_complete = false;
      
      while (!line_complete)
      {
         char c[1];
         int rsp_len;
         
         rsp_len = SocketRead(s, c, 1, 1000);
        
         if (rsp_len > 0)
         {
            result += CharArrayToString(c, 0, rsp_len);
            
            if (CharArrayToString(c, 0, rsp_len) == "\n")
            {
               StringReplace(result, "\n", "");
               json.Deserialize(result);
               line_complete = true;   
            }
         }
      }
      
      return json;
   }