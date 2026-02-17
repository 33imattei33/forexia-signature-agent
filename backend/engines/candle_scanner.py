"""
╔══════════════════════════════════════════════════════════════════════╗
║       FOREXIA SIGNATURE AGENT — CANDLESTICK ANATOMY SCANNER        ║
║   Railroad Tracks, Stars & Psychological Level Confirmation Engine   ║
╚══════════════════════════════════════════════════════════════════════╝

This scanner performs surgical analysis of individual candlestick anatomy
to confirm the EXACT entry tick after a stop hunt has been detected.

Patterns we scan for (NO retail indicator nonsense):

  RAILROAD TRACKS — Two large-range candles of opposite direction
  appearing back-to-back at a liquidity zone. The first candle IS the
  stop hunt. The second candle IS the reversal. Together they look like
  train tracks — two parallel bodies going opposite ways.

  STAR PATTERNS — Tiny-bodied candles (doji/spinning top) at the
  extreme of a stop hunt. The tiny body shows indecision = the algorithm
  has FINISHED its raid and is about to reverse.

  PSYCHOLOGICAL LEVEL CONFLUENCE — The above patterns gain extreme
  significance when they occur at round numbers (x.x000, x.x050, etc.).
  Retail clusters stops at these levels religiously, making them
  prime hunting grounds.
"""

import logging
from typing import List, Optional, Tuple

from backend.config import CONFIG
from backend.models.schemas import CandleData

logger = logging.getLogger("forexia.candle_scanner")


class CandlestickAnatomyScanner:
    """
    Surgical candlestick pattern analyzer for entry confirmation.
    
    This does NOT look for retail patterns (engulfing, hammer, etc.).
    We look for the SPECIFIC anatomy that confirms Smart Money has
    finished its operation and the reversal is beginning.
    """

    def __init__(self):
        self.config = CONFIG.candle_scanner

    # ─────────────────────────────────────────────────────────────────
    #  RAILROAD TRACKS — THE DEFINITIVE REVERSAL PRINT
    # ─────────────────────────────────────────────────────────────────

    def detect_railroad_tracks(
        self, candles: List[CandleData]
    ) -> Tuple[bool, Optional[str], float]:
        """
        Detect Railroad Tracks pattern.
        
        Railroad Tracks are two large-range candles of OPPOSITE direction,
        back to back, at a key level. They represent:
          - Candle 1: The stop hunt (big move in one direction)
          - Candle 2: The reversal (equally big move in the opposite)
        
        Together they form a massive rejection — like a train running
        over retail traders in both directions.
        
        Criteria:
          - Both candles have range >= min_range_pips
          - Body ratio <= railroad_body_ratio OR bodies are opposite
          - Candles are of opposite direction (bull then bear, or vice versa)
          - Combined wicks show rejection at the extreme
        
        Returns:
            (detected, reversal_direction, confidence)
        """
        if len(candles) < 2:
            return (False, None, 0.0)

        candle_1 = candles[-2]  # The hunt candle
        candle_2 = candles[-1]  # The reversal candle

        min_range = self.config.railroad_min_range_pips * 0.0001

        # Both candles must have significant range
        if candle_1.range_size < min_range or candle_2.range_size < min_range:
            return (False, None, 0.0)

        # Candles must be of OPPOSITE direction
        if candle_1.is_bullish == candle_2.is_bullish:
            return (False, None, 0.0)

        # The reversal candle's close should negate the hunt candle's body
        # (i.e., candle 2 closes back near candle 1's open)
        body_overlap = abs(candle_2.close - candle_1.open) / candle_1.range_size
        
        # Calculate confidence based on:
        # - How large the range is (bigger = more significant)
        # - How complete the reversal is (overlap with original body)
        # - Whether it occurs at a psychological level
        range_score = min(1.0, candle_2.range_size / (min_range * 2))
        overlap_score = max(0, 1 - body_overlap)
        
        confidence = (range_score * 0.5 + overlap_score * 0.5)

        if confidence >= 0.4:
            if candle_2.is_bullish:
                direction = "BUY"
                logger.info(
                    f"══╡ RAILROAD TRACKS — Bullish Reversal ╞══\n"
                    f"    Hunt candle (bearish): O={candle_1.open:.5f} "
                    f"C={candle_1.close:.5f} Range={candle_1.range_size * 10000:.1f}p\n"
                    f"    Reversal candle (bullish): O={candle_2.open:.5f} "
                    f"C={candle_2.close:.5f} Range={candle_2.range_size * 10000:.1f}p\n"
                    f"    Confidence: {confidence:.2f}\n"
                    f"    Smart Money has reversed direction. Retail shorts are dead."
                )
            else:
                direction = "SELL"
                logger.info(
                    f"══╡ RAILROAD TRACKS — Bearish Reversal ╞══\n"
                    f"    Hunt candle (bullish): O={candle_1.open:.5f} "
                    f"C={candle_1.close:.5f} Range={candle_1.range_size * 10000:.1f}p\n"
                    f"    Reversal candle (bearish): O={candle_2.open:.5f} "
                    f"C={candle_2.close:.5f} Range={candle_2.range_size * 10000:.1f}p\n"
                    f"    Confidence: {confidence:.2f}\n"
                    f"    Smart Money has reversed direction. Retail longs are dead."
                )
            return (True, direction, confidence)

        return (False, None, 0.0)

    # ─────────────────────────────────────────────────────────────────
    #  STAR PATTERN — ALGORITHMIC EXHAUSTION PRINT
    # ─────────────────────────────────────────────────────────────────

    def detect_star_pattern(
        self, candles: List[CandleData]
    ) -> Tuple[bool, Optional[str], float]:
        """
        Detect Star patterns at stop hunt extremes.
        
        A Star is a tiny-bodied candle (nearly a doji) at the tip of a
        stop hunt move. The tiny body means the algorithm has FINISHED
        its operation — buying and selling are now in equilibrium at
        the extreme. The next move will be the reversal.
        
        Criteria:
          - Body ratio <= star_body_max_ratio (very small body)
          - Appears after a strong directional move (the hunt)
          - Long wicks show rejection at the extreme
        
        Returns:
            (detected, reversal_direction, confidence)
        """
        if len(candles) < 3:
            return (False, None, 0.0)

        pre_move = candles[-3]   # Start of the move
        move = candles[-2]       # The strong hunt move
        star = candles[-1]       # The potential star

        # Star must have tiny body relative to range
        if star.range_size <= 0:
            return (False, None, 0.0)
        
        if star.body_ratio > self.config.star_body_max_ratio:
            return (False, None, 0.0)

        # The preceding candle must be a strong move (the hunt)
        move_threshold = self.config.railroad_min_range_pips * 0.0001 * 0.5
        if move.range_size < move_threshold:
            return (False, None, 0.0)

        # Star must gap or appear at the extreme of the move
        if move.is_bullish:
            # Bullish hunt → star at the top → reversal is SELL
            if star.open >= move.close * 0.9999:  # Star opens near move's close
                wick_rejection = star.upper_wick_ratio
                if wick_rejection >= 0.3:
                    confidence = min(1.0, (1 - star.body_ratio) * wick_rejection)
                    logger.info(
                        f"══╡ EVENING STAR — Bearish Reversal ╞══\n"
                        f"    Hunt move: {move.range_size * 10000:.1f} pips bullish\n"
                        f"    Star body ratio: {star.body_ratio:.3f} "
                        f"(exhaustion — algorithm is done)\n"
                        f"    Upper wick rejection: {wick_rejection:.2f}\n"
                        f"    Smart Money finished buying. Price going DOWN."
                    )
                    return (True, "SELL", confidence)
        else:
            # Bearish hunt → star at the bottom → reversal is BUY
            if star.open <= move.close * 1.0001:
                wick_rejection = star.lower_wick_ratio
                if wick_rejection >= 0.3:
                    confidence = min(1.0, (1 - star.body_ratio) * wick_rejection)
                    logger.info(
                        f"══╡ MORNING STAR — Bullish Reversal ╞══\n"
                        f"    Hunt move: {move.range_size * 10000:.1f} pips bearish\n"
                        f"    Star body ratio: {star.body_ratio:.3f} "
                        f"(exhaustion — algorithm is done)\n"
                        f"    Lower wick rejection: {wick_rejection:.2f}\n"
                        f"    Smart Money finished selling. Price going UP."
                    )
                    return (True, "BUY", confidence)

        return (False, None, 0.0)

    # ─────────────────────────────────────────────────────────────────
    #  PSYCHOLOGICAL LEVEL PROXIMITY — ROUND NUMBER MAGNETS
    # ─────────────────────────────────────────────────────────────────

    def is_at_psychological_level(self, price: float) -> Tuple[bool, Optional[float]]:
        """
        Check if price is near a psychological round number.
        
        Retail traders are OBSESSED with round numbers.
        They place stops and limit orders at .0000, .0050, .0020, etc.
        This makes these levels prime liquidity pools for harvesting.
        
        When our candle patterns (Railroad Tracks, Stars) occur AT
        a psychological level, the signal strength is amplified.
        
        Returns:
            (at_psych_level, nearest_level)
        """
        # Extract the last 4 decimal digits (for 5-digit brokers)
        # e.g., 1.08532 → pips portion = 8532
        fractional = price % 1
        pips_portion = int(round(fractional * 10000)) % 100  # Last 2 pips digits

        tolerance = self.config.psych_level_tolerance_pips

        for level in self.config.psych_levels:
            distance = min(abs(pips_portion - level), abs(pips_portion - level + 100),
                          abs(pips_portion - level - 100))
            if distance <= tolerance:
                # Calculate the actual round number
                base = int(price * 100) / 100
                nearest = base + level / 10000
                logger.info(
                    f"══╡ PSYCHOLOGICAL LEVEL — Price {price:.5f} near "
                    f"round number {nearest:.4f} ╞══\n"
                    f"    Distance: {distance} pips. Retail stops cluster here.\n"
                    f"    Signal strength AMPLIFIED at this level."
                )
                return (True, nearest)

        return (False, None)

    # ─────────────────────────────────────────────────────────────────
    #  FULL ANATOMY SCAN — COMBINED ANALYSIS
    # ─────────────────────────────────────────────────────────────────

    def full_scan(
        self, candles: List[CandleData]
    ) -> dict:
        """
        Run all candle anatomy scans and return a consolidated result.
        
        Returns a dict with:
          - railroad_tracks: (detected, direction, confidence)
          - star_pattern: (detected, direction, confidence)
          - psych_level: (at_level, nearest_level)
          - combined_confidence: weighted score considering all factors
          - recommended_direction: the direction with highest confluence
        """
        if len(candles) < 3:
            return {
                "railroad_tracks": (False, None, 0.0),
                "star_pattern": (False, None, 0.0),
                "psych_level": (False, None),
                "combined_confidence": 0.0,
                "recommended_direction": None,
            }

        rr_detected, rr_dir, rr_conf = self.detect_railroad_tracks(candles)
        star_detected, star_dir, star_conf = self.detect_star_pattern(candles)
        
        current_price = candles[-1].close
        at_psych, psych_level = self.is_at_psychological_level(current_price)

        # Combine confidence — psych level acts as a multiplier
        combined = 0.0
        direction = None

        if rr_detected:
            combined = rr_conf
            direction = rr_dir
        if star_detected:
            if star_conf > combined:
                combined = star_conf
                direction = star_dir

        # Psychological level boost: +20% confidence
        if at_psych and combined > 0:
            combined = min(1.0, combined * 1.2)
            logger.info(
                f"Psychological level confluence — "
                f"confidence boosted to {combined:.2f}"
            )

        return {
            "railroad_tracks": (rr_detected, rr_dir, rr_conf),
            "star_pattern": (star_detected, star_dir, star_conf),
            "psych_level": (at_psych, psych_level),
            "combined_confidence": round(combined, 3),
            "recommended_direction": direction,
        }
