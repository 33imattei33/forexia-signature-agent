"""
╔══════════════════════════════════════════════════════════════════════╗
║    FOREXIA — MULTI-ACCOUNT ORCHESTRATOR                              ║
║    Main Loop: Scan → Evaluate → Execute across all prop firm accounts║
╚══════════════════════════════════════════════════════════════════════╝

This module ties everything together:
  1. MultiAccountManager (connection to all MT5 terminals)
  2. MarketAdapter (FX vs NASDAQ handling)
  3. PropFirmRiskManager (compliance checks)
  4. SignatureTradeV2 (Wedge + Stop Hunt detection)

Main loop:
  every 120 seconds:
    for each enabled account:
      for each symbol in account.symbols:
        candles = bridge.get_candles(symbol)
        signal = signature.scan(symbol, candles)
        if signal.phase == ENTRY_READY:
          verdict = risk_manager.evaluate(account, signal)
          if verdict.approved:
            account_manager.execute_on_account(account, verdict)

NO FVG. Only Price Action, Wedge Patterns, Liquidity Grabs.
"""

import logging
import asyncio
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path

from backend.mt5_multi.account_manager import (
    MultiAccountManager, AccountConfig, PropFirmType, AccountTracker,
)
from backend.mt5_multi.market_adapter import MarketAdapter
from backend.mt5_multi.prop_risk_manager import PropFirmRiskManager, RiskVerdict
from backend.mt5_multi.signature_v2 import SignatureTradeV2, SignalPhase

logger = logging.getLogger("forexia.multi_orchestrator")


# ─────────────────────────────────────────────────────────────────────
#  MULTI-ACCOUNT ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────

class MultiAccountOrchestrator:
    """
    Orchestrates the Signature Trade strategy across multiple
    prop firm accounts simultaneously.
    
    Lifecycle:
      1. configure() — Load accounts from settings
      2. start() — Connect all accounts and begin scanning
      3. stop() — Disconnect and clean up
    
    The main loop runs every SCAN_INTERVAL seconds and:
      - Fetches candles for each account's symbols
      - Runs the SignatureTradeV2 detector
      - Evaluates signals through PropFirmRiskManager
      - Executes approved trades
    """

    SCAN_INTERVAL = 120  # seconds between full scan cycles

    def __init__(self):
        self.account_manager = MultiAccountManager()
        self.market_adapter = MarketAdapter()
        self.risk_manager = PropFirmRiskManager(
            account_manager=self.account_manager,
            market_adapter=self.market_adapter,
        )
        self.signature = SignatureTradeV2()

        self._running = False
        self._scan_task: Optional[asyncio.Task] = None
        self._trade_log: List[Dict] = []
        self._last_scan_results: Dict[str, Dict] = {}
        self._scan_count = 0

    # ─────────────────────── CONFIGURATION ───────────────────────

    def configure_from_settings(self, settings_path: str = "multi_accounts.json"):
        """
        Load account configurations from a JSON file.
        
        Expected format:
        {
          "accounts": [
            {
              "account_id": "APEX_1",
              "firm_type": "APEX",
              "login": 12345,
              "password": "pass",
              "server": "MetaQuotes-Demo",
              "mt5_path": "C:\\\\MT5_APEX\\\\terminal64.exe",
              "symbols": ["EURUSD", "GBPUSD", "US100"],
              "enabled": true
            }
          ],
          "scan_interval": 120,
          "max_risk_pct": 2.0
        }
        """
        path = Path(settings_path)
        if not path.exists():
            logger.warning(f"Settings file not found: {settings_path}")
            return

        with open(path) as f:
            data = json.load(f)

        self.SCAN_INTERVAL = data.get("scan_interval", 120)
        self.risk_manager._max_risk_pct = data.get("max_risk_pct", 2.0)

        for acct in data.get("accounts", []):
            config = AccountConfig(
                account_id=acct["account_id"],
                firm_type=PropFirmType(acct.get("firm_type", "GENERIC_MT5")),
                login=acct.get("login", 0),
                password=acct.get("password", ""),
                server=acct.get("server", ""),
                mt5_path=acct.get("mt5_path"),
                enabled=acct.get("enabled", True),
                symbols=acct.get("symbols", ["EURUSD", "GBPUSD"]),
            )
            self.account_manager.add_account(config)
            logger.info(f"Loaded account: {config.account_id}")

    def add_account_direct(self, config: AccountConfig):
        """Add an account directly (programmatic setup)."""
        self.account_manager.add_account(config)

    # ─────────────────────── LIFECYCLE ───────────────────────

    async def start(self) -> Dict[str, bool]:
        """Connect all accounts and start the scanning loop."""
        logger.info(
            "╔══════════════════════════════════════════════════════╗\n"
            "║    FOREXIA MULTI-ACCOUNT ORCHESTRATOR — STARTING     ║\n"
            "╚══════════════════════════════════════════════════════╝"
        )

        results = await self.account_manager.connect_all()

        connected = sum(1 for v in results.values() if v)
        if connected == 0:
            logger.error("No accounts connected — aborting start")
            return results

        self._running = True
        self._scan_task = asyncio.create_task(self._main_loop())

        logger.info(f"Scan loop started — interval: {self.SCAN_INTERVAL}s")
        return results

    async def stop(self):
        """Stop scanning and disconnect all accounts."""
        self._running = False

        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass

        await self.account_manager.disconnect_all()
        logger.info("Multi-Account Orchestrator stopped")

    # ─────────────────────── MAIN LOOP ───────────────────────

    async def _main_loop(self):
        """
        Main scanning loop — the heartbeat of the multi-account system.
        
        Runs every SCAN_INTERVAL seconds:
          1. Check each enabled account
          2. For each account's symbols, fetch candles
          3. Run SignatureTradeV2 detection
          4. Evaluate through PropFirmRiskManager
          5. Execute approved trades
        """
        while self._running:
            try:
                self._scan_count += 1
                scan_start = datetime.now(timezone.utc)

                logger.info(
                    f"━━━ SCAN #{self._scan_count} ━━━ "
                    f"{scan_start.strftime('%H:%M:%S')} UTC"
                )

                accounts = self.account_manager.get_enabled_accounts()
                total_signals = 0
                total_trades = 0

                for account_id in accounts:
                    try:
                        signals, trades = await self._scan_account(account_id)
                        total_signals += signals
                        total_trades += trades
                    except Exception as e:
                        logger.error(f"Scan error on {account_id}: {e}")

                elapsed = (datetime.now(timezone.utc) - scan_start).total_seconds()
                logger.info(
                    f"Scan #{self._scan_count} complete — "
                    f"{total_signals} signals, {total_trades} trades — "
                    f"{elapsed:.1f}s"
                )

                # Wait for next scan
                await asyncio.sleep(self.SCAN_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                await asyncio.sleep(10)

    async def _scan_account(self, account_id: str) -> tuple:
        """
        Scan all symbols for a single account.
        
        Returns: (signal_count, trade_count)
        """
        config = self.account_manager._accounts.get(account_id)
        bridge = self.account_manager.get_bridge(account_id)

        if not config or not bridge:
            return (0, 0)

        signal_count = 0
        trade_count = 0

        for symbol in config.symbols:
            try:
                # Skip if outside trade window
                if not self.market_adapter.in_trade_window(symbol):
                    continue

                # Fetch candles (M15 timeframe for Signature Trade)
                candles = await bridge.get_candles(
                    symbol=symbol,
                    timeframe="M15",
                    count=100,
                )

                if not candles or len(candles) < 30:
                    continue

                # Convert candle format if needed
                candle_dicts = self._normalize_candles(candles)

                # Run Signature Trade V2 detection
                signal = self.signature.scan(symbol, candle_dicts)

                # Store scan result
                self._last_scan_results[f"{account_id}:{symbol}"] = {
                    "phase": signal.phase.value,
                    "confidence": signal.confidence,
                    "direction": signal.direction,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                if signal.phase != SignalPhase.ENTRY_READY:
                    continue

                signal_count += 1

                # ── EVALUATE THROUGH RISK MANAGER ──
                verdict = self.risk_manager.evaluate(
                    account_id=account_id,
                    symbol=symbol,
                    direction=signal.direction,
                    entry_price=signal.entry_price,
                    hunt_extreme=signal.hunt_extreme,
                    wedge_start=signal.wedge_start_price,
                    candles=candle_dicts,
                )

                if not verdict.approved:
                    logger.info(
                        f"[{account_id}] {symbol} signal BLOCKED: {verdict.reason}"
                    )
                    continue

                # ── EXECUTE TRADE ──
                logger.info(
                    f"[{account_id}] 🎯 EXECUTING: {signal.direction} {symbol} "
                    f"lots={verdict.lot_size} SL={verdict.stop_loss} TP={verdict.take_profit} "
                    f"R:R={verdict.risk_reward_ratio}:1 "
                    f"confidence={signal.confidence}%"
                )

                # For limit orders (NASDAQ), use a limit entry
                if verdict.limit_price is not None:
                    # Place limit order via MT5
                    ticket = await self._execute_limit_order(
                        account_id=account_id,
                        bridge=bridge,
                        symbol=symbol,
                        direction=signal.direction,
                        lot_size=verdict.lot_size,
                        limit_price=verdict.limit_price,
                        stop_loss=verdict.stop_loss,
                        take_profit=verdict.take_profit,
                    )
                else:
                    # Market order (FX)
                    ticket = await self.account_manager.execute_on_account(
                        account_id=account_id,
                        symbol=symbol,
                        direction=signal.direction,
                        lot_size=verdict.lot_size,
                        stop_loss=verdict.stop_loss,
                        take_profit=verdict.take_profit,
                        comment=f"SIG_V2_{signal.confidence:.0f}",
                    )

                if ticket:
                    trade_count += 1
                    self._log_trade(
                        account_id=account_id,
                        symbol=symbol,
                        signal=signal,
                        verdict=verdict,
                        ticket=ticket,
                    )

            except Exception as e:
                logger.error(f"[{account_id}] Error scanning {symbol}: {e}")

        return (signal_count, trade_count)

    # ─────────────────────── LIMIT ORDERS (NASDAQ) ───────────────────────

    async def _execute_limit_order(
        self,
        account_id: str,
        bridge: Any,
        symbol: str,
        direction: str,
        lot_size: float,
        limit_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> Optional[int]:
        """
        Place a limit order for index instruments.
        
        MT5 uses ORDER_TYPE_BUY_LIMIT or ORDER_TYPE_SELL_LIMIT.
        MatchTrader uses pending order API.
        """
        try:
            # Check if bridge supports limit orders
            if hasattr(bridge, 'execute_limit_order'):
                from backend.models.schemas import TradeDirection
                dir_enum = TradeDirection.BUY if direction == "BUY" else TradeDirection.SELL
                return await bridge.execute_limit_order(
                    symbol=symbol,
                    direction=dir_enum,
                    lot_size=lot_size,
                    price=limit_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    comment=f"SIG_V2_LIMIT_{account_id}",
                )
            else:
                # Fallback: execute as market order with a note
                logger.warning(
                    f"[{account_id}] Bridge doesn't support limit orders — "
                    f"executing market order for {symbol}"
                )
                return await self.account_manager.execute_on_account(
                    account_id=account_id,
                    symbol=symbol,
                    direction=direction,
                    lot_size=lot_size,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    comment=f"SIG_V2_MKT_FALLBACK",
                )
        except Exception as e:
            logger.error(f"[{account_id}] Limit order error for {symbol}: {e}")
            return None

    # ─────────────────────── CANDLE NORMALIZATION ───────────────────────

    def _normalize_candles(self, candles: Any) -> List[Dict]:
        """
        Normalize candle data to standard dict format.
        
        Handles:
          - List of CandleData objects
          - List of dicts with various key names
          - MT5 rate tuples
        """
        if not candles:
            return []

        result = []
        for c in candles:
            if isinstance(c, dict):
                result.append({
                    "open": c.get("open", c.get("o", 0)),
                    "high": c.get("high", c.get("h", 0)),
                    "low": c.get("low", c.get("l", 0)),
                    "close": c.get("close", c.get("c", 0)),
                    "volume": c.get("volume", c.get("v", 0)),
                    "time": c.get("time", c.get("t", "")),
                })
            elif hasattr(c, "open"):
                result.append({
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": getattr(c, "volume", 0),
                    "time": getattr(c, "time", ""),
                })
            elif isinstance(c, (list, tuple)) and len(c) >= 5:
                # MT5 tuple format: (time, open, high, low, close, ...)
                result.append({
                    "time": c[0],
                    "open": c[1],
                    "high": c[2],
                    "low": c[3],
                    "close": c[4],
                    "volume": c[5] if len(c) > 5 else 0,
                })

        return result

    # ─────────────────────── TRADE LOGGING ───────────────────────

    def _log_trade(
        self,
        account_id: str,
        symbol: str,
        signal: Any,
        verdict: RiskVerdict,
        ticket: int,
    ):
        """Log a trade execution for audit trail."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "account_id": account_id,
            "symbol": symbol,
            "direction": signal.direction,
            "lot_size": verdict.lot_size,
            "entry_price": signal.entry_price,
            "stop_loss": verdict.stop_loss,
            "take_profit": verdict.take_profit,
            "risk_reward": verdict.risk_reward_ratio,
            "risk_amount": verdict.risk_amount,
            "risk_pct": verdict.risk_pct,
            "confidence": signal.confidence,
            "order_type": verdict.order_type,
            "ticket": ticket,
        }
        self._trade_log.append(entry)

        # Keep last 500 trades
        if len(self._trade_log) > 500:
            self._trade_log = self._trade_log[-500:]

        logger.info(f"Trade logged: {json.dumps(entry, default=str)}")

    # ─────────────────────── FORCE SCAN ───────────────────────

    async def force_scan(self) -> Dict:
        """Trigger an immediate scan across all accounts."""
        results = {"signals": 0, "trades": 0, "accounts_scanned": 0}

        for account_id in self.account_manager.get_enabled_accounts():
            try:
                signals, trades = await self._scan_account(account_id)
                results["signals"] += signals
                results["trades"] += trades
                results["accounts_scanned"] += 1
            except Exception as e:
                logger.error(f"Force scan error on {account_id}: {e}")

        return results

    # ─────────────────────── STATUS ───────────────────────

    def get_status(self) -> Dict:
        """Get complete status for the dashboard."""
        account_status = self.account_manager.get_status()

        # Add risk summaries per account
        for account_id in account_status.get("accounts", {}):
            risk_summary = self.risk_manager.get_account_risk_summary(account_id)
            account_status["accounts"][account_id]["risk"] = risk_summary

        return {
            "running": self._running,
            "scan_count": self._scan_count,
            "scan_interval": self.SCAN_INTERVAL,
            "last_scan_results": self._last_scan_results,
            "recent_trades": self._trade_log[-10:],
            **account_status,
        }

    def get_trade_log(self, limit: int = 50) -> List[Dict]:
        """Get recent trade log entries."""
        return self._trade_log[-limit:]
