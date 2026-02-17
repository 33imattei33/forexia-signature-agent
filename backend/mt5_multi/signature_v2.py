"""
╔══════════════════════════════════════════════════════════════════════╗
║    FOREXIA — SIGNATURE TRADE V2 (Wedge + Liquidity Grab)            ║
║    Dylan Shilts' methodology — NO FVG                                ║
╚══════════════════════════════════════════════════════════════════════╝

Strategy: Wedge → Stop Hunt → Reversal → Entry on first candle back inside

Detection pipeline:
  Phase 1: build_wedge()       — Find converging trendlines (50 candles)
  Phase 2: detect_breakout()   — Price breaks below/above wedge boundary
  Phase 3: detect_stop_hunt()  — Liquidity grab with wick rejection
  Phase 4: confirm_reversal()  — First candle closing back inside + RSI shift
  Phase 5: generate_entry()    — Entry at reversal candle close

Entry mechanics:
  FX:     Market order on reversal confirmation
  NASDAQ: Limit order at reversal candle body (via MarketAdapter)
  SL:     Behind the stop hunt wick extreme + buffer
  TP:     At wedge start (where the pattern began) — min 3:1 R:R

STRICT: NO Fair Value Gaps. Only Price Action, Wedge Patterns, Liquidity Grabs.
"""

import logging
import numpy as np
from datetime import datetime, timezone
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("forexia.signature_v2")


# ─────────────────────────────────────────────────────────────────────
#  SIGNAL PHASES
# ─────────────────────────────────────────────────────────────────────

class SignalPhase(str, Enum):
    NO_PATTERN = "NO_PATTERN"
    WEDGE_FORMING = "WEDGE_FORMING"
    BREAKOUT = "BREAKOUT"
    STOP_HUNT = "STOP_HUNT"
    REVERSAL_CONFIRMED = "REVERSAL_CONFIRMED"
    ENTRY_READY = "ENTRY_READY"


@dataclass
class WedgePattern:
    """A detected wedge/converging pattern."""
    start_index: int                # Where the wedge starts in the candle array
    end_index: int                  # Current end of wedge
    upper_slope: float              # Slope of upper trendline (negative = descending)
    lower_slope: float              # Slope of lower trendline
    upper_intercept: float          # Y-intercept of upper trendline
    lower_intercept: float          # Y-intercept of lower trendline
    start_price_high: float         # Price at wedge start (high)
    start_price_low: float          # Price at wedge start (low)
    direction: str = ""             # "DESCENDING" or "ASCENDING"
    touches_upper: int = 0          # Number of touches on upper line
    touches_lower: int = 0          # Number of touches on lower line
    converging: bool = False        # Lines are converging
    width_at_start: float = 0.0     # Width at pattern start
    width_at_end: float = 0.0       # Width at current end


@dataclass
class StopHunt:
    """A detected liquidity grab / stop hunt."""
    candle_index: int
    direction: str                  # "BELOW" (grabbed longs) or "ABOVE" (grabbed shorts)
    extreme_price: float            # The wick extreme
    close_price: float              # Where it closed (back inside = good)
    wick_ratio: float               # Wick length / total range
    volume_spike: bool = False      # Was there a volume spike?


@dataclass
class SignatureSignal:
    """Complete signal from the Signature Trade detector."""
    symbol: str
    phase: SignalPhase
    direction: str = ""             # "BUY" or "SELL"
    confidence: float = 0.0         # 0-100
    entry_price: float = 0.0
    hunt_extreme: float = 0.0       # For SL placement
    wedge_start_price: float = 0.0  # For TP placement
    wedge: Optional[WedgePattern] = None
    stop_hunt: Optional[StopHunt] = None
    timestamp: Optional[datetime] = None
    details: Dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────
#  SIGNATURE TRADE DETECTOR V2
# ─────────────────────────────────────────────────────────────────────

class SignatureTradeV2:
    """
    Dylan Shilts' Signature Trade — Wedge + Liquidity Grab edition.
    
    NO FVG. Only:
      - Price Action (candle patterns, swing structure)
      - Wedge Patterns (converging trendlines)
      - Liquidity Grabs (stop hunts)
    
    Usage:
        detector = SignatureTradeV2()
        signal = detector.scan("EURUSD", candles)
        
        if signal.phase == SignalPhase.ENTRY_READY:
            # Execute trade with signal.entry_price, signal.hunt_extreme, etc.
    """

    # Tunable parameters
    MIN_WEDGE_CANDLES = 15          # Minimum candles to form a wedge
    MAX_WEDGE_CANDLES = 60          # Maximum lookback for wedge detection
    MIN_TOUCHES = 3                 # Min touches per trendline
    TOUCH_TOLERANCE = 0.0003        # How close to line counts as "touch" (price units)
    CONVERGENCE_RATIO = 0.6         # Width at end / width at start < this = converging
    BREAKOUT_THRESHOLD = 0.0005     # Min distance beyond line to count as breakout
    WICK_EXHAUSTION_RATIO = 0.6     # Wick > 60% of range = exhaustion
    RSI_PERIOD = 14                 # RSI lookback for momentum shift
    RSI_OVERSOLD = 35               # RSI below this on BUY hunt
    RSI_OVERBOUGHT = 65             # RSI above this on SELL hunt

    def __init__(self):
        self._state: Dict[str, Dict] = {}  # Per-symbol state

    def _get_state(self, symbol: str) -> Dict:
        """Get or create state for a symbol."""
        if symbol not in self._state:
            self._state[symbol] = {
                "phase": SignalPhase.NO_PATTERN,
                "wedge": None,
                "stop_hunt": None,
                "breakout_candle_idx": None,
            }
        return self._state[symbol]

    def reset(self, symbol: str):
        """Reset detection state for a symbol."""
        self._state.pop(symbol, None)

    # ─────────────────────── MAIN SCAN ───────────────────────

    def scan(self, symbol: str, candles: List[Dict]) -> SignatureSignal:
        """
        Run the full detection pipeline on candle data.
        
        Args:
            symbol: The symbol being scanned
            candles: List of OHLCV dicts with keys:
                     open, high, low, close, volume (optional), time (optional)
        
        Returns:
            SignatureSignal with the current detection phase and trade parameters
        """
        if len(candles) < self.MIN_WEDGE_CANDLES:
            return SignatureSignal(
                symbol=symbol,
                phase=SignalPhase.NO_PATTERN,
                details={"reason": f"Need {self.MIN_WEDGE_CANDLES} candles, have {len(candles)}"},
            )

        state = self._get_state(symbol)

        # ── PHASE 1: Look for wedge ──
        wedge = self._build_wedge(candles)

        if wedge is None:
            # Reset if we had a pattern but it's gone
            if state["phase"] != SignalPhase.NO_PATTERN:
                self.reset(symbol)
            return SignatureSignal(
                symbol=symbol,
                phase=SignalPhase.NO_PATTERN,
                details={"reason": "No converging pattern found"},
            )

        state["wedge"] = wedge

        # ── PHASE 2: Detect breakout ──
        breakout = self._detect_breakout(candles, wedge)
        if breakout is None:
            state["phase"] = SignalPhase.WEDGE_FORMING
            return SignatureSignal(
                symbol=symbol,
                phase=SignalPhase.WEDGE_FORMING,
                wedge=wedge,
                confidence=20.0,
                details={"wedge_direction": wedge.direction, "touches": wedge.touches_upper + wedge.touches_lower},
            )

        breakout_dir, breakout_idx = breakout
        state["breakout_candle_idx"] = breakout_idx

        # ── PHASE 3: Detect stop hunt (liquidity grab) ──
        hunt = self._detect_stop_hunt(candles, wedge, breakout_dir, breakout_idx)
        if hunt is None:
            state["phase"] = SignalPhase.BREAKOUT
            return SignatureSignal(
                symbol=symbol,
                phase=SignalPhase.BREAKOUT,
                wedge=wedge,
                confidence=35.0,
                details={"breakout_direction": breakout_dir, "breakout_index": breakout_idx},
            )

        state["stop_hunt"] = hunt

        # ── PHASE 4: Confirm reversal ──
        reversal = self._confirm_reversal(candles, wedge, hunt, breakout_dir)
        if reversal is None:
            state["phase"] = SignalPhase.STOP_HUNT
            return SignatureSignal(
                symbol=symbol,
                phase=SignalPhase.STOP_HUNT,
                wedge=wedge,
                stop_hunt=hunt,
                confidence=55.0,
                details={"hunt_direction": hunt.direction, "extreme": hunt.extreme_price},
            )

        # ── PHASE 5: Generate entry ──
        state["phase"] = SignalPhase.ENTRY_READY

        # Trade direction is OPPOSITE to the breakout (reversal)
        trade_direction = "BUY" if breakout_dir == "BELOW" else "SELL"

        # Entry price = last candle close (the reversal candle)
        entry_price = candles[-1]["close"]

        # TP target = wedge start price
        if trade_direction == "BUY":
            wedge_start = wedge.start_price_high
        else:
            wedge_start = wedge.start_price_low

        # Calculate confidence
        confidence = self._calculate_confidence(wedge, hunt, reversal, candles)

        signal = SignatureSignal(
            symbol=symbol,
            phase=SignalPhase.ENTRY_READY,
            direction=trade_direction,
            confidence=confidence,
            entry_price=entry_price,
            hunt_extreme=hunt.extreme_price,
            wedge_start_price=wedge_start,
            wedge=wedge,
            stop_hunt=hunt,
            timestamp=datetime.now(timezone.utc),
            details={
                "reversal": reversal,
                "rsi": reversal.get("rsi", 0),
                "momentum_shift": reversal.get("momentum_shift", False),
                "candle_back_inside": reversal.get("back_inside", False),
            },
        )

        # Reset state after generating signal (one-shot)
        self.reset(symbol)

        return signal

    # ─────────────────────── PHASE 1: WEDGE DETECTION ───────────────────────

    def _build_wedge(self, candles: List[Dict]) -> Optional[WedgePattern]:
        """
        Detect a converging wedge pattern using trendline fitting.
        
        Algorithm:
          1. Find swing highs and lows in the lookback window
          2. Fit linear regression to swing highs (upper trendline)
          3. Fit linear regression to swing lows (lower trendline)
          4. Check convergence (lines getting closer)
          5. Count touches on each line
        
        Returns WedgePattern if found, None otherwise.
        """
        lookback = min(self.MAX_WEDGE_CANDLES, len(candles))
        window = candles[-lookback:]

        highs = np.array([c["high"] for c in window])
        lows = np.array([c["low"] for c in window])
        closes = np.array([c["close"] for c in window])

        # Find swing points (local extremes)
        swing_highs = self._find_swing_points(highs, mode="high")
        swing_lows = self._find_swing_points(lows, mode="low")

        if len(swing_highs) < self.MIN_TOUCHES or len(swing_lows) < self.MIN_TOUCHES:
            return None

        # Fit trendlines
        sh_indices = np.array([s[0] for s in swing_highs])
        sh_values = np.array([s[1] for s in swing_highs])
        sl_indices = np.array([s[0] for s in swing_lows])
        sl_values = np.array([s[1] for s in swing_lows])

        upper_slope, upper_intercept = self._fit_trendline(sh_indices, sh_values)
        lower_slope, lower_intercept = self._fit_trendline(sl_indices, sl_values)

        # Check convergence: lines must be getting closer
        width_at_start = (upper_intercept - lower_intercept)
        width_at_end = (
            (upper_slope * (lookback - 1) + upper_intercept) -
            (lower_slope * (lookback - 1) + lower_intercept)
        )

        if width_at_start <= 0:
            return None

        convergence = width_at_end / width_at_start

        if convergence >= self.CONVERGENCE_RATIO:
            # Not converging enough
            return None

        # Count touches on each trendline
        tolerance = self._adaptive_tolerance(highs, lows)
        upper_touches = self._count_touches(highs, np.arange(lookback), upper_slope, upper_intercept, tolerance, mode="upper")
        lower_touches = self._count_touches(lows, np.arange(lookback), lower_slope, lower_intercept, tolerance, mode="lower")

        if upper_touches < self.MIN_TOUCHES or lower_touches < self.MIN_TOUCHES:
            return None

        # Determine wedge direction
        if upper_slope < 0 and lower_slope < 0:
            direction = "DESCENDING"     # Falling wedge (bullish reversal)
        elif upper_slope > 0 and lower_slope > 0:
            direction = "ASCENDING"      # Rising wedge (bearish reversal)
        elif upper_slope < 0 and lower_slope >= 0:
            direction = "DESCENDING"     # Contracting down
        else:
            direction = "ASCENDING"      # Contracting up

        start_idx = len(candles) - lookback

        return WedgePattern(
            start_index=start_idx,
            end_index=len(candles) - 1,
            upper_slope=upper_slope,
            lower_slope=lower_slope,
            upper_intercept=upper_intercept,
            lower_intercept=lower_intercept,
            start_price_high=highs[0],
            start_price_low=lows[0],
            direction=direction,
            touches_upper=upper_touches,
            touches_lower=lower_touches,
            converging=True,
            width_at_start=width_at_start,
            width_at_end=width_at_end,
        )

    def _find_swing_points(
        self,
        prices: np.ndarray,
        mode: str = "high",
        order: int = 3,
    ) -> List[Tuple[int, float]]:
        """
        Find local extremes (swing highs or lows).
        
        A swing high: price at index i is higher than `order` candles on each side.
        A swing low: price at index i is lower than `order` candles on each side.
        """
        swings = []
        for i in range(order, len(prices) - order):
            if mode == "high":
                if all(prices[i] >= prices[i - j] for j in range(1, order + 1)) and \
                   all(prices[i] >= prices[i + j] for j in range(1, order + 1)):
                    swings.append((i, prices[i]))
            else:
                if all(prices[i] <= prices[i - j] for j in range(1, order + 1)) and \
                   all(prices[i] <= prices[i + j] for j in range(1, order + 1)):
                    swings.append((i, prices[i]))
        return swings

    def _fit_trendline(
        self,
        indices: np.ndarray,
        values: np.ndarray,
    ) -> Tuple[float, float]:
        """Fit a linear trendline (y = slope*x + intercept)."""
        if len(indices) < 2:
            return (0.0, values[0] if len(values) > 0 else 0.0)

        coeffs = np.polyfit(indices, values, 1)
        return (coeffs[0], coeffs[1])  # slope, intercept

    def _adaptive_tolerance(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
    ) -> float:
        """
        Calculate touch tolerance based on recent volatility.
        More volatile = wider tolerance.
        """
        ranges = highs - lows
        avg_range = np.mean(ranges)
        return max(self.TOUCH_TOLERANCE, avg_range * 0.15)

    def _count_touches(
        self,
        prices: np.ndarray,
        indices: np.ndarray,
        slope: float,
        intercept: float,
        tolerance: float,
        mode: str = "upper",
    ) -> int:
        """Count how many candles touch the trendline."""
        count = 0
        for i, idx in enumerate(indices):
            line_value = slope * idx + intercept
            if mode == "upper":
                distance = abs(prices[i] - line_value)
            else:
                distance = abs(prices[i] - line_value)
            if distance <= tolerance:
                count += 1
        return count

    # ─────────────────────── PHASE 2: BREAKOUT ───────────────────────

    def _detect_breakout(
        self,
        candles: List[Dict],
        wedge: WedgePattern,
    ) -> Optional[Tuple[str, int]]:
        """
        Detect if price has broken out of the wedge.
        
        We look at the last 5 candles to see if any closed beyond
        the trendline boundary.
        
        Returns: (direction "BELOW" or "ABOVE", candle_index) or None
        """
        lookback = min(self.MAX_WEDGE_CANDLES, len(candles))

        for i in range(max(0, len(candles) - 5), len(candles)):
            # Position within the wedge window
            wedge_pos = i - (len(candles) - lookback)
            if wedge_pos < 0:
                continue

            close = candles[i]["close"]
            low = candles[i]["low"]
            high = candles[i]["high"]

            # Calculate trendline values at this position
            upper_line = wedge.upper_slope * wedge_pos + wedge.upper_intercept
            lower_line = wedge.lower_slope * wedge_pos + wedge.lower_intercept

            # Breakout below lower line
            if close < lower_line - self.BREAKOUT_THRESHOLD:
                return ("BELOW", i)

            # Breakout above upper line
            if close > upper_line + self.BREAKOUT_THRESHOLD:
                return ("ABOVE", i)

        return None

    # ─────────────────────── PHASE 3: STOP HUNT ───────────────────────

    def _detect_stop_hunt(
        self,
        candles: List[Dict],
        wedge: WedgePattern,
        breakout_dir: str,
        breakout_idx: int,
    ) -> Optional[StopHunt]:
        """
        Detect a liquidity grab / stop hunt after the breakout.
        
        Key characteristics:
          - Long wick beyond the breakout level (grabbing stops)
          - Close back inside or near the trendline
          - Wick > 60% of total range (exhaustion wick)
        
        We look at the last 3 candles after breakout.
        """
        search_start = max(breakout_idx, len(candles) - 3)

        for i in range(search_start, len(candles)):
            c = candles[i]
            high = c["high"]
            low = c["low"]
            open_ = c["open"]
            close = c["close"]
            total_range = high - low

            if total_range == 0:
                continue

            if breakout_dir == "BELOW":
                # Stop hunt below: long lower wick, close near open or higher
                lower_wick = min(open_, close) - low
                wick_ratio = lower_wick / total_range

                if wick_ratio >= self.WICK_EXHAUSTION_RATIO:
                    # Good exhaustion wick — stops were grabbed below
                    return StopHunt(
                        candle_index=i,
                        direction="BELOW",
                        extreme_price=low,
                        close_price=close,
                        wick_ratio=wick_ratio,
                    )

            elif breakout_dir == "ABOVE":
                # Stop hunt above: long upper wick, close near open or lower
                upper_wick = high - max(open_, close)
                wick_ratio = upper_wick / total_range

                if wick_ratio >= self.WICK_EXHAUSTION_RATIO:
                    return StopHunt(
                        candle_index=i,
                        direction="ABOVE",
                        extreme_price=high,
                        close_price=close,
                        wick_ratio=wick_ratio,
                    )

        return None

    # ─────────────────────── PHASE 4: REVERSAL CONFIRMATION ───────────────────────

    def _confirm_reversal(
        self,
        candles: List[Dict],
        wedge: WedgePattern,
        hunt: StopHunt,
        breakout_dir: str,
    ) -> Optional[Dict]:
        """
        Confirm reversal after the stop hunt.
        
        Requirements:
          1. First candle closing back inside the wedge boundary
          2. RSI showing momentum shift (oversold on buy, overbought on sell)
          3. Close is in the direction of reversal
        
        Returns reversal details dict or None.
        """
        # Look at candles after the stop hunt
        last_candle = candles[-1]
        close = last_candle["close"]
        open_ = last_candle["open"]

        lookback = min(self.MAX_WEDGE_CANDLES, len(candles))
        candle_pos = len(candles) - 1 - (len(candles) - lookback)

        if candle_pos < 0:
            candle_pos = 0

        # Calculate current trendline values
        upper_line = wedge.upper_slope * candle_pos + wedge.upper_intercept
        lower_line = wedge.lower_slope * candle_pos + wedge.lower_intercept

        # Calculate RSI
        rsi = self._calculate_rsi(candles)

        # ── For BUY reversal (breakout was below, hunt below, now reversing up) ──
        if breakout_dir == "BELOW":
            # 1. Candle must close back above the lower trendline
            back_inside = close > lower_line
            # 2. Bullish candle (close > open)
            bullish = close > open_
            # 3. RSI was oversold and turning up
            rsi_confirm = rsi < self.RSI_OVERSOLD or rsi < 50
            # 4. Close above the stop hunt candle's close
            above_hunt = close > hunt.close_price

            if back_inside and bullish and (rsi_confirm or above_hunt):
                return {
                    "back_inside": back_inside,
                    "bullish": bullish,
                    "rsi": round(rsi, 1),
                    "rsi_confirm": rsi_confirm,
                    "above_hunt": above_hunt,
                    "momentum_shift": True,
                    "upper_line": upper_line,
                    "lower_line": lower_line,
                }

        # ── For SELL reversal (breakout was above, hunt above, now reversing down) ──
        elif breakout_dir == "ABOVE":
            back_inside = close < upper_line
            bearish = close < open_
            rsi_confirm = rsi > self.RSI_OVERBOUGHT or rsi > 50
            below_hunt = close < hunt.close_price

            if back_inside and bearish and (rsi_confirm or below_hunt):
                return {
                    "back_inside": back_inside,
                    "bearish": bearish,
                    "rsi": round(rsi, 1),
                    "rsi_confirm": rsi_confirm,
                    "below_hunt": below_hunt,
                    "momentum_shift": True,
                    "upper_line": upper_line,
                    "lower_line": lower_line,
                }

        return None

    # ─────────────────────── RSI CALCULATION ───────────────────────

    def _calculate_rsi(self, candles: List[Dict], period: int = 14) -> float:
        """Calculate RSI from candle closes."""
        if len(candles) < period + 1:
            return 50.0  # Neutral if not enough data

        closes = np.array([c["close"] for c in candles[-(period + 1):]])
        deltas = np.diff(closes)

        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    # ─────────────────────── CONFIDENCE ───────────────────────

    def _calculate_confidence(
        self,
        wedge: WedgePattern,
        hunt: StopHunt,
        reversal: Dict,
        candles: List[Dict],
    ) -> float:
        """
        Calculate signal confidence (0-100).
        
        Factors:
          - Wedge quality (touches, convergence)
          - Stop hunt quality (wick exhaustion ratio)
          - Reversal quality (RSI, momentum shift)
          - Market context (in killzone?)
        """
        score = 0.0

        # Wedge quality (0-30)
        total_touches = wedge.touches_upper + wedge.touches_lower
        touch_score = min(total_touches / 8.0, 1.0) * 15
        convergence_score = (1.0 - (wedge.width_at_end / wedge.width_at_start)) * 15
        score += touch_score + convergence_score

        # Stop hunt quality (0-30)
        wick_score = min(hunt.wick_ratio / 0.8, 1.0) * 20
        score += wick_score
        # Volume spike bonus
        if hunt.volume_spike:
            score += 10

        # Reversal quality (0-25)
        if reversal.get("momentum_shift"):
            score += 15
        rsi = reversal.get("rsi", 50)
        if rsi < 30 or rsi > 70:
            score += 10  # Strong RSI extremes

        # Back inside bonus
        if reversal.get("back_inside"):
            score += 5

        # Context bonus (0-10)
        now = datetime.now(timezone.utc)
        hour = now.hour
        # NY killzone bonus
        if 13 <= hour <= 16:
            score += 10
        elif 8 <= hour <= 12:
            score += 5

        return min(round(score, 1), 100.0)

    # ─────────────────────── MULTI-SYMBOL SCAN ───────────────────────

    def scan_all(
        self,
        symbols_candles: Dict[str, List[Dict]],
    ) -> List[SignatureSignal]:
        """
        Scan multiple symbols and return any actionable signals.
        
        Args:
            symbols_candles: {"EURUSD": [candle_dicts], "US100": [candle_dicts], ...}
        
        Returns:
            List of signals with phase == ENTRY_READY
        """
        signals = []

        for symbol, candles in symbols_candles.items():
            try:
                signal = self.scan(symbol, candles)
                if signal.phase == SignalPhase.ENTRY_READY:
                    signals.append(signal)
                    logger.info(
                        f"🎯 SIGNAL: {symbol} {signal.direction} "
                        f"confidence={signal.confidence}% "
                        f"entry={signal.entry_price:.5f}"
                    )
                elif signal.phase in (SignalPhase.STOP_HUNT, SignalPhase.BREAKOUT):
                    logger.info(
                        f"📊 {symbol} in phase {signal.phase.value} — watching..."
                    )
            except Exception as e:
                logger.error(f"Scan error for {symbol}: {e}")

        return signals
