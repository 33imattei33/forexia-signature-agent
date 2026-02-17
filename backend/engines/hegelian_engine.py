"""
╔══════════════════════════════════════════════════════════════════════╗
║         FOREXIA SIGNATURE AGENT — HEGELIAN DIALECTIC ENGINE         ║
║      Detecting the 3-Phase Daily Manipulation Cycle                  ║
╚══════════════════════════════════════════════════════════════════════╝

The Hegelian Dialectic of institutional trading:

  THESIS (Problem):    Asian Consolidation — retail sets stops at the
                       edges of the range. The problem is created.

  ANTITHESIS (Reaction): London Induction — Smart Money engineers a
                         false breakout to trap breakout traders. Retail
                         enters on the "trend." This is the bait.

  SYNTHESIS (Solution):  New York Reversal — Smart Money reverses
                         against the London induction. Retail gets
                         stopped out. We enter HERE.

This engine determines which phase is active and identifies the
transition points where institutional manipulation is most visible.
"""

import logging
from datetime import datetime, time, timedelta
from typing import List, Optional, Tuple

from backend.config import CONFIG
from backend.models.schemas import (
    SessionPhase, CandleData, LiquidityZone
)

logger = logging.getLogger("forexia.dialectic_engine")


class HegelianDialecticEngine:
    """
    The core timing engine that reads the institutional clock.
    
    We don't trade time — we trade manipulation phases.
    This engine tells us WHEN the trap is set and WHEN to strike.
    """

    def __init__(self):
        self.config = CONFIG.sessions
        self._asian_range: Optional[Tuple[float, float]] = None  # (high, low)
        self._london_extreme: Optional[float] = None
        self._london_direction: Optional[str] = None  # "UP" or "DOWN"
        self._induction_detected = False
        self._solution_phase_active = False

    # ─────────────────────────────────────────────────────────────────
    #  PHASE DETECTION — WHERE ARE WE IN THE DIALECTIC?
    # ─────────────────────────────────────────────────────────────────

    def get_current_phase(self, utc_now: Optional[datetime] = None) -> SessionPhase:
        """
        Determine which Hegelian phase is currently active.
        This drives all downstream trading decisions.
        """
        utc_now = utc_now or datetime.utcnow()
        current_time = utc_now.time()

        asian_start = self._parse_time(self.config.asian_start)
        asian_end = self._parse_time(self.config.asian_end)
        london_start = self._parse_time(self.config.london_start)
        london_end = self._parse_time(self.config.london_end)
        ny_start = self._parse_time(self.config.newyork_start)
        ny_end = self._parse_time(self.config.newyork_end)

        # Check weekend — market is closed
        if utc_now.weekday() >= 5:  # Saturday=5, Sunday=6
            return SessionPhase.CLOSED

        # THESIS — Asian Consolidation (Problem Phase)
        # Retail is placing stops above/below the range
        if asian_start <= current_time < asian_end:
            return SessionPhase.PROBLEM

        # ANTITHESIS — London Induction (Reaction Phase)
        # Smart Money breaks the Asian range to trap retail
        if london_start <= current_time < london_end:
            return SessionPhase.REACTION

        # SYNTHESIS — New York Reversal (Solution Phase)
        # We strike — entering opposite to London's false move
        if ny_start <= current_time < ny_end:
            return SessionPhase.SOLUTION

        return SessionPhase.CLOSED

    def is_in_killzone(self, utc_now: Optional[datetime] = None) -> bool:
        """
        Check if we're in the prime New York Kill Zone.
        This is the optimal execution window — 13:00-16:00 UTC.
        The highest probability entries occur here.
        """
        utc_now = utc_now or datetime.utcnow()
        current_time = utc_now.time()
        kz_start = self._parse_time(self.config.killzone_ny_start)
        kz_end = self._parse_time(self.config.killzone_ny_end)
        return kz_start <= current_time <= kz_end

    # ─────────────────────────────────────────────────────────────────
    #  THESIS — ASIAN RANGE ANALYSIS (The Problem)
    # ─────────────────────────────────────────────────────────────────

    def calculate_asian_range(self, candles: List[CandleData]) -> Tuple[float, float]:
        """
        Calculate the Asian session high/low range.
        
        This range is CRITICAL — it's where retail parks their stops.
        Smart Money WILL hunt these levels during London.
        The Asian range is the "Problem" that institutions will exploit.
        """
        asian_start = self._parse_time(self.config.asian_start)
        asian_end = self._parse_time(self.config.asian_end)

        asian_candles = [
            c for c in candles
            if asian_start <= c.timestamp.time() < asian_end
        ]

        if not asian_candles:
            logger.warning("No Asian session candles found — cannot define the Problem")
            return (0, 0)

        high = max(c.high for c in asian_candles)
        low = min(c.low for c in asian_candles)

        self._asian_range = (high, low)
        logger.info(
            f"══╡ THESIS (Problem) defined — Asian Range: "
            f"High {high:.5f} | Low {low:.5f} "
            f"| Retail stops are clustered here ╞══"
        )
        return (high, low)

    def get_asian_liquidity_zones(self) -> List[LiquidityZone]:
        """
        Generate liquidity zones from the Asian range.
        These are the pools of retail stop-losses that Smart Money
        will raid during the London Induction.
        """
        if not self._asian_range:
            return []

        high, low = self._asian_range
        now = datetime.utcnow()

        zones = [
            LiquidityZone(
                symbol="",  # Set by caller
                level=high,
                zone_type="ASIAN_HIGH",
                strength=7,  # Asian highs are moderately thick with stops
                formed_at=now,
            ),
            LiquidityZone(
                symbol="",
                level=low,
                zone_type="ASIAN_LOW",
                strength=7,
                formed_at=now,
            ),
        ]
        return zones

    # ─────────────────────────────────────────────────────────────────
    #  ANTITHESIS — LONDON INDUCTION DETECTION (The Reaction)
    # ─────────────────────────────────────────────────────────────────

    def detect_london_induction(
        self, candles: List[CandleData]
    ) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Detect if London session has engineered a false breakout
        of the Asian range.

        The Induction is when price breaks above/below the Asian range,
        sucking in retail breakout traders. These traders are the FUEL
        that Smart Money will burn during the New York Reversal.

        Returns:
            (induction_detected, direction, extreme_price)
        """
        if not self._asian_range:
            return (False, None, None)

        asian_high, asian_low = self._asian_range
        london_start = self._parse_time(self.config.london_start)
        london_end = self._parse_time(self.config.london_end)

        london_candles = [
            c for c in candles
            if london_start <= c.timestamp.time() < london_end
        ]

        if not london_candles:
            return (False, None, None)

        london_high = max(c.high for c in london_candles)
        london_low = min(c.low for c in london_candles)

        # Upside induction — London broke above Asian high
        # Retail is LONG, thinking it's a breakout. They're trapped.
        broke_high = london_high > asian_high + (
            CONFIG.signature.breakout_threshold_pips * 0.0001
        )

        # Downside induction — London broke below Asian low
        # Retail is SHORT, thinking it's a breakdown. Also trapped.
        broke_low = london_low < asian_low - (
            CONFIG.signature.breakout_threshold_pips * 0.0001
        )

        if broke_high and broke_low:
            # Both sides swept — double induction (rare but powerful)
            # Direction depends on which extreme was hit LAST
            last_candle = london_candles[-1]
            if last_candle.close > asian_high:
                direction = "UP"
                extreme = london_high
            else:
                direction = "DOWN"
                extreme = london_low
            logger.info(
                "══╡ DOUBLE INDUCTION — Both sides swept! "
                f"Last direction: {direction}. Retail is fully trapped ╞══"
            )
        elif broke_high:
            direction = "UP"
            extreme = london_high
            logger.info(
                f"══╡ ANTITHESIS (Reaction) — Upside Induction detected! "
                f"London pushed to {london_high:.5f} above Asian High {asian_high:.5f}. "
                f"Retail longs are TRAPPED — dumb money took the bait ╞══"
            )
        elif broke_low:
            direction = "DOWN"
            extreme = london_low
            logger.info(
                f"══╡ ANTITHESIS (Reaction) — Downside Induction detected! "
                f"London pushed to {london_low:.5f} below Asian Low {asian_low:.5f}. "
                f"Retail shorts are TRAPPED ╞══"
            )
        else:
            # No induction yet — London hasn't broken the range
            return (False, None, None)

        self._induction_detected = True
        self._london_direction = direction
        self._london_extreme = extreme
        return (True, direction, extreme)

    # ─────────────────────────────────────────────────────────────────
    #  SYNTHESIS — NEW YORK REVERSAL DETECTION (The Solution)
    # ─────────────────────────────────────────────────────────────────

    def detect_ny_reversal(
        self, candles: List[CandleData]
    ) -> Tuple[bool, Optional[str]]:
        """
        Detect if New York session is reversing the London Induction.
        
        This is the SOLUTION phase of the Hegelian Dialectic.
        Smart Money is now unwinding the trap — price reverses against
        the London push, and retail gets stopped out en masse.
        
        The reversal direction is OPPOSITE to the London induction.
        If London pushed UP (trapping longs), NY reverses DOWN.
        If London pushed DOWN (trapping shorts), NY reverses UP.
        
        Returns:
            (reversal_detected, our_trade_direction)
        """
        if not self._induction_detected or not self._london_direction:
            return (False, None)

        ny_start = self._parse_time(self.config.newyork_start)
        ny_candles = [
            c for c in candles
            if c.timestamp.time() >= ny_start
        ]

        if len(ny_candles) < CONFIG.signature.reversal_confirmation_candles:
            return (False, None)

        # The reversal direction — OPPOSITE to induction
        # Use a rolling window to avoid single-candle noise on M1
        lookback = min(10, len(ny_candles))
        recent_candles = ny_candles[-lookback:]
        recent_close = ny_candles[-1].close
        
        # Trend: compare current close to the average of the first half of the window
        first_half = recent_candles[:max(1, lookback // 2)]
        first_half_avg = sum(c.close for c in first_half) / len(first_half)

        if self._london_direction == "UP":
            # London trapped LONGS — NY reversal is SHORT
            # We need to see price moving back below the Asian range
            asian_high = self._asian_range[0] if self._asian_range else 0

            # Price is reversing back DOWN through/near the Asian high
            reversing_down = recent_close < first_half_avg
            near_or_below_range = recent_close <= asian_high + (asian_high * 0.0002)

            if reversing_down and near_or_below_range:
                self._solution_phase_active = True
                logger.info(
                    f"══╡ SYNTHESIS (Solution) — NY Reversal CONFIRMED! "
                    f"Direction: SELL (opposing London's upside induction). "
                    f"Close {recent_close:.5f} vs Asian High {asian_high:.5f}. "
                    f"Dumb money longs are getting liquidated ╞══"
                )
                return (True, "SELL")

        elif self._london_direction == "DOWN":
            # London trapped SHORTS — NY reversal is LONG
            asian_low = self._asian_range[1] if self._asian_range else 0

            # Price is reversing back UP through/near the Asian low
            reversing_up = recent_close > first_half_avg
            near_or_above_range = recent_close >= asian_low - (asian_low * 0.0002)

            if reversing_up and near_or_above_range:
                self._solution_phase_active = True
                logger.info(
                    f"══╡ SYNTHESIS (Solution) — NY Reversal CONFIRMED! "
                    f"Direction: BUY (opposing London's downside induction). "
                    f"Close {recent_close:.5f} vs Asian Low {asian_low:.5f}. "
                    f"Dumb money shorts are getting squeezed ╞══"
                )
                return (True, "BUY")

        return (False, None)

    # ─────────────────────────────────────────────────────────────────
    #  INDUCTION METER — HOW TRAPPED IS RETAIL?
    # ─────────────────────────────────────────────────────────────────

    def calculate_induction_meter(self, candles: List[CandleData]) -> float:
        """
        Calculate the Induction Meter (0-100).
        
        This measures how deeply retail is trapped in the wrong direction.
        Higher = more retail volume trapped = higher probability reversal.

        Factors:
          - Distance of London push beyond Asian range (deeper = more trapped)
          - Volume spike during induction (more volume = more victims)
          - Number of candles spent above/below the range (more time = more
            retail entries accumulated)
        """
        if not self._asian_range or not self._induction_detected:
            return 0.0

        asian_high, asian_low = self._asian_range
        asian_range_size = asian_high - asian_low
        if asian_range_size <= 0:
            return 0.0

        london_start = self._parse_time(self.config.london_start)
        london_end = self._parse_time(self.config.london_end)
        london_candles = [
            c for c in candles
            if london_start <= c.timestamp.time() < london_end
        ]

        if not london_candles:
            return 0.0

        # Factor 1: Penetration depth (0-40 points)
        # How far beyond the Asian range did London push?
        if self._london_direction == "UP":
            penetration = max(0, max(c.high for c in london_candles) - asian_high)
        else:
            penetration = max(0, asian_low - min(c.low for c in london_candles))

        depth_score = min(40, (penetration / asian_range_size) * 100)

        # Factor 2: Volume intensity during induction (0-30 points)
        avg_volume = sum(c.volume for c in candles) / len(candles) if candles else 1
        induction_volume = sum(c.volume for c in london_candles) / len(london_candles)
        volume_ratio = induction_volume / avg_volume if avg_volume > 0 else 1
        volume_score = min(30, volume_ratio * 15)

        # Factor 3: Time spent in the trap (0-30 points)
        # More candles beyond the range = more retail entries = more fuel
        if self._london_direction == "UP":
            trapped_candles = sum(1 for c in london_candles if c.close > asian_high)
        else:
            trapped_candles = sum(1 for c in london_candles if c.close < asian_low)

        time_score = min(30, (trapped_candles / max(len(london_candles), 1)) * 30)

        meter = min(100.0, depth_score + volume_score + time_score)

        logger.info(
            f"Induction Meter: {meter:.1f}% "
            f"[Depth: {depth_score:.0f} | Volume: {volume_score:.0f} | "
            f"Time: {time_score:.0f}]"
        )
        return round(meter, 1)

    # ─────────────────────────────────────────────────────────────────
    #  DAILY RESET
    # ─────────────────────────────────────────────────────────────────

    def reset_daily(self):
        """
        Reset all daily state.
        Called at the start of each new Asian session.
        A new dialectic cycle begins.
        """
        self._asian_range = None
        self._london_extreme = None
        self._london_direction = None
        self._induction_detected = False
        self._solution_phase_active = False
        logger.info("═══ Daily Dialectic Reset — New cycle begins ═══")

    def reset_symbol(self):
        """
        Reset per-symbol state to prevent cross-pair contamination.
        Called before each symbol analysis in the scan loop.
        """
        self._asian_range = None
        self._london_extreme = None
        self._london_direction = None
        self._induction_detected = False
        self._solution_phase_active = False

    # ─────────────────────────────────────────────────────────────────
    #  UTILITIES
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_time(time_str: str) -> time:
        """Parse 'HH:MM' string to time object."""
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))

    @property
    def asian_range(self) -> Optional[Tuple[float, float]]:
        return self._asian_range

    @property
    def london_direction(self) -> Optional[str]:
        return self._london_direction

    @property
    def is_induction_active(self) -> bool:
        return self._induction_detected

    @property
    def is_solution_active(self) -> bool:
        return self._solution_phase_active
