"""
╔══════════════════════════════════════════════════════════════════════╗
║      FOREXIA SIGNATURE AGENT — MULTI-PAIR SYNCHRONIZATION           ║
║     Dollar Basket Confirmation for Institutional Manipulation        ║
╚══════════════════════════════════════════════════════════════════════╝

Smart Money doesn't manipulate ONE pair — they manipulate the
ENTIRE DOLLAR BASKET simultaneously.

If the Signature Trade forms on EURUSD, the algorithm is likely also
moving GBPUSD and USDCHF in correlated fashion. We verify this
before firing to ensure we're aligned with the institutional flow.

Correlation logic:
  - EURUSD and GBPUSD should move TOGETHER (positive correlation)
  - EURUSD and USDCHF should move OPPOSITE (negative correlation)
  - If all correlated pairs confirm, confidence is maximum
  - If correlation breaks, something is wrong — DO NOT TRADE
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from backend.config import CONFIG
from backend.models.schemas import CandleData, LiquidityZone

logger = logging.getLogger("forexia.multi_pair")


class MultiPairSynchronizer:
    """
    Cross-pair correlation validator for institutional flow confirmation.
    
    Before firing any Signature Trade, this module checks that the
    Smart Money algorithm is manipulating the ENTIRE dollar basket,
    not just one pair. This prevents false signals from pair-specific
    noise (e.g., a EUR-only event that doesn't affect the dollar basket).
    """

    def __init__(self):
        self.config = CONFIG.multi_pair
        self._pair_states: Dict[str, dict] = {}  # symbol -> analysis state
        self._candle_cache: Dict[str, List[CandleData]] = {}

    # ─────────────────────────────────────────────────────────────────
    #  CANDLE DATA INGESTION
    # ─────────────────────────────────────────────────────────────────

    def update_pair_data(self, symbol: str, candles: List[CandleData]):
        """
        Update the candle cache for a specific pair.
        Called when new data arrives from MT4 for any watched pair.
        """
        self._candle_cache[symbol] = candles

    # ─────────────────────────────────────────────────────────────────
    #  INSTITUTIONAL FLOW DETECTION PER PAIR
    # ─────────────────────────────────────────────────────────────────

    def analyze_pair_flow(
        self, symbol: str, candles: List[CandleData]
    ) -> dict:
        """
        Analyze the institutional flow direction for a single pair.
        
        Returns a dict with:
          - direction: "BULLISH" or "BEARISH" or "NEUTRAL"
          - stop_hunt_detected: bool
          - wick_exhaustion: bool
          - confidence: 0.0-1.0
        """
        if len(candles) < 10:
            return {
                "direction": "NEUTRAL",
                "stop_hunt_detected": False,
                "wick_exhaustion": False,
                "confidence": 0.0,
            }

        recent = candles[-5:]  # Last 5 candles
        
        # Determine flow direction from recent candles
        closes = [c.close for c in recent]
        net_change = closes[-1] - closes[0]
        avg_range = sum(c.range_size for c in recent) / len(recent)

        if avg_range <= 0:
            direction = "NEUTRAL"
            confidence = 0.0
        elif abs(net_change) / avg_range > 0.5:
            direction = "BULLISH" if net_change > 0 else "BEARISH"
            confidence = min(1.0, abs(net_change) / (avg_range * 2))
        else:
            direction = "NEUTRAL"
            confidence = 0.2

        # Check for stop hunt pattern (wick > 60% of range)
        latest = candles[-1]
        stop_hunt = (
            latest.upper_wick_ratio > 0.6 or latest.lower_wick_ratio > 0.6
        )

        # Check for wick exhaustion on latest candle
        wick_exhaustion = False
        if direction == "BULLISH" and latest.upper_wick_ratio > 0.5:
            wick_exhaustion = True
        elif direction == "BEARISH" and latest.lower_wick_ratio > 0.5:
            wick_exhaustion = True

        state = {
            "direction": direction,
            "stop_hunt_detected": stop_hunt,
            "wick_exhaustion": wick_exhaustion,
            "confidence": round(confidence, 3),
        }

        self._pair_states[symbol] = state
        return state

    # ─────────────────────────────────────────────────────────────────
    #  DOLLAR BASKET CORRELATION CHECK
    # ─────────────────────────────────────────────────────────────────

    def check_basket_correlation(
        self,
        trigger_symbol: str,
        trigger_direction: str  # "BUY" or "SELL"
    ) -> Tuple[bool, float, dict]:
        """
        Verify that the dollar basket confirms the Signature Trade.
        
        When we detect a trade on the trigger_symbol, we check that
        the correlated pairs are moving in the EXPECTED direction.
        
        Correlation rules:
          - Positive correlation pairs (e.g., EURUSD ↔ GBPUSD):
            Should both show the SAME direction
          - Negative correlation pairs (e.g., EURUSD ↔ USDCHF):
            Should show OPPOSITE directions
        
        If the basket doesn't confirm, the manipulation may be
        pair-specific noise, not an institutional dollar move.
        
        Returns:
            (confirmed, aggregate_confidence, pair_details)
        """
        corr_pairs = self.config.correlation_pairs.get(trigger_symbol, [])
        if not corr_pairs:
            # No correlation data for this pair — allow trade
            logger.warning(
                f"No correlation pairs configured for {trigger_symbol} — "
                "skipping basket check"
            )
            return (True, 0.5, {})

        # Determine expected directions for correlated pairs
        # For USD pairs: EURUSD BUY = GBPUSD BUY = USDCHF SELL
        expected_directions = {}
        for pair in corr_pairs:
            if self._is_positive_correlation(trigger_symbol, pair):
                expected_directions[pair] = trigger_direction
            else:
                # Negative correlation — expect opposite
                expected_directions[pair] = (
                    "BUY" if trigger_direction == "SELL" else "SELL"
                )

        confirming = 0
        total = len(corr_pairs)
        details = {}

        for pair, expected_dir in expected_directions.items():
            state = self._pair_states.get(pair, {})
            actual_dir = state.get("direction", "NEUTRAL")

            # Convert BUY/SELL expectation to BULLISH/BEARISH state
            expected_flow = "BULLISH" if expected_dir == "BUY" else "BEARISH"

            if actual_dir == expected_flow:
                confirming += 1
                details[pair] = {
                    "status": "CONFIRMED",
                    "expected": expected_flow,
                    "actual": actual_dir,
                    "confidence": state.get("confidence", 0),
                }
            elif actual_dir == "NEUTRAL":
                details[pair] = {
                    "status": "NEUTRAL",
                    "expected": expected_flow,
                    "actual": actual_dir,
                    "confidence": state.get("confidence", 0),
                }
            else:
                details[pair] = {
                    "status": "DIVERGENT",
                    "expected": expected_flow,
                    "actual": actual_dir,
                    "confidence": state.get("confidence", 0),
                }

        confirmed = confirming >= self.config.min_confirming_pairs
        aggregate_confidence = confirming / total if total > 0 else 0

        status_str = "CONFIRMED" if confirmed else "NOT CONFIRMED"
        logger.info(
            f"══╡ DOLLAR BASKET CHECK — {status_str} ╞══\n"
            f"    Trigger: {trigger_symbol} {trigger_direction}\n"
            f"    Confirming pairs: {confirming}/{total}\n"
            f"    Aggregate confidence: {aggregate_confidence:.2f}"
        )
        for pair, detail in details.items():
            logger.info(
                f"    ▸ {pair}: {detail['status']} "
                f"(expected {detail['expected']}, got {detail['actual']})"
            )

        if not confirmed:
            logger.warning(
                "══╡ BASKET DIVERGENCE — Smart Money may NOT be manipulating "
                "the full dollar basket. Trade with caution or SKIP. ╞══"
            )

        return (confirmed, aggregate_confidence, details)

    # ─────────────────────────────────────────────────────────────────
    #  CROSS-PAIR STOP HUNT SYNCHRONIZATION
    # ─────────────────────────────────────────────────────────────────

    def detect_synchronized_stop_hunt(self) -> Dict[str, bool]:
        """
        Check if multiple pairs are experiencing stop hunts simultaneously.
        
        When the algorithm raids liquidity, it does so across the ENTIRE
        basket. If EURUSD, GBPUSD, and USDCHF are ALL showing stop hunt
        patterns at the same time, it's a high-confidence institutional event.
        """
        hunt_status = {}
        for symbol, state in self._pair_states.items():
            hunt_status[symbol] = state.get("stop_hunt_detected", False)

        active_hunts = sum(1 for v in hunt_status.values() if v)
        total_pairs = len(hunt_status)

        if active_hunts >= 2:
            logger.info(
                f"══╡ SYNCHRONIZED STOP HUNT — {active_hunts}/{total_pairs} "
                f"pairs being raided simultaneously ╞══\n"
                f"    Smart Money is manipulating the entire basket.\n"
                f"    This is a HIGH-CONFIDENCE institutional event."
            )

        return hunt_status

    # ─────────────────────────────────────────────────────────────────
    #  CORRELATION HELPERS
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _is_positive_correlation(pair_a: str, pair_b: str) -> bool:
        """
        Determine if two pairs have positive or negative correlation.
        
        Positive: Both pairs move in the same direction
          - EURUSD & GBPUSD (both EUR-like vs USD)
        
        Negative: Pairs move in opposite directions
          - EURUSD & USDCHF (USD is base in one, quote in other)
        """
        # Pairs where USD is in the SAME position = positive correlation
        # Pairs where USD switches position = negative correlation
        
        usd_positions = {
            "EURUSD": "QUOTE",
            "GBPUSD": "QUOTE",
            "AUDUSD": "QUOTE",
            "NZDUSD": "QUOTE",
            "USDCHF": "BASE",
            "USDJPY": "BASE",
            "USDCAD": "BASE",
        }

        pos_a = usd_positions.get(pair_a, "QUOTE")
        pos_b = usd_positions.get(pair_b, "QUOTE")

        return pos_a == pos_b  # Same position = positive correlation

    def get_status(self) -> dict:
        """Return current multi-pair synchronization status."""
        return {
            "pair_states": self._pair_states,
            "cached_pairs": list(self._candle_cache.keys()),
        }
