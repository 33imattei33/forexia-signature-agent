"""
╔══════════════════════════════════════════════════════════════════════╗
║        FOREXIA SIGNATURE AGENT — REMOTE MT5 BRIDGE                  ║
║   Cross-Platform MT5 Access via Self-Hosted REST Server             ║
╚══════════════════════════════════════════════════════════════════════╝

This bridge connects to a lightweight MT5 Remote Server
(tools/mt5_remote_server.py) running on any Windows machine.

No third-party accounts needed. You run the server yourself.
The bridge communicates via simple HTTP/JSON — works from any OS.

Setup:
  1. Copy tools/mt5_remote_server.py to a Windows PC with MT5
  2. pip install fastapi uvicorn MetaTrader5
  3. python mt5_remote_server.py
  4. Enter the server URL + auth key in Forexia Settings
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import httpx

from backend.models.schemas import (
    AccountState, CandleData, TradeDirection, TradeRecord, TradeStatus
)

logger = logging.getLogger("forexia.remote_mt5_bridge")


class RemoteMT5Bridge:
    """
    REST client that connects to the Forexia MT5 Remote Server.

    This bridge enables cross-platform MT5 access by proxying all
    MT5 operations through a small HTTP server running on Windows.

    Requires:
      - A Windows machine running tools/mt5_remote_server.py
      - Network connectivity between this machine and the server
      - Server URL and auth key configured in settings
    """

    def __init__(self):
        self._connected = False
        self._account_state = AccountState()
        self._latest_prices: Dict[str, Dict[str, float]] = {}
        self._server_url: Optional[str] = None
        self._auth_key: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

    # ─────────────────────────────────────────────────────────────────
    #  CONFIGURATION
    # ─────────────────────────────────────────────────────────────────

    def configure(self, server_url: str, auth_key: str):
        """Set remote server connection details."""
        # Strip trailing slash
        self._server_url = server_url.rstrip("/")
        self._auth_key = auth_key
        logger.info(f"Remote MT5 configured — Server: {self._server_url}")

    # ─────────────────────────────────────────────────────────────────
    #  HTTP HELPERS
    # ─────────────────────────────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._auth_key or ''}",
            "Content-Type": "application/json",
        }

    async def _get(self, path: str) -> Optional[Any]:
        """GET request to the remote MT5 server."""
        try:
            resp = await self._client.get(
                f"{self._server_url}{path}",
                headers=self._headers(),
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
            logger.error(f"Remote MT5 GET {path} — HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        except httpx.ConnectError:
            logger.error(f"Remote MT5 server unreachable at {self._server_url}")
            return None
        except Exception as e:
            logger.error(f"Remote MT5 GET error: {e}")
            return None

    async def _post(self, path: str, data: Dict = None) -> Optional[Any]:
        """POST request to the remote MT5 server."""
        try:
            resp = await self._client.post(
                f"{self._server_url}{path}",
                headers=self._headers(),
                json=data or {},
                timeout=30,
            )
            if resp.status_code in (200, 201):
                return resp.json()
            logger.error(f"Remote MT5 POST {path} — HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        except httpx.ConnectError:
            logger.error(f"Remote MT5 server unreachable at {self._server_url}")
            return None
        except Exception as e:
            logger.error(f"Remote MT5 POST error: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────
    #  CONNECTION LIFECYCLE
    # ─────────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """
        Connect to the Remote MT5 Server and verify it's alive.
        Returns True if the server is reachable and MT5 is connected.
        """
        if not self._server_url or not self._auth_key:
            logger.warning("Remote MT5 bridge: server URL or auth key not configured")
            return False

        try:
            self._client = httpx.AsyncClient()

            # Verify server is reachable and MT5 is connected
            data = await self._get("/health")
            if not data:
                logger.error(
                    f"Remote MT5 server not reachable at {self._server_url}. "
                    "Check the server is running and the URL is correct."
                )
                return False

            if not data.get("connected"):
                logger.warning("Remote MT5 server is running but MT5 is not connected")
                return False

            logger.info(
                f"Remote MT5 server verified — "
                f"Account: {data.get('account')}, "
                f"Server: {data.get('server')}"
            )

            # Get initial account state
            account_data = await self._get("/account")
            if account_data:
                self._account_state = self._parse_account(account_data)
                self._connected = True

                logger.info(
                    f"═══ REMOTE MT5 BRIDGE CONNECTED ═══\n"
                    f"    Balance: ${self._account_state.balance:.2f}\n"
                    f"    Equity: ${self._account_state.equity:.2f}\n"
                    f"    Server: {self._server_url}"
                )

                # Start heartbeat
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                return True
            else:
                logger.error("Could not fetch account data from remote server")
                return False

        except Exception as e:
            logger.error(f"Remote MT5 connection error: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Disconnect from the remote server."""
        self._connected = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        if self._client:
            await self._client.aclose()
            self._client = None

        logger.info("Remote MT5 Bridge disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ─────────────────────────────────────────────────────────────────
    #  ACCOUNT INFO
    # ─────────────────────────────────────────────────────────────────

    def _parse_account(self, data: Dict) -> AccountState:
        """Parse remote server account data into AccountState."""
        return AccountState(
            balance=data.get("balance", 0.0),
            equity=data.get("equity", 0.0),
            margin=data.get("margin", 0.0),
            free_margin=data.get("free_margin", 0.0),
            margin_level=data.get("margin_level", 0.0),
            open_trades=data.get("open_trades", 0),
            last_updated=datetime.now(timezone.utc),
        )

    async def get_account_state(self) -> AccountState:
        """Get current account info from the remote MT5 server."""
        if not self._connected or not self._client:
            return self._account_state

        data = await self._get("/account")
        if data:
            self._account_state = self._parse_account(data)

        return self._account_state

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
        """Execute a market order via the remote MT5 server."""
        if not self._connected:
            logger.error("Cannot execute — Remote MT5 bridge not connected")
            return None

        result = await self._post("/trade/open", {
            "symbol": symbol,
            "direction": direction.value,
            "volume": round(lot_size, 2),
            "sl": round(stop_loss, 5),
            "tp": round(take_profit, 5),
            "comment": comment,
        })

        if result and result.get("status") == "OK":
            order_id = result.get("order", 0)
            logger.info(
                f"Remote MT5 order executed — "
                f"{direction.value} {lot_size} {symbol}, Order #{order_id}"
            )
            return order_id

        error_msg = result.get("message", "Unknown error") if result else "No response"
        logger.error(f"Remote MT5 order failed: {error_msg}")
        return None

    async def modify_trade(
        self,
        ticket: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """Modify SL/TP of an open position via the remote server."""
        if not self._connected:
            return False

        data: Dict[str, Any] = {"ticket": ticket}
        if stop_loss is not None:
            data["sl"] = round(stop_loss, 5)
        if take_profit is not None:
            data["tp"] = round(take_profit, 5)

        result = await self._post("/trade/modify", data)
        return bool(result and result.get("modified"))

    async def close_trade(self, ticket: int) -> bool:
        """Close an open position via the remote server."""
        if not self._connected:
            return False

        result = await self._post("/trade/close", {"ticket": ticket})
        if result and result.get("closed"):
            logger.info(f"Remote MT5 position #{ticket} CLOSED")
            return True
        return False

    async def close_all_trades(self, symbol: Optional[str] = None) -> int:
        """Close all open positions via the remote server."""
        if not self._connected:
            return 0

        data = {"symbol": symbol} if symbol else {}
        result = await self._post("/trade/close-all", data)
        if result:
            closed = result.get("closed", 0)
            logger.info(f"Remote MT5 closed {closed} positions")
            return closed
        return 0

    # ─────────────────────────────────────────────────────────────────
    #  MARKET DATA
    # ─────────────────────────────────────────────────────────────────

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "M15",
        count: int = 100
    ) -> List[CandleData]:
        """Get historical candle data from the remote MT5 server."""
        if not self._connected or not self._client:
            return []

        data = await self._get(f"/candles/{symbol}?timeframe={timeframe}&count={count}")
        if not data or not isinstance(data, list):
            return []

        candles = []
        for bar in data:
            try:
                candles.append(CandleData(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=datetime.fromisoformat(
                        bar.get("time", "").replace("Z", "+00:00")
                    ),
                    open=float(bar.get("open", 0)),
                    high=float(bar.get("high", 0)),
                    low=float(bar.get("low", 0)),
                    close=float(bar.get("close", 0)),
                    volume=float(bar.get("tick_volume", 0)),
                    tick_volume=int(bar.get("tick_volume", 0)),
                ))
            except Exception as e:
                logger.debug(f"Skipping candle parse error: {e}")
                continue

        return candles

    async def get_current_price(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get current bid/ask for a symbol via the remote server."""
        if not self._connected or not self._client:
            return self._latest_prices.get(symbol)

        data = await self._get(f"/price/{symbol}")
        if data:
            price = {
                "bid": data.get("bid", 0),
                "ask": data.get("ask", 0),
                "spread": data.get("spread", 0),
            }
            self._latest_prices[symbol] = price
            return price

        return self._latest_prices.get(symbol)

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions from the remote server."""
        if not self._connected or not self._client:
            return []

        data = await self._get("/positions")
        if not data or not isinstance(data, list):
            return []

        result = []
        for pos in data:
            result.append({
                "ticket": pos.get("ticket", 0),
                "symbol": pos.get("symbol", ""),
                "type": pos.get("type", 0),
                "lots": pos.get("volume", 0),
                "open_price": pos.get("open_price", 0),
                "sl": pos.get("sl", 0),
                "tp": pos.get("tp", 0),
                "profit": pos.get("profit", 0),
                "comment": pos.get("comment", ""),
                "magic": pos.get("magic", 0),
            })
        return result

    # ─────────────────────────────────────────────────────────────────
    #  BACKGROUND TASKS
    # ─────────────────────────────────────────────────────────────────

    async def _heartbeat_loop(self):
        """Periodically verify remote server connection and refresh account data."""
        while self._connected:
            try:
                await asyncio.sleep(10)
                data = await self._get("/account")
                if data:
                    self._account_state = self._parse_account(data)
                else:
                    logger.warning("Remote MT5 heartbeat — server not responding")
                    # Don't immediately disconnect — it might be a temporary issue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Remote MT5 heartbeat error: {e}")
                await asyncio.sleep(5)
