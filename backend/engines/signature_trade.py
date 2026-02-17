"""
╔══════════════════════════════════════════════════════════════════════╗
║        FOREXIA SIGNATURE AGENT — SIGNATURE TRADE DETECTOR           ║
║   Wedge/Triangle Induction → Stop Hunt → Reversal Pattern Engine    ║
╚══════════════════════════════════════════════════════════════════════╝

The Signature Trade is the crown jewel of the Forexia system.
It detects the institutional manipulation pattern in real-time:

  1. WEDGE/TRIANGLE FORMATION — Price converges into a pattern.
     Retail sees "consolidation." Smart Money sees a TRAP being set.

  2. FALSE BREAKOUT (INDUCTION) — Price breaks the pattern boundary.
     Retail enters on the "breakout." They are the FUEL.

  3. STOP HUNT INTO LIQUIDITY — The breakout pushes into a Liquidity
     Zone (HOD/LOD, weekly levels). Retail stops cluster here.

  4. EXHAUSTION WICK — The stop hunt candle prints a massive wick,
     showing the institutional order block has absorbed all retail flow.

  5. REVERSAL EXECUTION — We fire in the opposite direction of the
     false breakout. Retail's pain is our profit.

NO FVG/imbalance logic. NO retail indicators. Pure price structure warfare.
"""

import logging
import numpy as np
from typing import List, Optional, Tuple
from datetime import datetime

from backend.config import CONFIG
from backend.models.schemas import (
    CandleData, LiquidityZone, InductionState, TradeDirection
)

logger = logging.getLogger("forexia.signature_trade")


class SignatureTradeDetector:
    """
    Pattern recognition engine for the Signature Trade.
    
    This detector scans for converging price structures (wedges/triangles),
    waits for the false breakout (induction), identifies the stop hunt
    into a liquidity zone, and confirms reversal via wick exhaustion.
    """

    def __init__(self):
        self.config = CONFIG.signature
        self._state = InductionState.NO_PATTERN
        self._pattern_type: Optional[str] = None  # "WEDGE" or "TRIANGLE"
        self._upper_trendline: Optional[Tuple[float, float]] = None  # (slope, intercept)
        self._lower_trendline: Optional[Tuple[float, float]] = None
        self._breakout_level: Optional[float] = None
        self._breakout_direction: Optional[str] = None  # "UP" or "DOWN"
        self._stop_hunt_extreme: Optional[float] = None

    @property
    def current_state(self) -> InductionState:
        return self._state

    # ─────────────────────────────────────────────────────────────────
    #  PHASE 1: PATTERN DETECTION — WEDGES & TRIANGLES
    # ─────────────────────────────────────────────────────────────────

    def detect_converging_pattern(
        self, candles: List[CandleData]
    ) -> Tuple[InductionState, Optional[str]]:
        """
        Scan for Wedge or Triangle formations.
        
        We find converging trendlines connecting swing highs and swing lows.
        These patterns are NOT "consolidation" — they are TRAPS.
        The converging structure squeezes retail into thinking a breakout 
        is imminent, concentrating their stop-losses at the boundaries.
        
        Returns:
            (current_state, pattern_type)
        """
        if len(candles) < self.config.min_pattern_bars:
            return (InductionState.NO_PATTERN, None)

        # Use only the last N candles for pattern detection
        window = candles[-self.config.max_pattern_bars:]
        highs = np.array([c.high for c in window])
        lows = np.array([c.low for c in window])

        # Find swing highs — local maxima where retail places sell stops
        swing_highs = self._find_swing_points(highs, is_high=True)
        # Find swing lows — local minima where retail places buy stops
        swing_lows = self._find_swing_points(lows, is_high=False)

        if len(swing_highs) < self.config.min_wedge_touches or \
           len(swing_lows) < self.config.min_wedge_touches:
            self._state = InductionState.NO_PATTERN
            return (self._state, None)

        # Fit trendlines through swing points
        upper_slope, upper_intercept = self._fit_trendline(swing_highs, highs)
        lower_slope, lower_intercept = self._fit_trendline(swing_lows, lows)

        if upper_slope is None or lower_slope is None:
            self._state = InductionState.NO_PATTERN
            return (self._state, None)

        # Classify the pattern based on trendline slopes
        pattern_type = self._classify_pattern(upper_slope, lower_slope)

        if pattern_type:
            self._upper_trendline = (upper_slope, upper_intercept)
            self._lower_trendline = (lower_slope, lower_intercept)
            self._pattern_type = pattern_type

            if pattern_type == "WEDGE":
                self._state = InductionState.WEDGE_FORMING
            else:
                self._state = InductionState.TRIANGLE_FORMING

            # Calculate where the pattern boundaries project to NOW
            n = len(window) - 1
            upper_boundary = upper_slope * n + upper_intercept
            lower_boundary = lower_slope * n + lower_intercept

            logger.info(
                f"══╡ {pattern_type} FORMING — The trap is being set ╞══\n"
                f"    Upper boundary: {upper_boundary:.5f} "
                f"(retail sell stops clustered above)\n"
                f"    Lower boundary: {lower_boundary:.5f} "
                f"(retail buy stops clustered below)\n"
                f"    Squeeze width: {(upper_boundary - lower_boundary) * 10000:.1f} pips"
            )

        return (self._state, pattern_type)

    # ─────────────────────────────────────────────────────────────────
    #  PHASE 2: FALSE BREAKOUT DETECTION (INDUCTION)
    # ─────────────────────────────────────────────────────────────────

    def detect_false_breakout(
        self, candles: List[CandleData]
    ) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Detect if price has broken through the pattern boundary.
        
        This is the INDUCTION — the moment retail traders see a "breakout"
        and pile in. They don't realize they are being HERDED into a
        liquidity zone where their stops will be harvested.
        
        The false breakout must exceed the pattern boundary by the
        configured threshold to confirm retail commitment.
        
        Returns:
            (breakout_detected, direction, breakout_price)
        """
        if self._state not in (InductionState.WEDGE_FORMING,
                                InductionState.TRIANGLE_FORMING):
            return (False, None, None)

        if not self._upper_trendline or not self._lower_trendline:
            return (False, None, None)

        # Project trendlines to current bar
        n = len(candles) - 1
        upper_level = self._upper_trendline[0] * n + self._upper_trendline[1]
        lower_level = self._lower_trendline[0] * n + self._lower_trendline[1]

        latest = candles[-1]
        threshold = self.config.breakout_threshold_pips * 0.0001

        # Upside breakout — retail goes LONG (they're about to get trapped)
        if latest.high > upper_level + threshold:
            self._state = InductionState.FALSE_BREAKOUT
            self._breakout_direction = "UP"
            self._breakout_level = upper_level
            logger.info(
                f"══╡ FALSE BREAKOUT DETECTED — Upside! ╞══\n"
                f"    Price: {latest.high:.5f} broke above {upper_level:.5f}\n"
                f"    Retail longs piling in — they're walking into the trap\n"
                f"    Dumb money is LONG here. Smart Money is loading shorts."
            )
            return (True, "UP", latest.high)

        # Downside breakout — retail goes SHORT (also trapped)
        if latest.low < lower_level - threshold:
            self._state = InductionState.FALSE_BREAKOUT
            self._breakout_direction = "DOWN"
            self._breakout_level = lower_level
            logger.info(
                f"══╡ FALSE BREAKOUT DETECTED — Downside! ╞══\n"
                f"    Price: {latest.low:.5f} broke below {lower_level:.5f}\n"
                f"    Retail shorts piling in — walking into the trap\n"
                f"    Dumb money is SHORT here. Smart Money is loading longs."
            )
            return (True, "DOWN", latest.low)

        return (False, None, None)

    # ─────────────────────────────────────────────────────────────────
    #  PHASE 3: STOP HUNT INTO LIQUIDITY ZONE
    # ─────────────────────────────────────────────────────────────────

    def detect_stop_hunt(
        self,
        candles: List[CandleData],
        liquidity_zones: List[LiquidityZone]
    ) -> Tuple[bool, Optional[LiquidityZone]]:
        """
        Detect if the false breakout has pushed into a known Liquidity Zone.
        
        Liquidity Zones are where retail stops cluster:
          - High of Day (HOD) / Low of Day (LOD)
          - Previous session highs/lows
          - Weekly highs/lows
          - Psychological round numbers
        
        When price reaches these zones, Smart Money is HARVESTING stops.
        The volume of stopped-out retail orders provides the liquidity for
        Smart Money to fill their real positions in the opposite direction.
        
        Returns:
            (stop_hunt_detected, targeted_liquidity_zone)
        """
        if self._state != InductionState.FALSE_BREAKOUT:
            return (False, None)

        latest = candles[-1]

        for zone in liquidity_zones:
            if zone.swept:
                continue  # Already raided — move on

            tolerance = 0.0005  # 5 pips tolerance

            zone_hit = False
            if self._breakout_direction == "UP" and zone.zone_type in (
                "ASIAN_HIGH", "HIGH_OF_DAY", "WEEKLY_HIGH", "PSYCH_LEVEL"
            ):
                zone_hit = latest.high >= zone.level - tolerance

            elif self._breakout_direction == "DOWN" and zone.zone_type in (
                "ASIAN_LOW", "LOW_OF_DAY", "WEEKLY_LOW", "PSYCH_LEVEL"
            ):
                zone_hit = latest.low <= zone.level + tolerance

            if zone_hit:
                self._state = InductionState.STOP_HUNT_ACTIVE
                self._stop_hunt_extreme = (
                    latest.high if self._breakout_direction == "UP" else latest.low
                )
                zone.swept = True
                zone.swept_at = datetime.utcnow()

                logger.info(
                    f"══╡ STOP HUNT ACTIVE — Liquidity Zone RAIDED! ╞══\n"
                    f"    Zone: {zone.zone_type} @ {zone.level:.5f}\n"
                    f"    Hunt extreme: {self._stop_hunt_extreme:.5f}\n"
                    f"    Retail stops are being harvested en masse.\n"
                    f"    Smart Money is filling their REAL position."
                )
                return (True, zone)

        return (False, None)

    # ─────────────────────────────────────────────────────────────────
    #  PHASE 4: EXHAUSTION & REVERSAL CONFIRMATION
    # ─────────────────────────────────────────────────────────────────

    def detect_exhaustion_reversal(
        self, candles: List[CandleData]
    ) -> Tuple[bool, Optional[TradeDirection], Optional[float]]:
        """
        Detect candlestick wick exhaustion and reversal confirmation.
        
        After the stop hunt, the candle prints a massive WICK in the
        direction of the hunt (exhaustion). This wick shows that all
        the retail liquidity has been absorbed and Smart Money is now
        reversing.
        
        We look for:
          - Wick exhaustion ratio >= 65% (configurable)
          - "Railroad tracks" — two opposing candles (rejection)
          - Reversal confirmation over N candles
        
        THIS IS OUR ENTRY SIGNAL.
        
        Returns:
            (reversal_confirmed, trade_direction, entry_price)
        """
        if self._state != InductionState.STOP_HUNT_ACTIVE:
            return (False, None, None)

        if len(candles) < self.config.reversal_confirmation_candles + 1:
            return (False, None, None)

        # Check the candle at the stop hunt extreme for exhaustion wick
        hunt_candle = candles[-2]  # The candle that made the extreme
        confirm_candle = candles[-1]  # The candle after

        if self._breakout_direction == "UP":
            # Upside stop hunt — look for UPPER wick exhaustion
            # The wick shows Smart Money rejecting higher prices
            wick_ratio = hunt_candle.upper_wick_ratio

            if wick_ratio >= self.config.wick_exhaustion_ratio:
                self._state = InductionState.EXHAUSTION_DETECTED
                logger.info(
                    f"══╡ EXHAUSTION WICK — Upper wick ratio: {wick_ratio:.2f} ╞══\n"
                    f"    Smart Money has absorbed all retail buy stops.\n"
                    f"    Price rejected at {hunt_candle.high:.5f}"
                )

                # Confirm reversal — next candle must be bearish
                if not confirm_candle.is_bullish and \
                   confirm_candle.close < hunt_candle.close:
                    self._state = InductionState.REVERSAL_CONFIRMED
                    entry = confirm_candle.close
                    logger.info(
                        f"══╡ REVERSAL CONFIRMED — SELL SIGNAL! ╞══\n"
                        f"    Entry: {entry:.5f} | Direction: SELL\n"
                        f"    Dumb money longs are about to get liquidated.\n"
                        f"    Executing on the Solution phase."
                    )
                    return (True, TradeDirection.SELL, entry)

        elif self._breakout_direction == "DOWN":
            # Downside stop hunt — look for LOWER wick exhaustion
            wick_ratio = hunt_candle.lower_wick_ratio

            if wick_ratio >= self.config.wick_exhaustion_ratio:
                self._state = InductionState.EXHAUSTION_DETECTED
                logger.info(
                    f"══╡ EXHAUSTION WICK — Lower wick ratio: {wick_ratio:.2f} ╞══\n"
                    f"    Smart Money has absorbed all retail sell stops.\n"
                    f"    Price rejected at {hunt_candle.low:.5f}"
                )

                # Confirm reversal — next candle must be bullish
                if confirm_candle.is_bullish and \
                   confirm_candle.close > hunt_candle.close:
                    self._state = InductionState.REVERSAL_CONFIRMED
                    entry = confirm_candle.close
                    logger.info(
                        f"══╡ REVERSAL CONFIRMED — BUY SIGNAL! ╞══\n"
                        f"    Entry: {entry:.5f} | Direction: BUY\n"
                        f"    Dumb money shorts are about to get squeezed.\n"
                        f"    Executing on the Solution phase."
                    )
                    return (True, TradeDirection.BUY, entry)

        return (False, None, None)

    # ─────────────────────────────────────────────────────────────────
    #  FULL SCAN — RUN ALL PHASES IN SEQUENCE
    # ─────────────────────────────────────────────────────────────────

    def scan(
        self,
        candles: List[CandleData],
        liquidity_zones: List[LiquidityZone]
    ) -> Tuple[InductionState, Optional[TradeDirection], Optional[float]]:
        """
        Run the complete Signature Trade scan pipeline.
        
        This method runs all four phases in sequence:
          1. Detect converging pattern
          2. Detect false breakout
          3. Detect stop hunt into liquidity
          4. Detect exhaustion & reversal
        
        Returns the current state and trade signal if reversal confirmed.
        """
        # Phase 1: Look for the trap formation
        if self._state == InductionState.NO_PATTERN:
            self.detect_converging_pattern(candles)

        # Phase 2: Watch for the false breakout
        if self._state in (InductionState.WEDGE_FORMING,
                           InductionState.TRIANGLE_FORMING):
            self.detect_false_breakout(candles)

        # Phase 3: Identify the stop hunt
        if self._state == InductionState.FALSE_BREAKOUT:
            self.detect_stop_hunt(candles, liquidity_zones)

        # Phase 4: Confirm exhaustion and reversal
        if self._state == InductionState.STOP_HUNT_ACTIVE:
            confirmed, direction, entry = self.detect_exhaustion_reversal(candles)
            if confirmed:
                return (self._state, direction, entry)

        return (self._state, None, None)

    def reset(self):
        """Reset all pattern state for a new scan cycle."""
        self._state = InductionState.NO_PATTERN
        self._pattern_type = None
        self._upper_trendline = None
        self._lower_trendline = None
        self._breakout_level = None
        self._breakout_direction = None
        self._stop_hunt_extreme = None
        logger.debug("Signature Trade detector reset")

    # ─────────────────────────────────────────────────────────────────
    #  INTERNAL PATTERN MATH
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _find_swing_points(
        prices: np.ndarray, is_high: bool = True, window: int = 3
    ) -> List[int]:
        """
        Find swing highs or swing lows (local extrema).
        
        A swing high is a bar whose high is higher than the N bars
        on either side. These are where retail places their stops —
        the targets for Smart Money stop hunts.
        """
        points = []
        for i in range(window, len(prices) - window):
            if is_high:
                is_extreme = all(
                    prices[i] >= prices[i - j] and prices[i] >= prices[i + j]
                    for j in range(1, window + 1)
                )
            else:
                is_extreme = all(
                    prices[i] <= prices[i - j] and prices[i] <= prices[i + j]
                    for j in range(1, window + 1)
                )
            if is_extreme:
                points.append(i)
        return points

    @staticmethod
    def _fit_trendline(
        indices: List[int], prices: np.ndarray
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Fit a linear trendline through swing points using least squares.
        Returns (slope, intercept) or (None, None) if insufficient data.
        """
        if len(indices) < 2:
            return (None, None)

        x = np.array(indices, dtype=float)
        y = np.array([prices[i] for i in indices], dtype=float)

        # Least squares linear fit: y = slope * x + intercept
        A = np.vstack([x, np.ones(len(x))]).T
        try:
            result = np.linalg.lstsq(A, y, rcond=None)
            slope, intercept = result[0]
            return (float(slope), float(intercept))
        except Exception:
            return (None, None)

    @staticmethod
    def _classify_pattern(
        upper_slope: float, lower_slope: float
    ) -> Optional[str]:
        """
        Classify the converging pattern:
        
        WEDGE: Both trendlines slope in the same direction but converge.
          - Rising wedge: both slope up, upper steeper (bearish)
          - Falling wedge: both slope down, lower steeper (bullish)
        
        TRIANGLE: Trendlines slope in opposite directions (converging).
          - Symmetric: roughly equal magnitude
          - Ascending: upper flat, lower rising
          - Descending: lower flat, upper falling
        
        We don't care about textbook classifications — we care that
        the lines CONVERGE, squeezing retail into a tighter range
        before the induction breakout.
        """
        # Check for convergence: slopes must bring lines closer
        convergence = upper_slope - lower_slope

        if abs(convergence) < 0.00001:
            return None  # Lines are parallel — no convergence, no trap

        # Both slopes same direction = WEDGE
        if (upper_slope > 0 and lower_slope > 0) or \
           (upper_slope < 0 and lower_slope < 0):
            # Must be converging (one slope less steep than the other)
            if convergence < 0:  # Upper falling faster or rising slower
                return "WEDGE"
            return None

        # Slopes in opposite directions = TRIANGLE
        if (upper_slope <= 0 and lower_slope >= 0):
            return "TRIANGLE"

        # Upper rising, lower falling = diverging, not a valid pattern
        return None

    @property
    def stop_hunt_extreme(self) -> Optional[float]:
        """The extreme price of the stop hunt — used for SL placement."""
        return self._stop_hunt_extreme

    @property
    def breakout_direction(self) -> Optional[str]:
        return self._breakout_direction
