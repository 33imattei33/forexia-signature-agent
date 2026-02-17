"""
╔══════════════════════════════════════════════════════════════════════╗
║            FOREXIA SIGNATURE AGENT — TRAUMA FILTER                  ║
║      God Candle Detection & Post-Spike Exhaustion Reversal          ║
╚══════════════════════════════════════════════════════════════════════╝

The Trauma Filter exists because of one truth:

  "God Candles" are ENGINEERED, not natural.

When a Red Folder event fires, the algorithm creates a massive, sudden
price spike — a "God Candle." This candle is designed to:
  1. Trigger retail stop-losses en masse (harvesting liquidity)
  2. Induce emotional responses (FOMO entries, panic exits)
  3. Create the illusion of a new "trend"

The Trauma Filter's job:
  - Detect the God Candle (ATR multiple spike)
  - SIT ON ITS HANDS during the initial push (DO NOT TRADE INTO IT)
  - Wait for the spike to pierce a Liquidity Pool (HOD/LOD/Weekly)
  - Watch for the exhaustion wick (the reversal signal)
  - Execute in the OPPOSITE direction of the initial spike
  - The retail "trauma" is our profit

We call it the Trauma Filter because it specifically targets the
emotional destruction that the algorithm inflicts on retail traders.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from backend.config import CONFIG
from backend.models.schemas import (
    CandleData, LiquidityZone, NewsCatalyst, TradeDirection
)

logger = logging.getLogger("forexia.trauma_filter")


class TraumaFilter:
    """
    Detects God Candles and targets the post-spike exhaustion reversal.
    
    When a Red Folder catalyst fires, the bot:
      1. DOES NOT TRADE during the initial spike (sits on hands)
      2. Waits for the spike to hit a liquidity pool
      3. Watches for the exhaustion wick printing
      4. Fires in the OPPOSITE direction
    
    This is the highest-volatility, highest-reward Forexia pattern.
    """

    def __init__(self):
        self.config = CONFIG.trauma
        self._active = False
        self._god_candle_detected = False
        self._spike_direction: Optional[str] = None  # "UP" or "DOWN"
        self._spike_extreme: Optional[float] = None
        self._spike_time: Optional[datetime] = None
        self._cooldown_until: Optional[datetime] = None
        self._atr_cache: dict = {}  # symbol -> ATR value

    @property
    def is_active(self) -> bool:
        """Whether the Trauma Filter is currently engaged."""
        return self._active

    @property
    def is_in_cooldown(self) -> bool:
        """Whether we're in the post-God-Candle cooldown period."""
        if not self._cooldown_until:
            return False
        return datetime.utcnow() < self._cooldown_until

    # ─────────────────────────────────────────────────────────────────
    #  ACTIVATION — ARM THE TRAUMA FILTER
    # ─────────────────────────────────────────────────────────────────

    def arm(self, catalyst: Optional[NewsCatalyst] = None):
        """
        Arm the Trauma Filter.
        Called when a Red Folder catalyst is imminent or firing.
        The bot enters "hands off" mode — NO entries until the
        God Candle exhaustion is detected.
        """
        self._active = True
        self._god_candle_detected = False
        self._spike_direction = None
        self._spike_extreme = None

        if catalyst:
            logger.info(
                f"══╡ TRAUMA FILTER ARMED — Catalyst: [{catalyst.currency}] "
                f"{catalyst.event_title} ╞══\n"
                f"    Bot is in OBSERVE ONLY mode.\n"
                f"    Waiting for the God Candle to print...\n"
                f"    DO NOT trade during the initial algorithmic push."
            )
        else:
            logger.info(
                "══╡ TRAUMA FILTER ARMED — Manual activation ╞══\n"
                "    Watching for God Candle spike..."
            )

    def disarm(self):
        """Disarm the Trauma Filter — return to normal operations."""
        self._active = False
        self._god_candle_detected = False
        self._spike_direction = None
        self._spike_extreme = None
        self._cooldown_until = None
        logger.info("Trauma Filter DISARMED — Normal operations resumed")

    # ─────────────────────────────────────────────────────────────────
    #  GOD CANDLE DETECTION — THE ALGORITHMIC NUKE
    # ─────────────────────────────────────────────────────────────────

    def detect_god_candle(
        self, candles: List[CandleData], symbol: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Detect a God Candle — a massive, sudden algorithmic push.
        
        A God Candle is identified when the current candle's range
        exceeds N times the Average True Range (ATR). This is NOT
        a normal market move — it's the algorithm executing its
        pre-programmed stop hunt under the cover of "news."
        
        During a God Candle:
          - Retail traders panic
          - Stop-losses are triggered en masse
          - Emotional FOMO entries pile in the wrong direction
          - The algorithm fills its REAL position against the flow
        
        WE DO NOT TRADE DURING THIS CANDLE.
        We WAIT for the exhaustion.
        
        Returns:
            (is_god_candle, spike_direction)
        """
        if len(candles) < 20:
            return (False, None)

        atr = self._calculate_atr(candles[:-1], period=14)
        self._atr_cache[symbol] = atr

        current = candles[-1]
        candle_range = current.range_size

        # God Candle = candle range >= multiplier * ATR
        # This is an ABNORMAL move — the algorithm is at work
        if candle_range >= atr * self.config.god_candle_multiplier:
            if current.is_bullish:
                self._spike_direction = "UP"
                self._spike_extreme = current.high
            else:
                self._spike_direction = "DOWN"
                self._spike_extreme = current.low

            self._god_candle_detected = True
            self._spike_time = datetime.utcnow()
            self._cooldown_until = datetime.utcnow() + timedelta(
                seconds=self.config.cooldown_seconds
            )

            logger.info(
                f"══╡ GOD CANDLE DETECTED — {symbol} ╞══\n"
                f"    Direction: {self._spike_direction}\n"
                f"    Range: {candle_range * 10000:.1f} pips "
                f"(ATR: {atr * 10000:.1f} pips, "
                f"Multiple: {candle_range / atr:.1f}x)\n"
                f"    Extreme: {self._spike_extreme:.5f}\n"
                f"    ┌─────────────────────────────────────────┐\n"
                f"    │ DO NOT TRADE. SIT ON HANDS.             │\n"
                f"    │ This is engineered retail TRAUMA.       │\n"
                f"    │ Wait for exhaustion wick...             │\n"
                f"    └─────────────────────────────────────────┘\n"
                f"    Cooldown: {self.config.cooldown_seconds}s"
            )
            return (True, self._spike_direction)

        return (False, None)

    # ─────────────────────────────────────────────────────────────────
    #  LIQUIDITY PIERCE DETECTION — DID THE SPIKE HIT A POOL?
    # ─────────────────────────────────────────────────────────────────

    def check_liquidity_pierce(
        self,
        current_candle: CandleData,
        liquidity_zones: List[LiquidityZone]
    ) -> Tuple[bool, Optional[LiquidityZone]]:
        """
        Check if the God Candle spike pierced a known Liquidity Pool.
        
        The spike is designed to reach these pools — that's where the
        retail stops are clustered. When the spike hits a pool, it means:
          - Maximum retail stops have been triggered
          - Maximum liquidity has been harvested
          - The algorithm has filled its position
          - The REVERSAL is imminent
        
        Returns:
            (pierced, zone)
        """
        if not self._god_candle_detected:
            return (False, None)

        tolerance = 0.0005  # 5 pips

        for zone in liquidity_zones:
            if zone.swept:
                continue

            if self._spike_direction == "UP":
                if current_candle.high >= zone.level - tolerance and \
                   zone.zone_type in ("HIGH_OF_DAY", "WEEKLY_HIGH",
                                      "ASIAN_HIGH", "PSYCH_LEVEL"):
                    zone.swept = True
                    zone.swept_at = datetime.utcnow()
                    logger.info(
                        f"══╡ LIQUIDITY PIERCED — God Candle hit {zone.zone_type} "
                        f"@ {zone.level:.5f} ╞══\n"
                        f"    Retail stops harvested. Waiting for exhaustion wick..."
                    )
                    return (True, zone)

            elif self._spike_direction == "DOWN":
                if current_candle.low <= zone.level + tolerance and \
                   zone.zone_type in ("LOW_OF_DAY", "WEEKLY_LOW",
                                      "ASIAN_LOW", "PSYCH_LEVEL"):
                    zone.swept = True
                    zone.swept_at = datetime.utcnow()
                    logger.info(
                        f"══╡ LIQUIDITY PIERCED — God Candle hit {zone.zone_type} "
                        f"@ {zone.level:.5f} ╞══\n"
                        f"    Retail stops harvested. Waiting for exhaustion wick..."
                    )
                    return (True, zone)

        return (False, None)

    # ─────────────────────────────────────────────────────────────────
    #  EXHAUSTION WICK DETECTION — THE REVERSAL SIGNAL
    # ─────────────────────────────────────────────────────────────────

    def detect_exhaustion_reversal(
        self, candles: List[CandleData]
    ) -> Tuple[bool, Optional[TradeDirection], Optional[float]]:
        """
        Detect the exhaustion wick that signals the God Candle reversal.
        
        After the spike pierces the liquidity pool, the candle prints a
        massive WICK in the spike direction. This wick represents the
        algorithm's absorption of all retail flow — the point where
        Smart Money has FINISHED filling and begins to reverse.
        
        The exhaustion wick must:
          1. Be in the direction of the spike
          2. Have a wick ratio >= configured threshold
          3. The candle must close AGAINST the spike direction
        
        Once detected, we fire in the OPPOSITE direction of the spike.
        The retail "trauma" (panic, stopped-out positions) is our fuel.
        
        Returns:
            (reversal_signal, trade_direction, entry_price)
        """
        if not self._god_candle_detected or not self._spike_direction:
            return (False, None, None)

        # Must be past cooldown period — don't jump in during the chaos
        if self.is_in_cooldown:
            seconds_remaining = (
                self._cooldown_until - datetime.utcnow()
            ).total_seconds()
            logger.debug(
                f"Trauma cooldown active — {seconds_remaining:.0f}s remaining. "
                "Sitting on hands."
            )
            return (False, None, None)

        if len(candles) < 2:
            return (False, None, None)

        # Look at the most recent candle for exhaustion wick
        current = candles[-1]
        previous = candles[-2]

        if self._spike_direction == "UP":
            # Spike was UP — look for upper wick exhaustion
            # then reversal DOWNWARD = our trade is SELL
            wick_ratio = current.upper_wick_ratio

            if wick_ratio >= self.config.wick_reversal_min_ratio:
                # Exhaustion wick detected — price rejected at the top
                # Confirm: current candle closes BELOW previous candle's close
                if not current.is_bullish and current.close < previous.close:
                    entry = current.close
                    logger.info(
                        f"══╡ TRAUMA REVERSAL — SELL SIGNAL! ╞══\n"
                        f"    God Candle spiked UP to {self._spike_extreme:.5f}\n"
                        f"    Exhaustion wick ratio: {wick_ratio:.2f}\n"
                        f"    Entry: {entry:.5f} (SELL — opposing the spike)\n"
                        f"    ┌─────────────────────────────────────────┐\n"
                        f"    │ Retail was traumatized LONG.            │\n"
                        f"    │ We execute SHORT on the exhaustion.     │\n"
                        f"    │ Their pain is our profit.               │\n"
                        f"    └─────────────────────────────────────────┘"
                    )
                    return (True, TradeDirection.SELL, entry)

        elif self._spike_direction == "DOWN":
            # Spike was DOWN — look for lower wick exhaustion
            # then reversal UPWARD = our trade is BUY
            wick_ratio = current.lower_wick_ratio

            if wick_ratio >= self.config.wick_reversal_min_ratio:
                # Exhaustion wick detected — price rejected at the bottom
                if current.is_bullish and current.close > previous.close:
                    entry = current.close
                    logger.info(
                        f"══╡ TRAUMA REVERSAL — BUY SIGNAL! ╞══\n"
                        f"    God Candle spiked DOWN to {self._spike_extreme:.5f}\n"
                        f"    Exhaustion wick ratio: {wick_ratio:.2f}\n"
                        f"    Entry: {entry:.5f} (BUY — opposing the spike)\n"
                        f"    ┌─────────────────────────────────────────┐\n"
                        f"    │ Retail was traumatized SHORT.           │\n"
                        f"    │ We execute LONG on the exhaustion.      │\n"
                        f"    │ Their pain is our profit.               │\n"
                        f"    └─────────────────────────────────────────┘"
                    )
                    return (True, TradeDirection.BUY, entry)

        return (False, None, None)

    # ─────────────────────────────────────────────────────────────────
    #  FULL TRAUMA SCAN — COMPLETE PIPELINE
    # ─────────────────────────────────────────────────────────────────

    def scan(
        self,
        candles: List[CandleData],
        symbol: str,
        liquidity_zones: List[LiquidityZone],
        catalyst_active: bool = False
    ) -> Tuple[bool, Optional[TradeDirection], Optional[float]]:
        """
        Run the complete Trauma Filter pipeline.
        
        1. If catalyst is imminent/active, arm the filter
        2. Detect God Candle
        3. Check if spike pierced liquidity
        4. Detect exhaustion reversal
        
        Returns:
            (signal_generated, direction, entry_price)
        """
        if catalyst_active and not self._active:
            self.arm()

        if not self._active:
            return (False, None, None)

        # Phase 1: Detect the God Candle
        if not self._god_candle_detected:
            self.detect_god_candle(candles, symbol)
            if not self._god_candle_detected:
                return (False, None, None)

        # Phase 2: Check if liquidity pool was pierced
        if candles:
            self.check_liquidity_pierce(candles[-1], liquidity_zones)

        # Phase 3: Detect exhaustion reversal
        confirmed, direction, entry = self.detect_exhaustion_reversal(candles)
        if confirmed:
            self.disarm()  # Mission accomplished — disarm
            return (True, direction, entry)

        return (False, None, None)

    # ─────────────────────────────────────────────────────────────────
    #  ATR CALCULATION
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _calculate_atr(candles: List[CandleData], period: int = 14) -> float:
        """
        Calculate Average True Range (ATR).
        Used to measure "normal" volatility — God Candles exceed this
        by the configured multiplier.
        """
        if len(candles) < period + 1:
            return sum(c.range_size for c in candles) / len(candles)

        true_ranges = []
        for i in range(1, len(candles)):
            current = candles[i]
            prev = candles[i - 1]

            tr = max(
                current.high - current.low,
                abs(current.high - prev.close),
                abs(current.low - prev.close)
            )
            true_ranges.append(tr)

        # Use last `period` TRs for the ATR
        return sum(true_ranges[-period:]) / period

    @property
    def spike_extreme(self) -> Optional[float]:
        """The extreme price of the God Candle spike (for SL placement)."""
        return self._spike_extreme

    @property
    def spike_direction(self) -> Optional[str]:
        return self._spike_direction
