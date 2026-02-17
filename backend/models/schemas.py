"""
╔══════════════════════════════════════════════════════════════════════╗
║              FOREXIA SIGNATURE AGENT — DATA MODELS                  ║
║       Pydantic schemas for institutional trade execution             ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────
#  ENUMS — THE LANGUAGE OF MARKET MANIPULATION
# ─────────────────────────────────────────────────────────────────────

class SessionPhase(str, Enum):
    """The Hegelian Dialectic phases within each trading day."""
    PROBLEM = "ASIAN_CONSOLIDATION"     # Retail sets their stops
    REACTION = "LONDON_INDUCTION"       # Smart Money traps breakout traders
    SOLUTION = "NEWYORK_REVERSAL"       # We execute
    CLOSED = "MARKET_CLOSED"            # No phase active


class WeeklyAct(str, Enum):
    """The 5-Act weekly manipulation structure."""
    ACT_1_CONNECTOR = "SUNDAY_CONNECTOR"
    ACT_2_INDUCTION = "MONDAY_INDUCTION"
    ACT_3_ACCUMULATION = "TUESDAY_ACCUMULATION"
    ACT_4_REVERSAL = "WEDNESDAY_REVERSAL"     # WTF Pattern — primary
    ACT_5_DISTRIBUTION = "THURSDAY_DISTRIBUTION"
    EPILOGUE = "FRIDAY_EPILOGUE"


class TradeDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    STOPPED_OUT = "STOPPED_OUT"
    TAKE_PROFIT = "TAKE_PROFIT"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


class SignalType(str, Enum):
    """Types of Forexia signals."""
    SIGNATURE_TRADE = "SIGNATURE_TRADE"         # Full wedge/triangle induction
    TRAUMA_REVERSAL = "TRAUMA_REVERSAL"         # God Candle exhaustion play
    WTF_PATTERN = "WTF_MIDWEEK_REVERSAL"        # Wednesday reversal
    LIQUIDITY_SWEEP = "LIQUIDITY_SWEEP"         # Pure stop hunt scalp
    MOMENTUM_REVERSAL = "MOMENTUM_REVERSAL"     # EMA + wick rejection fallback


class InductionState(str, Enum):
    """States of the retail induction trap."""
    NO_PATTERN = "NO_PATTERN"
    WEDGE_FORMING = "WEDGE_FORMING"
    TRIANGLE_FORMING = "TRIANGLE_FORMING"
    FALSE_BREAKOUT = "FALSE_BREAKOUT"           # Retail is trapped
    STOP_HUNT_ACTIVE = "STOP_HUNT_ACTIVE"       # Liquidity being raided
    EXHAUSTION_DETECTED = "EXHAUSTION_DETECTED" # Wick printed — ready
    REVERSAL_CONFIRMED = "REVERSAL_CONFIRMED"   # FIRE


# ─────────────────────────────────────────────────────────────────────
#  CANDLE DATA — RAW MARKET ANATOMY
# ─────────────────────────────────────────────────────────────────────

class CandleData(BaseModel):
    """Single OHLCV candle — the atom of price action."""
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    tick_volume: int = 0

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def range_size(self) -> float:
        return self.high - self.low

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def body_ratio(self) -> float:
        """Body as fraction of total range."""
        return self.body_size / self.range_size if self.range_size > 0 else 0

    @property
    def upper_wick_ratio(self) -> float:
        return self.upper_wick / self.range_size if self.range_size > 0 else 0

    @property
    def lower_wick_ratio(self) -> float:
        return self.lower_wick / self.range_size if self.range_size > 0 else 0


# ─────────────────────────────────────────────────────────────────────
#  LIQUIDITY ZONE — WHERE DUMB MONEY PARKS THEIR STOPS
# ─────────────────────────────────────────────────────────────────────

class LiquidityZone(BaseModel):
    """A pool of retail stop-losses ripe for institutional harvesting."""
    symbol: str
    level: float                                # Price level
    zone_type: str                              # "HIGH_OF_DAY", "LOW_OF_DAY", etc.
    strength: int = Field(ge=1, le=10)          # 1-10 how thick the liquidity is
    formed_at: datetime
    swept: bool = False                         # Has Smart Money already raided it?
    swept_at: Optional[datetime] = None


# ─────────────────────────────────────────────────────────────────────
#  NEWS CATALYST — RED FOLDER EVENTS (NO ECONOMIC NUMBERS)
# ─────────────────────────────────────────────────────────────────────

class NewsCatalyst(BaseModel):
    """
    Red Folder event — a pre-engineered volatility catalyst.
    CRITICAL: We strip ALL economic numbers. No Forecast, no Actual,
    no Previous. That data is bogus retail bait.
    We store ONLY what matters: WHEN and WHAT currency.
    """
    currency: str                   # e.g., "USD", "EUR"
    event_title: str                # e.g., "Non-Farm Payrolls"
    event_date: datetime            # Date of the event
    event_time: str                 # Time string (UTC)
    # NO forecast, actual, previous — those are retail noise


# ─────────────────────────────────────────────────────────────────────
#  TRADE SIGNAL — THE FOREXIA EXECUTION ORDER
# ─────────────────────────────────────────────────────────────────────

class ForexiaSignal(BaseModel):
    """A validated trade signal from the Forexia engine."""
    signal_id: str
    signal_type: SignalType
    symbol: str
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    session_phase: SessionPhase
    weekly_act: WeeklyAct
    induction_state: InductionState
    liquidity_zone: Optional[LiquidityZone] = None
    news_catalyst: Optional[NewsCatalyst] = None
    confidence: float = Field(ge=0.0, le=1.0)   # 0-1 signal strength
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    notes: str = ""


# ─────────────────────────────────────────────────────────────────────
#  TRADE RECORD — EXECUTION LEDGER
# ─────────────────────────────────────────────────────────────────────

class TradeRecord(BaseModel):
    """Immutable record of an executed trade."""
    trade_id: str
    signal: ForexiaSignal
    status: TradeStatus = TradeStatus.PENDING
    mt4_ticket: Optional[int] = None
    executed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    pnl: float = 0.0
    pnl_pips: float = 0.0
    close_reason: str = ""


# ─────────────────────────────────────────────────────────────────────
#  ACCOUNT STATE — LIVE PORTFOLIO SNAPSHOT
# ─────────────────────────────────────────────────────────────────────

class AccountState(BaseModel):
    """Current account snapshot from MT4."""
    balance: float = 0.0
    equity: float = 0.0
    margin: float = 0.0
    free_margin: float = 0.0
    margin_level: float = 0.0
    open_trades: int = 0
    daily_pnl: float = 0.0
    total_trades_today: int = 0
    win_count: int = 0
    loss_count: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @property
    def win_rate(self) -> float:
        total = self.win_count + self.loss_count
        return (self.win_count / total * 100) if total > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────
#  WEBHOOK PAYLOAD — TRADINGVIEW INCOMING
# ─────────────────────────────────────────────────────────────────────

class TradingViewWebhook(BaseModel):
    """Incoming webhook from TradingView alerts."""
    secret: str                             # Auth token
    symbol: str                             # e.g., "EURUSD"
    timeframe: str = "M15"                  # Chart timeframe
    action: str = "ANALYZE"                 # ANALYZE, FORCE_ENTRY, CLOSE
    price: Optional[float] = None
    candles: Optional[List[CandleData]] = None
    message: str = ""


# ─────────────────────────────────────────────────────────────────────
#  DASHBOARD STATE — FRONTEND PAYLOAD
# ─────────────────────────────────────────────────────────────────────

class DashboardState(BaseModel):
    """Complete state pushed to the React frontend."""
    account: AccountState
    current_session: SessionPhase
    current_weekly_act: WeeklyAct
    induction_meter: float = Field(ge=0.0, le=100.0, default=0.0)
    active_signals: List[ForexiaSignal] = []
    recent_trades: List[TradeRecord] = []
    upcoming_catalysts: List[NewsCatalyst] = []
    liquidity_zones: List[LiquidityZone] = []
    multi_pair_status: dict = {}
    trauma_filter_active: bool = False
    broker_connected: bool = False
    auto_trade: bool = False
    last_updated: datetime = Field(default_factory=datetime.utcnow)
