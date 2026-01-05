//+------------------------------------------------------------------+
//|                                        mt5_trading_operation.mq5 |
//|                                                                  | 
//| Expert Advisor for executing trading operations via socket       |
//| connection. Handles account info requests, order opening/closing |
//+------------------------------------------------------------------+
#property copyright "Alchemist Capital Management"
#property link      "https://github.com/maxnorm/Alchemist-AI"
#property version   "1.00"

#include <JAson.mqh>
#include <socket_utils.mqh>

#include <Trade\PositionInfo.mqh>
#include <Trade\Trade.mqh>
#include <Trade\SymbolInfo.mqh>
#include <Trade\AccountInfo.mqh>
#include <Trade\OrderInfo.mqh>

input string ip = "127.0.0.1";
input int port = 8080;

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
      Print("[EA] auth: Starting authentication...");
      CJAVal json;
      json["auth_code"] = auth_code;
      json["login"] = AccountInfoInteger(ACCOUNT_LOGIN);
      
      PrintFormat("[EA] auth: Sending auth - code: %d, login: %d", auth_code, AccountInfoInteger(ACCOUNT_LOGIN));

      send_msg(socket, json);
      Print("[EA] auth: Waiting for authentication response...");
      CJAVal msg = receive_msg(socket);
      
      string msg_str = "";
      msg.Serialize(msg_str);
      PrintFormat("[EA] auth: Received response: %s", msg_str);

      if (msg["auth_status"] == successful_auth_code)
      {
         terminal_id = msg["terminal_id"].ToInt();
         PrintFormat("[EA] auth: Authentication SUCCESS - Terminal ID: %d", terminal_id);
         return true;
      }
      PrintFormat("[EA] auth: Authentication FAILED - Status: %d (expected: %d)", 
                  msg["auth_status"].ToInt(), successful_auth_code);
      return false;
   }

// Listen from the server
void start_listenning()
   {
      Print("=== EA Started listening for server requests ===");
      PrintFormat("[EA] start_listenning: Socket handle: %d", socket);
      int request_count = 0;
      
      while (true)
      {
         PrintFormat("[EA] Waiting for message from server (request #%d)...", request_count);
         PrintFormat("[EA] start_listenning: Socket state check - handle: %d", socket);
         
         CJAVal infos = receive_msg(socket);
         request_count++;

         string out= "";
         infos.Serialize(out);
         PrintFormat("[EA] Received message #%d: %s", request_count, out);
         
         // Check if message is valid (has a request field)
         if (!infos.HasKey("request"))
         {
            PrintFormat("[EA] start_listenning: ERROR - Invalid message received (no 'request' field). Socket may be broken.");
            Print("[EA] start_listenning: Attempting to continue, but connection may be lost.");
            // Continue loop to try again - socket might recover or we'll detect it on next read
            continue;
         }

         // Wrap handle_request in error handling to prevent EA from crashing
         Print("[EA] start_listenning: About to call handle_request...");
         handle_request(infos);
         Print("[EA] start_listenning: handle_request completed successfully");
         
         PrintFormat("[EA] Finished processing request #%d", request_count);
      }
   }

// Handle the request from the server
void handle_request(CJAVal& infos)
   {
      Print("[EA] handle_request: Entry");
      long request = infos["request"].ToInt();
      PrintFormat("[EA] handle_request: Processing request type %d", request);

      if (request == ACCOUNT_INFOS)
      {
         Print("[EA] handle_request: ACCOUNT_INFOS request");
         CJAVal account_infos = get_account_infos();
         Print("[EA] handle_request: Got account infos, sending response...");
         send_msg(socket, account_infos);
         Print("[EA] handle_request: ACCOUNT_INFOS response sent");
      }
      else if (request == OPEN_ORDER)
      {
         Print("[EA] handle_request: OPEN_ORDER request received");
         Print("[EA] handle_request: Calling send_order...");
         CJAVal res = send_order(infos);
         Print("[EA] handle_request: send_order completed");
         
         string res_str = "";
         res.Serialize(res_str);
         PrintFormat("[EA] handle_request: Sending order response: %s", res_str);
         
         Print("[EA] handle_request: About to send response via socket...");
         send_msg(socket, res);
         Print("[EA] handle_request: OPEN_ORDER response sent successfully");
      }
      else if (request == CLOSE_ORDER)
      {
         Print("[EA] handle_request: CLOSE_ORDER request");
         CJAVal res = close_order(infos);
         send_msg(socket, res);
         Print("[EA] handle_request: CLOSE_ORDER response sent");
      }
      else
      {
         PrintFormat("[EA] handle_request: ERROR - Unknown request type: %d", request);
      }
      Print("[EA] handle_request: Exit");
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
      Print("=== [EA] send_order: Starting order processing ===");
      
      MqlTradeRequest request = {};
      MqlTradeResult result = {};

      // Get order type
      ENUM_ORDER_TYPE order_type = (ENUM_ORDER_TYPE)infos["order_type"].ToInt();
      request.type = order_type;
      PrintFormat("[EA] send_order: Order type = %d (%s)", order_type, 
                  (order_type == ORDER_TYPE_BUY ? "BUY" : 
                   order_type == ORDER_TYPE_SELL ? "SELL" : "OTHER"));
      
      // Get symbol and normalize it
      string symbol = infos["symbol"].ToStr();
      request.symbol = symbol;
      PrintFormat("[EA] send_order: Symbol = %s", symbol);
      
      // Validate symbol exists
      PrintFormat("[EA] send_order: Validating symbol %s...", symbol);
      if (!m_symbol.Name(symbol))
      {
         PrintFormat("[EA] send_order: ERROR - Invalid symbol: %s", symbol);
         CJAVal res;
         res["return_code"] = -1;
         res["ticket"] = 0;
         res["lotsize"] = 0;
         res["price"] = 0;
         res["comment"] = "Invalid symbol: " + symbol;
         return res;
      }
      PrintFormat("[EA] send_order: Symbol validated successfully");
      
      // Get volume (lot size)
      double lotsize = infos["lotsize"].ToDbl();
      PrintFormat("[EA] send_order: Requested lot size = %.2f", lotsize);
      
      // Normalize lot size to broker's requirements
      double min_lot = m_symbol.LotsMin();
      double max_lot = m_symbol.LotsMax();
      double lot_step = m_symbol.LotsStep();
      PrintFormat("[EA] send_order: Lot constraints - Min: %.2f, Max: %.2f, Step: %.2f", 
                  min_lot, max_lot, lot_step);
      
      // Round to lot step
      lotsize = MathFloor(lotsize / lot_step) * lot_step;
      
      // Clamp to min/max
      if (lotsize < min_lot) 
      {
         PrintFormat("[EA] send_order: Lot size %.2f < min %.2f, adjusting to min", lotsize, min_lot);
         lotsize = min_lot;
      }
      if (lotsize > max_lot) 
      {
         PrintFormat("[EA] send_order: Lot size %.2f > max %.2f, adjusting to max", lotsize, max_lot);
         lotsize = max_lot;
      }
      
      request.volume = lotsize;
      PrintFormat("[EA] send_order: Final lot size = %.2f", lotsize);

      // Set action based on order type
      if (order_type == ORDER_TYPE_BUY || order_type == ORDER_TYPE_SELL)
      {
         request.action = TRADE_ACTION_DEAL;
         Print("[EA] send_order: Market order (TRADE_ACTION_DEAL)");
         
         // For market orders, get current price
         if (order_type == ORDER_TYPE_BUY)
         {
            request.price = m_symbol.Ask();
            PrintFormat("[EA] send_order: BUY order - Using Ask price = %.5f", request.price);
         }
         else // ORDER_TYPE_SELL
         {
            request.price = m_symbol.Bid();
            PrintFormat("[EA] send_order: SELL order - Using Bid price = %.5f", request.price);
         }
      }
      else
      {
         request.action = TRADE_ACTION_PENDING;
         Print("[EA] send_order: Pending order (TRADE_ACTION_PENDING)");
         if (infos.HasKey("price"))
         {
            request.price = infos["price"].ToDbl();
            PrintFormat("[EA] send_order: Pending order price = %.5f", request.price);
         }
      }

      // Set stop loss if provided
      if (infos.HasKey("sl"))
      {
         Print("[EA] send_order: Stop loss provided");
         // Check if value is valid (not null, not empty)
         if (infos["sl"].m_type == jtDBL || infos["sl"].m_type == jtINT)
         {
            request.sl = infos["sl"].ToDbl();
            request.sl = NormalizeDouble(request.sl, m_symbol.Digits());
            PrintFormat("[EA] send_order: Stop loss = %.5f", request.sl);
         }
         else
         {
            string sl_str = infos["sl"].ToStr();
            PrintFormat("[EA] send_order: Stop loss as string: '%s'", sl_str);
            if (sl_str != "" && sl_str != "null" && sl_str != "None" && sl_str != "NULL")
            {
               request.sl = infos["sl"].ToDbl();
               request.sl = NormalizeDouble(request.sl, m_symbol.Digits());
               PrintFormat("[EA] send_order: Stop loss parsed = %.5f", request.sl);
            }
            else
            {
               Print("[EA] send_order: Stop loss is null/empty, skipping");
            }
         }
      }
      else
      {
         Print("[EA] send_order: No stop loss provided");
      }

      // Set take profit if provided
      if (infos.HasKey("tp"))
      {
         Print("[EA] send_order: Take profit provided");
         // Check if value is valid (not null, not empty)
         if (infos["tp"].m_type == jtDBL || infos["tp"].m_type == jtINT)
         {
            request.tp = infos["tp"].ToDbl();
            request.tp = NormalizeDouble(request.tp, m_symbol.Digits());
            PrintFormat("[EA] send_order: Take profit = %.5f", request.tp);
         }
         else
         {
            string tp_str = infos["tp"].ToStr();
            PrintFormat("[EA] send_order: Take profit as string: '%s'", tp_str);
            if (tp_str != "" && tp_str != "null" && tp_str != "None" && tp_str != "NULL")
            {
               request.tp = infos["tp"].ToDbl();
               request.tp = NormalizeDouble(request.tp, m_symbol.Digits());
               PrintFormat("[EA] send_order: Take profit parsed = %.5f", request.tp);
            }
            else
            {
               Print("[EA] send_order: Take profit is null/empty, skipping");
            }
         }
      }
      else
      {
         Print("[EA] send_order: No take profit provided");
      }

      // Set required fields for order execution
      request.deviation = 10; // Slippage tolerance in points
      request.magic = 123456; // EA magic number
      request.comment = "AI Trading System";
      request.type_filling = ORDER_FILLING_FOK; // Try Fill or Kill first
      
      PrintFormat("[EA] send_order: Request prepared - Symbol: %s, Type: %d, Volume: %.2f, Price: %.5f, SL: %.5f, TP: %.5f",
                  request.symbol, request.type, request.volume, request.price, request.sl, request.tp);
      PrintFormat("[EA] send_order: Deviation: %d, Magic: %d, Filling: FOK", 
                  request.deviation, request.magic);
      
      // Check if AutoTrading is enabled - FAIL EARLY if disabled
      if (!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
      {
         Print("[EA] send_order: ERROR - AutoTrading is disabled in terminal!");
         CJAVal res;
         res["return_code"] = 10004; // TRADE_RETCODE_REJECT
         res["ticket"] = 0;
         res["lotsize"] = 0;
         res["price"] = 0;
         res["comment"] = "AutoTrading is disabled in terminal. Enable it in Tools > Options > Expert Advisors";
         return res;
      }
      if (!MQLInfoInteger(MQL_TRADE_ALLOWED))
      {
         Print("[EA] send_order: ERROR - Trading is not allowed in MQL!");
         CJAVal res;
         res["return_code"] = 10004; // TRADE_RETCODE_REJECT
         res["ticket"] = 0;
         res["lotsize"] = 0;
         res["price"] = 0;
         res["comment"] = "Trading is not allowed in MQL. Check EA permissions.";
         return res;
      }
      
      Print("[EA] send_order: Attempting OrderSend with FOK filling...");
      // If FOK is not supported, try IOC
      if (!OrderSend(request, result))
      {
         int error = GetLastError();
         PrintFormat("[EA] send_order: OrderSend FAILED with FOK - Error code: %d", error);
         
         if (error == 10021) // ORDER_FILLING_NOT_ALLOWED
         {
            Print("[EA] send_order: FOK not allowed, trying IOC...");
            request.type_filling = ORDER_FILLING_IOC; // Try Immediate or Cancel
            if (!OrderSend(request, result))
            {
               error = GetLastError();
               PrintFormat("[EA] send_order: OrderSend FAILED with IOC - Error code: %d", error);
               
               if (error == 10021) // Still not allowed
               {
                  Print("[EA] send_order: IOC not allowed, trying RETURN...");
                  request.type_filling = ORDER_FILLING_RETURN; // Try Return
                  if (!OrderSend(request, result))
                  {
                     error = GetLastError();
                     PrintFormat("[EA] send_order: OrderSend FAILED with RETURN - Error code: %d", error);
                  }
                  else
                  {
                     Print("[EA] send_order: OrderSend SUCCESS with RETURN filling");
                  }
               }
               else
               {
                  Print("[EA] send_order: OrderSend SUCCESS with IOC filling");
               }
            }
            else
            {
               Print("[EA] send_order: OrderSend SUCCESS with IOC filling");
            }
         }
      }
      else
      {
         Print("[EA] send_order: OrderSend SUCCESS with FOK filling");
      }

      // Get result
      uint ret_code = result.retcode;
      ulong ticket = result.order;
      double volume = result.volume;
      double price = result.price;
      string comment = result.comment;
      
      PrintFormat("[EA] send_order: Order result - Retcode: %u, Ticket: %llu, Volume: %.2f, Price: %.5f", 
                  ret_code, ticket, volume, price);
      PrintFormat("[EA] send_order: Comment: %s", comment);
      
      // Log result for debugging
      if (ret_code != TRADE_RETCODE_DONE && ret_code != TRADE_RETCODE_PLACED)
      {
         PrintFormat("[EA] send_order: ORDER FAILED - retcode=%u, error=%d, comment=%s", 
                     ret_code, GetLastError(), comment);
         print_MqlTradeResult(result);
      }
      else
      {
         PrintFormat("[EA] send_order: ORDER SUCCESS - ticket=%llu, volume=%.2f, price=%.5f", 
                     ticket, volume, price);
      }

      CJAVal res;
      res["return_code"] = (int)ret_code;
      res["ticket"] = (long)ticket;
      res["lotsize"] = volume;
      res["price"] = price;
      res["comment"] = comment;
      
      string res_str = "";
      res.Serialize(res_str);
      PrintFormat("[EA] send_order: Response JSON: %s", res_str);
      Print("=== [EA] send_order: Finished order processing ===");

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
         Print("Closing pending order #" + IntegerToString(ticket_to_close));
         m_trade.OrderDelete(ticket_to_close);

         m_trade.Result(result);
      }
      else if (m_position.SelectByTicket(ticket_to_close))
      {
         // Open order
         Print("Closing open order #" + IntegerToString(ticket_to_close));
         m_trade.PositionClosePartial(ticket_to_close, infos["lotsize"].ToDbl());

         m_trade.Result(result);
      }

      print_MqlTradeResult(result);

      uint ret_code = result.retcode;
      ulong ticket = result.order;
      double volume = result.volume;
      double price = result.price;
      string comment = result.comment;

      CJAVal account_infos = update_account_infos();

      CJAVal order;
      order["lotsize"] = volume;
      order["close_price"] = price;

      CJAVal res;
      res["return_code"] = (int)ret_code;
      res["comment"] = comment;
      res["order"].Set(order);
      res["account"].Set(account_infos);

      return res;
   }


void print_MqlTradeResult(MqlTradeResult& res)
   {
      Print("");
      Print("MqlTradeResult");
      Print("Retcode: " + IntegerToString(res.retcode));
      Print("Comment: " + res.comment);
      Print("Deal: " + IntegerToString(res.deal));
      Print("Volume: " + DoubleToString(res.volume, 2));
      Print("Price: " + DoubleToString(res.price, 5));
      Print("");
   }
