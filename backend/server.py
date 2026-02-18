"""
╔══════════════════════════════════════════════════════════════════════╗
║       FOREXIA SIGNATURE AGENT — FASTAPI SERVER                      ║
║   TradingView Webhook Listener & REST API for the React Frontend    ║
╚══════════════════════════════════════════════════════════════════════╝

This server provides two interfaces:

  1. WEBHOOK ENDPOINT — Receives alerts from TradingView.
     When a TradingView alert fires, it sends a POST to /webhook
     with the symbol and candle data. The Forexia engine analyzes
     it and executes if a Signature Trade is confirmed.

  2. REST API — Serves the React frontend dashboard.
     Provides real-time account state, trade history, induction meter,
     weekly act status, and liquidity zone data.

All endpoints are authenticated via the webhook secret.
CORS is configured for the React frontend.
"""

import logging
import asyncio
import os
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.config import CONFIG
from backend.orchestrator import ForexiaOrchestrator
from backend.models.schemas import (
    TradingViewWebhook, DashboardState, ForexiaSignal,
    CandleData, TradeDirection
)
from backend.settings import (
    SETTINGS, ForexiaSettings, BrokerSettings, RiskSettings, AgentSettings
)
from backend.mt5_multi import (
    MultiAccountOrchestrator, AccountConfig, PropFirmType, PROP_FIRM_PRESETS,
)

logger = logging.getLogger("forexia.server")

# ─────────────────────────────────────────────────────────────────────
#  GLOBAL ORCHESTRATOR INSTANCE
# ─────────────────────────────────────────────────────────────────────
orchestrator = ForexiaOrchestrator()

# Multi-account orchestrator (prop firm system)
multi_orchestrator = MultiAccountOrchestrator()


# ─────────────────────────────────────────────────────────────────────
#  APPLICATION LIFECYCLE
# ─────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop the Forexia agent with the server."""
    # Startup
    logging.basicConfig(
        level=getattr(logging, CONFIG.server.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger.info("Starting Forexia Signature Agent server...")
    await orchestrator.start()
    # Load multi-account settings if file exists
    multi_orchestrator.configure_from_settings("multi_accounts.json")
    yield
    # Shutdown
    logger.info("Shutting down Forexia Signature Agent...")
    await orchestrator.stop()
    await multi_orchestrator.stop()


# ─────────────────────────────────────────────────────────────────────
#  FASTAPI APP
# ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Forexia Signature Agent",
    description=(
        "Institutional Trading Bot — "
        "Trading Market Manipulation, Not Retail Trends"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=CONFIG.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────
#  AUTHENTICATION
# ─────────────────────────────────────────────────────────────────────

def verify_webhook_secret(secret: str) -> bool:
    """Verify the webhook authentication token."""
    return secret == CONFIG.server.webhook_secret


# ═══════════════════════════════════════════════════════════════════════
#  WEBHOOK ENDPOINT — TRADINGVIEW ALERTS
# ═══════════════════════════════════════════════════════════════════════

@app.post("/webhook", response_model=dict)
async def receive_webhook(payload: TradingViewWebhook):
    """
    Receive and process TradingView webhook alerts.
    
    This is the primary entry point for market data.
    When TradingView detects an alert condition, it sends a POST here
    with the symbol and optional candle data.
    
    The Forexia engine runs the complete analysis pipeline:
      Weekly Gate → Session Phase → News Check → Trauma Filter →
      Signature Trade → Candle Anatomy → Multi-Pair → Risk → Execute
    
    TradingView Alert Message Format (JSON):
    {
        "secret": "your_webhook_secret",
        "symbol": "EURUSD",
        "timeframe": "M15",
        "action": "ANALYZE",
        "price": 1.08500
    }
    """
    # Authenticate
    if not verify_webhook_secret(payload.secret):
        logger.warning("Webhook received with INVALID secret")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    logger.info(
        f"══╡ WEBHOOK — {payload.symbol} {payload.action} ╞══"
    )

    # Route by action
    if payload.action == "ANALYZE":
        # Run the full analysis pipeline
        signal = await orchestrator.analyze(
            symbol=payload.symbol,
            candles=payload.candles,
            timeframe=payload.timeframe,
        )

        if signal:
            # Auto-execute if signal is strong enough
            if signal.confidence >= 0.6:
                trade = await orchestrator.execute_signal(signal)
                return {
                    "status": "EXECUTED",
                    "signal_id": signal.signal_id,
                    "direction": signal.direction.value,
                    "entry": signal.entry_price,
                    "sl": signal.stop_loss,
                    "tp": signal.take_profit,
                    "lots": signal.lot_size,
                    "confidence": signal.confidence,
                    "ticket": trade.mt4_ticket if trade else None,
                    "message": (
                        f"Signature Trade executed — "
                        f"trapping dumb money on the {signal.signal_type.value}"
                    ),
                }
            else:
                return {
                    "status": "SIGNAL_LOW_CONFIDENCE",
                    "signal_id": signal.signal_id,
                    "confidence": signal.confidence,
                    "message": "Signal generated but confidence below threshold",
                }
        else:
            return {
                "status": "NO_SIGNAL",
                "message": "No actionable Forexia signal at this time",
                "session": orchestrator.dialectic.get_current_phase().value,
                "weekly_act": orchestrator.weekly.get_current_act().value,
            }

    elif payload.action == "FORCE_ENTRY":
        # Manual force entry (override analysis)
        if not payload.price:
            raise HTTPException(400, "Price required for FORCE_ENTRY")

        signal = ForexiaSignal(
            signal_id=f"FX-MANUAL-{datetime.utcnow().strftime('%H%M%S')}",
            signal_type=SignalType.LIQUIDITY_SWEEP,
            symbol=payload.symbol,
            direction=TradeDirection.BUY,  # Override in message
            entry_price=payload.price,
            stop_loss=0,
            take_profit=0,
            lot_size=0.01,
            session_phase=orchestrator.dialectic.get_current_phase(),
            weekly_act=orchestrator.weekly.get_current_act(),
            induction_state=InductionState.NO_PATTERN,
            confidence=0.5,
            notes="MANUAL FORCE ENTRY",
        )
        return {"status": "MANUAL_SIGNAL_CREATED", "signal_id": signal.signal_id}

    elif payload.action == "CLOSE":
        # Close all trades for this symbol
        if orchestrator.bridge.is_connected:
            closed = await orchestrator.bridge.close_all_trades(payload.symbol)
            return {"status": "CLOSED", "count": closed}
        return {"status": "ERROR", "message": "Broker not connected"}

    return {"status": "UNKNOWN_ACTION", "action": payload.action}


# ═══════════════════════════════════════════════════════════════════════
#  DASHBOARD API — REACT FRONTEND
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/dashboard", response_model=DashboardState)
async def get_dashboard():
    """
    Get the complete dashboard state for the React frontend.
    
    Returns:
      - Account balance, equity, win rate
      - Current weekly act (Sun-Fri phase)
      - Current session phase (Asian/London/NY)
      - Induction meter (% trapped retail volume)
      - Active signals
      - Recent trade history
      - Upcoming Red Folder catalysts
      - Liquidity zones
      - Multi-pair status
      - Trauma filter status
    """
    return await orchestrator.get_dashboard_state()


@app.get("/api/account")
async def get_account():
    """Get current account state from MT4."""
    if orchestrator.bridge.is_connected:
        account = await orchestrator.bridge.get_account_state()
        return account.model_dump()
    return orchestrator._account.model_dump()


@app.get("/api/signals")
async def get_signals():
    """Get recent trading signals."""
    return [s.model_dump() for s in orchestrator._active_signals[-20:]]


@app.get("/api/trades")
async def get_trades():
    """Get trade history."""
    return [t.model_dump() for t in orchestrator._trade_history[-50:]]


@app.get("/api/trade-history")
async def get_trade_history(days: int = 30):
    """
    Get full transaction history — combines open positions + closed trades
    from the broker, plus agent-tracked trades.
    """
    bridge = orchestrator.bridge
    result = {"open": [], "closed": [], "agent_trades": []}

    # 1) Open positions from broker
    if bridge and bridge.is_connected:
        try:
            positions = await bridge.get_open_positions()
            for pos in positions:
                direction = "BUY" if pos.get("type", 0) == 0 else "SELL"
                result["open"].append({
                    "id": pos.get("id", ""),
                    "ticket": pos.get("ticket", 0),
                    "symbol": (pos.get("symbol") or "").rstrip("."),
                    "side": direction,
                    "volume": pos.get("lots", 0),
                    "open_price": pos.get("open_price", 0),
                    "sl": pos.get("sl", 0),
                    "tp": pos.get("tp", 0),
                    "profit": round(pos.get("profit", 0), 2),
                    "swap": round(pos.get("swap", 0), 2),
                    "commission": round(pos.get("commission", 0), 2),
                    "status": "open",
                })
        except Exception as e:
            logger.error(f"Trade history — open positions error: {e}")

    # 2) Closed trades from broker (if supported)
    if bridge and bridge.is_connected and hasattr(bridge, 'get_trade_history'):
        try:
            closed = await bridge.get_trade_history(days=days)
            result["closed"] = closed
        except Exception as e:
            logger.error(f"Trade history — closed trades error: {e}")

    # 3) Agent-tracked trades (always available)
    for t in orchestrator._trade_history[-50:]:
        try:
            td = t.model_dump()
            result["agent_trades"].append({
                "id": td.get("trade_id", ""),
                "symbol": td.get("signal", {}).get("symbol", ""),
                "side": td.get("signal", {}).get("direction", ""),
                "volume": td.get("signal", {}).get("lot_size", 0),
                "status": td.get("status", ""),
                "ticket": td.get("mt4_ticket", 0),
                "executed_at": td.get("executed_at", ""),
                "confidence": td.get("signal", {}).get("confidence", 0),
                "signal_type": td.get("signal", {}).get("signal_type", ""),
            })
        except Exception:
            pass

    # 4) Win-rate statistics from closed trades
    closed_list = result.get("closed", [])
    if closed_list:
        wins = [t for t in closed_list if (t.get("profit") or 0) > 0]
        losses = [t for t in closed_list if (t.get("profit") or 0) < 0]
        total = len(wins) + len(losses)
        net_pnl = sum(t.get("profit", 0) for t in closed_list)
        gross_profit = sum(t.get("profit", 0) for t in wins)
        gross_loss = abs(sum(t.get("profit", 0) for t in losses))
        avg_win = gross_profit / len(wins) if wins else 0
        avg_loss = gross_loss / len(losses) if losses else 0

        result["win_rate_stats"] = {
            "total_trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / total * 100, 1) if total else 0,
            "net_pnl": round(net_pnl, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else 0,
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "reward_risk_ratio": round(avg_win / avg_loss, 2) if avg_loss else 0,
        }
    else:
        result["win_rate_stats"] = {
            "total_trades": 0, "wins": 0, "losses": 0,
            "win_rate": 0, "net_pnl": 0, "profit_factor": 0,
        }

    return result


@app.get("/api/news")
async def get_news():
    """Get upcoming Red Folder catalysts (NO economic numbers — BOGUS data stripped)."""
    catalysts = orchestrator.news.get_upcoming_catalysts(48)
    return [c.model_dump() for c in catalysts]


@app.get("/api/liquidity")
async def get_liquidity_zones():
    """Get current liquidity zones across all pairs."""
    all_zones = []
    for zones in orchestrator._liquidity_zones.values():
        all_zones.extend([z.model_dump() for z in zones])
    return all_zones


@app.get("/api/session")
async def get_session_info():
    """Get current session/phase information."""
    utc_now = datetime.utcnow()
    return {
        "session_phase": orchestrator.dialectic.get_current_phase(utc_now).value,
        "weekly_act": orchestrator.weekly.get_current_act(utc_now).value,
        "in_killzone": orchestrator.dialectic.is_in_killzone(utc_now),
        "trading_permitted": orchestrator.weekly.is_trading_permitted(utc_now),
        "is_primary_day": orchestrator.weekly.is_primary_trade_day(utc_now),
        "trauma_filter_active": orchestrator.trauma.is_active,
        "circuit_breaker_active": orchestrator.risk.is_circuit_breaker_active,
        "timestamp_utc": utc_now.isoformat(),
    }


@app.get("/api/multi-pair")
async def get_multi_pair_status():
    """Get multi-pair synchronization status."""
    return orchestrator.multi_pair.get_status()


# ═══════════════════════════════════════════════════════════════════════
#  CONTROL ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/close-all")
async def close_all_positions():
    """Emergency close all positions."""
    try:
        bridge = orchestrator.bridge
        if not bridge or not bridge.is_connected:
            return {"status": "ERROR", "message": "Broker not connected"}
        logger.info("[CLOSE-ALL] Closing all open positions...")
        closed = await bridge.close_all_trades()
        logger.info(f"[CLOSE-ALL] Closed {closed} positions")
        return {"status": "OK", "closed_count": closed}
    except Exception as e:
        logger.error(f"[CLOSE-ALL] Exception: {e}", exc_info=True)
        return {"status": "ERROR", "message": f"Server error: {str(e)}"}


@app.post("/api/reset/daily")
async def reset_daily():
    """Trigger daily reset of all engines."""
    orchestrator.daily_reset()
    return {"status": "OK", "message": "Daily reset complete"}


@app.post("/api/reset/weekly")
async def reset_weekly():
    """Trigger weekly reset."""
    orchestrator.weekly_reset()
    return {"status": "OK", "message": "Weekly reset complete"}


@app.post("/api/scrape-news")
async def trigger_news_scrape():
    """Manually trigger a ForexFactory scrape."""
    catalysts = await orchestrator.news.scrape_red_folder_events()
    return {
        "status": "OK",
        "events_found": len(catalysts),
        "catalysts": [c.model_dump() for c in catalysts],
    }


@app.post("/api/trauma/arm")
async def arm_trauma_filter():
    """Manually arm the Trauma Filter."""
    orchestrator.trauma.arm()
    return {"status": "OK", "message": "Trauma Filter ARMED"}


@app.post("/api/trauma/disarm")
async def disarm_trauma_filter():
    """Manually disarm the Trauma Filter."""
    orchestrator.trauma.disarm()
    return {"status": "OK", "message": "Trauma Filter DISARMED"}


# ─────────────────────────────────────────────────────────────────────
#  HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """System health check."""
    bridge = orchestrator.bridge
    platform = orchestrator.settings.broker.platform
    return {
        "status": "OPERATIONAL",
        "agent": "Forexia Signature Agent v1.0",
        "platform": platform,
        "broker_connected": bridge.is_connected if bridge else False,
        "timestamp": datetime.utcnow().isoformat(),
        "session": orchestrator.dialectic.get_current_phase().value,
        "weekly_act": orchestrator.weekly.get_current_act().value,
    }


# ─────────────────────────────────────────────────────────────────────
#  MISSING IMPORT FIX — for FORCE_ENTRY endpoint
# ─────────────────────────────────────────────────────────────────────
from backend.models.schemas import SignalType, InductionState


# ═══════════════════════════════════════════════════════════════════════
#  INSTRUMENTS ENDPOINT
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/instruments")
async def get_instruments():
    """Get available trading instruments from the broker."""
    bridge = orchestrator.bridge
    if not bridge or not bridge.is_connected:
        return {"instruments": [], "message": "Broker not connected"}

    instruments = getattr(bridge, '_broker_instruments', [])
    instrument_map = getattr(bridge, '_instrument_map', {})
    return {
        "instruments": instruments,
        "map": instrument_map,
        "count": len(instruments),
    }


# ═══════════════════════════════════════════════════════════════════════
#  MANUAL TRADING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/trade/open")
async def open_manual_trade(request: Request):
    """
    Open a manual trade via the active broker bridge.

    Body:
    {
        "symbol": "EURUSD",
        "direction": "BUY" | "SELL",
        "lot_size": 0.01,
        "stop_loss": 0,       // 0 = no SL
        "take_profit": 0      // 0 = no TP
    }
    """
    bridge = orchestrator.bridge
    if not bridge or not bridge.is_connected:
        return {"status": "ERROR", "message": "Broker not connected"}

    body = await request.json()
    symbol = body.get("symbol", "").upper()
    direction_str = body.get("direction", "").upper()
    lot_size = float(body.get("lot_size", 0.01))
    stop_loss = float(body.get("stop_loss", 0))
    take_profit = float(body.get("take_profit", 0))

    if not symbol:
        return {"status": "ERROR", "message": "Symbol is required"}
    if direction_str not in ("BUY", "SELL"):
        return {"status": "ERROR", "message": "Direction must be BUY or SELL"}
    if lot_size <= 0:
        return {"status": "ERROR", "message": "Lot size must be > 0"}

    direction = TradeDirection.BUY if direction_str == "BUY" else TradeDirection.SELL

    ticket = await bridge.execute_market_order(
        symbol=symbol,
        direction=direction,
        lot_size=lot_size,
        stop_loss=stop_loss,
        take_profit=take_profit,
        comment="FOREXIA_MANUAL",
    )

    if ticket:
        # Refresh account state
        orchestrator._account = await bridge.get_account_state()
        logger.info(f"Manual trade executed — {direction_str} {lot_size} {symbol}, ticket #{ticket}")
        return {
            "status": "OK",
            "ticket": ticket,
            "symbol": symbol,
            "direction": direction_str,
            "lot_size": lot_size,
        }

    return {"status": "ERROR", "message": f"Order rejected by broker for {direction_str} {lot_size} {symbol}"}


@app.post("/api/trade/close")
async def close_single_trade(request: Request):
    """
    Close a single open position by ticket ID or position ID.
    Body: { "ticket": 12345 } or { "id": "W12345" } or both.
    Prefers the string 'id' field for exact matching with the broker API.
    """
    try:
        bridge = orchestrator.bridge
        if not bridge or not bridge.is_connected:
            logger.warning("Close request received but broker not connected")
            return {"status": "ERROR", "message": "Broker not connected"}

        body = await request.json()
        ticket = body.get("ticket")
        pos_id = body.get("id")  # Original string ID like "W4250023165791583"
        logger.info(f"[CLOSE] Received close request — ticket={ticket}, id={pos_id}, body={body}")

        if not ticket and not pos_id:
            return {"status": "ERROR", "message": "Ticket ID or position ID required"}

        # Prefer string ID for exact broker API matching, fall back to numeric ticket
        search_key = str(pos_id) if pos_id else str(ticket)
        logger.info(f"[CLOSE] Searching for position with key: '{search_key}'")

        result = await bridge.close_by_id(search_key)
        if result:
            orchestrator._account = await bridge.get_account_state()
            logger.info(f"[CLOSE] SUCCESS — Position {search_key} closed via dashboard")
            return {"status": "OK", "id": search_key}

        logger.error(f"[CLOSE] FAILED — bridge.close_by_id('{search_key}') returned False")
        return {"status": "ERROR", "message": f"Failed to close position {search_key}"}
    except Exception as e:
        logger.error(f"[CLOSE] Exception in close_single_trade: {e}", exc_info=True)
        return {"status": "ERROR", "message": f"Server error: {str(e)}"}


@app.post("/api/trade/modify")
async def modify_trade(request: Request):
    """
    Modify SL/TP on an existing position.
    Body: { "ticket": 12345, "stop_loss": 1.08000, "take_profit": 1.09500 }
    """
    bridge = orchestrator.bridge
    if not bridge or not bridge.is_connected:
        return {"status": "ERROR", "message": "Broker not connected"}

    body = await request.json()
    ticket = body.get("ticket")
    sl = body.get("stop_loss")
    tp = body.get("take_profit")

    if not ticket:
        return {"status": "ERROR", "message": "Ticket ID required"}

    result = await bridge.modify_trade(
        int(ticket),
        stop_loss=float(sl) if sl is not None else None,
        take_profit=float(tp) if tp is not None else None,
    )
    if result:
        return {"status": "OK", "ticket": ticket}
    return {"status": "ERROR", "message": f"Failed to modify position #{ticket}"}


@app.get("/api/positions")
async def get_open_positions():
    """Get all open positions from the broker."""
    bridge = orchestrator.bridge
    if not bridge or not bridge.is_connected:
        return []

    positions = await bridge.get_open_positions()
    return positions


# ═══════════════════════════════════════════════════════════════════════
#  CHART DATA ENDPOINTS — Candles + Position Overlays for Live Chart
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/candles")
async def get_candles(symbol: str = "EURUSD", timeframe: str = "H1", count: int = 300):
    """
    Get OHLCV candle data for the live chart.
    Returns: [{ time, open, high, low, close, volume }, ...]
    Time is UTC epoch seconds (lightweight-charts format).
    """
    bridge = orchestrator.bridge
    if not bridge or not bridge.is_connected:
        return []

    candles = await bridge.get_candles(symbol, timeframe, min(count, 1000))
    result = []
    for c in candles:
        ts = c.timestamp
        # lightweight-charts needs UTC unix timestamp in seconds
        if ts.tzinfo:
            epoch = int(ts.timestamp())
        else:
            from datetime import timezone as tz
            epoch = int(ts.replace(tzinfo=tz.utc).timestamp())
        result.append({
            "time": epoch,
            "open": round(c.open, 5),
            "high": round(c.high, 5),
            "low": round(c.low, 5),
            "close": round(c.close, 5),
            "volume": c.volume,
        })

    # Deduplicate and sort by time (lightweight-charts requires ascending order)
    seen = set()
    deduped = []
    for bar in sorted(result, key=lambda x: x["time"]):
        if bar["time"] not in seen:
            seen.add(bar["time"])
            deduped.append(bar)

    return deduped


@app.get("/api/chart/positions")
async def get_chart_positions(symbol: str = ""):
    """
    Get open positions formatted for chart overlay lines.
    Returns entry, SL, and TP lines for the given symbol.
    """
    bridge = orchestrator.bridge
    if not bridge or not bridge.is_connected:
        return []

    positions = await bridge.get_open_positions()
    lines = []

    for pos in positions:
        pos_symbol = (pos.get("symbol") or "").rstrip(".").upper()
        req_symbol = symbol.upper().rstrip(".") if symbol else ""
        if req_symbol and pos_symbol != req_symbol:
            continue

        direction = "BUY" if pos.get("type", 0) == 0 else "SELL"
        lots = pos.get("lots", 0)
        profit = pos.get("profit", 0)
        entry_price = pos.get("open_price", 0)
        sl = pos.get("sl", 0)
        tp = pos.get("tp", 0)

        # Entry line
        lines.append({
            "type": "entry",
            "price": entry_price,
            "direction": direction,
            "lots": lots,
            "profit": round(profit, 2),
            "ticket": pos.get("ticket", 0),
            "id": pos.get("id", ""),
            "color": "#10b981" if direction == "BUY" else "#ef4444",
            "label": f"{direction} {lots}",
        })

        # SL line
        if sl and sl > 0:
            lines.append({
                "type": "sl",
                "price": sl,
                "direction": direction,
                "ticket": pos.get("ticket", 0),
                "color": "#ef4444",
                "label": f"SL {sl:.5f}",
            })

        # TP line
        if tp and tp > 0:
            lines.append({
                "type": "tp",
                "price": tp,
                "direction": direction,
                "ticket": pos.get("ticket", 0),
                "color": "#10b981",
                "label": f"TP {tp:.5f}",
            })

    return lines


# ═══════════════════════════════════════════════════════════════════════
#  AUTO-TRADE BOT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/bot/toggle")
async def toggle_auto_trade(request: Request):
    """
    Toggle auto-trade on/off.
    Body: { "enabled": true } or no body to toggle.
    Also starts/stops the background auto-scan loop.
    """
    body = await request.json() if request.headers.get("content-length", "0") != "0" else {}
    settings = orchestrator.settings

    if "enabled" in body:
        settings.agent.auto_trade = bool(body["enabled"])
    else:
        settings.agent.auto_trade = not settings.agent.auto_trade

    settings.save()
    orchestrator.apply_settings(settings)

    # Start or stop the auto-scan background loop
    if settings.agent.auto_trade:
        orchestrator._start_auto_scan()
    else:
        orchestrator._stop_auto_scan()

    status = "ENABLED" if settings.agent.auto_trade else "DISABLED"
    logger.info(f"Auto-Trade Bot {status}")
    return {
        "status": "OK",
        "auto_trade": settings.agent.auto_trade,
        "message": f"Auto-Trade Bot {status}",
    }


@app.post("/api/bot/scan")
async def trigger_bot_scan():
    """
    Manually trigger the analysis bot to scan all configured pairs.
    Runs the full 9-gate Forexia pipeline on each pair.
    Returns any signals found + trades executed (if auto-trade is on).
    Manual scans bypass the weekly-structure gate (force mode).
    """
    bridge = orchestrator.bridge
    if not bridge or not bridge.is_connected:
        return {"status": "ERROR", "message": "Broker not connected — cannot scan"}

    settings = orchestrator.settings
    pairs = settings.agent.pairs
    timeframe = settings.agent.default_timeframe
    auto_execute = settings.agent.auto_trade
    min_confidence = settings.agent.min_confidence

    # Get current weekly/session status for diagnostics
    from datetime import datetime as dt
    utc_now = dt.utcnow()
    weekly_act = orchestrator.weekly.get_current_act(utc_now)
    trading_permitted = orchestrator.weekly.is_trading_permitted(utc_now)
    session_phase = orchestrator.dialectic.get_current_phase(utc_now)

    results = []

    for symbol in pairs:
        try:
            # Manual scan uses force=True to bypass weekly gate
            signal = await orchestrator.analyze(
                symbol=symbol,
                timeframe=timeframe,
                force=True,
            )
            if signal:
                # Calculate risk metrics for display
                pip_val = 0.01 if "JPY" in symbol else 0.0001
                risk_pips = round(abs(signal.entry_price - signal.stop_loss) / pip_val, 1)
                reward_pips = round(abs(signal.take_profit - signal.entry_price) / pip_val, 1)
                rr_ratio = round(reward_pips / risk_pips, 1) if risk_pips > 0 else 0

                entry = {
                    "symbol": symbol,
                    "signal_id": signal.signal_id,
                    "direction": signal.direction.value,
                    "confidence": signal.confidence,
                    "entry": signal.entry_price,
                    "sl": signal.stop_loss,
                    "tp": signal.take_profit,
                    "lots": signal.lot_size,
                    "type": signal.signal_type.value,
                    "risk_pips": risk_pips,
                    "reward_pips": reward_pips,
                    "rr_ratio": rr_ratio,
                    "executed": False,
                }

                if auto_execute and signal.confidence >= min_confidence:
                    trade = await orchestrator.execute_signal(signal)
                    entry["executed"] = trade is not None and trade.status.value == "EXECUTED"
                    entry["ticket"] = trade.mt4_ticket if trade else None

                results.append(entry)
            else:
                results.append({"symbol": symbol, "signal_id": None, "message": "No signal"})
        except Exception as e:
            logger.error(f"Bot scan error for {symbol}: {e}")
            results.append({"symbol": symbol, "signal_id": None, "message": f"Error: {str(e)}"})

    executed_count = sum(1 for r in results if r.get("executed"))
    signal_count = sum(1 for r in results if r.get("signal_id"))

    logger.info(
        f"Bot scan complete — {len(pairs)} pairs scanned, "
        f"{signal_count} signals, {executed_count} executed"
    )

    return {
        "status": "OK",
        "pairs_scanned": len(pairs),
        "signals_found": signal_count,
        "trades_executed": executed_count,
        "auto_trade": auto_execute,
        "weekly_act": weekly_act.value,
        "trading_permitted": trading_permitted,
        "session_phase": session_phase.value if hasattr(session_phase, 'value') else str(session_phase),
        "results": results,
    }


@app.get("/api/bot/status")
async def get_bot_status():
    """Get the current auto-trade bot status."""
    settings = orchestrator.settings
    bridge = orchestrator.bridge

    return {
        "auto_trade": settings.agent.auto_trade,
        "min_confidence": settings.agent.min_confidence,
        "pairs": settings.agent.pairs,
        "timeframe": settings.agent.default_timeframe,
        "broker_connected": bridge.is_connected if bridge else False,
        "active_signals": len(orchestrator._active_signals),
        "total_trades": len(orchestrator._trade_history),
    }


# ═══════════════════════════════════════════════════════════════════════
#  SETTINGS API — Configuration Management
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/settings")
async def get_settings():
    """Get current settings (password masked)."""
    return orchestrator.settings.to_safe_dict()


@app.put("/api/settings")
async def update_settings(request: Request):
    """
    Update agent settings. Accepts partial updates.
    Changes are persisted to disk and applied immediately.
    """
    body = await request.json()

    current = orchestrator.settings

    # Update broker settings
    if "broker" in body:
        broker_data = body["broker"]
        # Don't overwrite passwords with the masked value
        if broker_data.get("password") in ("••••••••", "", None):
            broker_data["password"] = current.broker.password
        if broker_data.get("matchtrader_password") in ("••••••••", "", None):
            broker_data["matchtrader_password"] = current.broker.matchtrader_password
        current.broker = BrokerSettings(**{**current.broker.model_dump(), **broker_data})

    # Update risk settings
    if "risk" in body:
        current.risk = RiskSettings(**{**current.risk.model_dump(), **body["risk"]})

    # Update agent settings
    if "agent" in body:
        current.agent = AgentSettings(**{**current.agent.model_dump(), **body["agent"]})

    # Save and apply
    current.save()
    orchestrator.apply_settings(current)

    logger.info("Settings updated and applied")
    return {"status": "OK", "message": "Settings saved", "settings": current.to_safe_dict()}


@app.post("/api/settings/connect")
async def connect_broker():
    """
    (Re)connect to the broker using current settings.
    Call this after updating broker settings to establish the connection.
    """
    settings = orchestrator.settings
    platform = settings.broker.platform.lower()

    # Disconnect existing
    try:
        await orchestrator.mt4.disconnect()
    except Exception:
        pass
    try:
        await orchestrator.mt5.disconnect()
    except Exception:
        pass
    try:
        await orchestrator.remote_mt5.disconnect()
    except Exception:
        pass
    try:
        await orchestrator.matchtrader.disconnect()
    except Exception:
        pass

    if platform == "matchtrader":
        if not settings.broker.matchtrader_url or not settings.broker.matchtrader_login:
            return {"status": "ERROR", "platform": "matchtrader", "connected": False,
                    "message": "MatchTrader API URL and login are required."}
        orchestrator.matchtrader.configure(
            base_url=settings.broker.matchtrader_url,
            login=settings.broker.matchtrader_login,
            password=settings.broker.matchtrader_password,
            partner_id=settings.broker.matchtrader_partner_id,
        )
        connected = await orchestrator.matchtrader.connect()
        if connected:
            orchestrator._bridge = orchestrator.matchtrader
            account = await orchestrator.matchtrader.get_account_state()
            orchestrator._account = account
            return {
                "status": "OK",
                "platform": "matchtrader",
                "connected": True,
                "balance": account.balance,
                "equity": account.equity,
            }
        return {"status": "ERROR", "platform": "matchtrader", "connected": False,
                "message": "MatchTrader connection failed. Check your API URL, login, and password."}
    elif platform == "remote_mt5":
        if not settings.broker.remote_mt5_url:
            return {"status": "ERROR", "platform": "remote_mt5", "connected": False,
                    "message": "Remote MT5 Server URL is required. Run tools/mt5_remote_server.py on a Windows PC first."}
        orchestrator.remote_mt5.configure(
            server_url=settings.broker.remote_mt5_url,
            auth_key=settings.broker.remote_mt5_auth_key,
        )
        connected = await orchestrator.remote_mt5.connect()
        if connected:
            orchestrator._bridge = orchestrator.remote_mt5
            account = await orchestrator.remote_mt5.get_account_state()
            orchestrator._account = account
            return {
                "status": "OK",
                "platform": "remote_mt5",
                "connected": True,
                "balance": account.balance,
                "equity": account.equity,
            }
        return {"status": "ERROR", "platform": "remote_mt5", "connected": False,
                "message": "Cannot reach MT5 Remote Server. Check the URL and ensure mt5_remote_server.py is running on Windows."}
    elif platform == "mt5":
        if settings.broker.login and settings.broker.server:
            orchestrator.mt5.configure(
                login=settings.broker.login,
                password=settings.broker.password,
                server=settings.broker.server,
                mt5_path=settings.broker.mt5_path or None,
            )
        connected = await orchestrator.mt5.connect()
        if connected:
            orchestrator._bridge = orchestrator.mt5
            account = await orchestrator.mt5.get_account_state()
            orchestrator._account = account
            return {
                "status": "OK",
                "platform": "mt5",
                "connected": True,
                "balance": account.balance,
                "equity": account.equity,
            }
        # Auto-fallback to Remote MT5 if configured
        if settings.broker.remote_mt5_url:
            orchestrator.remote_mt5.configure(
                server_url=settings.broker.remote_mt5_url,
                auth_key=settings.broker.remote_mt5_auth_key,
            )
            connected = await orchestrator.remote_mt5.connect()
            if connected:
                orchestrator._bridge = orchestrator.remote_mt5
                account = await orchestrator.remote_mt5.get_account_state()
                orchestrator._account = account
                return {
                    "status": "OK",
                    "platform": "remote_mt5",
                    "connected": True,
                    "balance": account.balance,
                    "equity": account.equity,
                    "message": "MT5 unavailable on this OS — connected via Remote MT5 Server",
                }
        return {"status": "ERROR", "platform": "mt5", "connected": False,
                "message": "MT5 connection failed. On macOS/Linux, use Remote MT5 Server for cross-platform access."}
    else:
        connected = await orchestrator.mt4.connect()
        if connected:
            orchestrator._bridge = orchestrator.mt4
            account = await orchestrator.mt4.get_account_state()
            orchestrator._account = account
            return {
                "status": "OK",
                "platform": "mt4",
                "connected": True,
                "balance": account.balance,
                "equity": account.equity,
            }
        return {"status": "ERROR", "platform": "mt4", "connected": False,
                "message": "MT4 connection failed. Check ZeroMQ EA is running."}


@app.post("/api/settings/test")
async def test_connection():
    """Test broker connection without saving."""
    bridge = orchestrator.bridge
    if bridge and bridge.is_connected:
        account = await bridge.get_account_state()
        return {
            "status": "OK",
            "connected": True,
            "balance": account.balance,
            "equity": account.equity,
            "open_trades": account.open_trades,
        }
    return {"status": "ERROR", "connected": False, "message": "Not connected to any broker"}


# ═══════════════════════════════════════════════════════════════════════
#  MULTI-ACCOUNT API — Prop Firm System
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/multi/status")
async def multi_account_status():
    """Get full multi-account system status."""
    return multi_orchestrator.get_status()


@app.post("/api/multi/start")
async def multi_account_start():
    """Connect all accounts and start the multi-account scan loop."""
    try:
        results = await multi_orchestrator.start()
        connected = sum(1 for v in results.values() if v)
        return {
            "status": "OK",
            "connected": connected,
            "total": len(results),
            "details": results,
        }
    except Exception as e:
        logger.error(f"Multi-account start error: {e}")
        return {"status": "ERROR", "message": str(e)}


@app.post("/api/multi/stop")
async def multi_account_stop():
    """Stop the multi-account system."""
    await multi_orchestrator.stop()
    return {"status": "OK", "message": "Multi-account system stopped"}


@app.post("/api/multi/scan")
async def multi_account_force_scan():
    """Trigger an immediate scan across all accounts."""
    if not multi_orchestrator._running:
        raise HTTPException(400, "Multi-account system not running")
    results = await multi_orchestrator.force_scan()
    return {"status": "OK", **results}


@app.post("/api/multi/account")
async def multi_account_add(request: Request):
    """Add a new prop firm account."""
    data = await request.json()
    config = AccountConfig(
        account_id=data["account_id"],
        firm_type=PropFirmType(data.get("firm_type", "GENERIC_MT5")),
        login=data.get("login", 0),
        password=data.get("password", ""),
        server=data.get("server", ""),
        mt5_path=data.get("mt5_path"),
        enabled=data.get("enabled", True),
        symbols=data.get("symbols", ["EURUSD", "GBPUSD"]),
    )
    multi_orchestrator.add_account_direct(config)
    return {"status": "OK", "account_id": config.account_id}


@app.delete("/api/multi/account/{account_id}")
async def multi_account_remove(account_id: str):
    """Remove a prop firm account."""
    multi_orchestrator.account_manager.remove_account(account_id)
    return {"status": "OK", "removed": account_id}


@app.get("/api/multi/trades")
async def multi_account_trades(limit: int = 50):
    """Get recent trade log from the multi-account system."""
    return multi_orchestrator.get_trade_log(limit)


@app.get("/api/multi/risk/{account_id}")
async def multi_account_risk(account_id: str):
    """Get risk summary for a specific account."""
    return multi_orchestrator.risk_manager.get_account_risk_summary(account_id)


@app.get("/api/multi/presets")
async def multi_account_presets():
    """Get available prop firm preset configurations."""
    presets = {}
    for firm_type, rules in PROP_FIRM_PRESETS.items():
        presets[firm_type.value] = {
            "daily_loss_limit_pct": rules.daily_loss_limit_pct,
            "max_trailing_dd_pct": rules.max_trailing_dd_pct,
            "max_total_dd_pct": rules.max_total_dd_pct,
            "max_positions": rules.max_positions,
            "use_trailing_dd": rules.use_trailing_dd,
            "weekend_holding": rules.weekend_holding,
            "news_lockout_minutes": rules.news_lockout_minutes,
        }
    return presets


@app.post("/api/multi/daily-reset")
async def multi_account_daily_reset():
    """Reset daily counters for all accounts."""
    multi_orchestrator.account_manager.daily_reset()
    return {"status": "OK", "message": "Daily reset complete"}


# ─────────────────────────────────────────────────────────────────────
#  FRONTEND SERVING — Serve React Dashboard
# ─────────────────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the React frontend or redirect to the dev server."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(), status_code=200)
    # If no build exists, redirect to Vite dev server
    return RedirectResponse(url="http://localhost:3000")


# Mount static assets from the built frontend (if exists)
if FRONTEND_DIR.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIR / "assets")),
        name="frontend-assets",
    )
