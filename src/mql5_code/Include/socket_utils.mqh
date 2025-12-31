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
      uchar req[];
      int len = StringToCharArray(request, req);
      if (len > 0)
      {
         PrintFormat("[EA] send_msg: Sending message (%d bytes): %s", len, out);
         uint sent = SocketSend(s, req, (uint)len);
         if (sent > 0)
         {
            PrintFormat("[EA] send_msg: Successfully sent %u bytes", sent);
         }
         else
         {
            PrintFormat("[EA] send_msg: ERROR - Failed to send message. Error: %d", GetLastError());
         }
      }
      else
      {
         Print("[EA] send_msg: ERROR - Message length is 0");
      }
   }
   
// Receive message from server
CJAVal receive_msg(int s)
   {
      Print("[EA] receive_msg: Waiting for message from server...");
      string result = "";
      CJAVal json;
      bool line_complete = false;
      int char_count = 0;
      
      while (!line_complete)
      {
         uchar c[1];
         uint rsp_len;
         
         rsp_len = SocketRead(s, c, 1, 1000);
         
         if (rsp_len > 0)
         {
            char_count++;
            result += CharArrayToString(c, 0, (int)rsp_len);
            
            if (CharArrayToString(c, 0, (int)rsp_len) == "\n")
            {
               StringReplace(result, "\n", "");
               PrintFormat("[EA] receive_msg: Received complete message (%d chars): %s", char_count, result);
               
               if (!json.Deserialize(result))
               {
                  PrintFormat("[EA] receive_msg: ERROR - Failed to deserialize JSON: %s", result);
               }
               else
               {
                  Print("[EA] receive_msg: JSON deserialized successfully");
               }
               line_complete = true;   
            }
         }
         else if (rsp_len == 0)
         {
            PrintFormat("[EA] receive_msg: SocketRead returned 0 (timeout or connection closed). Error: %d", GetLastError());
         }
         else
         {
            PrintFormat("[EA] receive_msg: SocketRead error: %d", GetLastError());
         }
      }
      
      return json;
   }