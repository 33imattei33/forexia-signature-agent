"""
╔══════════════════════════════════════════════════════════════════════╗
║         FOREXIA — MARKET STRUCTURE ANALYZER                          ║
║   Pure computation: no AI calls, runs on every candle set            ║
║   Detects trend, order blocks, liquidity zones, psych levels         ║
╚══════════════════════════════════════════════════════════════════════╝

This module provides data-driven market structure analysis that feeds
into the AI prompt, giving Gemini concrete structural data instead of
asking it to derive structure from raw OHLC. This dramatically improves
AI decision quality.

Forexia methodology: NO Fair Value Gaps. Only liquidity zones, order blocks,
psychological levels, swing structure, and session ranges.
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger("forexia.market_structure")


@dataclass
class MarketStructure:
    """Complete market structure analysis for one symbol."""
    symbol: str = ""
    trend: str = "neutral"              # bullish, bearish, neutral
    trend_strength: float = 0.0         # 0-1
    swing_highs: List[float] = field(default_factory=list)
    swing_lows: List[float] = field(default_factory=list)
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    order_blocks: List[Dict] = field(default_factory=list)
    psychological_levels: List[float] = field(default_factory=list)
    current_structure: str = ""          # "higher_highs", "lower_lows", "range"
    atr_pips: float = 0.0
    volatility_state: str = "normal"     # low, normal, high, extreme
    liquidity_above: List[float] = field(default_factory=list)  # buy-side liquidity pools
    liquidity_below: List[float] = field(default_factory=list)  # sell-side liquidity pools
    session_range: Dict = field(default_factory=dict)  # asian/london/ny ranges
    bias_score: float = 0.0             # -1 (bearish) to +1 (bullish)

    def to_prompt_context(self) -> str:
        """Convert to a concise string for AI prompt injection."""
        lines = []
        lines.append(f"TREND: {self.trend} (strength: {self.trend_strength:.0%})")
        lines.append(f"STRUCTURE: {self.current_structure}")
        lines.append(f"VOLATILITY: {self.volatility_state} (ATR: {self.atr_pips:.1f} pips)")
        lines.append(f"BIAS SCORE: {self.bias_score:+.2f} (-1=bear, +1=bull)")

        if self.support_levels:
            lines.append(f"SUPPORT: {', '.join(f'{s:.5f}' for s in self.support_levels[:3])}")
        if self.resistance_levels:
            lines.append(f"RESISTANCE: {', '.join(f'{r:.5f}' for r in self.resistance_levels[:3])}")
        if self.order_blocks:
            obs = [f"{ob['type']} @ {ob['price']:.5f}" for ob in self.order_blocks[:3]]
            lines.append(f"ORDER BLOCKS: {', '.join(obs)}")
        if self.psychological_levels:
            lines.append(f"PSYCH LEVELS: {', '.join(f'{p:.5f}' for p in self.psychological_levels[:5])}")
        if self.liquidity_above:
            lines.append(f"BUY-SIDE LIQ: {', '.join(f'{l:.5f}' for l in self.liquidity_above[:3])}")
        if self.liquidity_below:
            lines.append(f"SELL-SIDE LIQ: {', '.join(f'{l:.5f}' for l in self.liquidity_below[:3])}")
        if self.session_range:
            sr = self.session_range
            if 'asian_high' in sr:
                lines.append(f"ASIAN RANGE: {sr['asian_low']:.5f} - {sr['asian_high']:.5f}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "trend": self.trend,
            "trend_strength": round(self.trend_strength, 2),
            "current_structure": self.current_structure,
            "atr_pips": round(self.atr_pips, 1),
            "volatility_state": self.volatility_state,
            "bias_score": round(self.bias_score, 2),
            "support_levels": [round(s, 5) for s in self.support_levels[:5]],
            "resistance_levels": [round(r, 5) for r in self.resistance_levels[:5]],
            "order_blocks": self.order_blocks[:5],
            "psychological_levels": [round(p, 5) for p in self.psychological_levels[:5]],
            "liquidity_above": [round(l, 5) for l in self.liquidity_above[:5]],
            "liquidity_below": [round(l, 5) for l in self.liquidity_below[:5]],
            "session_range": {k: round(v, 5) for k, v in self.session_range.items()},
        }


class MarketStructureAnalyzer:
    """
    Pure-computation market structure analyzer.
    No AI calls — runs instantly on candle data.
    Provides structured data that feeds into AI prompts.
    """

    def __init__(self):
        self._cache: Dict[str, MarketStructure] = {}

    def analyze(self, symbol: str, candles: List[Any], pip_value: float = 0.0001) -> MarketStructure:
        """
        Run full market structure analysis on candle data.
        Expects candles with .open, .high, .low, .close attributes.
        """
        if not candles or len(candles) < 20:
            return MarketStructure(symbol=symbol)

        ms = MarketStructure(symbol=symbol)

        # Extract OHLC arrays
        opens = [getattr(c, "open", 0) for c in candles]
        highs = [getattr(c, "high", 0) for c in candles]
        lows = [getattr(c, "low", 0) for c in candles]
        closes = [getattr(c, "close", 0) for c in candles]

        # Auto-detect pip value
        if "JPY" in symbol.upper() or "XAU" in symbol.upper() or "GOLD" in symbol.upper():
            pip_value = 0.01

        # 1. ATR & Volatility
        ms.atr_pips = self._calculate_atr(highs, lows, closes, pip_value)
        ms.volatility_state = self._classify_volatility(ms.atr_pips, symbol)

        # 2. Swing Points
        ms.swing_highs = self._find_swing_highs(highs, lows, closes)
        ms.swing_lows = self._find_swing_lows(highs, lows, closes)

        # 3. Trend & Structure
        ms.trend, ms.trend_strength, ms.current_structure = self._analyze_trend(
            ms.swing_highs, ms.swing_lows, closes
        )

        # 4. Support & Resistance
        ms.support_levels = self._find_support(lows, closes, ms.swing_lows)
        ms.resistance_levels = self._find_resistance(highs, closes, ms.swing_highs)

        # 5. Order Blocks
        ms.order_blocks = self._find_order_blocks(opens, highs, lows, closes)

        # 6. Psychological Levels (round numbers near current price)
        ms.psychological_levels = self._find_psychological_levels(closes, pip_value)

        # 7. Liquidity Pools
        ms.liquidity_above = self._find_liquidity_pools(highs, ms.swing_highs, "above")
        ms.liquidity_below = self._find_liquidity_pools(lows, ms.swing_lows, "below")

        # 8. Composite Bias Score
        ms.bias_score = self._calculate_bias_score(ms, closes)

        # Cache
        self._cache[symbol] = ms
        return ms

    def get_cached(self, symbol: str) -> Optional[MarketStructure]:
        return self._cache.get(symbol)

    def get_all_cached(self) -> Dict[str, Dict]:
        return {sym: ms.to_dict() for sym, ms in self._cache.items()}

    # ─────────────────────────────────────────────────────────────────
    #  INTERNAL CALCULATIONS
    # ─────────────────────────────────────────────────────────────────

    def _calculate_atr(self, highs: List[float], lows: List[float],
                       closes: List[float], pip_value: float, period: int = 14) -> float:
        """Average True Range in pips."""
        if len(highs) < period + 1:
            return 0.0
        trs = []
        for i in range(1, len(highs)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )
            trs.append(tr)
        if not trs:
            return 0.0
        atr = sum(trs[-period:]) / min(period, len(trs))
        return atr / pip_value if pip_value > 0 else 0

    def _classify_volatility(self, atr_pips: float, symbol: str) -> str:
        """Classify volatility state based on ATR."""
        # Different thresholds per asset class
        s = symbol.upper()
        if "XAU" in s or "GOLD" in s:
            if atr_pips < 30: return "low"
            if atr_pips < 80: return "normal"
            if atr_pips < 150: return "high"
            return "extreme"
        elif "JPY" in s:
            if atr_pips < 5: return "low"
            if atr_pips < 15: return "normal"
            if atr_pips < 30: return "high"
            return "extreme"
        else:
            if atr_pips < 3: return "low"
            if atr_pips < 10: return "normal"
            if atr_pips < 20: return "high"
            return "extreme"

    def _find_swing_highs(self, highs: List[float], lows: List[float],
                          closes: List[float], lookback: int = 3) -> List[float]:
        """Find swing high points (local maxima)."""
        swings = []
        for i in range(lookback, len(highs) - lookback):
            is_swing = True
            for j in range(1, lookback + 1):
                if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                    is_swing = False
                    break
            if is_swing:
                swings.append(highs[i])
        return swings[-10:]  # Last 10

    def _find_swing_lows(self, highs: List[float], lows: List[float],
                         closes: List[float], lookback: int = 3) -> List[float]:
        """Find swing low points (local minima)."""
        swings = []
        for i in range(lookback, len(lows) - lookback):
            is_swing = True
            for j in range(1, lookback + 1):
                if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                    is_swing = False
                    break
            if is_swing:
                swings.append(lows[i])
        return swings[-10:]

    def _analyze_trend(self, swing_highs: List[float], swing_lows: List[float],
                       closes: List[float]) -> Tuple[str, float, str]:
        """Determine trend direction, strength, and structure type."""
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return "neutral", 0.0, "insufficient_data"

        # Check last 4 swing points
        recent_highs = swing_highs[-4:]
        recent_lows = swing_lows[-4:]

        hh_count = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i] > recent_highs[i - 1])
        ll_count = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i] < recent_lows[i - 1])
        hl_count = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i] > recent_lows[i - 1])
        lh_count = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i] < recent_highs[i - 1])

        # EMA trend confirmation
        ema_fast = self._ema(closes, 8)
        ema_slow = self._ema(closes, 21)
        ema_bullish = ema_fast > ema_slow if ema_fast and ema_slow else False

        # Determine structure
        if hh_count >= 2 and hl_count >= 1:
            structure = "higher_highs_higher_lows"
            trend = "bullish"
            strength = min(1.0, (hh_count + hl_count) / 6)
            if ema_bullish: strength = min(1.0, strength + 0.2)
        elif ll_count >= 2 and lh_count >= 1:
            structure = "lower_highs_lower_lows"
            trend = "bearish"
            strength = min(1.0, (ll_count + lh_count) / 6)
            if not ema_bullish: strength = min(1.0, strength + 0.2)
        else:
            structure = "ranging"
            trend = "neutral"
            strength = 0.3

        return trend, round(strength, 2), structure

    def _ema(self, data: List[float], period: int) -> Optional[float]:
        """Calculate EMA of the last value."""
        if len(data) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for val in data[period:]:
            ema = (val - ema) * multiplier + ema
        return ema

    def _find_support(self, lows: List[float], closes: List[float],
                      swing_lows: List[float]) -> List[float]:
        """Find support levels from swing lows and price clusters."""
        current = closes[-1] if closes else 0
        levels = []

        # Swing lows below current price
        for sl in swing_lows:
            if sl < current:
                levels.append(sl)

        # Price cluster detection (levels tested multiple times)
        if len(lows) >= 20:
            price_range = max(lows[-50:]) - min(lows[-50:])
            if price_range > 0:
                bucket_size = price_range / 20
                buckets: Dict[int, List[float]] = {}
                for low in lows[-50:]:
                    b = int((low - min(lows[-50:])) / bucket_size) if bucket_size > 0 else 0
                    if b not in buckets:
                        buckets[b] = []
                    buckets[b].append(low)

                # Levels tested 3+ times
                for b, prices in sorted(buckets.items()):
                    if len(prices) >= 3:
                        avg = sum(prices) / len(prices)
                        if avg < current:
                            levels.append(avg)

        # De-duplicate (merge levels within 0.1% of each other)
        levels = self._merge_levels(levels, current)
        return sorted(levels, reverse=True)[:5]  # Closest first

    def _find_resistance(self, highs: List[float], closes: List[float],
                         swing_highs: List[float]) -> List[float]:
        """Find resistance levels from swing highs and price clusters."""
        current = closes[-1] if closes else 0
        levels = []

        for sh in swing_highs:
            if sh > current:
                levels.append(sh)

        if len(highs) >= 20:
            price_range = max(highs[-50:]) - min(highs[-50:])
            if price_range > 0:
                bucket_size = price_range / 20
                buckets: Dict[int, List[float]] = {}
                for high in highs[-50:]:
                    b = int((high - min(highs[-50:])) / bucket_size) if bucket_size > 0 else 0
                    if b not in buckets:
                        buckets[b] = []
                    buckets[b].append(high)

                for b, prices in sorted(buckets.items()):
                    if len(prices) >= 3:
                        avg = sum(prices) / len(prices)
                        if avg > current:
                            levels.append(avg)

        levels = self._merge_levels(levels, current)
        return sorted(levels)[:5]

    def _merge_levels(self, levels: List[float], current: float, threshold: float = 0.001) -> List[float]:
        """Merge levels within threshold % of each other."""
        if not levels:
            return []
        levels = sorted(set(levels))
        merged = [levels[0]]
        for lv in levels[1:]:
            if abs(lv - merged[-1]) / max(abs(current), 1e-10) > threshold:
                merged.append(lv)
            else:
                merged[-1] = (merged[-1] + lv) / 2  # Average
        return merged

    def _find_order_blocks(self, opens: List[float], highs: List[float],
                           lows: List[float], closes: List[float]) -> List[Dict]:
        """
        Find bullish and bearish order blocks.
        OB = last opposite candle before a strong move.
        """
        obs = []
        if len(closes) < 5:
            return obs

        for i in range(2, len(closes) - 1):
            body_prev = abs(closes[i - 1] - opens[i - 1])
            body_curr = abs(closes[i] - opens[i])

            # Bullish OB: bearish candle followed by strong bullish candle
            if closes[i - 1] < opens[i - 1] and closes[i] > opens[i]:
                if body_curr > body_prev * 1.5:
                    obs.append({
                        "type": "bullish_ob",
                        "price": lows[i - 1],
                        "high": opens[i - 1],
                        "index": i - 1,
                    })

            # Bearish OB: bullish candle followed by strong bearish candle
            if closes[i - 1] > opens[i - 1] and closes[i] < opens[i]:
                if body_curr > body_prev * 1.5:
                    obs.append({
                        "type": "bearish_ob",
                        "price": highs[i - 1],
                        "high": highs[i - 1],
                        "index": i - 1,
                    })

        return obs[-5:]  # Most recent 5

    def _find_psychological_levels(self, closes: List[float], pip_value: float) -> List[float]:
        """
        Find psychological round-number levels near current price.
        These are where retail clusters orders — institutions target them.
        Major: .000, .500 | Minor: .200, .800
        """
        if not closes:
            return []

        current = closes[-1]
        levels = []

        if pip_value >= 0.005:
            # JPY pairs or Gold: round to nearest 0.50 and 1.00
            base = round(current)
            for offset in [-3, -2.5, -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5, 3]:
                lv = base + offset
                if abs(lv - current) <= 3.0:
                    levels.append(lv)
        else:
            # Standard pairs: round to nearest .00000 with .00200, .00500, .00800
            base = round(current, 2)  # nearest .01000
            for offset_100 in range(-5, 6):
                lv_base = base + offset_100 * 0.01
                for sub in [0.0, 0.002, 0.005, 0.008]:
                    lv = lv_base + sub
                    if abs(lv - current) <= 0.005:
                        levels.append(round(lv, 5))

        # Sort by proximity to current price
        levels = sorted(set(levels), key=lambda x: abs(x - current))
        return levels[:8]

    def _find_liquidity_pools(self, prices: List[float], swings: List[float],
                              direction: str) -> List[float]:
        """
        Find liquidity pool clusters (equal highs/lows where stops accumulate).
        """
        if len(swings) < 2:
            return []

        # Levels where 2+ swing points cluster
        pools = []
        for i in range(len(swings)):
            for j in range(i + 1, len(swings)):
                if swings[i] > 0 and abs(swings[i] - swings[j]) / max(swings[i], 1e-10) < 0.0005:
                    pools.append((swings[i] + swings[j]) / 2)

        return sorted(set(pools), reverse=(direction == "above"))[:5]

    def _calculate_bias_score(self, ms: MarketStructure, closes: List[float]) -> float:
        """
        Composite bias score from -1 (strong bear) to +1 (strong bull).
        Combines trend, structure, EMA alignment, and momentum.
        """
        score = 0.0

        # Trend component (40%)
        if ms.trend == "bullish":
            score += 0.4 * ms.trend_strength
        elif ms.trend == "bearish":
            score -= 0.4 * ms.trend_strength

        # EMA alignment (20%)
        if len(closes) >= 21:
            ema8 = self._ema(closes, 8)
            ema21 = self._ema(closes, 21)
            if ema8 and ema21:
                if ema8 > ema21:
                    score += 0.2
                else:
                    score -= 0.2

        # Recent momentum (20%)
        if len(closes) >= 10:
            recent = closes[-10:]
            momentum = (recent[-1] - recent[0]) / max(abs(recent[0]), 1e-10)
            score += max(-0.2, min(0.2, momentum * 100))

        # Price vs structure (20%)
        current = closes[-1] if closes else 0
        if ms.support_levels and ms.resistance_levels:
            nearest_sup = max(ms.support_levels) if ms.support_levels else 0
            nearest_res = min(ms.resistance_levels) if ms.resistance_levels else 0
            if nearest_res > nearest_sup > 0:
                position = (current - nearest_sup) / (nearest_res - nearest_sup)
                # Near support = bullish bias, near resistance = bearish bias
                score += 0.2 * (0.5 - position)

        return max(-1.0, min(1.0, round(score, 2)))
