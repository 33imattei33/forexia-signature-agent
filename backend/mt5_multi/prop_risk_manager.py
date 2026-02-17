"""
╔══════════════════════════════════════════════════════════════════════╗
║    FOREXIA — PROP FIRM RISK MANAGER                                  ║
║    Per-account risk compliance for prop firm rules                    ║
╚══════════════════════════════════════════════════════════════════════╝

This module enforces prop firm constraints at the trade level:
  - Daily loss limit (hard stop)
  - Max trailing drawdown (APEX-style)
  - News lockout (no trades N minutes before/after high-impact news)
  - Position sizing (per-account equity × prop firm lot rules)
  - Friday close deadline
  - Max concurrent positions

NO FVG. Only Price Action, Wedge Patterns, and Liquidity Grabs.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass

from backend.mt5_multi.account_manager import (
    MultiAccountManager, PropFirmRules, AccountTracker,
)
from backend.mt5_multi.market_adapter import MarketAdapter, MarketProfile

logger = logging.getLogger("forexia.prop_risk")


# ─────────────────────────────────────────────────────────────────────
#  RISK VERDICT
# ─────────────────────────────────────────────────────────────────────

@dataclass
class RiskVerdict:
    """Result of a risk check. If approved=False, the trade is blocked."""
    approved: bool
    reason: str
    lot_size: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    order_type: str = "ORDER_TYPE_BUY"  # or SELL, BUY_LIMIT, SELL_LIMIT
    limit_price: Optional[float] = None
    risk_reward_ratio: float = 0.0
    risk_amount: float = 0.0
    risk_pct: float = 0.0


# ─────────────────────────────────────────────────────────────────────
#  PROP FIRM RISK MANAGER
# ─────────────────────────────────────────────────────────────────────

class PropFirmRiskManager:
    """
    Prop firm-aware risk manager.
    
    Sits between the signal generator and trade execution.
    Every signal must pass through this before reaching the broker.
    
    Pipeline:
      Signal → PropFirmRiskManager.evaluate() → RiskVerdict → Execute/Block
    
    Checks performed:
      1. Account health (daily loss, trailing DD, total DD)
      2. Position limits
      3. News lockout
      4. Friday close deadline
      5. Trade window (via MarketAdapter)
      6. Risk-based position sizing
      7. SL/TP validation
    """

    def __init__(
        self,
        account_manager: MultiAccountManager,
        market_adapter: MarketAdapter,
        news_events: Optional[List[Dict]] = None,
    ):
        self._accounts = account_manager
        self._market = market_adapter
        self._news_events = news_events or []
        self._max_risk_pct = 2.0  # Max 2% risk per trade

    def set_news_events(self, events: List[Dict]):
        """
        Update upcoming news events.
        Each event: {"time": datetime, "currency": "USD", "impact": "HIGH"}
        """
        self._news_events = events

    # ─────────────────────── MAIN EVALUATION ───────────────────────

    def evaluate(
        self,
        account_id: str,
        symbol: str,
        direction: str,          # "BUY" or "SELL"
        entry_price: float,
        hunt_extreme: float,     # Stop hunt wick extreme
        wedge_start: float,      # Where the pattern started (for TP)
        candles: List[dict],     # Recent candles for ATR
        now: Optional[datetime] = None,
    ) -> RiskVerdict:
        """
        Full risk evaluation for a proposed trade.
        
        Returns a RiskVerdict with approved=True and lot_size/SL/TP
        if the trade passes all checks, or approved=False with reason.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # ── CHECK 1: Account health ──
        tracker = self._accounts.get_tracker(account_id)
        if not tracker:
            return RiskVerdict(approved=False, reason="Account not found")
        if not tracker.connected:
            return RiskVerdict(approved=False, reason="Account disconnected")

        allowed, block_reason = self._accounts.can_trade(account_id)
        if not allowed:
            return RiskVerdict(approved=False, reason=block_reason)

        rules = self._accounts.get_rules(account_id)

        # ── CHECK 2: Trade window ──
        if not self._market.in_trade_window(symbol, now):
            profile = self._market.get_profile(symbol)
            return RiskVerdict(
                approved=False,
                reason=f"Outside trade window: {profile.trade_window_start}:00-{profile.trade_window_end}:00 UTC"
            )

        # ── CHECK 3: Friday close deadline ──
        if now.weekday() == 4:  # Friday
            if now.hour >= rules.friday_close_utc:
                return RiskVerdict(
                    approved=False,
                    reason=f"Past Friday deadline ({rules.friday_close_utc}:00 UTC)"
                )

        # ── CHECK 4: Weekend holding ──
        if now.weekday() == 4 and not rules.weekend_holding:
            hours_to_close = rules.friday_close_utc - now.hour
            if hours_to_close <= 2:
                return RiskVerdict(
                    approved=False,
                    reason="Too close to market close — weekend holding not allowed"
                )

        # ── CHECK 5: News lockout ──
        news_blocked, news_reason = self._check_news_lockout(symbol, now, rules)
        if news_blocked:
            return RiskVerdict(approved=False, reason=news_reason)

        # ── CHECK 6: Calculate SL ──
        sl_price = self._market.calculate_sl_price(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            hunt_extreme=hunt_extreme,
            candles=candles,
        )

        # Validate SL distance
        sl_distance = abs(entry_price - sl_price)
        profile = self._market.get_profile(symbol)
        min_sl = profile.min_sl_distance * profile.pip_size

        if sl_distance < min_sl:
            return RiskVerdict(
                approved=False,
                reason=f"SL too tight: {sl_distance:.5f} < min {min_sl:.5f}"
            )

        # ── CHECK 7: Calculate TP ──
        tp_price = self._market.calculate_tp_price(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            sl_price=sl_price,
            wedge_start_price=wedge_start,
            min_rr=3.0,
        )

        # Validate direction consistency
        if direction == "BUY":
            if sl_price >= entry_price or tp_price <= entry_price:
                return RiskVerdict(
                    approved=False,
                    reason=f"Invalid BUY levels: SL={sl_price}, Entry={entry_price}, TP={tp_price}"
                )
        else:
            if sl_price <= entry_price or tp_price >= entry_price:
                return RiskVerdict(
                    approved=False,
                    reason=f"Invalid SELL levels: SL={sl_price}, Entry={entry_price}, TP={tp_price}"
                )

        # ── CHECK 8: Risk-reward ratio ──
        tp_distance = abs(tp_price - entry_price)
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0

        if rr_ratio < 2.0:
            return RiskVerdict(
                approved=False,
                reason=f"R:R too low: {rr_ratio:.1f}:1 (min 2:1)"
            )

        # ── CHECK 9: Position sizing ──
        equity = tracker.current_equity
        if equity <= 0:
            return RiskVerdict(approved=False, reason="No equity available")

        # Prop firm lot sizing
        lot_size = self._calculate_prop_lot_size(
            symbol=symbol,
            equity=equity,
            sl_distance=sl_distance,
            rules=rules,
        )

        if lot_size < profile.min_lot:
            return RiskVerdict(
                approved=False,
                reason=f"Calculated lot {lot_size} below minimum {profile.min_lot}"
            )

        # ── CHECK 10: Risk amount validation ──
        risk_amount = sl_distance * lot_size * profile.contract_size
        risk_pct = (risk_amount / equity * 100) if equity > 0 else 100

        if risk_pct > self._max_risk_pct * 1.5:
            return RiskVerdict(
                approved=False,
                reason=f"Risk too high: {risk_pct:.1f}% (max {self._max_risk_pct * 1.5:.1f}%)"
            )

        # ── CHECK 11: Would this trade breach daily loss if it loses? ──
        daily_loss_limit = tracker.starting_balance * (rules.daily_loss_limit_pct / 100)
        current_loss = abs(min(0, tracker.daily_pnl))
        remaining_room = daily_loss_limit - current_loss

        if risk_amount > remaining_room:
            return RiskVerdict(
                approved=False,
                reason=f"Would breach daily loss: risk ${risk_amount:.2f} > room ${remaining_room:.2f}"
            )

        # ── CHECK 12: Order type ──
        order_type = self._market.get_order_type(symbol, direction)
        limit_price = self._market.get_limit_price(symbol, direction, entry_price)

        # ✅ ALL CHECKS PASSED
        return RiskVerdict(
            approved=True,
            reason="All risk checks passed",
            lot_size=lot_size,
            stop_loss=round(sl_price, 5),
            take_profit=round(tp_price, 5),
            order_type=order_type,
            limit_price=round(limit_price, 5) if limit_price else None,
            risk_reward_ratio=round(rr_ratio, 2),
            risk_amount=round(risk_amount, 2),
            risk_pct=round(risk_pct, 2),
        )

    # ─────────────────────── NEWS LOCKOUT ───────────────────────

    def _check_news_lockout(
        self,
        symbol: str,
        now: datetime,
        rules: PropFirmRules,
    ) -> Tuple[bool, str]:
        """
        Check if a high-impact news event blocks trading.
        
        Returns (is_blocked, reason).
        """
        lockout_window = timedelta(minutes=rules.news_lockout_minutes)
        clean_symbol = self._market._clean_symbol(symbol)

        # Extract currencies from pair
        currencies = set()
        if len(clean_symbol) >= 6:
            currencies.add(clean_symbol[:3])
            currencies.add(clean_symbol[3:6])

        for event in self._news_events:
            event_time = event.get("time")
            event_currency = event.get("currency", "")
            event_impact = event.get("impact", "").upper()

            if not event_time or event_impact not in ("HIGH", "CRITICAL"):
                continue

            if event_currency not in currencies:
                continue

            if isinstance(event_time, str):
                try:
                    event_time = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                except ValueError:
                    continue

            # Check if we're within the lockout window
            if abs((now - event_time).total_seconds()) < lockout_window.total_seconds():
                return (
                    True,
                    f"News lockout: {event_currency} {event_impact} event at {event_time.strftime('%H:%M')} UTC"
                )

        return (False, "")

    # ─────────────────────── LOT SIZING ───────────────────────

    def _calculate_prop_lot_size(
        self,
        symbol: str,
        equity: float,
        sl_distance: float,
        rules: PropFirmRules,
    ) -> float:
        """
        Calculate lot size respecting prop firm rules.
        
        Method 1 (Prop firm scaling):
            FX:     0.01 lots per $10k equity
            NASDAQ: 0.1 contracts per $10k equity
        
        Method 2 (Risk-based):
            risk_amount / (sl_pips × pip_value)
        
        We take the MINIMUM of both to stay safe.
        """
        profile = self._market.get_profile(symbol)

        # Method 1: Prop firm scaling
        if profile.market_type.value == "INDEX":
            prop_lots = (equity / 10000) * rules.nasdaq_contract_per_10k
        else:
            prop_lots = (equity / 10000) * rules.lot_per_10k

        # Method 2: Risk-based
        risk_lots = self._market.calculate_lot_size(
            symbol=symbol,
            equity=equity,
            sl_distance_price=sl_distance,
            risk_pct=self._max_risk_pct,
        )

        # Take the more conservative
        final_lots = min(prop_lots, risk_lots)

        # Clamp to prop firm limits
        final_lots = max(rules.min_lot_size, min(final_lots, rules.max_lot_size))

        # Round to step
        final_lots = round(final_lots / profile.lot_step) * profile.lot_step

        return round(final_lots, 2)

    # ─────────────────────── PORTFOLIO RISK ───────────────────────

    def get_account_risk_summary(self, account_id: str) -> Dict:
        """Get current risk state for an account."""
        tracker = self._accounts.get_tracker(account_id)
        rules = self._accounts.get_rules(account_id)

        if not tracker:
            return {"error": "Account not found"}

        daily_loss_limit = tracker.starting_balance * (rules.daily_loss_limit_pct / 100)
        daily_used = abs(min(0, tracker.daily_pnl))
        daily_remaining = daily_loss_limit - daily_used

        result = {
            "account_id": account_id,
            "firm_type": tracker.firm_type.value,
            "equity": round(tracker.current_equity, 2),
            "daily_pnl": round(tracker.daily_pnl, 2),
            "daily_loss_limit": round(daily_loss_limit, 2),
            "daily_remaining": round(daily_remaining, 2),
            "daily_used_pct": round((daily_used / daily_loss_limit * 100) if daily_loss_limit > 0 else 0, 1),
            "open_positions": tracker.open_positions,
            "max_positions": rules.max_positions,
            "can_trade": self._accounts.can_trade(account_id)[0],
            "block_reason": self._accounts.can_trade(account_id)[1],
        }

        # Trailing DD info (APEX)
        if rules.use_trailing_dd:
            trailing_dd = tracker.high_water_mark - tracker.current_equity
            trailing_limit = tracker.high_water_mark * (rules.max_trailing_dd_pct / 100)
            result["trailing_dd"] = round(trailing_dd, 2)
            result["trailing_dd_limit"] = round(trailing_limit, 2)
            result["trailing_dd_pct"] = round((trailing_dd / tracker.high_water_mark * 100) if tracker.high_water_mark > 0 else 0, 2)

        return result
