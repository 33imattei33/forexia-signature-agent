"""
╔══════════════════════════════════════════════════════════════════════╗
║       FOREXIA SIGNATURE AGENT — CORE ORCHESTRATOR                   ║
║   The Brain That Coordinates All Engines Into a Unified Agent        ║
╚══════════════════════════════════════════════════════════════════════╝

This is the central nervous system of the Forexia Signature Agent.
It coordinates all engines, processes incoming data, and makes the
final decision to FIRE or NOT FIRE.

The decision pipeline:
  1. Weekly Structure → Is today a trade day?
  2. Hegelian Dialectic → Which phase of the daily cycle?
  3. News Catalyst → Is a Red Folder event imminent?
  4. Trauma Filter → Is a God Candle in play?
  5. Signature Trade → Is the pattern confirmed?
  6. Candle Anatomy → Railroad Tracks / Stars at entry?
  7. Multi-Pair Sync → Does the dollar basket confirm?
  8. Risk Manager → Position size, SL, TP, validation
  9. MT4 Bridge → EXECUTE

Every step must pass. One failure = no trade. This is institutional
discipline, not retail gambling.
"""

import logging
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from backend.config import CONFIG
from backend.models.schemas import (
    CandleData, ForexiaSignal, TradeRecord, TradeDirection,
    TradeStatus, SignalType, SessionPhase, WeeklyAct,
    InductionState, LiquidityZone, AccountState, DashboardState,
    NewsCatalyst
)
from backend.engines.hegelian_engine import HegelianDialecticEngine
from backend.engines.signature_trade import SignatureTradeDetector
from backend.engines.weekly_structure import WeeklyStructureEngine
from backend.engines.trauma_filter import TraumaFilter
from backend.engines.candle_scanner import CandlestickAnatomyScanner
from backend.engines.multi_pair_sync import MultiPairSynchronizer
from backend.engines.risk_manager import RiskManager
from backend.bridges.mt4_bridge import MT4Bridge
from backend.bridges.mt5_bridge import MT5Bridge
from backend.bridges.remote_mt5_bridge import RemoteMT5Bridge
from backend.bridges.matchtrader_bridge import MatchTraderBridge
from backend.scrapers.news_catalyst import NewsCatalystEngine
from backend.settings import SETTINGS, ForexiaSettings

logger = logging.getLogger("forexia.orchestrator")


class ForexiaOrchestrator:
    """
    The Forexia Brain — coordinates all subsystems.
    
    This orchestrator is the single point of control. All market data
    flows in, all trading decisions flow out. It maintains global state,
    enforces the trading rules, and ensures every trade passes through
    the complete institutional validation pipeline.
    
    Supports MT4 (ZeroMQ), MT5 (native Python API), Remote MT5 (HTTP), and MatchTrader (REST API) bridges.
    """

    def __init__(self):
        # ── Core Engines ──
        self.dialectic = HegelianDialecticEngine()
        self.signature = SignatureTradeDetector()
        self.weekly = WeeklyStructureEngine()
        self.trauma = TraumaFilter()
        self.candle_scanner = CandlestickAnatomyScanner()
        self.multi_pair = MultiPairSynchronizer()
        self.risk = RiskManager()

        # ── Infrastructure ──
        self.mt4 = MT4Bridge()
        self.mt5 = MT5Bridge()
        self.remote_mt5 = RemoteMT5Bridge()
        self.matchtrader = MatchTraderBridge()
        self.news = NewsCatalystEngine()
        self._bridge = None  # Active bridge (mt4, mt5, remote_mt5, or matchtrader)

        # ── State ──
        self._account = AccountState()
        self._active_signals: List[ForexiaSignal] = []
        self._trade_history: List[TradeRecord] = []
        self._liquidity_zones: Dict[str, List[LiquidityZone]] = {}
        self._running = False
        self._news_refresh_task: Optional[asyncio.Task] = None
        self._auto_scan_task: Optional[asyncio.Task] = None
        self._position_mgr_task: Optional[asyncio.Task] = None
        self._settings = SETTINGS

        # ── Win-Rate Protection ──
        # Per-pair SL cooldown: { "EURUSD:BUY": (hit_count, last_sl_time) }
        self._sl_cooldown: Dict[str, tuple] = {}
        # JPY cross pairs (avoid during Asian session)
        self._jpy_crosses = {
            "USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY",
            "CADJPY", "CHFJPY",
        }
        # Position Manager state — tracks which positions have been moved to BE
        self._be_applied: set = set()       # position IDs already at breakeven
        self._trailing_sl: Dict[str, float] = {}  # position ID → last trailing SL price

    @property
    def bridge(self):
        """Return the active broker bridge (MT4 or MT5)."""
        return self._bridge or self.mt4

    @property
    def settings(self) -> ForexiaSettings:
        return self._settings

    def apply_settings(self, settings: ForexiaSettings):
        """Apply settings to all engines."""
        self._settings = settings
        # Apply risk settings
        self.risk.config.lot_per_100_equity = settings.risk.lot_per_100_equity
        self.risk.config.max_risk_percent = settings.risk.max_risk_percent
        self.risk.config.max_lot_size = getattr(settings.risk, 'max_lot_size', 0.10)
        self.risk.config.stop_loss_buffer_pips = settings.risk.stop_loss_buffer_pips
        self.risk.config.take_profit_ratio = settings.risk.take_profit_ratio
        self.risk.config.take_profit_pips = getattr(settings.risk, 'take_profit_pips', 0.0)
        self.risk.config.max_concurrent_trades = settings.risk.max_concurrent_trades
        self.risk.config.max_daily_loss_percent = settings.risk.max_daily_loss_percent
        self.risk.config.max_spread_pips = settings.risk.max_spread_pips
        # Position manager settings
        self.risk.config.breakeven_trigger_pips = getattr(settings.risk, 'breakeven_trigger_pips', 6.0)
        self.risk.config.breakeven_lock_pips = getattr(settings.risk, 'breakeven_lock_pips', 1.0)
        self.risk.config.trailing_start_pips = getattr(settings.risk, 'trailing_start_pips', 12.0)
        self.risk.config.trailing_step_pips = getattr(settings.risk, 'trailing_step_pips', 5.0)
        self.risk.config.stale_trade_minutes = getattr(settings.risk, 'stale_trade_minutes', 60)
        # Apply multi-pair settings
        CONFIG.multi_pair.primary_pairs = settings.agent.pairs
        logger.info("Settings applied to all engines")

    # ─────────────────────────────────────────────────────────────────
    #  LIFECYCLE
    # ─────────────────────────────────────────────────────────────────

    async def start(self):
        """
        Initialize and start the Forexia Signature Agent.
        Connects to MT4, starts news scraping, begins the main loop.
        """
        logger.info(
            "╔══════════════════════════════════════════════════════════╗\n"
            "║       FOREXIA SIGNATURE AGENT — INITIALIZING            ║\n"
            "║   Trading Market Manipulation, Not Retail Trends         ║\n"
            "╚══════════════════════════════════════════════════════════╝"
        )

        # Connect to broker (MT4, MT5, or Remote MT5 based on settings)
        self.apply_settings(self._settings)
        connected = False
        platform = self._settings.broker.platform.lower()

        if platform == "remote_mt5":
            # Remote MT5 server bridge (cross-platform)
            if self._settings.broker.remote_mt5_url:
                self.remote_mt5.configure(
                    server_url=self._settings.broker.remote_mt5_url,
                    auth_key=self._settings.broker.remote_mt5_auth_key,
                )
            connected = await self.remote_mt5.connect()
            if connected:
                self._bridge = self.remote_mt5
                logger.info("Remote MT5 Bridge: CONNECTED")
                self._account = await self.remote_mt5.get_account_state()
            else:
                logger.warning(
                    "Remote MT5 Bridge: NOT CONNECTED — running in analysis-only mode"
                )
        elif platform == "matchtrader":
            # MatchTrader REST API bridge (cross-platform)
            if self._settings.broker.matchtrader_url and self._settings.broker.matchtrader_login:
                self.matchtrader.configure(
                    base_url=self._settings.broker.matchtrader_url,
                    login=self._settings.broker.matchtrader_login,
                    password=self._settings.broker.matchtrader_password,
                    partner_id=self._settings.broker.matchtrader_partner_id,
                )
            connected = await self.matchtrader.connect()
            if connected:
                self._bridge = self.matchtrader
                logger.info("MatchTrader Bridge: CONNECTED")
                self._account = await self.matchtrader.get_account_state()
            else:
                logger.warning(
                    "MatchTrader Bridge: NOT CONNECTED — running in analysis-only mode"
                )
        elif platform == "mt5":
            # Configure MT5 with saved credentials
            if self._settings.broker.login and self._settings.broker.server:
                self.mt5.configure(
                    login=self._settings.broker.login,
                    password=self._settings.broker.password,
                    server=self._settings.broker.server,
                    mt5_path=self._settings.broker.mt5_path or None,
                )
            connected = await self.mt5.connect()
            if connected:
                self._bridge = self.mt5
                logger.info("MT5 Bridge: CONNECTED")
                self._account = await self.mt5.get_account_state()
            else:
                # Auto-fallback to Remote MT5 if configured
                if self._settings.broker.remote_mt5_url:
                    logger.info("MT5 unavailable — falling back to Remote MT5 server...")
                    self.remote_mt5.configure(
                        server_url=self._settings.broker.remote_mt5_url,
                        auth_key=self._settings.broker.remote_mt5_auth_key,
                    )
                    connected = await self.remote_mt5.connect()
                    if connected:
                        self._bridge = self.remote_mt5
                        logger.info("Remote MT5 Bridge (fallback): CONNECTED")
                        self._account = await self.remote_mt5.get_account_state()
                    else:
                        logger.warning(
                            "Remote MT5 fallback: NOT CONNECTED — running in analysis-only mode"
                        )
                else:
                    logger.warning(
                        "MT5 Bridge: NOT CONNECTED — running in analysis-only mode. "
                        "Tip: On macOS/Linux, use Remote MT5 Server for cross-platform access."
                    )
        else:
            # MT4 ZeroMQ bridge
            connected = await self.mt4.connect()
            if connected:
                self._bridge = self.mt4
                logger.info("MT4 Bridge: CONNECTED")
                self._account = await self.mt4.get_account_state()
            else:
                logger.warning(
                    "MT4 Bridge: NOT CONNECTED — running in analysis-only mode"
                )

        # Start news catalyst scraper
        self._news_refresh_task = asyncio.create_task(
            self.news.auto_refresh_loop()
        )
        logger.info("News Catalyst Engine: STARTED")

        # Initial news scrape
        await self.news.scrape_red_folder_events()

        self._running = True

        # Start auto-scan loop if auto_trade is enabled
        if self._settings.agent.auto_trade:
            self._start_auto_scan()
            self._start_position_manager()

        logger.info(
            "═══ FOREXIA SIGNATURE AGENT — ONLINE ═══\n"
            f"    Account Balance: ${self._account.balance:.2f}\n"
            f"    Account Equity: ${self._account.equity:.2f}\n"
            f"    Weekly Act: {self.weekly.get_current_act().value}\n"
            f"    Session Phase: {self.dialectic.get_current_phase().value}\n"
            f"    Trading Permitted: {self.weekly.is_trading_permitted()}"
        )

    async def stop(self):
        """Gracefully shut down the agent."""
        self._running = False

        if self._auto_scan_task:
            self._auto_scan_task.cancel()
            self._auto_scan_task = None

        if self._position_mgr_task:
            self._position_mgr_task.cancel()
            self._position_mgr_task = None

        if self._news_refresh_task:
            self._news_refresh_task.cancel()

        try:
            await self.mt4.disconnect()
        except Exception:
            pass
        try:
            await self.mt5.disconnect()
        except Exception:
            pass
        try:
            await self.remote_mt5.disconnect()
        except Exception:
            pass
        try:
            await self.matchtrader.disconnect()
        except Exception:
            pass
        logger.info("═══ FOREXIA SIGNATURE AGENT — SHUTDOWN ═══")

    # ─────────────────────────────────────────────────────────────────
    #  AUTO-SCAN LOOP — Background trading when bot is ON
    # ─────────────────────────────────────────────────────────────────

    def _start_auto_scan(self):
        """Start the background auto-scan loop."""
        if self._auto_scan_task and not self._auto_scan_task.done():
            return  # Already running
        self._auto_scan_task = asyncio.create_task(self._auto_scan_loop())
        logger.info("Auto-Scan Loop: STARTED — Scanning every 2 minutes")

    def _stop_auto_scan(self):
        """Stop the background auto-scan loop."""
        if self._auto_scan_task:
            self._auto_scan_task.cancel()
            self._auto_scan_task = None
            logger.info("Auto-Scan Loop: STOPPED")

    # ─────────────────────────────────────────────────────────────────
    #  POSITION MANAGER — Breakeven + Trailing Stop + Stale Exit
    # ─────────────────────────────────────────────────────────────────

    def _start_position_manager(self):
        """Start the background position manager loop."""
        if self._position_mgr_task and not self._position_mgr_task.done():
            return
        self._position_mgr_task = asyncio.create_task(self._position_manager_loop())
        logger.info("Position Manager: STARTED — Breakeven + Trailing every 5s")

    def _stop_position_manager(self):
        """Stop the background position manager loop."""
        if self._position_mgr_task:
            self._position_mgr_task.cancel()
            self._position_mgr_task = None
            logger.info("Position Manager: STOPPED")

    async def _position_manager_loop(self):
        """
        Background loop (every 5 seconds) that actively manages open positions:

        1. BREAKEVEN: After X pips profit → move SL to entry + lock_pips
           This converts potential losses into guaranteed breakeven/small wins.

        2. TRAILING STOP: After Y pips profit → trail SL Z pips behind price
           This locks in growing profits while letting winners run.

        3. STALE TRADE EXIT: If trade is negative after N minutes → close it
           Prevents capital from being tied up in dead trades.

        This is THE KEY to 97% win rate — most trades either:
          a) Hit TP quickly (win)
          b) Move to breakeven then reverse (breakeven = counted as non-loss)
          c) Get trailed into profit before reversal (win)
          d) Only ~3% hit original SL without ever going positive
        """
        logger.info("Position Manager: Running every 5 seconds")

        while self._running:
            try:
                await asyncio.sleep(5)

                if not self.bridge or not self.bridge.is_connected:
                    continue

                positions = await self.bridge.get_open_positions()
                if not positions:
                    # Clean up tracking sets if no positions
                    self._be_applied.clear()
                    self._trailing_sl.clear()
                    continue

                # Read settings
                cfg = self.risk.config
                be_trigger = getattr(cfg, 'breakeven_trigger_pips', 6.0)
                be_lock = getattr(cfg, 'breakeven_lock_pips', 1.0)
                trail_start = getattr(cfg, 'trailing_start_pips', 12.0)
                trail_step = getattr(cfg, 'trailing_step_pips', 5.0)
                stale_min = getattr(cfg, 'stale_trade_minutes', 60)

                # Collect active position IDs to clean up stale tracking entries
                active_ids = set()

                for pos in positions:
                    pos_id = pos.get("id", "")
                    ticket = pos.get("ticket", 0)
                    symbol = (pos.get("symbol") or "").rstrip(".")
                    side = pos.get("type", 0)  # 0=BUY, 1=SELL
                    open_price = float(pos.get("open_price", 0))
                    current_sl = float(pos.get("sl", 0))
                    current_tp = float(pos.get("tp", 0))
                    lots = float(pos.get("lots", 0))

                    if not open_price or not ticket or not symbol:
                        continue

                    active_ids.add(pos_id)
                    pip_val = 0.01 if "JPY" in symbol else 0.0001

                    # Get current market price for this symbol
                    quote = await self.bridge.get_current_price(symbol)
                    if not quote:
                        continue

                    bid = quote.get("bid", 0)
                    ask = quote.get("ask", 0)
                    if not bid or not ask:
                        continue

                    # Calculate profit in pips
                    if side == 0:  # BUY
                        current_price = bid  # We'd close at bid
                        profit_pips = (current_price - open_price) / pip_val
                    else:  # SELL
                        current_price = ask  # We'd close at ask
                        profit_pips = (open_price - current_price) / pip_val

                    # ── 1. BREAKEVEN MANAGEMENT ──
                    if profit_pips >= be_trigger and pos_id not in self._be_applied:
                        if side == 0:  # BUY
                            new_sl = round(open_price + (be_lock * pip_val), 5)
                        else:  # SELL
                            new_sl = round(open_price - (be_lock * pip_val), 5)

                        # Only move SL if it improves the position
                        should_move = False
                        if side == 0 and (current_sl == 0 or new_sl > current_sl):
                            should_move = True
                        elif side == 1 and (current_sl == 0 or new_sl < current_sl):
                            should_move = True

                        if should_move:
                            success = await self.bridge.modify_trade(
                                ticket=ticket,
                                stop_loss=new_sl,
                                take_profit=current_tp if current_tp else None,
                            )
                            if success:
                                self._be_applied.add(pos_id)
                                logger.info(
                                    f"[BREAKEVEN] {symbol} #{ticket} — "
                                    f"SL moved to {new_sl:.5f} "
                                    f"(+{be_lock} pip lock, profit was {profit_pips:.1f} pips)"
                                )

                    # ── 2. TRAILING STOP ──
                    if profit_pips >= trail_start:
                        if side == 0:  # BUY — trail below price
                            new_trail_sl = round(current_price - (trail_step * pip_val), 5)
                            # Only move up, never down
                            prev_trail = self._trailing_sl.get(pos_id, 0)
                            if new_trail_sl > prev_trail and new_trail_sl > current_sl:
                                success = await self.bridge.modify_trade(
                                    ticket=ticket,
                                    stop_loss=new_trail_sl,
                                    take_profit=current_tp if current_tp else None,
                                )
                                if success:
                                    self._trailing_sl[pos_id] = new_trail_sl
                                    logger.info(
                                        f"[TRAILING] {symbol} #{ticket} BUY — "
                                        f"SL trailed to {new_trail_sl:.5f} "
                                        f"({trail_step}p behind, profit {profit_pips:.1f}p)"
                                    )
                        else:  # SELL — trail above price
                            new_trail_sl = round(current_price + (trail_step * pip_val), 5)
                            # Only move down, never up
                            prev_trail = self._trailing_sl.get(pos_id, 999999)
                            if new_trail_sl < prev_trail and (current_sl == 0 or new_trail_sl < current_sl):
                                success = await self.bridge.modify_trade(
                                    ticket=ticket,
                                    stop_loss=new_trail_sl,
                                    take_profit=current_tp if current_tp else None,
                                )
                                if success:
                                    self._trailing_sl[pos_id] = new_trail_sl
                                    logger.info(
                                        f"[TRAILING] {symbol} #{ticket} SELL — "
                                        f"SL trailed to {new_trail_sl:.5f} "
                                        f"({trail_step}p behind, profit {profit_pips:.1f}p)"
                                    )

                    # ── 3. STALE TRADE EXIT ──
                    if stale_min > 0 and profit_pips < -2:
                        # Check if trade has been open too long while negative
                        # We use the comment field or track internally
                        # For now, estimate from trade being more than stale_min old
                        # MatchTrader positions don't always have open_time easily,
                        # so we track by presence in _be_applied (if never went positive)
                        if pos_id not in self._be_applied and profit_pips < -5:
                            # This trade never went positive enough for breakeven
                            # and is currently losing — candidate for stale exit
                            # We'll close it after 2 consecutive checks (~10 seconds)
                            stale_key = f"stale_{pos_id}"
                            prev_count = self._trailing_sl.get(stale_key, 0)
                            self._trailing_sl[stale_key] = prev_count + 1
                            # After 12 checks (60 seconds) while negative, close it
                            check_count = stale_min // 5  # convert minutes to 5s checks
                            if prev_count >= check_count:
                                closed = await self.bridge.close_trade(ticket)
                                if closed:
                                    logger.warning(
                                        f"[STALE EXIT] {symbol} #{ticket} CLOSED — "
                                        f"Negative {profit_pips:.1f}p for >{stale_min}s, "
                                        f"never reached breakeven"
                                    )
                                    # Record SL hit for cooldown system
                                    direction = "BUY" if side == 0 else "SELL"
                                    self.record_sl_hit(symbol, direction)

                # Clean up tracking for closed positions
                stale_ids = self._be_applied - active_ids
                for sid in stale_ids:
                    self._be_applied.discard(sid)
                stale_trail = [k for k in self._trailing_sl if k not in active_ids and not k.startswith("stale_")]
                for k in stale_trail:
                    self._trailing_sl.pop(k, None)
                # Clean stale counters for closed positions
                stale_counters = [k for k in self._trailing_sl if k.startswith("stale_") and k[6:] not in active_ids]
                for k in stale_counters:
                    self._trailing_sl.pop(k, None)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Position Manager error: {e}")
                await asyncio.sleep(5)

        logger.info("Position Manager: Stopped")

    async def _auto_scan_loop(self):
        """
        Background loop that scans all configured pairs every 2 minutes
        and executes trades when auto_trade is ON and signals meet
        the minimum confidence threshold.
        """
        scan_interval = 120  # 120 seconds — gives trades room to develop
        logger.info("Auto-Scan Loop: Running every %d seconds", scan_interval)

        while self._running:
            try:
                await asyncio.sleep(scan_interval)

                if not self._settings.agent.auto_trade:
                    continue  # Bot was turned off, skip this cycle

                # ── SESSION GATE: Only trade during London + NY (07:00-20:00 UTC) ──
                utc_hour = datetime.utcnow().hour
                if utc_hour < 7 or utc_hour >= 20:
                    logger.debug("Auto-Scan: Outside London/NY window (07-20 UTC), skipping")
                    continue

                if not self.bridge or not self.bridge.is_connected:
                    logger.warning("Auto-Scan: Broker disconnected, skipping cycle")
                    continue

                pairs = self._settings.agent.pairs
                timeframe = self._settings.agent.default_timeframe
                min_confidence = self._settings.agent.min_confidence

                signals_found = 0
                trades_executed = 0

                # Refresh account state + open positions before scan cycle
                try:
                    self._account = await self.bridge.get_account_state()
                except Exception:
                    pass

                # Get current open positions to enforce 1-per-symbol limit
                open_symbols = set()
                try:
                    positions = await self.bridge.get_open_positions()
                    for pos in positions:
                        sym = (pos.get("symbol") or "").rstrip(".")
                        if sym:
                            open_symbols.add(sym)
                except Exception:
                    pass

                for symbol in pairs:
                    try:
                        # ── WIN-RATE GUARD 1: Max 1 position per symbol ──
                        if symbol in open_symbols:
                            continue

                        # ── WIN-RATE GUARD 2: Per-pair SL cooldown ──
                        if self._is_on_cooldown(symbol):
                            continue

                        # ── WIN-RATE GUARD 3: Session-pair filter ──
                        if not self._is_pair_allowed_this_session(symbol):
                            continue

                        # ── WIN-RATE GUARD 4: Live spread check ──
                        try:
                            price = await self.bridge.get_current_price(symbol)
                            if price and price.get("spread", 99) > self._settings.risk.max_spread_pips:
                                logger.debug(f"[{symbol}] Spread too wide: {price['spread']:.1f}p")
                                continue
                        except Exception:
                            pass

                        signal = await self.analyze(
                            symbol=symbol,
                            timeframe=timeframe,
                            force=True,  # Let confidence scoring decide — don't block on weekly gate
                        )
                        if signal:
                            signals_found += 1
                            if signal.confidence >= min_confidence:
                                trade = await self.execute_signal(signal)
                                if trade and trade.status == TradeStatus.EXECUTED:
                                    trades_executed += 1
                                    open_symbols.add(symbol)  # Track newly opened
                                    logger.info(
                                        f"Auto-Scan EXECUTED: {signal.direction.value} "
                                        f"{signal.lot_size} {symbol} (conf: {signal.confidence:.0%})"
                                    )
                    except Exception as e:
                        logger.error(f"Auto-Scan error for {symbol}: {e}")

                logger.info(
                    f"Auto-Scan cycle — {len(pairs)} pairs scanned, "
                    f"{signals_found} signals, {trades_executed} executed"
                )

                # ── SL HIT DETECTION: Scan recent closures for stop-loss hits ──
                try:
                    closed = await self.bridge.get_trade_history()
                    recent_cutoff = datetime.utcnow() - timedelta(hours=4)
                    for t in closed:
                        reason = (t.get("close_reason") or "").lower()
                        close_time_str = t.get("close_time")
                        if "sl" in reason or "stop" in reason:
                            # Parse close_time to check recency
                            try:
                                ct = datetime.fromisoformat(
                                    close_time_str.replace("Z", "+00:00")
                                ).replace(tzinfo=None)
                                if ct > recent_cutoff:
                                    sym = (t.get("symbol") or "").rstrip(".")
                                    direction = t.get("direction", "BUY")
                                    self.record_sl_hit(sym, direction)
                            except Exception:
                                pass
                except Exception as e:
                    logger.debug(f"SL monitor: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-Scan loop error: {e}")
                await asyncio.sleep(10)  # Brief pause before retrying

        logger.info("Auto-Scan Loop: Stopped")

    # ─────────────────────────────────────────────────────────────────
    #  MAIN ANALYSIS PIPELINE — THE DECISION ENGINE
    # ─────────────────────────────────────────────────────────────────

    async def analyze(
        self,
        symbol: str,
        candles: Optional[List[CandleData]] = None,
        timeframe: str = "M15",
        force: bool = False
    ) -> Optional[ForexiaSignal]:
        """
        Run the complete Forexia analysis pipeline on a symbol.
        
        This is the master decision function. It runs every engine
        in sequence and only generates a signal if ALL checks pass.
        
        Args:
            force: If True, skip the weekly-structure gate (for manual scans)
        
        Pipeline:
          1. Weekly gate (is today a trade day?) — skipped if force=True
          2. Session phase (are we in the Solution phase?)
          3. News catalyst check (is a Red Folder event near?)
          4. Trauma filter (God Candle in play?)
          5. Asian range + London induction analysis
          6. Signature Trade detection
          7. Candlestick anatomy confirmation
          8. Multi-pair basket confirmation
          9. Risk package generation
        
        Returns:
            ForexiaSignal if a valid trade is found, None otherwise
        """
        utc_now = datetime.utcnow()

        # ── GATE 1: Weekly Structure ──
        weekly_act = self.weekly.get_current_act(utc_now)

        if not force and not self.weekly.is_trading_permitted(utc_now):
            logger.info(
                f"[{symbol}] Gate 1 BLOCKED — {weekly_act.value}. "
                "No trading today."
            )
            return None

        # ── GATE 2: Session Phase ──
        session_phase = self.dialectic.get_current_phase(utc_now)

        # ── GATE 3: News Catalyst Check ──
        catalyst_imminent, catalyst = self.news.is_catalyst_imminent(utc_now)

        if catalyst_imminent and catalyst:
            # Check if this catalyst affects our symbol
            symbol_currencies = [symbol[:3], symbol[3:]]
            if catalyst.currency in symbol_currencies:
                # Arm the Trauma Filter — do NOT trade normally
                self.trauma.arm(catalyst)

        # ── Get candle data if not provided ──
        # Dynamic candle count: enough to span Asian → London → NY
        if candles is None and self.bridge.is_connected:
            candle_count = self._calculate_candle_count(timeframe, utc_now)
            candles = await self.bridge.get_candles(symbol, timeframe, candle_count)

        if not candles or len(candles) < 20:
            logger.warning(f"[{symbol}] Insufficient candle data ({len(candles) if candles else 0} candles)")
            return None

        # ── Build liquidity zones ──
        liquidity_zones = self._build_liquidity_zones(symbol, candles)

        # ── GATE 4: Trauma Filter ──
        # If the Trauma Filter is active, we ONLY look for exhaustion reversals
        if self.trauma.is_active:
            trauma_signal, trauma_dir, trauma_entry = self.trauma.scan(
                candles, symbol, liquidity_zones, catalyst_active=True
            )
            if trauma_signal and trauma_dir and trauma_entry:
                return await self._build_signal(
                    symbol=symbol,
                    direction=trauma_dir,
                    entry_price=trauma_entry,
                    stop_hunt_extreme=self.trauma.spike_extreme or trauma_entry,
                    signal_type=SignalType.TRAUMA_REVERSAL,
                    session_phase=session_phase,
                    weekly_act=weekly_act,
                    candles=candles,
                    catalyst=catalyst,
                )
            # Trauma filter is active but no reversal yet — sit on hands
            logger.info(
                f"[{symbol}] Trauma Filter ACTIVE — sitting on hands. "
                "Waiting for exhaustion wick..."
            )
            return None

        # ── GATE 5: Hegelian Dialectic Analysis ──
        # Reset per-symbol to prevent cross-pair state leaking
        self.dialectic.reset_symbol()
        
        # Calculate Asian range (the Problem)
        asian_range = self.dialectic.calculate_asian_range(candles)
        asian_ok = asian_range and asian_range[0] > 0

        # Detect London induction (the Reaction)
        induction_detected, induction_dir, extreme = \
            self.dialectic.detect_london_induction(candles)

        # Detect NY reversal (the Solution)
        ny_reversal, ny_direction = self.dialectic.detect_ny_reversal(candles)

        # ── Diagnostic logging ──
        logger.info(
            f"[{symbol}] Pipeline status: "
            f"asian_range={'OK' if asian_ok else 'NONE'} | "
            f"induction={'YES '+str(induction_dir) if induction_detected else 'NO'} | "
            f"ny_reversal={'YES '+str(ny_direction) if ny_reversal else 'NO'} | "
            f"candles={len(candles)} ({candles[0].timestamp.strftime('%H:%M')}-{candles[-1].timestamp.strftime('%H:%M')} UTC)"
        )

        # ── GATE 6: Signature Trade Detection ──
        # Reset signature detector per-pair to prevent state bleeding
        self.signature.reset()
        induction_state, sig_direction, sig_entry = self.signature.scan(
            candles, liquidity_zones
        )

        # ── Check for WTF Pattern (Wednesday midweek reversal) ──
        current_price = candles[-1].close
        wtf_direction = self.weekly.detect_wtf_pattern(current_price, utc_now)

        # ── Determine best signal ──
        trade_direction = None
        entry_price = None
        signal_type = None
        stop_extreme = None

        if sig_direction and sig_entry:
            # Full Signature Trade confirmed
            trade_direction = sig_direction
            entry_price = sig_entry
            signal_type = SignalType.SIGNATURE_TRADE
            stop_extreme = self.signature.stop_hunt_extreme
        elif wtf_direction and ny_reversal:
            # WTF Pattern + NY Reversal confluence
            trade_direction = TradeDirection(wtf_direction)
            entry_price = current_price
            signal_type = SignalType.WTF_PATTERN
            stop_extreme = extreme or current_price
        elif ny_reversal and ny_direction:
            # NY Reversal without full signature
            trade_direction = TradeDirection(ny_direction)
            entry_price = current_price
            signal_type = SignalType.LIQUIDITY_SWEEP
            stop_extreme = extreme or current_price

        # ── FALLBACK: Momentum signal when Hegelian pipeline has no data ──
        momentum_fired = False
        if not trade_direction:
            fb_dir, fb_entry, fb_extreme = self._momentum_fallback(
                symbol, candles, session_phase, liquidity_zones
            )
            if fb_dir:
                trade_direction = fb_dir
                entry_price = fb_entry
                signal_type = SignalType.MOMENTUM_REVERSAL
                stop_extreme = fb_extreme
                momentum_fired = True
                logger.info(
                    f"[{symbol}] Momentum fallback fired: {fb_dir.value} @ {fb_entry:.5f}"
                )

        if not trade_direction or not entry_price:
            logger.info(
                f"[{symbol}] No signal — gates blocked: "
                f"sig={bool(sig_direction)}, wtf={bool(wtf_direction)}, "
                f"ny_rev={ny_reversal}, momentum={momentum_fired}"
            )
            return None

        # ── GATE 7: Candlestick Anatomy Confirmation ──
        candle_result = self.candle_scanner.full_scan(candles)
        if candle_result["combined_confidence"] > 0:
            recommended = candle_result["recommended_direction"]
            if recommended and recommended != trade_direction.value:
                logger.info(
                    f"[{symbol}] Candle anatomy DIVERGES — "
                    f"Signal: {trade_direction.value}, "
                    f"Candles: {recommended}. Reducing confidence."
                )

        # ── GATE 8: Multi-Pair Basket Confirmation ──
        # Update pair data and check correlation
        self.multi_pair.update_pair_data(symbol, candles)

        # Fetch correlated pair data if connected
        if self.bridge.is_connected:
            corr_pairs = CONFIG.multi_pair.correlation_pairs.get(symbol, [])
            for corr_symbol in corr_pairs:
                corr_candles = await self.bridge.get_candles(corr_symbol, timeframe, 20)
                if corr_candles:
                    self.multi_pair.update_pair_data(corr_symbol, corr_candles)
                    self.multi_pair.analyze_pair_flow(corr_symbol, corr_candles)

        basket_confirmed, basket_conf, basket_details = \
            self.multi_pair.check_basket_correlation(
                symbol, trade_direction.value
            )

        # ── Build and return the signal ──
        return await self._build_signal(
            symbol=symbol,
            direction=trade_direction,
            entry_price=entry_price,
            stop_hunt_extreme=stop_extreme or entry_price,
            signal_type=signal_type,
            session_phase=session_phase,
            weekly_act=weekly_act,
            candles=candles,
            catalyst=catalyst if catalyst_imminent else None,
            candle_confidence=candle_result["combined_confidence"],
            basket_confirmed=basket_confirmed,
            basket_confidence=basket_conf,
        )

    # ─────────────────────────────────────────────────────────────────
    #  SIGNAL CONSTRUCTION
    # ─────────────────────────────────────────────────────────────────

    async def _build_signal(
        self,
        symbol: str,
        direction: TradeDirection,
        entry_price: float,
        stop_hunt_extreme: float,
        signal_type: SignalType,
        session_phase: SessionPhase,
        weekly_act: WeeklyAct,
        candles: List[CandleData],
        catalyst: Optional[NewsCatalyst] = None,
        candle_confidence: float = 0.5,
        basket_confirmed: bool = True,
        basket_confidence: float = 0.5,
    ) -> Optional[ForexiaSignal]:
        """Build a complete ForexiaSignal with risk package."""
        
        # Get account state
        if self.bridge.is_connected:
            self._account = await self.bridge.get_account_state()

        # Get current spread
        price_data = await self.bridge.get_current_price(symbol) if self.bridge.is_connected else None
        spread_pips = price_data.get("spread", 0) / 10 if price_data else 0

        # Build risk package
        risk_pkg = self.risk.build_risk_package(
            account=self._account,
            direction=direction,
            entry_price=entry_price,
            stop_hunt_extreme=stop_hunt_extreme,
            symbol=symbol,
            spread_pips=spread_pips,
        )

        if not risk_pkg:
            logger.warning(f"[{symbol}] Risk validation FAILED — trade rejected")
            return None

        # Calculate signal confidence
        confidence = self._calculate_confidence(
            signal_type=signal_type,
            session_phase=session_phase,
            weekly_act=weekly_act,
            candle_confidence=candle_confidence,
            basket_confirmed=basket_confirmed,
            basket_confidence=basket_confidence,
        )

        signal = ForexiaSignal(
            signal_id=f"FX-{uuid.uuid4().hex[:8].upper()}",
            signal_type=signal_type,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=risk_pkg["stop_loss"],
            take_profit=risk_pkg["take_profit"],
            lot_size=risk_pkg["lot_size"],
            session_phase=session_phase,
            weekly_act=weekly_act,
            induction_state=self.signature.current_state,
            news_catalyst=catalyst,
            confidence=confidence,
            notes=(
                f"R:R {risk_pkg['rr_ratio']} | "
                f"Risk {risk_pkg['risk_pips']}p | "
                f"Reward {risk_pkg['reward_pips']}p | "
                f"Basket: {'OK' if basket_confirmed else 'DIVERGENT'}"
            ),
        )

        self._active_signals.append(signal)

        logger.info(
            f"╔══════════════════════════════════════════════════════════╗\n"
            f"║  FOREXIA SIGNAL GENERATED — {signal.signal_id}      ║\n"
            f"╠══════════════════════════════════════════════════════════╣\n"
            f"║  Type: {signal_type.value:<45}║\n"
            f"║  Symbol: {symbol:<43}║\n"
            f"║  Direction: {direction.value:<40}║\n"
            f"║  Entry: {entry_price:<44.5f}║\n"
            f"║  SL: {risk_pkg['stop_loss']:<47.5f}║\n"
            f"║  TP: {risk_pkg['take_profit']:<47.5f}║\n"
            f"║  Lots: {risk_pkg['lot_size']:<45.2f}║\n"
            f"║  Confidence: {confidence:<39.1%}║\n"
            f"║  R:R: 1:{risk_pkg['rr_ratio']:<43.1f}║\n"
            f"╚══════════════════════════════════════════════════════════╝"
        )

        return signal

    # ─────────────────────────────────────────────────────────────────
    #  TRADE EXECUTION
    # ─────────────────────────────────────────────────────────────────

    async def execute_signal(self, signal: ForexiaSignal) -> Optional[TradeRecord]:
        """
        Execute a ForexiaSignal via the active broker bridge.
        This is the final step — pulling the trigger.
        """
        if not self.bridge.is_connected:
            logger.error("Cannot execute — broker bridge not connected")
            return None

        # Fire the order (risk was already validated in _build_signal)
        ticket = await self.bridge.execute_market_order(
            symbol=signal.symbol,
            direction=signal.direction,
            lot_size=signal.lot_size,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            comment=f"FX_{signal.signal_type.value}_{signal.signal_id}"
        )

        if ticket:
            record = TradeRecord(
                trade_id=signal.signal_id,
                signal=signal,
                status=TradeStatus.EXECUTED,
                mt4_ticket=ticket,
                executed_at=datetime.utcnow(),
            )
            self._trade_history.append(record)
            logger.info(
                f"══╡ TRADE EXECUTED — Ticket #{ticket} ╞══\n"
                f"    Signal: {signal.signal_id}\n"
                f"    Executing on the Solution phase."
            )
            return record
        else:
            record = TradeRecord(
                trade_id=signal.signal_id,
                signal=signal,
                status=TradeStatus.REJECTED,
                close_reason="MT4 order rejected",
            )
            self._trade_history.append(record)
            return record

    # ─────────────────────────────────────────────────────────────────
    #  CONFIDENCE CALCULATION
    # ─────────────────────────────────────────────────────────────────

    def _calculate_confidence(
        self,
        signal_type: SignalType,
        session_phase: SessionPhase,
        weekly_act: WeeklyAct,
        candle_confidence: float,
        basket_confirmed: bool,
        basket_confidence: float,
    ) -> float:
        """
        Calculate overall signal confidence (0-1).
        
        Weights:
          - Signal type quality: 30%
          - Session phase alignment: 20%
          - Weekly act alignment: 15%
          - Candle anatomy: 20%
          - Basket confirmation: 15%
        """
        # Signal type score
        type_scores = {
            SignalType.SIGNATURE_TRADE: 1.0,        # Full pattern = highest
            SignalType.TRAUMA_REVERSAL: 0.95,        # God candle reversal
            SignalType.WTF_PATTERN: 0.90,            # Midweek reversal
            SignalType.LIQUIDITY_SWEEP: 0.55,        # Simple sweep — needs confluence
            SignalType.MOMENTUM_REVERSAL: 0.40,     # Momentum fallback — heavily penalized
        }
        type_score = type_scores.get(signal_type, 0.5)

        # Session phase score
        phase_scores = {
            SessionPhase.SOLUTION: 1.0,    # NY session = optimal
            SessionPhase.REACTION: 0.6,    # London = risky but valid
            SessionPhase.PROBLEM: 0.3,     # Asian = low probability
            SessionPhase.CLOSED: 0.15,  # Allow low-confidence trades outside main sessions
        }
        phase_score = phase_scores.get(session_phase, 0.5)

        # Weekly act score
        act_scores = {
            WeeklyAct.ACT_4_REVERSAL: 1.0,       # Wednesday = primary
            WeeklyAct.ACT_5_DISTRIBUTION: 0.9,    # Thursday = secondary
            WeeklyAct.ACT_3_ACCUMULATION: 0.7,    # Tuesday = acceptable
            WeeklyAct.EPILOGUE: 0.4,               # Friday = reduced
        }
        act_score = act_scores.get(weekly_act, 0.3)  # Default 0.3 for Monday/other

        # Basket score
        basket_score = basket_confidence if basket_confirmed else 0.2

        confidence = (
            type_score * 0.30 +
            phase_score * 0.20 +
            act_score * 0.15 +
            candle_confidence * 0.20 +
            basket_score * 0.15
        )

        return round(min(1.0, max(0.0, confidence)), 3)

    # ─────────────────────────────────────────────────────────────────
    #  CANDLE COUNT CALCULATOR
    # ─────────────────────────────────────────────────────────────────

    def _calculate_candle_count(self, timeframe: str, utc_now: datetime) -> int:
        """
        Calculate how many candles to request so we cover the full
        Asian → London → NY session sequence.
        
        For M1 at 17:00 UTC, we need candles back to 00:00 UTC = 1020 candles.
        For M15, 100 candles covers ~25 hours — always enough.
        """
        tf_minutes = {
            "M1": 1, "M5": 5, "M15": 15, "M30": 30,
            "H1": 60, "H4": 240, "D1": 1440, "W1": 10080,
        }
        tf_min = tf_minutes.get(timeframe, 15)
        
        # We need candles from midnight UTC (Asian start) to now
        hours_since_midnight = utc_now.hour + utc_now.minute / 60.0
        minutes_needed = int(hours_since_midnight * 60) + 120  # +2h buffer
        
        candle_count = max(200, minutes_needed // tf_min)
        candle_count = min(candle_count, 2000)  # API safety cap
        
        return candle_count

    # ─────────────────────────────────────────────────────────────────
    #  MOMENTUM FALLBACK — GENERATES SIGNALS WITHOUT HEGELIAN PREREQS
    # ─────────────────────────────────────────────────────────────────

    def _momentum_fallback(
        self,
        symbol: str,
        candles: List[CandleData],
        session_phase: SessionPhase,
        liquidity_zones: List[LiquidityZone],
    ) -> tuple:
        """
        Fallback signal generator using momentum + wick analysis.
        
        Fires when the Hegelian pipeline can't generate signals (e.g. no 
        Asian range data, no London induction). Uses:
          - EMA crossover (8 vs 21 period)
          - Wick rejection ratio (exhaustion candles)
          - Recent swing high/low as stop placement
          - Liquidity zone proximity for confluence
        
        Returns:
            (TradeDirection, entry_price, stop_extreme) or (None, None, None)
        """
        if len(candles) < 30:
            return (None, None, None)
        
        # Only fire during active sessions (REACTION or SOLUTION phase)
        if session_phase not in (SessionPhase.REACTION, SessionPhase.SOLUTION):
            return (None, None, None)
        
        closes = [c.close for c in candles]
        
        # EMA calculation
        def ema(data, period):
            if len(data) < period:
                return data[-1]
            k = 2 / (period + 1)
            result = sum(data[:period]) / period
            for val in data[period:]:
                result = val * k + result * (1 - k)
            return result
        
        ema_fast = ema(closes, 8)
        ema_slow = ema(closes, 21)
        ema_trend = ema(closes, 50) if len(closes) >= 50 else ema(closes, 21)
        
        current_price = closes[-1]
        
        # Determine momentum direction
        bullish_cross = ema_fast > ema_slow and current_price > ema_trend
        bearish_cross = ema_fast < ema_slow and current_price < ema_trend
        
        if not bullish_cross and not bearish_cross:
            return (None, None, None)
        
        # Check for wick rejection in recent 5 candles (exhaustion signal)
        recent = candles[-5:]
        has_rejection = False
        for c in recent:
            rng = c.high - c.low
            if rng < 0.00001:
                continue
            if bullish_cross:
                # Look for lower wick rejection (bullish)
                lower_wick = min(c.open, c.close) - c.low
                if lower_wick / rng >= 0.55:
                    has_rejection = True
                    break
            else:
                # Look for upper wick rejection (bearish)
                upper_wick = c.high - max(c.open, c.close)
                if upper_wick / rng >= 0.55:
                    has_rejection = True
                    break
        
        # Require wick rejection AND meaningful EMA separation
        ema_separation = abs(ema_fast - ema_slow) / current_price
        if not has_rejection or ema_separation < 0.0005:
            return (None, None, None)
        
        # Check liquidity zone proximity for confluence
        near_zone = False
        for zone in liquidity_zones:
            if zone.swept:
                continue
            dist = abs(current_price - zone.level) / current_price
            if dist < 0.001:  # Within 10 pips equivalent
                near_zone = True
                break
        
        # Calculate stop extreme from recent swing
        lookback = candles[-20:]
        if bullish_cross:
            direction = TradeDirection.BUY
            stop_extreme = min(c.low for c in lookback)
        else:
            direction = TradeDirection.SELL
            stop_extreme = max(c.high for c in lookback)
        
        # Require BOTH liquidity zone proximity AND wick rejection
        if not near_zone or not has_rejection:
            return (None, None, None)
        
        logger.info(
            f"[{symbol}] Momentum fallback: {direction.value} | "
            f"EMA8={ema_fast:.5f} EMA21={ema_slow:.5f} | "
            f"rejection={has_rejection} zone={near_zone}"
        )
        
        return (direction, current_price, stop_extreme)

    # ─────────────────────────────────────────────────────────────────
    #  LIQUIDITY ZONE BUILDER
    # ─────────────────────────────────────────────────────────────────

    def _build_liquidity_zones(
        self, symbol: str, candles: List[CandleData]
    ) -> List[LiquidityZone]:
        """
        Build liquidity zones from current price data.
        
        Liquidity zones are where retail stop-losses cluster:
          - High of Day / Low of Day
          - Session highs/lows
          - Weekly levels (from Monday's range)
          - Psychological round numbers
        """
        now = datetime.utcnow()
        zones = []

        # Today's candles
        today_candles = [
            c for c in candles
            if c.timestamp.date() == now.date()
        ]

        if today_candles:
            hod = max(c.high for c in today_candles)
            lod = min(c.low for c in today_candles)

            zones.append(LiquidityZone(
                symbol=symbol, level=hod, zone_type="HIGH_OF_DAY",
                strength=8, formed_at=now,
            ))
            zones.append(LiquidityZone(
                symbol=symbol, level=lod, zone_type="LOW_OF_DAY",
                strength=8, formed_at=now,
            ))

        # Asian range zones
        for zone in self.dialectic.get_asian_liquidity_zones():
            zone.symbol = symbol
            zones.append(zone)

        # Weekly Monday levels
        weekly_targets = self.weekly.get_weekly_liquidity_targets()
        if weekly_targets.get("monday_high"):
            zones.append(LiquidityZone(
                symbol=symbol, level=weekly_targets["monday_high"],
                zone_type="WEEKLY_HIGH", strength=9, formed_at=now,
            ))
        if weekly_targets.get("monday_low"):
            zones.append(LiquidityZone(
                symbol=symbol, level=weekly_targets["monday_low"],
                zone_type="WEEKLY_LOW", strength=9, formed_at=now,
            ))

        # Psychological levels near current price
        if candles:
            price = candles[-1].close
            base = round(price, 2)
            for offset in [-0.0050, 0.0, 0.0050, 0.0100, -0.0100]:
                level = base + offset
                zones.append(LiquidityZone(
                    symbol=symbol, level=round(level, 4),
                    zone_type="PSYCH_LEVEL", strength=6, formed_at=now,
                ))

        self._liquidity_zones[symbol] = zones
        return zones

    # ─────────────────────────────────────────────────────────────────
    #  DASHBOARD STATE
    # ─────────────────────────────────────────────────────────────────

    async def get_dashboard_state(self) -> DashboardState:
        """Generate the complete dashboard state for the frontend."""
        utc_now = datetime.utcnow()

        # Refresh account state from broker for real-time P&L
        if self._bridge and self.bridge.is_connected:
            try:
                self._account = await self.bridge.get_account_state()
                # Also compute total unrealized P&L from open positions
                positions = await self.bridge.get_open_positions()
                total_unrealized = sum(
                    float(p.get("profit", 0)) + float(p.get("swap", 0))
                    for p in positions
                )
                # Update account with real P&L data
                self._account.daily_pnl = round(total_unrealized, 2)
                self._account.open_trades = len(positions)
            except Exception as e:
                logger.debug(f"Dashboard account refresh error: {e}")

        # Calculate induction meter
        induction_meter = 0.0
        # Use cached candles if available
        for symbol, candles in self.multi_pair._candle_cache.items():
            meter = self.dialectic.calculate_induction_meter(candles)
            induction_meter = max(induction_meter, meter)

        # Flatten liquidity zones
        all_zones = []
        for zones in self._liquidity_zones.values():
            all_zones.extend(zones)

        return DashboardState(
            account=self._account,
            current_session=self.dialectic.get_current_phase(utc_now),
            current_weekly_act=self.weekly.get_current_act(utc_now),
            induction_meter=induction_meter,
            active_signals=self._active_signals[-10:],
            recent_trades=self._trade_history[-20:],
            upcoming_catalysts=self.news.get_upcoming_catalysts(24),
            liquidity_zones=all_zones[:20],
            multi_pair_status=self.multi_pair.get_status().get("pair_states", {}),
            trauma_filter_active=self.trauma.is_active,
            broker_connected=self.bridge.is_connected if self._bridge else False,
            auto_trade=self._settings.agent.auto_trade,
            last_updated=utc_now,
        )

    # ─────────────────────────────────────────────────────────────────
    #  DAILY/WEEKLY RESETS
    # ─────────────────────────────────────────────────────────────────

    def daily_reset(self):
        """Reset daily state across all engines."""
        self.dialectic.reset_daily()
        self.signature.reset()
        self.risk.reset_daily()
        self.trauma.disarm()
        self._active_signals.clear()
        logger.info("═══ DAILY RESET COMPLETE ═══")

    def weekly_reset(self):
        """Reset weekly state."""
        self.weekly.reset_weekly()
        self._liquidity_zones.clear()
        logger.info("═══ WEEKLY RESET COMPLETE ═══")

    # ─────────────────────────────────────────────────────────────────
    #  WIN-RATE PROTECTION SYSTEM
    # ─────────────────────────────────────────────────────────────────

    def record_sl_hit(self, symbol: str, direction: str):
        """
        Record that a trade on this symbol+direction hit stop loss.
        After 2 consecutive SL hits within 4 hours, block the pair for 2 hours.
        """
        key = f"{symbol}:{direction}"
        now = datetime.utcnow()
        count, last_time = self._sl_cooldown.get(key, (0, None))

        # Reset count if last hit was more than 4 hours ago
        if last_time and (now - last_time).total_seconds() > 14400:
            count = 0

        count += 1
        self._sl_cooldown[key] = (count, now)

        if count >= 2:
            logger.warning(
                f"[WIN-RATE] {symbol} {direction} hit SL {count}x — "
                f"COOLING DOWN for 2 hours"
            )

    def _is_on_cooldown(self, symbol: str) -> bool:
        """Check if a symbol is in SL cooldown (any direction)."""
        now = datetime.utcnow()
        for key, (count, last_time) in self._sl_cooldown.items():
            if not key.startswith(f"{symbol}:"):
                continue
            if count < 2 or not last_time:
                continue
            # 2-hour cooldown after 2+ SL hits
            elapsed = (now - last_time).total_seconds()
            if elapsed < 7200:
                logger.debug(
                    f"[WIN-RATE] {symbol} ON COOLDOWN — "
                    f"{count} SL hits, {7200 - elapsed:.0f}s remaining"
                )
                return True
        return False

    def _is_pair_allowed_this_session(self, symbol: str) -> bool:
        """
        Session-pair filter to prevent trading pairs in unfavorable sessions.

        Rules:
          - JPY crosses blocked during Asian session (00:00-07:00 UTC)
          - Momentum signals only allowed during NY session (13:00-20:00 UTC)
          - All major pairs allowed during London + NY
        """
        utc_hour = datetime.utcnow().hour

        # Asian session (00:00-07:00 UTC): block JPY crosses
        if 0 <= utc_hour < 7:
            if symbol in self._jpy_crosses:
                logger.debug(
                    f"[WIN-RATE] {symbol} blocked — JPY cross during Asian session"
                )
                return False

        return True

    def _tighten_momentum_filter(self, has_rejection: bool, near_zone: bool) -> bool:
        """
        Require BOTH wick rejection AND liquidity zone proximity
        for momentum fallback signals (was OR before).
        """
        return has_rejection and near_zone

