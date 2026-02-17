"""
╔══════════════════════════════════════════════════════════════════════╗
║              FOREXIA SIGNATURE AGENT — MT4 BRIDGE                   ║
║        ZeroMQ Python-to-MT4 Institutional Execution Layer           ║
╚══════════════════════════════════════════════════════════════════════╝

This bridge provides sub-second order execution to MetaTrader 4 via
ZeroMQ sockets. The MT4 side runs an Expert Advisor (EA) that listens
on a PULL socket for commands and pushes data back on a PUSH socket.

Commands flow:  Python (REQ) ──► MT4 EA (REP)
Data flows:     MT4 EA (PUSH) ──► Python (PULL)

The bridge handles:
  - Trade execution (market orders, pending orders)
  - Account state polling
  - Live price streaming
  - Position management (modify SL/TP, close trades)
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any

import zmq
import zmq.asyncio

from backend.config import CONFIG
from backend.models.schemas import (
    AccountState, CandleData, TradeDirection, TradeRecord, TradeStatus
)

logger = logging.getLogger("forexia.mt4_bridge")


class MT4Bridge:
    """
    ZeroMQ bridge to MetaTrader 4.
    
    This is the execution arm — when the Forexia engine says "FIRE,"
    this bridge pulls the trigger with institutional precision.
    
    Architecture:
      - REQ/REP pattern for commands (send order, get response)
      - PULL socket for streaming market data from MT4
      - Heartbeat monitor to detect disconnections
    """

    def __init__(self):
        self.config = CONFIG.mt4
        self.context: Optional[zmq.asyncio.Context] = None
        self.command_socket: Optional[zmq.asyncio.Socket] = None  # REQ
        self.data_socket: Optional[zmq.asyncio.Socket] = None     # PULL
        self._connected = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._data_listener_task: Optional[asyncio.Task] = None
        self._account_state = AccountState()
        self._latest_prices: Dict[str, Dict[str, float]] = {}
        self._pending_responses: Dict[str, asyncio.Future] = {}

    # ─────────────────────────────────────────────────────────────────
    #  CONNECTION LIFECYCLE
    # ─────────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """
        Establish ZeroMQ connections to the MT4 Expert Advisor.
        Returns True if connection is live, False on failure.
        """
        try:
            self.context = zmq.asyncio.Context()

            # REQ socket — we send commands, MT4 replies
            self.command_socket = self.context.socket(zmq.REQ)
            self.command_socket.setsockopt(zmq.RCVTIMEO, self.config.command_timeout * 1000)
            self.command_socket.setsockopt(zmq.SNDTIMEO, 5000)
            self.command_socket.setsockopt(zmq.LINGER, 0)
            self.command_socket.connect(
                f"{self.config.host}:{self.config.push_port}"
            )

            # PULL socket — MT4 pushes live data to us
            self.data_socket = self.context.socket(zmq.PULL)
            self.data_socket.setsockopt(zmq.RCVTIMEO, 1000)
            self.data_socket.connect(
                f"{self.config.host}:{self.config.pull_port}"
            )

            # Verify connection with heartbeat
            response = await self._send_command({"action": "HEARTBEAT"})
            if response and response.get("status") == "OK":
                self._connected = True
                logger.info("═══ MT4 BRIDGE CONNECTED — Execution arm is LIVE ═══")

                # Start background tasks
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                self._data_listener_task = asyncio.create_task(self._data_listener())
                return True
            else:
                logger.warning("MT4 heartbeat failed — bridge not connected")
                return False

        except Exception as e:
            logger.error(f"MT4 Bridge connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Cleanly shut down ZeroMQ connections."""
        self._connected = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._data_listener_task:
            self._data_listener_task.cancel()

        if self.command_socket:
            self.command_socket.close()
        if self.data_socket:
            self.data_socket.close()
        if self.context:
            self.context.term()

        logger.info("MT4 Bridge disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ─────────────────────────────────────────────────────────────────
    #  COMMAND INTERFACE — TALKING TO MT4
    # ─────────────────────────────────────────────────────────────────

    async def _send_command(self, command: Dict[str, Any]) -> Optional[Dict]:
        """
        Send a JSON command to MT4 and await the response.
        This is the fundamental communication primitive.
        """
        if not self.command_socket:
            logger.error("Cannot send command — socket not initialized")
            return None

        try:
            payload = json.dumps(command).encode("utf-8")
            await self.command_socket.send(payload)
            response_raw = await self.command_socket.recv()
            return json.loads(response_raw.decode("utf-8"))
        except zmq.Again:
            logger.error(f"MT4 command timeout: {command.get('action', 'UNKNOWN')}")
            self._connected = False
            return None
        except Exception as e:
            logger.error(f"MT4 command error: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────
    #  TRADE EXECUTION — PULLING THE TRIGGER
    # ─────────────────────────────────────────────────────────────────

    async def execute_market_order(
        self,
        symbol: str,
        direction: TradeDirection,
        lot_size: float,
        stop_loss: float,
        take_profit: float,
        comment: str = "FOREXIA_SIGNATURE"
    ) -> Optional[int]:
        """
        Execute a market order on MT4.
        
        This is where the Forexia engine's analysis becomes real money.
        The order fires AFTER the stop hunt exhaustion — we're entering
        on the Solution phase, trapping dumb money behind us.

        Returns: MT4 ticket number, or None on failure.
        """
        if not self._connected:
            logger.error("Cannot execute — MT4 bridge is disconnected")
            return None

        command = {
            "action": "TRADE_OPEN",
            "type": 0 if direction == TradeDirection.BUY else 1,  # 0=BUY, 1=SELL
            "symbol": symbol,
            "lots": round(lot_size, 2),
            "price": 0,  # 0 = market price
            "stop_loss": round(stop_loss, 5),
            "take_profit": round(take_profit, 5),
            "slippage": 3,  # Max 3 pips slippage
            "comment": comment,
            "magic": 20260215  # Forexia magic number
        }

        logger.info(
            f"══╡ EXECUTING {direction.value} {lot_size} {symbol} "
            f"| SL: {stop_loss} | TP: {take_profit} "
            f"| Trapping dumb money here ╞══"
        )

        response = await self._send_command(command)

        if response and response.get("status") == "OK":
            ticket = response.get("ticket")
            logger.info(f"✓ Order filled — MT4 Ticket #{ticket}")
            return ticket
        else:
            error = response.get("error", "Unknown") if response else "No response"
            logger.error(f"✗ Order REJECTED: {error}")
            return None

    async def modify_trade(
        self,
        ticket: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """
        Modify an existing trade's SL/TP.
        Used to trail stops after the reversal confirms.
        """
        command = {
            "action": "TRADE_MODIFY",
            "ticket": ticket,
        }
        if stop_loss is not None:
            command["stop_loss"] = round(stop_loss, 5)
        if take_profit is not None:
            command["take_profit"] = round(take_profit, 5)

        response = await self._send_command(command)
        success = response and response.get("status") == "OK"
        if success:
            logger.info(f"Trade #{ticket} modified — SL: {stop_loss}, TP: {take_profit}")
        return success

    async def close_trade(self, ticket: int) -> bool:
        """Close an open trade by ticket number."""
        command = {
            "action": "TRADE_CLOSE",
            "ticket": ticket,
        }
        response = await self._send_command(command)
        success = response and response.get("status") == "OK"
        if success:
            logger.info(f"Trade #{ticket} CLOSED")
        return success

    async def close_all_trades(self, symbol: Optional[str] = None) -> int:
        """
        Emergency close — shut down all positions.
        Used on Friday wind-down or when daily loss limit is hit.
        """
        command = {"action": "TRADE_CLOSE_ALL"}
        if symbol:
            command["symbol"] = symbol

        response = await self._send_command(command)
        if response and response.get("status") == "OK":
            closed = response.get("closed_count", 0)
            logger.info(f"Closed {closed} trades {'for ' + symbol if symbol else '(all)'}")
            return closed
        return 0

    # ─────────────────────────────────────────────────────────────────
    #  ACCOUNT & MARKET DATA
    # ─────────────────────────────────────────────────────────────────

    async def get_account_state(self) -> AccountState:
        """Pull fresh account state from MT4."""
        command = {"action": "ACCOUNT_INFO"}
        response = await self._send_command(command)

        if response and response.get("status") == "OK":
            self._account_state = AccountState(
                balance=response.get("balance", 0),
                equity=response.get("equity", 0),
                margin=response.get("margin", 0),
                free_margin=response.get("free_margin", 0),
                margin_level=response.get("margin_level", 0),
                open_trades=response.get("open_trades", 0),
                last_updated=datetime.utcnow()
            )
        return self._account_state

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "M15",
        count: int = 100
    ) -> List[CandleData]:
        """
        Request historical candle data from MT4.
        Timeframe codes: M1, M5, M15, M30, H1, H4, D1, W1
        """
        tf_map = {
            "M1": 1, "M5": 5, "M15": 15, "M30": 30,
            "H1": 60, "H4": 240, "D1": 1440, "W1": 10080
        }

        command = {
            "action": "GET_CANDLES",
            "symbol": symbol,
            "timeframe": tf_map.get(timeframe, 15),
            "count": count
        }

        response = await self._send_command(command)
        candles = []

        if response and response.get("status") == "OK":
            for bar in response.get("candles", []):
                candles.append(CandleData(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=datetime.fromtimestamp(bar["time"]),
                    open=bar["open"],
                    high=bar["high"],
                    low=bar["low"],
                    close=bar["close"],
                    volume=bar.get("volume", 0),
                    tick_volume=bar.get("tick_volume", 0)
                ))

        return candles

    async def get_current_price(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get current bid/ask for a symbol."""
        command = {
            "action": "GET_PRICE",
            "symbol": symbol
        }
        response = await self._send_command(command)

        if response and response.get("status") == "OK":
            price = {
                "bid": response["bid"],
                "ask": response["ask"],
                "spread": response.get("spread", 0)
            }
            self._latest_prices[symbol] = price
            return price
        return self._latest_prices.get(symbol)

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all currently open positions from MT4."""
        command = {"action": "GET_POSITIONS"}
        response = await self._send_command(command)

        if response and response.get("status") == "OK":
            return response.get("positions", [])
        return []

    # ─────────────────────────────────────────────────────────────────
    #  BACKGROUND TASKS
    # ─────────────────────────────────────────────────────────────────

    async def _heartbeat_loop(self):
        """
        Continuous heartbeat to verify MT4 connection is alive.
        If the bridge goes down, Smart Money can't execute.
        """
        while self._connected:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                response = await self._send_command({"action": "HEARTBEAT"})
                if not response or response.get("status") != "OK":
                    logger.warning("MT4 heartbeat FAILED — attempting reconnect")
                    self._connected = False
                    # Auto-reconnect attempt
                    await asyncio.sleep(self.config.reconnect_delay)
                    await self.connect()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(self.config.reconnect_delay)

    async def _data_listener(self):
        """
        Listen for streaming data from MT4's PUSH socket.
        This receives live ticks, trade updates, and alerts.
        """
        while self._connected:
            try:
                if self.data_socket:
                    raw = await self.data_socket.recv()
                    data = json.loads(raw.decode("utf-8"))
                    await self._handle_mt4_data(data)
            except zmq.Again:
                continue  # Timeout — normal, just loop
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Data listener error: {e}")
                await asyncio.sleep(1)

    async def _handle_mt4_data(self, data: Dict[str, Any]):
        """Process incoming data from MT4."""
        msg_type = data.get("type", "")

        if msg_type == "TICK":
            symbol = data.get("symbol", "")
            self._latest_prices[symbol] = {
                "bid": data["bid"],
                "ask": data["ask"],
                "spread": data.get("spread", 0)
            }

        elif msg_type == "TRADE_UPDATE":
            logger.info(f"MT4 Trade Update: Ticket #{data.get('ticket')} "
                       f"Status: {data.get('status')}")

        elif msg_type == "ACCOUNT_UPDATE":
            self._account_state = AccountState(
                balance=data.get("balance", 0),
                equity=data.get("equity", 0),
                margin=data.get("margin", 0),
                free_margin=data.get("free_margin", 0),
                open_trades=data.get("open_trades", 0),
                last_updated=datetime.utcnow()
            )


# ─────────────────────────────────────────────────────────────────────
#  MT4 EXPERT ADVISOR MQL4 TEMPLATE
# ─────────────────────────────────────────────────────────────────────
#  Deploy the following EA on your MT4 terminal to complete the bridge.
#  File: Forexia_Bridge_EA.mq4
# ─────────────────────────────────────────────────────────────────────

MT4_EA_TEMPLATE = '''
//+------------------------------------------------------------------+
//|                                        Forexia_Bridge_EA.mq4      |
//|                        Forexia Signature Agent — MT4 Bridge        |
//|                       ZeroMQ REP/PUSH Socket Handler               |
//+------------------------------------------------------------------+
#property copyright "Forexia"
#property version   "1.00"
#property strict

// Include ZeroMQ for MQL4 (download from: https://github.com/dingmaotu/mql-zmq)
#include <Zmq/Zmq.mqh>

input int    REP_PORT  = 32768;    // REP socket port (receive commands)
input int    PUSH_PORT = 32769;    // PUSH socket port (send data)
input int    MAGIC     = 20260215; // Forexia magic number

Context context("Forexia_Bridge");
Socket repSocket(context, ZMQ_REP);
Socket pushSocket(context, ZMQ_PUSH);

int OnInit()
{
   // Bind REP socket — listen for Python commands
   string repAddr = "tcp://*:" + IntegerToString(REP_PORT);
   if(!repSocket.bind(repAddr))
   {
      Print("ERROR: Failed to bind REP socket on ", repAddr);
      return INIT_FAILED;
   }
   
   // Bind PUSH socket — stream data to Python
   string pushAddr = "tcp://*:" + IntegerToString(PUSH_PORT);
   if(!pushSocket.bind(pushAddr))
   {
      Print("ERROR: Failed to bind PUSH socket on ", pushAddr);
      return INIT_FAILED;
   }
   
   Print("═══ Forexia Bridge EA ACTIVE — Awaiting Python commands ═══");
   EventSetMillisecondTimer(100);  // 100ms tick
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   repSocket.unbind("tcp://*:" + IntegerToString(REP_PORT));
   pushSocket.unbind("tcp://*:" + IntegerToString(PUSH_PORT));
   EventKillTimer();
   Print("Forexia Bridge EA stopped");
}

void OnTimer()
{
   // Check for incoming commands
   ZmqMsg request;
   if(repSocket.recv(request, ZMQ_DONTWAIT))
   {
      string cmdStr = request.getData();
      string response = ProcessCommand(cmdStr);
      
      ZmqMsg reply(response);
      repSocket.send(reply);
   }
   
   // Push live tick data
   PushTickData();
}

string ProcessCommand(string cmdJson)
{
   // Parse JSON command and route to handler
   // (Uses JAson library or simple string parsing)
   
   if(StringFind(cmdJson, "HEARTBEAT") >= 0)
      return "{\\"status\\":\\"OK\\",\\"time\\":" + IntegerToString(TimeCurrent()) + "}";
   
   if(StringFind(cmdJson, "ACCOUNT_INFO") >= 0)
      return GetAccountInfo();
   
   if(StringFind(cmdJson, "TRADE_OPEN") >= 0)
      return ExecuteTrade(cmdJson);
   
   if(StringFind(cmdJson, "TRADE_CLOSE") >= 0)
      return CloseTrade(cmdJson);
   
   if(StringFind(cmdJson, "TRADE_MODIFY") >= 0)
      return ModifyTrade(cmdJson);
      
   if(StringFind(cmdJson, "GET_CANDLES") >= 0)
      return GetCandles(cmdJson);
   
   if(StringFind(cmdJson, "GET_PRICE") >= 0)
      return GetPrice(cmdJson);
   
   if(StringFind(cmdJson, "GET_POSITIONS") >= 0)
      return GetPositions();
   
   return "{\\"status\\":\\"ERROR\\",\\"error\\":\\"Unknown command\\"}";
}

string GetAccountInfo()
{
   return StringFormat(
      "{\\"status\\":\\"OK\\",\\"balance\\":%.2f,\\"equity\\":%.2f,"
      "\\"margin\\":%.2f,\\"free_margin\\":%.2f,\\"margin_level\\":%.2f,"
      "\\"open_trades\\":%d}",
      AccountBalance(), AccountEquity(), AccountMargin(),
      AccountFreeMargin(), AccountMarginLevel(), OrdersTotal()
   );
}

string ExecuteTrade(string cmdJson)
{
   // Parse trade parameters from JSON
   int type = ExtractInt(cmdJson, "type");
   string symbol = ExtractString(cmdJson, "symbol");
   double lots = ExtractDouble(cmdJson, "lots");
   double sl = ExtractDouble(cmdJson, "stop_loss");
   double tp = ExtractDouble(cmdJson, "take_profit");
   int slippage = ExtractInt(cmdJson, "slippage");
   string comment = ExtractString(cmdJson, "comment");
   
   double price = (type == 0) ? MarketInfo(symbol, MODE_ASK) 
                               : MarketInfo(symbol, MODE_BID);
   
   int ticket = OrderSend(symbol, type, lots, price, slippage, 
                           sl, tp, comment, MAGIC, 0, 
                           type == 0 ? clrGreen : clrRed);
   
   if(ticket > 0)
      return StringFormat("{\\"status\\":\\"OK\\",\\"ticket\\":%d,\\"price\\":%.5f}", 
                          ticket, price);
   else
      return StringFormat("{\\"status\\":\\"ERROR\\",\\"error\\":\\"OrderSend failed: %d\\"}", 
                          GetLastError());
}

string CloseTrade(string cmdJson)
{
   int ticket = ExtractInt(cmdJson, "ticket");
   if(OrderSelect(ticket, SELECT_BY_TICKET))
   {
      double price = (OrderType() == OP_BUY) ? MarketInfo(OrderSymbol(), MODE_BID)
                                              : MarketInfo(OrderSymbol(), MODE_ASK);
      if(OrderClose(ticket, OrderLots(), price, 3))
         return "{\\"status\\":\\"OK\\"}";
   }
   return StringFormat("{\\"status\\":\\"ERROR\\",\\"error\\":\\"Close failed: %d\\"}", GetLastError());
}

string ModifyTrade(string cmdJson)
{
   int ticket = ExtractInt(cmdJson, "ticket");
   double sl = ExtractDouble(cmdJson, "stop_loss");
   double tp = ExtractDouble(cmdJson, "take_profit");
   
   if(OrderSelect(ticket, SELECT_BY_TICKET))
   {
      if(sl == 0) sl = OrderStopLoss();
      if(tp == 0) tp = OrderTakeProfit();
      
      if(OrderModify(ticket, OrderOpenPrice(), sl, tp, 0))
         return "{\\"status\\":\\"OK\\"}";
   }
   return StringFormat("{\\"status\\":\\"ERROR\\",\\"error\\":\\"Modify failed: %d\\"}", GetLastError());
}

string GetCandles(string cmdJson)
{
   string symbol = ExtractString(cmdJson, "symbol");
   int tf = ExtractInt(cmdJson, "timeframe");
   int count = ExtractInt(cmdJson, "count");
   
   string result = "{\\"status\\":\\"OK\\",\\"candles\\":[";
   for(int i = count - 1; i >= 0; i--)
   {
      if(i < count - 1) result += ",";
      result += StringFormat(
         "{\\"time\\":%d,\\"open\\":%.5f,\\"high\\":%.5f,\\"low\\":%.5f,"
         "\\"close\\":%.5f,\\"volume\\":%.0f}",
         (int)iTime(symbol, tf, i),
         iOpen(symbol, tf, i), iHigh(symbol, tf, i),
         iLow(symbol, tf, i), iClose(symbol, tf, i),
         (double)iVolume(symbol, tf, i)
      );
   }
   result += "]}";
   return result;
}

string GetPrice(string cmdJson)
{
   string symbol = ExtractString(cmdJson, "symbol");
   return StringFormat(
      "{\\"status\\":\\"OK\\",\\"bid\\":%.5f,\\"ask\\":%.5f,\\"spread\\":%d}",
      MarketInfo(symbol, MODE_BID),
      MarketInfo(symbol, MODE_ASK),
      (int)MarketInfo(symbol, MODE_SPREAD)
   );
}

string GetPositions()
{
   string result = "{\\"status\\":\\"OK\\",\\"positions\\":[";
   bool first = true;
   for(int i = 0; i < OrdersTotal(); i++)
   {
      if(OrderSelect(i, SELECT_BY_POS) && OrderMagicNumber() == MAGIC)
      {
         if(!first) result += ",";
         first = false;
         result += StringFormat(
            "{\\"ticket\\":%d,\\"symbol\\":\\"%s\\",\\"type\\":%d,"
            "\\"lots\\":%.2f,\\"open_price\\":%.5f,\\"sl\\":%.5f,"
            "\\"tp\\":%.5f,\\"profit\\":%.2f}",
            OrderTicket(), OrderSymbol(), OrderType(),
            OrderLots(), OrderOpenPrice(), OrderStopLoss(),
            OrderTakeProfit(), OrderProfit()
         );
      }
   }
   result += "]}";
   return result;
}

void PushTickData()
{
   string symbols[] = {"EURUSD", "GBPUSD", "USDCHF", "USDJPY"};
   for(int i = 0; i < ArraySize(symbols); i++)
   {
      string data = StringFormat(
         "{\\"type\\":\\"TICK\\",\\"symbol\\":\\"%s\\",\\"bid\\":%.5f,"
         "\\"ask\\":%.5f,\\"spread\\":%d}",
         symbols[i],
         MarketInfo(symbols[i], MODE_BID),
         MarketInfo(symbols[i], MODE_ASK),
         (int)MarketInfo(symbols[i], MODE_SPREAD)
      );
      ZmqMsg msg(data);
      pushSocket.send(msg, ZMQ_DONTWAIT);
   }
}

// ─── Simple JSON extraction helpers ───
int ExtractInt(string json, string key)
{
   string search = "\\"" + key + "\\":";
   int pos = StringFind(json, search);
   if(pos < 0) return 0;
   pos += StringLen(search);
   string val = "";
   for(int i = pos; i < StringLen(json); i++)
   {
      ushort c = StringGetCharacter(json, i);
      if(c == ',' || c == '}' || c == ' ') break;
      val += CharToString((uchar)c);
   }
   return (int)StringToInteger(val);
}

double ExtractDouble(string json, string key)
{
   string search = "\\"" + key + "\\":";
   int pos = StringFind(json, search);
   if(pos < 0) return 0;
   pos += StringLen(search);
   string val = "";
   for(int i = pos; i < StringLen(json); i++)
   {
      ushort c = StringGetCharacter(json, i);
      if(c == ',' || c == '}' || c == ' ') break;
      val += CharToString((uchar)c);
   }
   return StringToDouble(val);
}

string ExtractString(string json, string key)
{
   string search = "\\"" + key + "\\":\\"";
   int pos = StringFind(json, search);
   if(pos < 0) return "";
   pos += StringLen(search);
   string val = "";
   for(int i = pos; i < StringLen(json); i++)
   {
      ushort c = StringGetCharacter(json, i);
      if(c == '"') break;
      val += CharToString((uchar)c);
   }
   return val;
}
'''
