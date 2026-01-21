//+---------------------------------------------------------------------------------------------------+
//| mt5_zeromq_trading.mq5                                                                             |
//| ZeroMQ-based Expert Advisor for executing trading operations                                       |
//+---------------------------------------------------------------------------------------------------+
#property copyright "Alchemist Capital Management"
#property link      "https://github.com/maxnorm/Alchemist-AI"
#property version   "2.00"

#include <Zmq/Zmq.mqh>
#include <JAson.mqh>

#include <Trade\PositionInfo.mqh>
#include <Trade\Trade.mqh>
#include <Trade\SymbolInfo.mqh>
#include <Trade\AccountInfo.mqh>
#include <Trade\OrderInfo.mqh>

input int order_port = 5556;
input string auth_token = "";

int auth_code = 2;
int successful_auth_code = 0;

Context context;
Socket repSocket(context, ZMQ_REP);

CPositionInfo  m_position;
CTrade         m_trade;
CSymbolInfo    m_symbol;
CAccountInfo   m_account;
COrderInfo     m_order;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(!repSocket.bind(StringFormat("tcp://*:%d", order_port)))
     {
      PrintFormat("Failed to bind REP socket on port %d", order_port);
      return(INIT_FAILED);
     }
   PrintFormat("ZeroMQ REP socket bound to port %d", order_port);
   EventSetTimer(1);
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+

void OnDeinit(const int reason)
  {
   EventKillTimer();
   repSocket.unbind(StringFormat("tcp://*:%d", order_port));
  }

//+------------------------------------------------------------------+
//| Timer event - receive requests                                   |
//+------------------------------------------------------------------+
void OnTimer()
  {
   ZmqMsg request_msg;
   if(repSocket.recv(request_msg, true))  // true for non-blocking
     {
      string request_str = request_msg.getData();
      
      if(StringLen(request_str) == 0)
        {
         CJAVal error_response;
         error_response["return_code"] = -1;
         error_response["comment"] = "Empty message received";
         string error_str = "";
         error_response.Serialize(error_str);
         ZmqMsg error_msg(error_str);
         repSocket.send(error_msg);
         return;
        }
      
      CJAVal json;
      if(json.Deserialize(request_str))
        {
         CJAVal response;
         if(json.HasKey("auth_code"))
           {
            response = handle_auth(json);
           }
         else if(json.HasKey("request"))
           {
            response = handle_request(json);
           }
         else
           {
            response["return_code"] = -1;
            response["comment"] = "Invalid message format";
           }

         string response_str = "";
         response.Serialize(response_str);
         ZmqMsg reply_msg(response_str);
         repSocket.send(reply_msg);
        }
      else
        {
         CJAVal error_response;
         error_response["return_code"] = -1;
         error_response["comment"] = "JSON deserialization failed";
         string error_str = "";
         error_response.Serialize(error_str);
         ZmqMsg error_msg(error_str);
         repSocket.send(error_msg);
        }
     }
  }
//+------------------------------------------------------------------+

// Authentication to the server as a terminal
CJAVal handle_auth(CJAVal& request)
  {
   CJAVal response;
   long account_login = request["login"].ToInt();
   string provided_token = request["auth_token"].ToStr();

   if(provided_token == auth_token && account_login == AccountInfoInteger(ACCOUNT_LOGIN))
     {
      response["auth_status"] = successful_auth_code;
      response["terminal_id"] = AccountInfoInteger(ACCOUNT_LOGIN);
      response["comment"] = "Authentication successful";
     }
   else
     {
      response["auth_status"] = -1;
      response["comment"] = "Authentication failed";
     }
   return response;
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
//| Handle the request from the server                               |
//+------------------------------------------------------------------+
CJAVal handle_request(CJAVal& infos)
  {
   long request = infos["request"].ToInt();
   if(request == ACCOUNT_INFOS)
      return get_account_infos();
   if(request == OPEN_ORDER)
      return send_order(infos);
   if(request == CLOSE_ORDER)
      return close_order(infos);

   CJAVal res;
   res["return_code"] = -1;
   res["comment"] = "Unknown request";
   return res;
  }

//+------------------------------------------------------------------+
//| Account info                                                     |
//+------------------------------------------------------------------+
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

//+------------------------------------------------------------------+
//| Send order                                                       |
//+------------------------------------------------------------------+
CJAVal send_order(CJAVal& infos)
  {
   MqlTradeRequest request = {};
   MqlTradeResult result = {};

   ENUM_ORDER_TYPE order_type = (ENUM_ORDER_TYPE)infos["order_type"].ToInt();
   request.type = order_type;

   string symbol = infos["symbol"].ToStr();
   request.symbol = symbol;
   if(!m_symbol.Name(symbol))
     {
      CJAVal res;
      res["return_code"] = -1;
      res["ticket"] = 0;
      res["lotsize"] = 0;
      res["price"] = 0;
      res["comment"] = "Invalid symbol: " + symbol;
      return res;
     }

   double lotsize = infos["lotsize"].ToDbl();
   double min_lot = m_symbol.LotsMin();
   double max_lot = m_symbol.LotsMax();
   double lot_step = m_symbol.LotsStep();
   lotsize = MathFloor(lotsize / lot_step) * lot_step;
   if(lotsize < min_lot) lotsize = min_lot;
   if(lotsize > max_lot) lotsize = max_lot;
   request.volume = lotsize;

   if(order_type == ORDER_TYPE_BUY || order_type == ORDER_TYPE_SELL)
     {
      request.action = TRADE_ACTION_DEAL;
      if(order_type == ORDER_TYPE_BUY)
         request.price = m_symbol.Ask();
      else
         request.price = m_symbol.Bid();
     }
   else
     {
      request.action = TRADE_ACTION_PENDING;
      if(infos.HasKey("price"))
         request.price = infos["price"].ToDbl();
     }

   if(infos.HasKey("sl") && (infos["sl"].m_type == jtDBL || infos["sl"].m_type == jtINT))
     {
      request.sl = NormalizeDouble(infos["sl"].ToDbl(), m_symbol.Digits());
     }
   if(infos.HasKey("tp") && (infos["tp"].m_type == jtDBL || infos["tp"].m_type == jtINT))
     {
      request.tp = NormalizeDouble(infos["tp"].ToDbl(), m_symbol.Digits());
     }

   request.deviation = 10;
   request.magic = 123456;
   request.comment = "AI Trading System";
   request.type_filling = ORDER_FILLING_FOK;

   if(!OrderSend(request, result))
     {
      if(GetLastError() == 10021)
        {
         request.type_filling = ORDER_FILLING_IOC;
         if(!OrderSend(request, result))
           {
            // Ignore return value, result struct contains the error info
           }
        }
     }

   CJAVal res;
   res["return_code"] = (int)result.retcode;
   res["ticket"] = (long)result.order;
   res["lotsize"] = result.volume;
   res["price"] = result.price;
   res["comment"] = result.comment;
   return res;
  }

//+------------------------------------------------------------------+
//| Close order                                                      |
//+------------------------------------------------------------------+
CJAVal close_order(CJAVal& infos)
  {
   long ticket_to_close = infos["ticket"].ToInt();
   MqlTradeResult result;

   if(m_order.Select(ticket_to_close))
     {
      m_trade.OrderDelete(ticket_to_close);
      m_trade.Result(result);
     }
   else if(m_position.SelectByTicket(ticket_to_close))
     {
      m_trade.PositionClosePartial(ticket_to_close, infos["lotsize"].ToDbl());
      m_trade.Result(result);
     }

   CJAVal account_infos = update_account_infos();
   CJAVal order;
   order["lotsize"] = result.volume;
   order["close_price"] = result.price;

   CJAVal res;
   res["return_code"] = (int)result.retcode;
   res["comment"] = result.comment;
   res["order"].Set(order);
   res["account"].Set(account_infos);
   return res;
  }
