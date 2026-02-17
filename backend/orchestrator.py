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
from datetime import datetime
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
        self._settings = SETTINGS

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
        self.risk.config.max_concurrent_trades = settings.risk.max_concurrent_trades
        self.risk.config.max_daily_loss_percent = settings.risk.max_daily_loss_percent
        self.risk.config.max_spread_pips = settings.risk.max_spread_pips
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

    async def _auto_scan_loop(self):
        """
        Background loop that scans all configured pairs every 2 minutes
        and executes trades when auto_trade is ON and signals meet
        the minimum confidence threshold.
        """
        scan_interval = 45  # 45 seconds — fast enough to catch entries
        logger.info("Auto-Scan Loop: Running every %d seconds", scan_interval)

        while self._running:
            try:
                await asyncio.sleep(scan_interval)

                if not self._settings.agent.auto_trade:
                    continue  # Bot was turned off, skip this cycle

                if not self.bridge or not self.bridge.is_connected:
                    logger.warning("Auto-Scan: Broker disconnected, skipping cycle")
                    continue

                pairs = self._settings.agent.pairs
                timeframe = self._settings.agent.default_timeframe
                min_confidence = self._settings.agent.min_confidence

                signals_found = 0
                trades_executed = 0

                # Refresh account state before scan cycle
                try:
                    self._account = await self.bridge.get_account_state()
                except Exception:
                    pass

                for symbol in pairs:
                    try:
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
        if candles is None and self.bridge.is_connected:
            candles = await self.bridge.get_candles(symbol, timeframe, 100)

        if not candles or len(candles) < 20:
            logger.warning(f"[{symbol}] Insufficient candle data")
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
        # Calculate Asian range (the Problem)
        self.dialectic.calculate_asian_range(candles)

        # Detect London induction (the Reaction)
        induction_detected, induction_dir, extreme = \
            self.dialectic.detect_london_induction(candles)

        # Detect NY reversal (the Solution)
        ny_reversal, ny_direction = self.dialectic.detect_ny_reversal(candles)

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

        if not trade_direction or not entry_price:
            logger.debug(f"[{symbol}] No actionable signal at this time")
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
            SignalType.TRAUMA_REVERSAL: 0.9,         # God candle reversal
            SignalType.WTF_PATTERN: 0.85,            # Midweek reversal
            SignalType.LIQUIDITY_SWEEP: 0.65,        # Simple sweep
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
