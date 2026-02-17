"""
╔══════════════════════════════════════════════════════════════════════╗
║    FOREXIA — MARKET ADAPTER                                         ║
║    Unified interface for FX pairs and indices (NASDAQ)               ║
╚══════════════════════════════════════════════════════════════════════╝

Detects whether a symbol is FX or an Index, and applies different:
  - Trade windows (when to scan/enter)
  - SL buffer sizing (ATR-based for NQ vs fixed pips for FX)
  - Order types (limit orders for NASDAQ, market for FX)
  - Lot sizing logic (lots vs contracts)
  - Pip/point value calculations
"""

import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum

logger = logging.getLogger("forexia.market_adapter")


# ─────────────────────────────────────────────────────────────────────
#  MARKET TYPE CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────

class MarketType(str, Enum):
    FX = "FX"
    INDEX = "INDEX"
    COMMODITY = "COMMODITY"


# Symbol classification database
SYMBOL_CLASSIFICATION: Dict[str, MarketType] = {
    # FX Majors
    "EURUSD": MarketType.FX, "GBPUSD": MarketType.FX,
    "USDJPY": MarketType.FX, "USDCHF": MarketType.FX,
    "AUDUSD": MarketType.FX, "NZDUSD": MarketType.FX,
    "USDCAD": MarketType.FX,
    # FX Crosses
    "EURJPY": MarketType.FX, "GBPJPY": MarketType.FX,
    "EURGBP": MarketType.FX, "EURAUD": MarketType.FX,
    "GBPAUD": MarketType.FX, "AUDNZD": MarketType.FX,
    "NZDJPY": MarketType.FX, "CHFJPY": MarketType.FX,
    "CADJPY": MarketType.FX, "AUDCAD": MarketType.FX,
    "EURCAD": MarketType.FX, "GBPCAD": MarketType.FX,
    "GBPNZD": MarketType.FX, "EURNZD": MarketType.FX,
    # Indices
    "NAS100": MarketType.INDEX, "US100": MarketType.INDEX,
    "USTEC": MarketType.INDEX, "NASDAQ": MarketType.INDEX,
    "NQ100": MarketType.INDEX,
    "US30": MarketType.INDEX, "DJ30": MarketType.INDEX,
    "SP500": MarketType.INDEX, "US500": MarketType.INDEX,
    "DAX40": MarketType.INDEX, "GER40": MarketType.INDEX,
    "UK100": MarketType.INDEX, "FTSE100": MarketType.INDEX,
    # Commodities
    "XAUUSD": MarketType.COMMODITY, "GOLD": MarketType.COMMODITY,
    "XAGUSD": MarketType.COMMODITY, "SILVER": MarketType.COMMODITY,
}


# ─────────────────────────────────────────────────────────────────────
#  MARKET PROFILE
# ─────────────────────────────────────────────────────────────────────

@dataclass
class MarketProfile:
    """
    Everything the system needs to know about a symbol's market type.
    """
    market_type: MarketType
    # Trade windows (UTC hours)
    trade_window_start: int = 8          # When to start scanning
    trade_window_end: int = 21           # When to stop
    killzone_start: int = 13             # Prime execution window
    killzone_end: int = 16
    # Pip/point value
    pip_size: float = 0.0001             # 0.0001 for most FX, 0.01 for JPY
    point_value: float = 10.0            # Dollar value per pip per lot
    # SL/TP configuration
    sl_buffer_pips: float = 3.0          # Extra pips behind SL
    use_atr_sl: bool = False             # Use ATR-based SL (for indices)
    atr_sl_multiplier: float = 2.0       # ATR × this = SL distance
    min_sl_distance: float = 10.0        # Min SL distance in pips/points
    # Order type
    use_limit_orders: bool = False       # Limit orders for indices
    limit_offset_pips: float = 5.0       # How far from current to place limit
    # Contract sizing
    contract_size: float = 100000        # Standard lot = 100k for FX
    # Min/max lot
    min_lot: float = 0.01
    max_lot: float = 10.0
    lot_step: float = 0.01


# Pre-configured market profiles
FX_PROFILE = MarketProfile(
    market_type=MarketType.FX,
    trade_window_start=8,       # London open
    trade_window_end=21,        # NYSE close
    killzone_start=13,          # NY killzone
    killzone_end=16,
    pip_size=0.0001,
    point_value=10.0,           # $10 per pip per standard lot
    sl_buffer_pips=3.0,
    use_atr_sl=False,
    min_sl_distance=10.0,       # 10 pips min
    use_limit_orders=False,     # Market orders for FX
    contract_size=100000,
    min_lot=0.01,
    max_lot=10.0,
    lot_step=0.01,
)

FX_JPY_PROFILE = MarketProfile(
    market_type=MarketType.FX,
    trade_window_start=8,
    trade_window_end=21,
    killzone_start=13,
    killzone_end=16,
    pip_size=0.01,              # JPY pairs use 0.01
    point_value=6.7,            # ~$6.7 per pip per lot (varies with rate)
    sl_buffer_pips=3.0,
    use_atr_sl=False,
    min_sl_distance=10.0,
    use_limit_orders=False,
    contract_size=100000,
    min_lot=0.01,
    max_lot=10.0,
    lot_step=0.01,
)

NASDAQ_PROFILE = MarketProfile(
    market_type=MarketType.INDEX,
    trade_window_start=14,      # US cash open (14:30 UTC but we use 14)
    trade_window_end=21,        # US close
    killzone_start=14,
    killzone_end=17,            # Prime NQ hours
    pip_size=0.01,              # 1 point
    point_value=1.0,            # $1 per point per mini contract
    sl_buffer_pips=0,           # Not used — ATR-based
    use_atr_sl=True,            # ATR-based SL for NASDAQ
    atr_sl_multiplier=2.0,
    min_sl_distance=15.0,       # 15 points min
    use_limit_orders=True,      # Limit orders for NASDAQ
    limit_offset_pips=10.0,     # 10 points from current
    contract_size=1,            # 1 contract
    min_lot=0.1,                # 0.1 mini lots NQ
    max_lot=20.0,
    lot_step=0.1,
)

INDEX_PROFILE = MarketProfile(
    market_type=MarketType.INDEX,
    trade_window_start=8,
    trade_window_end=21,
    killzone_start=14,
    killzone_end=17,
    pip_size=0.01,
    point_value=1.0,
    sl_buffer_pips=0,
    use_atr_sl=True,
    atr_sl_multiplier=2.0,
    min_sl_distance=10.0,
    use_limit_orders=True,
    limit_offset_pips=5.0,
    contract_size=1,
    min_lot=0.1,
    max_lot=20.0,
    lot_step=0.1,
)

GOLD_PROFILE = MarketProfile(
    market_type=MarketType.COMMODITY,
    trade_window_start=8,
    trade_window_end=21,
    killzone_start=13,
    killzone_end=17,
    pip_size=0.01,
    point_value=1.0,
    sl_buffer_pips=0,
    use_atr_sl=True,
    atr_sl_multiplier=1.5,
    min_sl_distance=3.0,        # $3 min
    use_limit_orders=False,
    contract_size=100,
    min_lot=0.01,
    max_lot=10.0,
    lot_step=0.01,
)


# ─────────────────────────────────────────────────────────────────────
#  MARKET ADAPTER
# ─────────────────────────────────────────────────────────────────────

class MarketAdapter:
    """
    Adapter that normalizes how the strategy interacts with
    different market types. One strategy, multiple markets.
    
    Usage:
        adapter = MarketAdapter()
        profile = adapter.get_profile("US100")  # Returns NASDAQ_PROFILE
        
        if adapter.in_trade_window("US100"):
            sl_distance = adapter.calculate_sl_distance("US100", candles)
            lot_size = adapter.calculate_lot_size("US100", equity, sl_distance)
    """

    def __init__(self):
        self._custom_profiles: Dict[str, MarketProfile] = {}

    def classify(self, symbol: str) -> MarketType:
        """Classify a symbol into its market type."""
        # Strip suffixes like '.', '_m', etc.
        clean = self._clean_symbol(symbol)

        if clean in SYMBOL_CLASSIFICATION:
            return SYMBOL_CLASSIFICATION[clean]

        # Heuristic classification
        clean_upper = clean.upper()
        if any(idx in clean_upper for idx in ["NAS", "US100", "USTEC", "NQ", "SP500", "US500", "US30", "DJ", "DAX", "GER", "UK100", "FTSE"]):
            return MarketType.INDEX
        if any(cmd in clean_upper for cmd in ["XAU", "XAG", "GOLD", "SILVER", "OIL", "WTI", "BRENT"]):
            return MarketType.COMMODITY
        # Default to FX
        return MarketType.FX

    def get_profile(self, symbol: str) -> MarketProfile:
        """Get the full market profile for a symbol."""
        clean = self._clean_symbol(symbol)

        # Check custom overrides first
        if clean in self._custom_profiles:
            return self._custom_profiles[clean]

        market_type = self.classify(symbol)

        if market_type == MarketType.INDEX:
            # Specific NASDAQ profile
            if any(nq in clean.upper() for nq in ["NAS", "US100", "USTEC", "NQ"]):
                return NASDAQ_PROFILE
            return INDEX_PROFILE
        elif market_type == MarketType.COMMODITY:
            return GOLD_PROFILE
        else:
            # JPY pairs have different pip size
            if "JPY" in clean.upper():
                return FX_JPY_PROFILE
            return FX_PROFILE

    def set_custom_profile(self, symbol: str, profile: MarketProfile):
        """Override profile for a specific symbol."""
        clean = self._clean_symbol(symbol)
        self._custom_profiles[clean] = profile

    # ─────────────────────── TRADE WINDOW ───────────────────────

    def in_trade_window(self, symbol: str, now: Optional[datetime] = None) -> bool:
        """Check if we're inside the valid trade window for this symbol."""
        if now is None:
            now = datetime.now(timezone.utc)

        profile = self.get_profile(symbol)
        hour = now.hour

        return profile.trade_window_start <= hour < profile.trade_window_end

    def in_killzone(self, symbol: str, now: Optional[datetime] = None) -> bool:
        """Check if we're in the prime execution window (killzone)."""
        if now is None:
            now = datetime.now(timezone.utc)

        profile = self.get_profile(symbol)
        hour = now.hour

        return profile.killzone_start <= hour < profile.killzone_end

    # ─────────────────────── SL CALCULATION ───────────────────────

    def calculate_sl_distance(
        self,
        symbol: str,
        candles: List[dict],
        atr_period: int = 14,
    ) -> float:
        """
        Calculate the SL distance for a symbol.
        
        FX: Fixed pips + buffer
        NASDAQ/Index: ATR × multiplier
        
        Returns distance in price units (not pips).
        """
        profile = self.get_profile(symbol)

        if profile.use_atr_sl and len(candles) >= atr_period:
            # ATR-based SL for indices
            atr = self._calculate_atr(candles, atr_period)
            sl_distance = atr * profile.atr_sl_multiplier
            min_distance = profile.min_sl_distance * profile.pip_size
            return max(sl_distance, min_distance)
        else:
            # Fixed pips for FX
            return profile.sl_buffer_pips * profile.pip_size

    def calculate_sl_price(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        hunt_extreme: float,
        candles: List[dict],
    ) -> float:
        """
        Calculate the actual SL price.
        
        SL goes behind the stop hunt extreme + buffer.
        
        Args:
            direction: "BUY" or "SELL"
            entry_price: Where we're entering
            hunt_extreme: The stop hunt wick extreme
            candles: Recent candles for ATR
        """
        profile = self.get_profile(symbol)

        if profile.use_atr_sl:
            # ATR buffer for indices
            buffer = self.calculate_sl_distance(symbol, candles)
        else:
            # Fixed pip buffer for FX
            buffer = profile.sl_buffer_pips * profile.pip_size

        if direction == "BUY":
            # SL below the hunt low
            return hunt_extreme - buffer
        else:
            # SL above the hunt high
            return hunt_extreme + buffer

    def calculate_tp_price(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        sl_price: float,
        wedge_start_price: float,
        min_rr: float = 3.0,
    ) -> float:
        """
        Calculate TP price.
        
        TP = wedge start level (where the pattern began).
        But never less than min R:R ratio.
        """
        sl_distance = abs(entry_price - sl_price)
        min_tp_distance = sl_distance * min_rr

        if direction == "BUY":
            # TP at wedge start (above entry) or min R:R
            tp_at_wedge = wedge_start_price
            tp_at_rr = entry_price + min_tp_distance
            return max(tp_at_wedge, tp_at_rr)
        else:
            tp_at_wedge = wedge_start_price
            tp_at_rr = entry_price - min_tp_distance
            return min(tp_at_wedge, tp_at_rr)

    # ─────────────────────── LOT SIZING ───────────────────────

    def calculate_lot_size(
        self,
        symbol: str,
        equity: float,
        sl_distance_price: float,
        risk_pct: float = 2.0,
    ) -> float:
        """
        Calculate position size based on risk.
        
        FX:     risk_amount / (sl_pips × pip_value)
        Index:  risk_amount / (sl_points × point_value)
        
        Args:
            equity: Account equity
            sl_distance_price: SL distance in price units
            risk_pct: Risk percentage of equity (1.0 = 1%)
        """
        profile = self.get_profile(symbol)
        risk_amount = equity * (risk_pct / 100.0)

        if sl_distance_price <= 0:
            return profile.min_lot

        if profile.market_type == MarketType.FX:
            sl_pips = sl_distance_price / profile.pip_size
            if sl_pips <= 0:
                return profile.min_lot
            # Risk per pip per lot = pip_value
            lots = risk_amount / (sl_pips * profile.point_value)
        else:
            # Index/Commodity: SL in points
            sl_points = sl_distance_price / profile.pip_size
            if sl_points <= 0:
                return profile.min_lot
            lots = risk_amount / (sl_points * profile.point_value)

        # Round to step size
        lots = round(lots / profile.lot_step) * profile.lot_step
        lots = max(profile.min_lot, min(lots, profile.max_lot))

        # HARD CAP: Never exceed 0.10 lots per order
        lots = min(lots, 0.10)

        return round(lots, 2)

    # ─────────────────────── ORDER TYPE ───────────────────────

    def get_order_type(self, symbol: str, direction: str) -> str:
        """
        Determine order type for this market.
        
        FX: Market orders (ORDER_TYPE_BUY / ORDER_TYPE_SELL)
        NASDAQ: Limit orders (ORDER_TYPE_BUY_LIMIT / ORDER_TYPE_SELL_LIMIT)
        """
        profile = self.get_profile(symbol)

        if profile.use_limit_orders:
            if direction == "BUY":
                return "ORDER_TYPE_BUY_LIMIT"
            else:
                return "ORDER_TYPE_SELL_LIMIT"
        else:
            if direction == "BUY":
                return "ORDER_TYPE_BUY"
            else:
                return "ORDER_TYPE_SELL"

    def get_limit_price(
        self,
        symbol: str,
        direction: str,
        current_price: float,
    ) -> Optional[float]:
        """
        For limit order markets, calculate the limit price.
        
        We place the limit slightly behind the current price to catch
        the post-reversal entry at a better level.
        
        Returns None for market order symbols.
        """
        profile = self.get_profile(symbol)

        if not profile.use_limit_orders:
            return None

        offset = profile.limit_offset_pips * profile.pip_size

        if direction == "BUY":
            # Limit below current for buy
            return current_price - offset
        else:
            # Limit above current for sell
            return current_price + offset

    # ─────────────────────── UTILITIES ───────────────────────

    def _clean_symbol(self, symbol: str) -> str:
        """Remove broker suffixes from symbol names."""
        # Common suffixes: ".", "_m", ".raw", ".pro", etc.
        clean = symbol.rstrip(".")
        for suffix in ["_m", "_M", ".raw", ".pro", ".std", ".ecn", ".stp"]:
            if clean.endswith(suffix):
                clean = clean[: -len(suffix)]
        return clean.upper()

    def _calculate_atr(self, candles: List[dict], period: int = 14) -> float:
        """Calculate ATR from candle data."""
        if len(candles) < period + 1:
            # Not enough data — use last N candles' ranges
            ranges = [c.get("high", 0) - c.get("low", 0) for c in candles[-period:]]
            return sum(ranges) / len(ranges) if ranges else 0

        true_ranges = []
        for i in range(1, min(period + 1, len(candles))):
            high = candles[-i].get("high", 0)
            low = candles[-i].get("low", 0)
            prev_close = candles[-i - 1].get("close", 0)
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        return sum(true_ranges) / len(true_ranges) if true_ranges else 0

    def get_symbol_info(self, symbol: str) -> Dict:
        """Get a summary of how this symbol will be traded."""
        profile = self.get_profile(symbol)
        market_type = self.classify(symbol)

        return {
            "symbol": symbol,
            "clean_symbol": self._clean_symbol(symbol),
            "market_type": market_type.value,
            "trade_window": f"{profile.trade_window_start:02d}:00 - {profile.trade_window_end:02d}:00 UTC",
            "killzone": f"{profile.killzone_start:02d}:00 - {profile.killzone_end:02d}:00 UTC",
            "order_type": "LIMIT" if profile.use_limit_orders else "MARKET",
            "sl_method": "ATR" if profile.use_atr_sl else "FIXED_PIPS",
            "pip_size": profile.pip_size,
            "min_lot": profile.min_lot,
        }
