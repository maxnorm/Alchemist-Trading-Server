#property copyright "Maxime Normandin"
#property link      "https://www.mql5.com"
#property version   "1.00"

#include <JAson.mqh>
#include <socket_utils.mqh>

#include <Trade\PositionInfo.mqh>
#include <Trade\Trade.mqh>
#include <Trade\SymbolInfo.mqh>
#include <Trade\AccountInfo.mqh>
#include <Trade\OrderInfo.mqh>

input string ip = "127.0.0.1";
input int port = 1234;

int auth_code = 2;
int successful_auth_code = 0;

int socket;
long terminal_id;

CPositionInfo  m_position;                   // trade position object
CTrade         m_trade;                      // trading object
CSymbolInfo    m_symbol;                     // symbol info object
CAccountInfo   m_account;                    // account info wrapper
COrderInfo     m_order;
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
   SocketClose(socket);
  }

//+------------------------------------------------------------------+
//| Request Code                                                     |
//+------------------------------------------------------------------+

enum REQUEST_CODE
   {
      ACCOUNT_INFOS = 100,
      OPEN_ORDER = 101,
      CLOSE_ORDER = 102,
      MODIFY_ORDER = 103
   };


//+------------------------------------------------------------------+
//| Functions                                                        |
//+------------------------------------------------------------------+

// Authentication to the server as a terminal
bool auth()
   {
      CJAVal json;
      json["auth_code"] = auth_code;
      json["login"] = AccountInfoInteger(ACCOUNT_LOGIN);

      send_msg(socket, json);
      CJAVal msg = receive_msg(socket);

      if (msg["auth_status"] == successful_auth_code)
      {
         terminal_id = msg["terminal_id"].ToInt();

         return true;
      }
      return false;
   }

// Listen from the server
void start_listenning()
   {
      while (true)
      {
         CJAVal infos = receive_msg(socket);

         string out= "";
         infos.Serialize(out);
         Print(out);

         handle_request(infos);
      }
   }

// Handle the request from the server
void handle_request(CJAVal& infos)
   {
      long request = infos["request"].ToInt();

      if (request == ACCOUNT_INFOS)
      {
         CJAVal account_infos = get_account_infos();
         send_msg(socket, account_infos);
      }
      else if (request == OPEN_ORDER)
      {
         CJAVal res = send_order(infos);
         send_msg(socket, res);
      }
      else if (request == CLOSE_ORDER)
      {
         CJAVal res = close_order(infos);
         send_msg(socket, res);
      }
   }

// Get the necessary account informations for the request ACCOUNT_INFOS(100)
CJAVal get_account_infos()
   {
      CJAVal json;
      json["currency"] = AccountInfoString(ACCOUNT_CURRENCY);
      json["leverage"] = AccountInfoInteger(ACCOUNT_LEVERAGE);
      json["balance"] = AccountInfoDouble(ACCOUNT_BALANCE);
      json["equity"] =  AccountInfoDouble(ACCOUNT_EQUITY);
      json["profit"] = AccountInfoDouble(ACCOUNT_PROFIT);
      json["margin"] = AccountInfoDouble(ACCOUNT_MARGIN);
      json["margin_free"] = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      return json;
   }

CJAVal update_account_infos()
   {
      CJAVal json;
      json["balance"] = AccountInfoDouble(ACCOUNT_BALANCE);
      json["equity"] =  AccountInfoDouble(ACCOUNT_EQUITY);
      json["profit"] = AccountInfoDouble(ACCOUNT_PROFIT);
      json["margin"] = AccountInfoDouble(ACCOUNT_MARGIN);
      json["margin_free"] = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      return json;
   }

// Send order base on request OPEN_ORDER(101)
CJAVal send_order(CJAVal& infos)
   {
      MqlTradeRequest request = {};
      MqlTradeResult result = {};

      ENUM_ORDER_TYPE order_type = (ENUM_ORDER_TYPE)infos["order_type"].ToInt();

      request.type = order_type;
      request.symbol = infos["symbol"].ToStr();
      request.volume = infos["lotsize"].ToDbl();

      if (order_type == ORDER_TYPE_BUY || order_type == ORDER_TYPE_SELL)
      {
         request.action = TRADE_ACTION_DEAL;
      }
      else
      {
         request.action = TRADE_ACTION_PENDING;
         request.price = infos["price"].ToDbl();
      }

      if (infos["sl"].ToStr() != "")
      {
         request.sl = infos["sl"].ToDbl();
      }

      if (infos["tp"].ToStr() != "")
      {
         request.tp = infos["tp"].ToDbl();
      }

      if (!OrderSend(request, result))
      {
         PrintFormat("OrderSend error %d",GetLastError());
      }

      int ret_code = result.retcode;
      long ticket = result.order;
      double volume = result.volume;
      double price = result.price;
      string comment = result.comment;

      CJAVal res;
      res["return_code"] = ret_code;
      res["ticket"] = ticket;
      res["lotsize"] = volume;
      res["price"] = price;
      res["comment"] = comment;

      return res;
   }

// Close a order
CJAVal close_order(CJAVal& infos)
   {
      long ticket_to_close = infos["ticket"].ToInt();
      MqlTradeResult result;

      if (m_order.Select(ticket_to_close))
      {
         // Pending order
         Print("Closing pending order #" + ticket_to_close);
         m_trade.OrderDelete(ticket_to_close);

         m_trade.Result(result);
      }
      else if (m_position.SelectByTicket(ticket_to_close))
      {
         // Open order
         Print("Closing open order #" + ticket_to_close);
         m_trade.PositionClosePartial(ticket_to_close, infos["lotsize"].ToDbl());

         m_trade.Result(result);
      }

      print_MqlTradeResult(result);

      int ret_code = result.retcode;
      long ticket = result.order;
      double volume = result.volume;
      double price = result.price;
      string comment = result.comment;

      CJAVal account_infos = update_account_infos();

      CJAVal order;
      order["lotsize"] = volume;
      order["close_price"] = price;

      CJAVal res;
      res["return_code"] = ret_code;
      res["comment"] = comment;
      res["order"].Set(order);
      res["account"].Set(account_infos);

      return res;
   }


void print_MqlTradeResult(MqlTradeResult& res)
   {
      Print("");
      Print("MqlTradeResult");
      Print("Retcode: " + res.retcode);
      Print("Comment: " + res.comment);
      Print("Deal: " + res.deal);
      Print("Volume: " + res.volume);
      Print("Price: " + res.price);
      Print("");
   }
