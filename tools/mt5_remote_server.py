"""
╔══════════════════════════════════════════════════════════════════════╗
║        FOREXIA — MT5 REMOTE SERVER (Run this on Windows)            ║
║    Exposes your MT5 account over REST API for cross-platform use    ║
╚══════════════════════════════════════════════════════════════════════╝

HOW TO USE:
  1. Copy this single file to any Windows machine that has MT5 installed
  2. Install dependencies:
       pip install fastapi uvicorn MetaTrader5
  3. Edit the CONFIG section below with your MT5 credentials
  4. Run:
       python mt5_remote_server.py
  5. On your Mac, open Forexia Settings → select "Remote MT5 Server"
     → enter http://<windows-ip>:8089 and the auth key below

The server exposes a simple REST API that the Forexia agent calls
from macOS/Linux. All MT5 operations are proxied through this server.

For remote access (different machines), use your Windows machine's
LAN IP or set up port forwarding / ngrok / tailscale.
"""

import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

# ═══════════════════════════════════════════════════════════════
#  CONFIG — Edit these values
# ═══════════════════════════════════════════════════════════════
MT5_LOGIN = 000000000           # Your MT5 account number
MT5_PASSWORD = "YOUR_PASSWORD"    # Your MT5 password
MT5_SERVER = "FxPro-MT5 Demo"   # Your broker server
MT5_PATH = ""                   # Optional: path to terminal64.exe
AUTH_KEY = "change_me"  # Auth key (change this!)
HOST = "0.0.0.0"                # Listen on all interfaces
PORT = 8089                     # Server port
# ═══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("mt5_remote")

try:
    import MetaTrader5 as mt5
except ImportError:
    print("\n❌ MetaTrader5 package not installed!")
    print("   Run: pip install MetaTrader5")
    print("   Note: Only works on Windows with MT5 terminal installed.\n")
    exit(1)

try:
    from fastapi import FastAPI, HTTPException, Header, Request
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
except ImportError:
    print("\n❌ FastAPI/Uvicorn not installed!")
    print("   Run: pip install fastapi uvicorn\n")
    exit(1)


# ─────────────────────────────────────────────────────────────────
#  MT5 CONNECTION
# ─────────────────────────────────────────────────────────────────

def init_mt5() -> bool:
    """Initialize MT5 and login."""
    kwargs = {}
    if MT5_PATH:
        kwargs["path"] = MT5_PATH

    if not mt5.initialize(**kwargs):
        logger.error(f"MT5 init failed: {mt5.last_error()}")
        return False

    if MT5_LOGIN and MT5_PASSWORD and MT5_SERVER:
        if not mt5.login(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
            logger.error(f"MT5 login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False

    info = mt5.account_info()
    if info:
        logger.info(
            f"✓ MT5 Connected — Account: {info.login}, "
            f"Balance: ${info.balance:.2f}, "
            f"Server: {info.server}"
        )
    return True


# ─────────────────────────────────────────────────────────────────
#  FASTAPI APP
# ─────────────────────────────────────────────────────────────────

app = FastAPI(title="Forexia MT5 Remote Server", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_auth(authorization: Optional[str] = Header(None)):
    """Check auth key from header."""
    if authorization != f"Bearer {AUTH_KEY}":
        raise HTTPException(status_code=401, detail="Invalid auth key")


# ─────────────────────────────────────────────────────────────────
#  ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health(authorization: Optional[str] = Header(None)):
    verify_auth(authorization)
    info = mt5.terminal_info()
    account = mt5.account_info()
    return {
        "status": "OK",
        "connected": info is not None,
        "account": account.login if account else None,
        "server": account.server if account else None,
    }


@app.get("/account")
async def get_account(authorization: Optional[str] = Header(None)):
    verify_auth(authorization)
    info = mt5.account_info()
    if not info:
        raise HTTPException(500, "Cannot get account info")

    positions = mt5.positions_get()
    open_count = len(positions) if positions else 0

    return {
        "balance": info.balance,
        "equity": info.equity,
        "margin": info.margin,
        "free_margin": info.margin_free,
        "margin_level": info.margin_level if info.margin_level else 0,
        "open_trades": open_count,
        "currency": info.currency,
        "server": info.server,
        "login": info.login,
    }


@app.get("/positions")
async def get_positions(authorization: Optional[str] = Header(None)):
    verify_auth(authorization)
    positions = mt5.positions_get()
    if not positions:
        return []

    result = []
    for pos in positions:
        result.append({
            "ticket": pos.ticket,
            "symbol": pos.symbol,
            "type": pos.type,
            "volume": pos.volume,
            "open_price": pos.price_open,
            "current_price": pos.price_current,
            "sl": pos.sl,
            "tp": pos.tp,
            "profit": pos.profit,
            "swap": pos.swap,
            "comment": pos.comment,
            "magic": pos.magic,
            "time": pos.time,
        })
    return result


@app.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    timeframe: str = "M15",
    count: int = 100,
    authorization: Optional[str] = Header(None),
):
    verify_auth(authorization)
    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1,
    }
    mt5_tf = tf_map.get(timeframe, mt5.TIMEFRAME_M15)
    rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)

    if rates is None or len(rates) == 0:
        return []

    candles = []
    for bar in rates:
        candles.append({
            "time": datetime.fromtimestamp(bar['time'], tz=timezone.utc).isoformat(),
            "open": float(bar['open']),
            "high": float(bar['high']),
            "low": float(bar['low']),
            "close": float(bar['close']),
            "tick_volume": int(bar['tick_volume']),
            "real_volume": int(bar['real_volume']) if 'real_volume' in bar.dtype.names else 0,
        })
    return candles


@app.get("/price/{symbol}")
async def get_price(
    symbol: str,
    authorization: Optional[str] = Header(None),
):
    verify_auth(authorization)
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        raise HTTPException(404, f"Symbol {symbol} not found")
    return {
        "bid": tick.bid,
        "ask": tick.ask,
        "spread": int((tick.ask - tick.bid) * 100000),
        "time": datetime.fromtimestamp(tick.time, tz=timezone.utc).isoformat(),
    }


@app.post("/trade/open")
async def open_trade(request: Request, authorization: Optional[str] = Header(None)):
    verify_auth(authorization)
    body = await request.json()

    symbol = body["symbol"]
    direction = body["direction"]  # "BUY" or "SELL"
    volume = round(body["volume"], 2)
    sl = body.get("sl", 0)
    tp = body.get("tp", 0)
    comment = body.get("comment", "FOREXIA_SIGNATURE")

    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        raise HTTPException(400, f"Cannot get price for {symbol}")

    price = tick.ask if direction == "BUY" else tick.bid

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": round(sl, 5) if sl else 0.0,
        "tp": round(tp, 5) if tp else 0.0,
        "deviation": 30,
        "magic": 20260215,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(req)
    if result is None:
        raise HTTPException(500, f"order_send returned None: {mt5.last_error()}")

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f"✓ Order filled — Deal #{result.deal}, Order #{result.order}")
        return {"status": "OK", "order": result.order, "deal": result.deal}
    else:
        return {
            "status": "ERROR",
            "retcode": result.retcode,
            "message": result.comment,
        }


@app.post("/trade/modify")
async def modify_trade(request: Request, authorization: Optional[str] = Header(None)):
    verify_auth(authorization)
    body = await request.json()
    ticket = body["ticket"]
    sl = body.get("sl")
    tp = body.get("tp")

    position = mt5.positions_get(ticket=ticket)
    if not position:
        raise HTTPException(404, f"Position #{ticket} not found")

    pos = position[0]
    req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": pos.symbol,
        "position": ticket,
        "sl": round(sl, 5) if sl is not None else pos.sl,
        "tp": round(tp, 5) if tp is not None else pos.tp,
    }
    result = mt5.order_send(req)
    success = result and result.retcode == mt5.TRADE_RETCODE_DONE
    return {"status": "OK" if success else "ERROR", "modified": success}


@app.post("/trade/close")
async def close_trade(request: Request, authorization: Optional[str] = Header(None)):
    verify_auth(authorization)
    body = await request.json()
    ticket = body["ticket"]

    position = mt5.positions_get(ticket=ticket)
    if not position:
        raise HTTPException(404, f"Position #{ticket} not found")

    pos = position[0]
    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(pos.symbol)
    price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

    req = {
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
    result = mt5.order_send(req)
    success = result and result.retcode == mt5.TRADE_RETCODE_DONE
    if success:
        logger.info(f"✓ Position #{ticket} closed")
    return {"status": "OK" if success else "ERROR", "closed": success}


@app.post("/trade/close-all")
async def close_all(request: Request, authorization: Optional[str] = Header(None)):
    verify_auth(authorization)
    body = await request.json() if await request.body() else {}
    symbol = body.get("symbol")

    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if not positions:
        return {"status": "OK", "closed": 0}

    closed = 0
    for pos in positions:
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            continue
        price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": pos.ticket,
            "price": price,
            "deviation": 30,
            "magic": 20260215,
            "comment": "FOREXIA_CLOSE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(req)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            closed += 1

    logger.info(f"Closed {closed} positions")
    return {"status": "OK", "closed": closed}


# ─────────────────────────────────────────────────────────────────
#  STARTUP
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("═" * 60)
    print("  FOREXIA — MT5 Remote Server")
    print("  Run this on Windows alongside MetaTrader 5")
    print("═" * 60)
    print()

    if not init_mt5():
        print("❌ Failed to connect to MT5. Make sure:")
        print("   1. MetaTrader 5 terminal is installed and running")
        print("   2. Login credentials above are correct")
        print("   3. You're on Windows")
        exit(1)

    print()
    print(f"🟢 Server starting on http://{HOST}:{PORT}")
    print(f"   Auth key: {AUTH_KEY}")
    print()
    print("   On your Mac, open Forexia Settings:")
    print("   → Platform: Remote MT5 Server")
    print(f"   → Server URL: http://<this-pc-ip>:{PORT}")
    print(f"   → Auth Key: {AUTH_KEY}")
    print()

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
