"""
╔══════════════════════════════════════════════════════════════════════╗
║              FOREXIA SIGNATURE AGENT — MT5 BRIDGE                   ║
║      MetaTrader 5 Python API — Direct Institutional Execution       ║
╚══════════════════════════════════════════════════════════════════════╝

This bridge connects directly to MetaTrader 5 using the official
MetaTrader5 Python package. Unlike the MT4 bridge which requires
ZeroMQ + an EA, MT5 connects natively via the Python API.

Setup:
  1. Install MetaTrader 5 terminal
  2. pip install MetaTrader5
  3. Configure account credentials in Settings
  4. The bridge handles everything else
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from backend.models.schemas import (
    AccountState, CandleData, TradeDirection, TradeRecord, TradeStatus
)

logger = logging.getLogger("forexia.mt5_bridge")

# Try to import MetaTrader5 — it's only available on Windows
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None
    logger.info("MetaTrader5 package not available (requires Windows + MT5 terminal)")


class MT5Bridge:
    """
    Direct connection to MetaTrader 5 via the official Python API.

    This bridge provides:
      - Native Python integration (no ZeroMQ needed)
      - Account login with credentials
      - Trade execution, modification, closure
      - Historical candle data retrieval
      - Live price streaming
    """

    def __init__(self):
        self._connected = False
        self._account_state = AccountState()
        self._latest_prices: Dict[str, Dict[str, float]] = {}
        self._login: Optional[int] = None
        self._password: Optional[str] = None
        self._server: Optional[str] = None
        self._mt5_path: Optional[str] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

    # ─────────────────────────────────────────────────────────────────
    #  CONFIGURATION
    # ─────────────────────────────────────────────────────────────────

    def configure(
        self,
        login: int,
        password: str,
        server: str,
        mt5_path: Optional[str] = None
    ):
        """Set MT5 account credentials."""
        self._login = login
        self._password = password
        self._server = server
        self._mt5_path = mt5_path
        logger.info(f"MT5 configured — Login: {login}, Server: {server}")

    # ─────────────────────────────────────────────────────────────────
    #  CONNECTION LIFECYCLE
    # ─────────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """
        Initialize MT5 terminal and log in to the trading account.
        Returns True if connection is successful.
        """
        if not MT5_AVAILABLE:
            logger.warning(
                "MT5 bridge unavailable — MetaTrader5 package not installed. "
                "Install with: pip install MetaTrader5 (Windows only)"
            )
            return False

        try:
            # Initialize MT5
            init_kwargs = {}
            if self._mt5_path:
                init_kwargs["path"] = self._mt5_path

            if not mt5.initialize(**init_kwargs):
                error = mt5.last_error()
                logger.error(f"MT5 initialization failed: {error}")
                return False

            # Login if credentials provided
            if self._login and self._password and self._server:
                authorized = mt5.login(
                    login=self._login,
                    password=self._password,
                    server=self._server,
                )
                if not authorized:
                    error = mt5.last_error()
                    logger.error(f"MT5 login failed: {error}")
                    mt5.shutdown()
                    return False

                logger.info(
                    f"═══ MT5 BRIDGE CONNECTED ═══\n"
                    f"    Account: {self._login}\n"
                    f"    Server: {self._server}"
                )

            self._connected = True

            # Start heartbeat
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # Get initial account state
            self._account_state = await self.get_account_state()

            return True

        except Exception as e:
            logger.error(f"MT5 connection error: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Shut down MT5 connection."""
        self._connected = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        if MT5_AVAILABLE and mt5:
            try:
                mt5.shutdown()
            except Exception:
                pass

        logger.info("MT5 Bridge disconnected")

    @property
    def is_connected(self) -> bool:
        if not MT5_AVAILABLE or not self._connected:
            return False
        try:
            info = mt5.terminal_info()
            return info is not None
        except Exception:
            self._connected = False
            return False

    # ─────────────────────────────────────────────────────────────────
    #  TRADE EXECUTION
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
        Execute a market order on MT5.
        Returns the ticket/deal number on success, None on failure.
        """
        if not self.is_connected:
            logger.error("Cannot execute — MT5 not connected")
            return None

        order_type = mt5.ORDER_TYPE_BUY if direction == TradeDirection.BUY else mt5.ORDER_TYPE_SELL

        # Get current price
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"Cannot get price for {symbol}")
            return None

        price = tick.ask if direction == TradeDirection.BUY else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": round(lot_size, 2),
            "type": order_type,
            "price": price,
            "sl": round(stop_loss, 5),
            "tp": round(take_profit, 5),
            "deviation": 30,  # slippage in points
            "magic": 20260215,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        logger.info(
            f"══╡ MT5 EXECUTING {direction.value} {lot_size} {symbol} "
            f"@ {price} | SL: {stop_loss} | TP: {take_profit} ╞══"
        )

        result = mt5.order_send(request)

        if result is None:
            logger.error(f"MT5 order_send returned None: {mt5.last_error()}")
            return None

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"✓ MT5 Order filled — Deal #{result.deal}, Order #{result.order}")
            return result.order
        else:
            logger.error(
                f"✗ MT5 Order REJECTED — Code: {result.retcode}, "
                f"Comment: {result.comment}"
            )
            return None

    async def execute_limit_order(
        self,
        symbol: str,
        direction: TradeDirection,
        lot_size: float,
        price: float,
        stop_loss: float,
        take_profit: float,
        comment: str = "FOREXIA_LIMIT"
    ) -> Optional[int]:
        """
        Place a pending limit order on MT5.
        Used for index instruments (NASDAQ) where we want entry at a specific price.
        
        Returns the order ticket on success, None on failure.
        """
        if not self.is_connected:
            logger.error("Cannot execute — MT5 not connected")
            return None

        order_type = (
            mt5.ORDER_TYPE_BUY_LIMIT if direction == TradeDirection.BUY
            else mt5.ORDER_TYPE_SELL_LIMIT
        )

        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": round(lot_size, 2),
            "type": order_type,
            "price": round(price, 5),
            "sl": round(stop_loss, 5),
            "tp": round(take_profit, 5),
            "deviation": 30,
            "magic": 20260215,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        logger.info(
            f"══╡ MT5 LIMIT ORDER {direction.value} {lot_size} {symbol} "
            f"@ {price} | SL: {stop_loss} | TP: {take_profit} ╞══"
        )

        result = mt5.order_send(request)

        if result is None:
            logger.error(f"MT5 limit order_send returned None: {mt5.last_error()}")
            return None

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"✓ MT5 Limit Order placed — Order #{result.order}")
            return result.order
        else:
            logger.error(
                f"✗ MT5 Limit Order REJECTED — Code: {result.retcode}, "
                f"Comment: {result.comment}"
            )
            return None

    async def modify_trade(
        self,
        ticket: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """Modify SL/TP of an open position."""
        if not self.is_connected:
            return False

        position = mt5.positions_get(ticket=ticket)
        if not position:
            logger.error(f"Position #{ticket} not found")
            return False

        pos = position[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": pos.symbol,
            "position": ticket,
            "sl": round(stop_loss, 5) if stop_loss is not None else pos.sl,
            "tp": round(take_profit, 5) if take_profit is not None else pos.tp,
        }

        result = mt5.order_send(request)
        success = result and result.retcode == mt5.TRADE_RETCODE_DONE
        if success:
            logger.info(f"MT5 Position #{ticket} modified — SL: {stop_loss}, TP: {take_profit}")
        return success

    async def close_trade(self, ticket: int) -> bool:
        """Close an open position by ticket."""
        if not self.is_connected:
            return False

        position = mt5.positions_get(ticket=ticket)
        if not position:
            return False

        pos = position[0]
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(pos.symbol)
        price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 30,
            "magic": 20260215,
            "comment": "FOREXIA_CLOSE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        success = result and result.retcode == mt5.TRADE_RETCODE_DONE
        if success:
            logger.info(f"MT5 Position #{ticket} CLOSED")
        return success

    async def close_all_trades(self, symbol: Optional[str] = None) -> int:
        """Close all open positions, optionally filtered by symbol."""
        if not self.is_connected:
            return 0

        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if not positions:
            return 0

        closed = 0
        for pos in positions:
            if pos.magic == 20260215:
                success = await self.close_trade(pos.ticket)
                if success:
                    closed += 1

        logger.info(f"Closed {closed} MT5 positions {'for ' + symbol if symbol else '(all)'}")
        return closed

    # ─────────────────────────────────────────────────────────────────
    #  ACCOUNT & MARKET DATA
    # ─────────────────────────────────────────────────────────────────

    async def get_account_state(self) -> AccountState:
        """Get current account info from MT5."""
        if not self.is_connected:
            return self._account_state

        info = mt5.account_info()
        if info is None:
            return self._account_state

        positions = mt5.positions_get()
        open_count = len(positions) if positions else 0

        self._account_state = AccountState(
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.margin_free,
            margin_level=info.margin_level if info.margin_level else 0,
            open_trades=open_count,
            last_updated=datetime.now(timezone.utc),
        )
        return self._account_state

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "M15",
        count: int = 100
    ) -> List[CandleData]:
        """Get historical candle data from MT5."""
        if not self.is_connected:
            return []

        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
        }

        mt5_tf = tf_map.get(timeframe, mt5.TIMEFRAME_M15)
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)

        if rates is None or len(rates) == 0:
            return []

        candles = []
        for bar in rates:
            candles.append(CandleData(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.fromtimestamp(bar['time'], tz=timezone.utc),
                open=float(bar['open']),
                high=float(bar['high']),
                low=float(bar['low']),
                close=float(bar['close']),
                volume=float(bar['real_volume']) if 'real_volume' in bar.dtype.names else 0,
                tick_volume=int(bar['tick_volume']),
            ))

        return candles

    async def get_current_price(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get current bid/ask/spread for a symbol."""
        if not self.is_connected:
            return self._latest_prices.get(symbol)

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return self._latest_prices.get(symbol)

        price = {
            "bid": tick.bid,
            "ask": tick.ask,
            "spread": int((tick.ask - tick.bid) * 100000),  # convert to points
        }
        self._latest_prices[symbol] = price
        return price

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all currently open positions."""
        if not self.is_connected:
            return []

        positions = mt5.positions_get()
        if not positions:
            return []

        result = []
        for pos in positions:
            if pos.magic == 20260215:
                result.append({
                    "ticket": pos.ticket,
                    "symbol": pos.symbol,
                    "type": pos.type,
                    "lots": pos.volume,
                    "open_price": pos.price_open,
                    "sl": pos.sl,
                    "tp": pos.tp,
                    "profit": pos.profit,
                })
        return result

    # ─────────────────────────────────────────────────────────────────
    #  BACKGROUND TASKS
    # ─────────────────────────────────────────────────────────────────

    async def _heartbeat_loop(self):
        """Verify MT5 connection periodically."""
        while self._connected:
            try:
                await asyncio.sleep(5)
                if MT5_AVAILABLE:
                    info = mt5.terminal_info()
                    if info is None:
                        logger.warning("MT5 heartbeat FAILED — terminal not responding")
                        self._connected = False
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"MT5 heartbeat error: {e}")
                await asyncio.sleep(3)
