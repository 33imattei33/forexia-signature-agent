"""
╔══════════════════════════════════════════════════════════════════════╗
║        FOREXIA SIGNATURE AGENT — MATCHTRADER BRIDGE                 ║
║   Cross-Platform Broker Access via MatchTrader Platform API         ║
╚══════════════════════════════════════════════════════════════════════╝

Connects to any broker running on the MatchTrader platform via the
official MatchTrader Platform REST API.

Works from macOS, Linux, and Windows — no MetaTrader terminal required.

MatchTrader Platform API Reference:
  https://app.theneo.io/match-trade/platform-api

Authentication Flow:
  1. POST /manager/mtr-login → returns session `token` + `tradingApiToken`
  2. `token` is used as Cookie: co-auth={token}
  3. `tradingApiToken` is used as Header: Auth-trading-api
  4. Tokens valid 15 min — refresh via POST /manager/refresh-token
  5. Login response includes `systemUUID` for trading endpoint paths

Trading Endpoints:
  All trading endpoints follow pattern: /mtr-api/{SYSTEM_UUID}/...
  - GET  /balance          → account balance, equity, margin
  - GET  /quotations       → current bid/ask prices
  - GET  /open-positions   → list open positions
  - POST /position/open    → open a new position
  - POST /position/edit    → modify SL/TP on existing position
  - POST /position/close   → close a position
  - GET  /candles          → historical candle data
  - GET  /effective-instruments → available symbols

Tested with: E8 Markets (https://mtr.e8markets.com, partnerId: 2)
"""

import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from curl_cffi.requests import AsyncSession as CffiAsyncSession

from backend.models.schemas import (
    AccountState, CandleData, TradeDirection, TradeRecord, TradeStatus
)

logger = logging.getLogger("forexia.matchtrader_bridge")

# MatchTrader interval names (used directly — same as our timeframe names)
TIMEFRAME_MAP = {
    "M1": "M1", "M5": "M5", "M15": "M15", "M30": "M30",
    "H1": "H1", "H4": "H4", "D1": "D1", "W1": "W1", "MN": "MN",
    # Accept lowercase too
    "m1": "M1", "m5": "M5", "m15": "M15", "m30": "M30",
    "h1": "H1", "h4": "H4", "d1": "D1", "w1": "W1", "mn": "MN",
}


class MatchTraderBridge:
    """
    REST API bridge for MatchTrader-based brokers.

    Uses the official MatchTrader Platform API with dual-token auth:
      - Session token (Cookie: co-auth=...)
      - Trading API token (Header: Auth-trading-api)

    Compatible with any broker on the MatchTrader platform
    (E8 Markets, Match-Trader Demo, etc.)
    """

    def __init__(self):
        self._connected = False
        self._account_state = AccountState()
        self._latest_prices: Dict[str, Dict[str, float]] = {}

        # Connection config
        self._base_url: Optional[str] = None
        self._login: Optional[str] = None      # email
        self._password: Optional[str] = None
        self._partner_id: Optional[str] = None  # brokerId / partnerId

        # Auth state (dual-token system)
        self._session_token: Optional[str] = None      # Cookie: co-auth={token}
        self._trading_api_token: Optional[str] = None   # Header: Auth-trading-api
        self._system_uuid: Optional[str] = None         # For /mtr-api/{uuid}/... paths
        self._trading_api_domain: Optional[str] = None  # Separate domain for trading API (if any)
        self._trading_account_id: Optional[str] = None
        self._account_currency: str = "USD"
        self._leverage: int = 100

        # Instrument symbol mapping (e.g. GBPUSD → GBPUSD.)
        self._instrument_map: Dict[str, str] = {}  # clean_name → broker_name
        self._broker_instruments: List[str] = []     # raw list from API

        # HTTP client (curl_cffi with Chrome TLS fingerprint to bypass Cloudflare)
        self._client: Optional[CffiAsyncSession] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._token_refresh_task: Optional[asyncio.Task] = None
        self._token_obtained_at: Optional[datetime] = None

    # ─────────────────────────────────────────────────────────────────
    #  CONFIGURATION
    # ─────────────────────────────────────────────────────────────────

    def configure(
        self,
        base_url: str,
        login: str,
        password: str,
        partner_id: str = "",
    ):
        """
        Set MatchTrader connection details.

        Args:
            base_url: Broker's MatchTrader platform URL
                      (e.g. https://mtr.e8markets.com)
            login:    Email address used to log in
            password: Account password
            partner_id: Broker's partnerId/brokerId
                        (auto-discovered if empty)
        """
        self._base_url = base_url.rstrip("/")
        self._login = login
        self._password = password
        self._partner_id = partner_id
        logger.info(f"MatchTrader configured — Server: {self._base_url}")

    # ─────────────────────────────────────────────────────────────────
    #  HTTP HELPERS
    # ─────────────────────────────────────────────────────────────────

    def _auth_headers(self) -> Dict[str, str]:
        """Build headers with both auth tokens for trading API calls."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._trading_api_token:
            headers["Auth-trading-api"] = self._trading_api_token
        if self._session_token:
            headers["Cookie"] = f"co-auth={self._session_token}"
        return headers

    def _trading_base(self) -> str:
        """
        Base URL for trading API calls (/mtr-api/...).
        Uses tradingApiDomain if available, otherwise falls back to base_url.
        """
        if self._trading_api_domain:
            domain = self._trading_api_domain.rstrip("/")
            if not domain.startswith("http"):
                domain = f"https://{domain}"
            return domain
        return self._base_url

    def _mtr_path(self, endpoint: str) -> str:
        """Build full URL for a trading API endpoint."""
        return f"{self._trading_base()}/mtr-api/{self._system_uuid}/{endpoint}"

    def _resolve_symbol(self, symbol: str) -> str:
        """
        Resolve a clean symbol name to the broker's actual instrument name.
        E.g. 'GBPUSD' → 'GBPUSD.' for E8 Markets.
        Falls back to the original symbol if no mapping found.
        """
        clean = symbol.upper().rstrip(".")
        # Direct match in map
        if clean in self._instrument_map:
            return self._instrument_map[clean]
        # Already a valid broker name
        if symbol in self._broker_instruments:
            return symbol
        # Try with dot suffix (common for MatchTrader brokers)
        if f"{clean}." in self._broker_instruments:
            self._instrument_map[clean] = f"{clean}."
            return f"{clean}."
        return symbol

    def _clean_symbol(self, broker_symbol: str) -> str:
        """Strip broker suffix from symbol for display (e.g. GBPUSD. → GBPUSD)."""
        return broker_symbol.rstrip(".")

    async def _fetch_instruments(self):
        """Fetch available instruments and build symbol mapping."""
        try:
            url = self._mtr_path("effective-instruments")
            data = await self._get(url)
            if not data:
                logger.warning("Could not fetch instruments — symbol mapping unavailable")
                return

            instruments = []
            if isinstance(data, list):
                instruments = data
            elif isinstance(data, dict):
                instruments = data.get("instruments", data.get("symbols", []))

            for inst in instruments:
                if isinstance(inst, str):
                    name = inst
                elif isinstance(inst, dict):
                    name = inst.get("symbol") or inst.get("alias") or inst.get("name") or ""
                else:
                    continue
                if name:
                    self._broker_instruments.append(name)
                    # Map clean name → broker name
                    clean = name.rstrip(".")
                    self._instrument_map[clean] = name

            logger.info(
                f"MatchTrader instruments loaded — {len(self._broker_instruments)} symbols available "
                f"(sample: {', '.join(self._broker_instruments[:5])})"
            )
        except Exception as e:
            logger.warning(f"Failed to fetch instruments: {e}")

    async def _get(self, url: str, params: Dict = None) -> Optional[Any]:
        """GET request with auto-refresh on 401."""
        try:
            resp = await self._client.get(
                url,
                headers=self._auth_headers(),
                params=params,
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 401:
                logger.warning("MatchTrader 401 — refreshing token...")
                if await self._refresh_auth():
                    resp = await self._client.get(
                        url,
                        headers=self._auth_headers(),
                        params=params,
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        return resp.json()
            logger.error(f"MatchTrader GET {url} — HTTP {resp.status_code}: {resp.text[:300]}")
            return None
        except ConnectionError:
            logger.error(f"MatchTrader API unreachable: {url}")
            return None
        except Exception as e:
            logger.error(f"MatchTrader GET error: {e}")
            return None

    async def _post(self, url: str, data: Dict = None) -> Optional[Any]:
        """POST request with auto-refresh on 401."""
        try:
            resp = await self._client.post(
                url,
                headers=self._auth_headers(),
                json=data or {},
                timeout=30,
            )
            if resp.status_code in (200, 201):
                try:
                    return resp.json()
                except Exception:
                    return {"status": "OK"}
            if resp.status_code == 401 and self._session_token:
                logger.warning("MatchTrader 401 — refreshing token...")
                if await self._refresh_auth():
                    resp = await self._client.post(
                        url,
                        headers=self._auth_headers(),
                        json=data or {},
                        timeout=30,
                    )
                    if resp.status_code in (200, 201):
                        try:
                            return resp.json()
                        except Exception:
                            return {"status": "OK"}
            logger.error(f"MatchTrader POST {url} — HTTP {resp.status_code}: {resp.text[:300]}")
            return None
        except ConnectionError:
            logger.error(f"MatchTrader API unreachable: {url}")
            return None
        except Exception as e:
            logger.error(f"MatchTrader POST error: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────
    #  AUTHENTICATION — MatchTrader Platform API
    # ─────────────────────────────────────────────────────────────────

    async def _discover_partner_id(self) -> Optional[str]:
        """
        Auto-discover brokerId/partnerId via /manager/platform-details.
        This endpoint doesn't require authentication.
        """
        try:
            resp = await self._client.get(
                f"{self._base_url}/manager/platform-details",
                headers={"Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                partner_id = str(data.get("partnerId", ""))
                broker_name = data.get("brokerName", "Unknown")
                logger.info(
                    f"MatchTrader platform discovered — "
                    f"Broker: {broker_name}, partnerId: {partner_id}"
                )
                return partner_id
        except Exception as e:
            logger.warning(f"Could not auto-discover partnerId: {e}")
        return None

    async def _authenticate(self) -> bool:
        """
        Authenticate via POST /manager/mtr-login.

        The login response contains:
          - token: session token (used as Cookie: co-auth={token})
          - tradingApiToken: trading API token (header: Auth-trading-api)
          - selectedTradingAccount.offer.system.uuid: system UUID for API paths
          - selectedTradingAccount.offer.system.tradingApiDomain: trading API domain
        """
        # Always auto-discover partnerId from the platform
        discovered = await self._discover_partner_id()
        if discovered:
            if self._partner_id and self._partner_id != discovered:
                logger.info(
                    f"Overriding configured partnerId '{self._partner_id}' "
                    f"with auto-discovered '{discovered}'"
                )
            self._partner_id = discovered
        elif not self._partner_id:
            logger.error(
                "MatchTrader brokerId/partnerId is required and could not be auto-discovered. "
                "Set it manually in Settings."
            )
            return False

        login_payload = {
            "email": self._login,
            "password": self._password,
            "brokerId": self._partner_id,
        }

        try:
            resp = await self._client.post(
                f"{self._base_url}/manager/mtr-login",
                json=login_payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )

            if resp.status_code == 200:
                data = resp.json()
                return self._extract_auth_from_login(data)

            elif resp.status_code == 401:
                logger.error(
                    "MatchTrader login failed (401) — invalid email or password. "
                    "Use the same email and password you use to log in at "
                    f"{self._base_url}/app/trade (the MatchTrader web platform)."
                )
                return False
            elif resp.status_code == 403:
                logger.error(
                    "MatchTrader login blocked (403). "
                    "The broker may have Cloudflare protection or IP restrictions."
                )
                return False
            else:
                body = resp.text[:500]
                logger.error(f"MatchTrader login failed — HTTP {resp.status_code}: {body}")
                return False

        except ConnectionError:
            logger.error(f"Cannot reach MatchTrader API at {self._base_url}")
            return False
        except Exception as e:
            logger.error(f"MatchTrader login error: {e}")
            return False

    def _extract_auth_from_login(self, data: Dict[str, Any]) -> bool:
        """
        Extract auth tokens and system info from the login response.

        Handles both response formats:
          - Documented: selectedTradingAccount / tradingAccounts
          - E8 Markets actual: selectedAccount / accounts
        """
        # Session token (used as cookie)
        self._session_token = data.get("token")
        if not self._session_token:
            logger.error("Login response missing 'token'")
            return False

        # Get the selected trading account (try both key names)
        selected = (
            data.get("selectedTradingAccount")
            or data.get("selectedAccount")
        )
        if not selected:
            # Fall back to first in accounts list
            accounts = data.get("tradingAccounts") or data.get("accounts") or []
            if accounts:
                selected = accounts[0]
            else:
                logger.error(
                    "Login response has no trading accounts. "
                    f"Response keys: {list(data.keys())}"
                )
                return False

        # Trading API token
        self._trading_api_token = selected.get("tradingApiToken")
        if not self._trading_api_token:
            logger.error("Login response missing 'tradingApiToken'")
            return False

        # Trading account ID
        self._trading_account_id = str(selected.get("tradingAccountId", ""))

        # System UUID (needed for /mtr-api/{uuid}/... paths)
        offer = selected.get("offer", {})
        system = offer.get("system", {})
        self._system_uuid = system.get("uuid")
        if not self._system_uuid:
            logger.error("Login response missing system UUID")
            return False

        # Trading API domain (may be different from login domain)
        # Only use if it looks like a real public domain (ignore internal like http://ta-qfx-mtr:8080)
        trading_domain = system.get("tradingApiDomain", "").strip()
        if trading_domain and ("." in trading_domain) and not trading_domain.startswith("http://ta-"):
            self._trading_api_domain = trading_domain
            logger.info(f"Trading API domain: {self._trading_api_domain}")
        else:
            # Internal hostname — route through main base URL
            self._trading_api_domain = None
            if trading_domain:
                logger.info(f"Ignoring internal trading API domain: {trading_domain} (using base URL)")

        # Account metadata
        self._account_currency = offer.get("currency", "USD")
        self._leverage = selected.get("leverage") or offer.get("leverage") or 100

        # Token timestamp
        self._token_obtained_at = datetime.now(timezone.utc)

        # Log account info
        account_email = data.get("email", "")
        offer_name = offer.get("name", "")

        logger.info(
            f"MatchTrader authenticated — "
            f"Account: {self._trading_account_id}, "
            f"Offer: {offer_name}, "
            f"User: {account_email}, "
            f"System: {self._system_uuid[:12]}..."
        )
        return True

    async def _refresh_auth(self) -> bool:
        """
        Refresh the session token via POST /manager/refresh-token.
        Falls back to full re-authentication if refresh fails.
        """
        if not self._session_token:
            return await self._authenticate()

        try:
            resp = await self._client.post(
                f"{self._base_url}/manager/refresh-token",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Cookie": f"co-auth={self._session_token}",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                # The refresh endpoint returns a new token
                # It may be in the response body or in Set-Cookie header
                try:
                    data = resp.json()
                    new_token = data.get("token")
                    if new_token:
                        self._session_token = new_token
                        self._token_obtained_at = datetime.now(timezone.utc)
                        logger.info("MatchTrader session token refreshed")
                        return True
                except Exception:
                    pass

                # Check Set-Cookie header for new token
                import re
                set_cookie = resp.headers.get("set-cookie", "")
                if "co-auth=" in set_cookie:
                    match = re.search(r'co-auth=([^;]+)', set_cookie)
                    if match:
                        self._session_token = match.group(1)
                        self._token_obtained_at = datetime.now(timezone.utc)
                        logger.info("MatchTrader session token refreshed (from cookie)")
                        return True

                # Token may have been refreshed even without clear response
                self._token_obtained_at = datetime.now(timezone.utc)
                logger.info("MatchTrader token refresh acknowledged")
                return True

        except Exception as e:
            logger.warning(f"Token refresh failed: {e}")

        # Refresh failed — full re-auth
        logger.info("Token refresh failed, re-authenticating...")
        return await self._authenticate()

    # ─────────────────────────────────────────────────────────────────
    #  CONNECTION LIFECYCLE
    # ─────────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """
        Connect to the MatchTrader API.
        Authenticates and fetches initial account data.
        """
        if not self._base_url or not self._login or not self._password:
            logger.warning("MatchTrader bridge: credentials not configured")
            return False

        try:
            self._client = CffiAsyncSession(
                impersonate="chrome",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                },
            )

            # Authenticate via /manager/mtr-login
            if not await self._authenticate():
                await self._client.close()
                self._client = None
                return False

            # Fetch account balance
            account_data = await self._fetch_balance()
            if account_data:
                self._account_state = account_data
                self._connected = True

                logger.info(
                    f"═══ MATCHTRADER BRIDGE CONNECTED ═══\n"
                    f"    Balance: ${self._account_state.balance:.2f}\n"
                    f"    Equity: ${self._account_state.equity:.2f}\n"
                    f"    Free Margin: ${self._account_state.free_margin:.2f}\n"
                    f"    Currency: {self._account_currency}\n"
                    f"    Leverage: 1:{self._leverage}\n"
                    f"    Server: {self._base_url}"
                )

                # Fetch available instruments for symbol mapping
                await self._fetch_instruments()

                # Start background tasks
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                self._token_refresh_task = asyncio.create_task(self._token_refresh_loop())
                return True
            else:
                logger.error(
                    "MatchTrader authenticated but could not fetch balance. "
                    "The trading API domain or system UUID may be incorrect."
                )
                # Still mark as connected — auth worked
                self._connected = True
                await self._fetch_instruments()
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                self._token_refresh_task = asyncio.create_task(self._token_refresh_loop())
                return True

        except Exception as e:
            logger.error(f"MatchTrader connection error: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Disconnect from the MatchTrader API."""
        self._connected = False
        self._session_token = None
        self._trading_api_token = None
        self._system_uuid = None

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        if self._token_refresh_task:
            self._token_refresh_task.cancel()
            self._token_refresh_task = None
        if self._client:
            await self._client.close()
            self._client = None

        logger.info("MatchTrader Bridge disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ─────────────────────────────────────────────────────────────────
    #  ACCOUNT INFO — GET /mtr-api/{uuid}/balance
    # ─────────────────────────────────────────────────────────────────

    async def _fetch_balance(self) -> Optional[AccountState]:
        """
        Fetch account balance via GET /mtr-api/{SYSTEM_UUID}/balance.

        Response:
        {
          "balance": "10000.00",
          "equity": "10000.00",
          "freeMargin": "10000.00",
          "marginLevel": "0",
          "credit": "0.00",
          "currency": "USD",
          "margin": "0.00",
          "profit": "0",
          "netProfit": "0",
          "currencyPrecision": 2
        }
        """
        url = self._mtr_path("balance")
        data = await self._get(url)
        if not data:
            return None

        def _num(val, default=0.0) -> float:
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        # Also count open positions
        open_count = 0
        positions = await self._get(self._mtr_path("open-positions"))
        if positions and isinstance(positions, dict):
            pos_list = positions.get("positions", [])
            open_count = len(pos_list)

        # Calculate unrealized P&L from broker data
        unrealized_pnl = _num(data.get("profit")) or _num(data.get("netProfit"))
        # Also try equity - balance as fallback
        if unrealized_pnl == 0.0:
            eq = _num(data.get("equity"))
            bal = _num(data.get("balance"))
            if eq > 0 and bal > 0:
                unrealized_pnl = round(eq - bal, 2)

        return AccountState(
            balance=_num(data.get("balance")),
            equity=_num(data.get("equity")),
            margin=_num(data.get("margin")),
            free_margin=_num(data.get("freeMargin")),
            margin_level=_num(data.get("marginLevel")),
            open_trades=open_count,
            daily_pnl=unrealized_pnl,
            last_updated=datetime.now(timezone.utc),
        )

    async def get_account_state(self) -> AccountState:
        """Get current account info from the MatchTrader API."""
        if not self._connected or not self._client:
            return self._account_state

        account = await self._fetch_balance()
        if account:
            self._account_state = account

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
        """
        Execute a market order via POST /mtr-api/{uuid}/position/open.

        Payload:
        {
          "instrument": "EURUSD",
          "orderSide": "BUY",
          "volume": 0.01,
          "slPrice": 0,       // 0 = no stop loss
          "tpPrice": 0,       // 0 = no take profit
          "isMobile": false
        }
        """
        if not self._connected:
            logger.error("Cannot execute — MatchTrader bridge not connected")
            return None

        order_side = "BUY" if direction == TradeDirection.BUY else "SELL"

        # Resolve symbol to broker's instrument name (e.g. GBPUSD → GBPUSD.)
        resolved_symbol = self._resolve_symbol(symbol)
        if resolved_symbol != symbol:
            logger.info(f"Symbol resolved: {symbol} → {resolved_symbol}")

        order_data = {
            "instrument": resolved_symbol,
            "orderSide": order_side,
            "volume": round(lot_size, 2),
            "slPrice": round(stop_loss, 5) if stop_loss else 0,
            "tpPrice": round(take_profit, 5) if take_profit else 0,
            "isMobile": False,
        }

        url = self._mtr_path("position/open")
        result = await self._post(url, order_data)

        if not result:
            logger.error(f"MatchTrader order failed — no response from {url}")
            return None

        status = (result.get("status") or "").upper()
        order_id = result.get("orderId", "")
        error_msg = result.get("errorMessage", "")

        if status == "OK":
            logger.info(
                f"MatchTrader order EXECUTED — "
                f"{order_side} {lot_size} {symbol}, "
                f"SL={stop_loss}, TP={take_profit}, "
                f"Order #{order_id}"
            )
            # Convert order ID to int (strip non-numeric prefix)
            try:
                return int("".join(filter(str.isdigit, str(order_id)))) or 1
            except (ValueError, TypeError):
                return 1
        else:
            logger.error(
                f"MatchTrader order REJECTED — "
                f"{order_side} {lot_size} {symbol}: "
                f"{error_msg or status}"
            )
            return None

    async def modify_trade(
        self,
        ticket: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """
        Modify SL/TP of an open position via POST /mtr-api/{uuid}/position/edit.

        Requires the position's instrument, side, and volume (fetched from open positions).
        """
        if not self._connected:
            return False

        # Find the position to get its details
        position = await self._find_position(str(ticket))
        if not position:
            logger.error(f"Position #{ticket} not found for modification")
            return False

        edit_data = {
            "instrument": position["symbol"],
            "id": position["id"],
            "orderSide": position["side"],
            "volume": float(position["volume"]),
            "slPrice": round(stop_loss, 5) if stop_loss is not None else float(position.get("stopLoss") or 0),
            "tpPrice": round(take_profit, 5) if take_profit is not None else float(position.get("takeProfit") or 0),
            "isMobile": False,
        }

        url = self._mtr_path("position/edit")
        result = await self._post(url, edit_data)

        if result and (result.get("status") or "").upper() == "OK":
            logger.info(f"MatchTrader position #{ticket} modified — SL={stop_loss}, TP={take_profit}")
            return True

        error_msg = (result or {}).get("errorMessage", "Unknown error")
        logger.error(f"MatchTrader modify failed for #{ticket}: {error_msg}")
        return False

    async def close_trade(self, ticket: int) -> bool:
        """Close an open position by numeric ticket (backward-compatible)."""
        return await self.close_by_id(str(ticket))

    async def close_by_id(self, search_key: str) -> bool:
        """
        Close an open position via POST /mtr-api/{uuid}/position/close.

        Accepts any identifier: original ID ("W168933563011635"),
        numeric ticket ("168933563011635"), or clean string.

        Payload:
        {
          "positionId": "W168933563011635",
          "instrument": "EURUSD",
          "orderSide": "BUY",
          "volume": "0.01"
        }
        """
        if not self._connected:
            logger.error(f"close_by_id('{search_key}'): Bridge not connected")
            return False

        # Find the position to get its details
        logger.info(f"close_by_id: Searching for position '{search_key}'...")
        position = await self._find_position(search_key)
        if not position:
            logger.error(
                f"close_by_id: Position '{search_key}' NOT FOUND. "
                f"Fetching all positions for debug..."
            )
            # Debug: list all current positions
            data = await self._get(self._mtr_path("open-positions"))
            if data and isinstance(data, dict):
                all_pos = data.get("positions", [])
                for p in all_pos:
                    logger.error(
                        f"  Available position: id='{p.get('id')}', "
                        f"symbol='{p.get('symbol')}', side='{p.get('side')}'"
                    )
            return False

        close_data = {
            "positionId": position["id"],
            "instrument": position["symbol"],
            "orderSide": position["side"],
            "volume": str(position["volume"]),
        }

        logger.info(
            f"close_by_id: Sending close request — "
            f"positionId={position['id']}, instrument={position['symbol']}, "
            f"orderSide={position['side']}, volume={position['volume']}"
        )

        url = self._mtr_path("position/close")
        result = await self._post(url, close_data)

        if result and (result.get("status") or "").upper() == "OK":
            logger.info(f"MatchTrader position {position['id']} CLOSED successfully")
            return True

        error_msg = (result or {}).get("errorMessage", "Unknown error")
        logger.error(
            f"MatchTrader close FAILED for {position['id']}: "
            f"error={error_msg}, full_response={result}"
        )
        return False

    async def close_all_trades(self, symbol: Optional[str] = None) -> int:
        """Close all open positions (optionally filtered by symbol)."""
        if not self._connected:
            return 0

        positions = await self.get_open_positions()
        if symbol:
            clean = symbol.upper().rstrip(".")
            positions = [p for p in positions if (p.get("symbol") or "").rstrip(".").upper() == clean]

        closed = 0
        for pos in positions:
            pos_id = pos.get("id") or str(pos.get("ticket", ""))
            if pos_id:
                # Use the original position ID string for closing
                position = await self._find_position(pos_id)
                if position:
                    close_data = {
                        "positionId": position["id"],
                        "instrument": position["symbol"],
                        "orderSide": position["side"],
                        "volume": str(position["volume"]),
                    }
                    url = self._mtr_path("position/close")
                    result = await self._post(url, close_data)
                    if result and (result.get("status") or "").upper() == "OK":
                        closed += 1

        logger.info(f"MatchTrader closed {closed}/{len(positions)} positions")
        return closed

    async def _find_position(self, ticket_str: str) -> Optional[Dict[str, Any]]:
        """Find an open position by its ID (or numeric part of ID)."""
        data = await self._get(self._mtr_path("open-positions"))
        if not data or not isinstance(data, dict):
            return None

        positions = data.get("positions", [])
        for pos in positions:
            pos_id = pos.get("id", "")
            # Match by exact ID or by numeric part
            numeric_part = "".join(filter(str.isdigit, pos_id))
            if pos_id == ticket_str or numeric_part == ticket_str or str(ticket_str) in pos_id:
                return {
                    "id": pos_id,
                    "symbol": pos.get("symbol") or pos.get("alias") or "",
                    "side": pos.get("side", "BUY"),
                    "volume": pos.get("volume", 0),
                    "stopLoss": pos.get("stopLoss"),
                    "takeProfit": pos.get("takeProfit"),
                    "openPrice": pos.get("openPrice"),
                    "profit": pos.get("profit"),
                }

        return None

    # ─────────────────────────────────────────────────────────────────
    #  MARKET DATA
    # ─────────────────────────────────────────────────────────────────

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "M15",
        count: int = 100
    ) -> List[CandleData]:
        """
        Get historical candle data via GET /mtr-api/{uuid}/candles.

        Query params: symbol, interval, from, to
        """
        if not self._connected or not self._client:
            return []

        # Resolve symbol to broker's instrument name
        resolved_symbol = self._resolve_symbol(symbol)
        interval = TIMEFRAME_MAP.get(timeframe, timeframe)

        # Calculate from/to based on count and timeframe
        now = datetime.now(timezone.utc)
        tf_minutes = {
            "M1": 1, "M5": 5, "M15": 15, "M30": 30,
            "H1": 60, "H4": 240, "D1": 1440, "W1": 10080, "MN": 43200,
        }
        minutes = tf_minutes.get(interval, 15) * count
        from_time = now - timedelta(minutes=minutes)

        params = {
            "symbol": resolved_symbol,
            "interval": interval,
            "from": from_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        url = self._mtr_path("candles")
        data = await self._get(url, params)
        if not data:
            return []

        return self._parse_candles(data, symbol, timeframe)

    def _parse_candles(self, data: Any, symbol: str, timeframe: str) -> List[CandleData]:
        """Parse candle data from MatchTrader response."""
        candles_list = []
        if isinstance(data, dict):
            candles_list = data.get("candles", [])
        elif isinstance(data, list):
            candles_list = data

        result = []
        for bar in candles_list:
            try:
                time_val = bar.get("time")
                if isinstance(time_val, (int, float)):
                    # Millisecond timestamp
                    if time_val > 1e12:
                        time_val = time_val / 1000
                    ts = datetime.fromtimestamp(time_val, tz=timezone.utc)
                elif isinstance(time_val, str):
                    ts = datetime.fromisoformat(time_val.replace("Z", "+00:00"))
                else:
                    continue

                result.append(CandleData(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=ts,
                    open=float(bar.get("open", 0)),
                    high=float(bar.get("high", 0)),
                    low=float(bar.get("low", 0)),
                    close=float(bar.get("close", 0)),
                    volume=float(bar.get("volume", 0)),
                    tick_volume=int(bar.get("volume", 0)),
                ))
            except Exception as e:
                logger.debug(f"Skipping candle parse error: {e}")
                continue

        return result

    async def get_current_price(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        Get current bid/ask via GET /mtr-api/{uuid}/quotations?symbols=EURUSD.
        """
        if not self._connected or not self._client:
            return self._latest_prices.get(symbol)

        resolved_symbol = self._resolve_symbol(symbol)
        url = self._mtr_path("quotations")
        data = await self._get(url, {"symbols": resolved_symbol})

        if data and isinstance(data, list) and len(data) > 0:
            quote = data[0]
            bid = float(quote.get("bid", 0))
            ask = float(quote.get("ask", 0))

            if bid > 0 and ask > 0:
                # Calculate pip size based on symbol
                pip_factor = 100 if "JPY" in symbol else 100000
                price = {
                    "bid": bid,
                    "ask": ask,
                    "spread": round((ask - bid) * pip_factor, 1),
                }
                self._latest_prices[symbol] = price
                return price

        return self._latest_prices.get(symbol)

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions via GET /mtr-api/{uuid}/open-positions.
        """
        if not self._connected or not self._client:
            return []

        data = await self._get(self._mtr_path("open-positions"))
        if not data or not isinstance(data, dict):
            return []

        positions = data.get("positions", [])
        result = []

        for pos in positions:
            side = (pos.get("side") or "BUY").upper()
            trade_type = 0 if side == "BUY" else 1

            # Extract numeric ticket from ID (e.g. "W6910422326264457" → 6910422326264457)
            pos_id = pos.get("id", "0")
            try:
                numeric_id = int("".join(filter(str.isdigit, str(pos_id))))
            except (ValueError, TypeError):
                numeric_id = 0

            result.append({
                "ticket": numeric_id,
                "id": pos_id,  # Keep original ID for API calls
                "symbol": pos.get("symbol") or pos.get("alias") or "",
                "type": trade_type,
                "lots": float(pos.get("volume", 0)),
                "open_price": float(pos.get("openPrice", 0)),
                "sl": float(pos.get("stopLoss") or 0),
                "tp": float(pos.get("takeProfit") or 0),
                "profit": float(pos.get("profit") or pos.get("netProfit") or 0),
                "swap": float(pos.get("swap") or 0),
                "commission": float(pos.get("commission") or 0),
                "comment": "",
                "magic": 0,
            })

        return result

    # ─────────────────────────────────────────────────────────────────
    #  TRADE HISTORY — Closed positions / deals
    # ─────────────────────────────────────────────────────────────────

    async def get_trade_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Fetch closed trades / deals from MatchTrader.

        Uses POST /mtr-api/{uuid}/closed-positions with date range body.
        """
        if not self._connected or not self._client:
            return []

        from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:59Z")

        url = self._mtr_path("closed-positions")
        data = None
        try:
            data = await self._post(url, {"from": from_date, "to": to_date})
            if data:
                logger.info("Trade history fetched from /closed-positions (POST)")
        except Exception as e:
            logger.error(f"Trade history fetch failed: {e}")

        if not data:
            logger.debug("No trade history endpoint available — returning agent-tracked history")
            return []

        # Parse the response (MatchTrader closed-positions format)
        trades = []
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("operations", data.get("deals", data.get("trades", data.get("positions", data.get("history", [])))))

        for item in items:
            try:
                side = (item.get("side") or item.get("orderSide") or "BUY").upper()
                symbol = self._clean_symbol(item.get("symbol") or item.get("instrument") or item.get("alias") or "")
                volume = float(item.get("volume") or item.get("lots") or 0)
                profit = float(item.get("profit") or item.get("netProfit") or 0)
                swap = float(item.get("swap") or 0)
                commission = float(item.get("commission") or 0)
                open_price = float(item.get("openPrice") or item.get("entryPrice") or 0)
                close_price = float(item.get("closePrice") or item.get("exitPrice") or 0)

                # Parse timestamps
                open_time = item.get("openTime") or item.get("openDate") or ""
                close_time = item.get("time") or item.get("closeTime") or item.get("closeDate") or ""
                close_reason = item.get("closeReason") or ""

                trades.append({
                    "id": item.get("id") or item.get("dealId") or "",
                    "symbol": symbol,
                    "side": side,
                    "volume": volume,
                    "open_price": open_price,
                    "close_price": close_price,
                    "profit": round(profit, 2),
                    "swap": round(swap, 2),
                    "commission": round(commission, 2),
                    "net_profit": round(profit + swap + commission, 2),
                    "open_time": str(open_time),
                    "close_time": str(close_time),
                    "close_reason": close_reason,
                    "status": "closed",
                })
            except Exception as e:
                logger.debug(f"Skipping trade history item: {e}")
                continue

        logger.info(f"Trade history: {len(trades)} closed trades loaded")
        return trades

    # ─────────────────────────────────────────────────────────────────
    #  BACKGROUND TASKS
    # ─────────────────────────────────────────────────────────────────

    async def _heartbeat_loop(self):
        """Periodically refresh account data (every 10 seconds)."""
        while self._connected:
            try:
                await asyncio.sleep(10)
                account = await self._fetch_balance()
                if account:
                    self._account_state = account
                else:
                    logger.warning("MatchTrader heartbeat — could not fetch balance")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"MatchTrader heartbeat error: {e}")
                await asyncio.sleep(5)

    async def _token_refresh_loop(self):
        """
        Refresh the session token every 12 minutes.
        MatchTrader tokens expire after 15 minutes.
        """
        while self._connected:
            try:
                await asyncio.sleep(12 * 60)  # 12 minutes
                if self._connected:
                    await self._refresh_auth()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Token refresh error: {e}")
                await asyncio.sleep(60)
