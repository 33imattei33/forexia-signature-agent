"""
╔══════════════════════════════════════════════════════════════════════╗
║                 FOREXIA SIGNATURE AGENT — CONFIG                    ║
║         Institutional Configuration for Smart Money Execution       ║
╚══════════════════════════════════════════════════════════════════════╝

All parameters are tuned for institutional market manipulation detection.
No retail indicators. No bogus economic numbers. Pure price action warfare.
"""

import os
from dataclasses import dataclass, field
from typing import List


# ─────────────────────────────────────────────────────────────────────
#  MT4 BRIDGE CONFIGURATION (ZeroMQ)
# ─────────────────────────────────────────────────────────────────────
@dataclass
class MT4BridgeConfig:
    """ZeroMQ connection to the MT4 Expert Advisor."""
    push_port: int = 32768          # Commands TO MT4 (REQ socket)
    pull_port: int = 32769          # Data FROM MT4 (PULL socket)
    host: str = "tcp://127.0.0.1"   # Localhost bridge
    heartbeat_interval: int = 5     # Seconds between heartbeat pings
    reconnect_delay: int = 3        # Seconds before reconnect attempt
    command_timeout: int = 10       # Max seconds to wait for MT4 response


# ─────────────────────────────────────────────────────────────────────
#  RISK MANAGEMENT — HARDCODED INSTITUTIONAL RULES
# ─────────────────────────────────────────────────────────────────────
@dataclass
class RiskConfig:
    """
    Risk is non-negotiable.
    0.01 lots per $100 of equity. Period.
    Stop-loss placed just beyond the stop hunt wick — trapping dumb money
    behind us as a shield.
    """
    lot_per_100_equity: float = 0.01        # Hardcoded: 0.01 lot / $100
    max_risk_percent: float = 2.0           # Max 2% of equity per trade
    max_lot_size: float = 0.10              # ABSOLUTE max lot size per order
    stop_loss_buffer_pips: float = 30.0     # Wide SL — room to breathe
    take_profit_ratio: float = 0.4          # TP = 0.4x SL distance
    take_profit_pips: float = 12.0          # Fixed TP in pips (overrides ratio when > 0)
    max_concurrent_trades: int = 3          # Max open positions
    max_daily_loss_percent: float = 5.0     # Daily circuit breaker
    max_spread_pips: float = 2.0            # Reject entries with wide spreads
    # ── Position Manager (Breakeven + Trailing) ──
    breakeven_trigger_pips: float = 6.0     # Move SL to entry after X pips profit
    breakeven_lock_pips: float = 1.0        # Lock X pips above entry at breakeven
    trailing_start_pips: float = 12.0       # Start trailing after X pips profit
    trailing_step_pips: float = 5.0         # Trail X pips behind price
    stale_trade_minutes: int = 60           # Close negative trades after X minutes (0=disabled)


# ─────────────────────────────────────────────────────────────────────
#  SESSION TIMES — THE HEGELIAN DIALECTIC CLOCK
# ─────────────────────────────────────────────────────────────────────
@dataclass
class SessionConfig:
    """
    The 3-phase daily cycle that institutions exploit:
      Phase 1 (Problem):  Asian build-up — retail sets their stops
      Phase 2 (Reaction): London induction — trap the breakout traders
      Phase 3 (Solution): New York reversal — we strike
    All times in UTC.
    """
    asian_start: str = "00:00"     # Problem phase begins
    asian_end: str = "08:00"       # Consolidation range defined
    london_start: str = "08:00"    # Reaction/Induction begins
    london_end: str = "13:00"      # Trap is set
    newyork_start: str = "13:00"   # Solution phase — execution window
    newyork_end: str = "21:00"     # Market wind-down
    killzone_ny_start: str = "13:00"  # Prime NY kill zone start
    killzone_ny_end: str = "16:00"    # Prime NY kill zone end


# ─────────────────────────────────────────────────────────────────────
#  WEEKLY 5-ACT STRUCTURE — THE INSTITUTIONAL PLAYBOOK
# ─────────────────────────────────────────────────────────────────────
@dataclass
class WeeklyActConfig:
    """
    The weekly manipulation cycle:
      Sunday:    Act 1 — The Connector (gap analysis, no trading)
      Monday:    Act 2 — Retail Induction (dumb money takes the bait)
      Tuesday:   Act 3 — Accumulation (smart money builds positions)
      Wednesday: Act 4 — The Midweek Reversal (WTF Pattern — primary target)
      Thursday:  Act 5 — Distribution/Continuation (secondary target)
      Friday:    Epilogue — Profit-taking, reduce exposure
    """
    no_trade_days: List[str] = field(default_factory=lambda: ["Sunday", "Monday"])
    primary_trade_days: List[str] = field(default_factory=lambda: ["Wednesday", "Thursday"])
    secondary_trade_days: List[str] = field(default_factory=lambda: ["Tuesday"])
    reduce_exposure_day: str = "Friday"
    friday_close_hour_utc: int = 18   # Close all positions by 18:00 UTC Friday


# ─────────────────────────────────────────────────────────────────────
#  SIGNATURE TRADE DETECTION PARAMETERS
# ─────────────────────────────────────────────────────────────────────
@dataclass
class SignatureTradeConfig:
    """
    Pattern recognition for the Wedge/Triangle induction trap.
    We wait for the false breakout, identify the stop hunt into
    the liquidity zone, then execute on the reversal.
    """
    min_wedge_touches: int = 3              # Min touches on converging lines
    breakout_threshold_pips: float = 5.0    # Min pips beyond pattern boundary
    wick_exhaustion_ratio: float = 0.65     # Wick must be >= 65% of candle range
    reversal_confirmation_candles: int = 2  # Candles confirming reversal
    liquidity_zone_lookback: int = 20       # Bars to scan for liquidity pools
    min_pattern_bars: int = 10              # Min bars to form valid pattern
    max_pattern_bars: int = 60              # Max bars before pattern invalidated


# ─────────────────────────────────────────────────────────────────────
#  CANDLESTICK ANATOMY SCANNER
# ─────────────────────────────────────────────────────────────────────
@dataclass
class CandleScannerConfig:
    """
    Railroad Tracks and Star patterns at psychological whole numbers.
    These confirm the exact entry tick after the stop hunt.
    """
    railroad_body_ratio: float = 0.35       # Max body size relative to range
    railroad_min_range_pips: float = 10.0   # Minimum candle range for RR tracks
    star_body_max_ratio: float = 0.15       # Star: tiny body relative to range
    psych_levels: List[int] = field(default_factory=lambda: [0, 20, 50, 80, 100])
    psych_level_tolerance_pips: float = 5.0  # Pips from round number


# ─────────────────────────────────────────────────────────────────────
#  TRAUMA FILTER — GOD CANDLE DETECTION
# ─────────────────────────────────────────────────────────────────────
@dataclass
class TraumaFilterConfig:
    """
    Detects 'God Candles' — massive algorithmic pushes designed to trigger
    retail emotional responses. The bot sits on its hands during the push,
    then targets the exact opposite direction once the exhaustion wick prints.
    """
    god_candle_multiplier: float = 3.0      # Multiple of ATR to qualify
    cooldown_seconds: int = 120             # Wait time after God Candle spike
    wick_reversal_min_ratio: float = 0.60   # Exhaustion wick min ratio
    news_pre_buffer_seconds: int = 300      # 5 min before Red Folder event
    news_post_buffer_seconds: int = 600     # 10 min after — wait for exhaustion


# ─────────────────────────────────────────────────────────────────────
#  MULTI-PAIR SYNCHRONIZATION — DOLLAR BASKET CONFIRMATION
# ─────────────────────────────────────────────────────────────────────
@dataclass
class MultiPairConfig:
    """
    If the Signature Trade forms on one pair, we verify the Smart Money
    algorithm is manipulating the entire dollar basket before firing.
    """
    primary_pairs: List[str] = field(default_factory=lambda: [
        "EURUSD", "GBPUSD", "USDCHF", "USDJPY"
    ])
    correlation_pairs: dict = field(default_factory=lambda: {
        "EURUSD": ["GBPUSD", "USDCHF"],
        "GBPUSD": ["EURUSD", "USDCHF"],
        "USDCHF": ["EURUSD", "GBPUSD"],
        "USDJPY": ["EURUSD", "GBPUSD"],
    })
    min_confirming_pairs: int = 1   # At least 1 correlated pair must confirm
    correlation_timeframe: str = "H1"


# ─────────────────────────────────────────────────────────────────────
#  NEWS CATALYST ENGINE — FOREXFACTORY RED FOLDER ONLY
# ─────────────────────────────────────────────────────────────────────
@dataclass
class NewsCatalystConfig:
    """
    Red Folder events are pre-engineered volatility catalysts.
    We strip ALL economic numbers (Forecast, Actual, Previous) — that
    data is bogus noise for retail consumption.
    We store ONLY: Currency, Date, Time.
    """
    forexfactory_url: str = "https://www.forexfactory.com/calendar"
    scrape_interval_minutes: int = 60       # Re-scrape every hour
    red_folder_only: bool = True            # CRITICAL: Red events ONLY
    strip_economic_numbers: bool = True     # DELETE Forecast/Actual/Previous
    pre_event_lockout_minutes: int = 5      # No new trades 5 min before
    post_event_window_minutes: int = 10     # Trauma filter active window


# ─────────────────────────────────────────────────────────────────────
#  FASTAPI / WEBHOOK CONFIG
# ─────────────────────────────────────────────────────────────────────
@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    webhook_secret: str = os.getenv("FOREXIA_WEBHOOK_SECRET", "change_me")
    cors_origins: List[str] = field(default_factory=lambda: ["http://localhost:3000"])
    log_level: str = "INFO"


# ─────────────────────────────────────────────────────────────────────
#  MASTER CONFIG AGGREGATOR
# ─────────────────────────────────────────────────────────────────────
@dataclass
class ForexiaConfig:
    """Master configuration — the brain's neural pathways."""
    mt4: MT4BridgeConfig = field(default_factory=MT4BridgeConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    sessions: SessionConfig = field(default_factory=SessionConfig)
    weekly: WeeklyActConfig = field(default_factory=WeeklyActConfig)
    signature: SignatureTradeConfig = field(default_factory=SignatureTradeConfig)
    candle_scanner: CandleScannerConfig = field(default_factory=CandleScannerConfig)
    trauma: TraumaFilterConfig = field(default_factory=TraumaFilterConfig)
    multi_pair: MultiPairConfig = field(default_factory=MultiPairConfig)
    news: NewsCatalystConfig = field(default_factory=NewsCatalystConfig)
    server: ServerConfig = field(default_factory=ServerConfig)


# Singleton instance — import this everywhere
CONFIG = ForexiaConfig()
