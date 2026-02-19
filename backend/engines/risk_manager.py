"""
╔══════════════════════════════════════════════════════════════════════╗
║         FOREXIA SIGNATURE AGENT — RISK MANAGEMENT MODULE            ║
║    Institutional-Grade Position Sizing & Stop Placement Engine       ║
╚══════════════════════════════════════════════════════════════════════╝

RISK IS NON-NEGOTIABLE.

Hardcoded rule: 0.01 lots per $100 of account equity.
This is not configurable by enthusiasm, greed, or "conviction."

Stop-loss placement: Just beyond the Stop Hunt wick.
When we enter after the exhaustion, we place our SL behind the
extreme of the hunt wick. This means:
  - If Smart Money hunted stops above, our SL goes ABOVE the wick
  - We are using the swept liquidity zone as a SHIELD
  - Any stop above/below the hunt extreme = retail would have to
    get hunted AGAIN for us to get stopped out (very unlikely)

Take-Profit: Minimum 1:3 risk-reward ratio.
We target the opposite liquidity pool or the origin of the move.
"""

import logging
import math
from typing import Optional, Tuple

from backend.config import CONFIG
from backend.models.schemas import AccountState, TradeDirection

logger = logging.getLogger("forexia.risk_management")


class RiskManager:
    """
    Institutional risk management — the shield that keeps you alive.
    
    Every signal from the Forexia engines passes through here.
    No matter how "perfect" the setup looks, risk rules are ABSOLUTE:
      - Position size is calculated MECHANICALLY
      - Stop-loss is placed BEHIND the stop hunt wick
      - Daily loss limits trigger a circuit breaker
      - Max concurrent trades are enforced
    """

    def __init__(self):
        self.config = CONFIG.risk
        self._daily_pnl = 0.0
        self._trades_today = 0
        self._daily_loss_triggered = False

    # ─────────────────────────────────────────────────────────────────
    #  LOT SIZE CALCULATION — THE IRON RULE
    # ─────────────────────────────────────────────────────────────────

    def calculate_lot_size(
        self,
        account: AccountState,
        entry_price: float = 0.0,
        stop_loss: float = 0.0,
        symbol: str = "EURUSD",
    ) -> float:
        """
        Calculate position size using RISK-BASED sizing.
        
        Primary rule: Never risk more than max_risk_percent (2%) of equity.
        Fallback rule: 0.01 lots per $100 of equity.
        We take the MINIMUM of both to stay safe.
        
        Risk-based formula:
          risk_amount = equity * (max_risk_percent / 100)
          sl_pips = |entry - sl| / pip_value
          pip_dollar_value = contract_size * pip_value / rate (for JPY)
          lot_size = risk_amount / (sl_pips * pip_dollar_value)
        
        Returns: lot size rounded to 2 decimal places
        """
        if account.equity <= 0:
            logger.error("Account equity is zero or negative — cannot calculate lots")
            return 0.0

        # Method 1: Equity-based rule (0.01 lots per $100)
        equity_lots = (account.equity / 100.0) * self.config.lot_per_100_equity

        # Method 2: Risk-based sizing (max 2% risk per trade)
        risk_lots = equity_lots  # default to equity-based if no SL info
        sl_distance = abs(entry_price - stop_loss) if entry_price > 0 and stop_loss > 0 else 0

        if sl_distance > 0:
            pip_value = self._get_pip_value(symbol)
            sl_pips = sl_distance / pip_value

            if sl_pips > 0:
                risk_amount = account.equity * (self.config.max_risk_percent / 100.0)
                # Pip dollar value per standard lot
                # For XXX/USD pairs: $10 per pip per lot
                # For XXX/JPY pairs: ~$6.50 per pip per lot (100000 * 0.01 / rate)
                if "JPY" in symbol:
                    rate = entry_price if entry_price > 1 else 150.0
                    pip_dollar = 100000 * 0.01 / rate
                else:
                    pip_dollar = 10.0  # $10 per pip per standard lot

                risk_lots = risk_amount / (sl_pips * pip_dollar)

        # Take the MORE CONSERVATIVE of the two
        lot_size = min(equity_lots, risk_lots)

        # HARD CAP: Never exceed max_lot_size (default 0.10 lots)
        max_lot = getattr(self.config, 'max_lot_size', 0.10)
        lot_size = min(lot_size, max_lot)

        # Minimum lot size: 0.01
        lot_size = max(0.01, lot_size)

        # Round to 2 decimal places (broker standard)
        lot_size = round(lot_size, 2)

        logger.info(
            f"══╡ POSITION SIZE — {lot_size} lots ╞══\n"
            f"    Equity: ${account.equity:.2f}\n"
            f"    Equity-based: {round(equity_lots, 2)} lots\n"
            f"    Risk-based ({self.config.max_risk_percent}% max): {round(risk_lots, 2)} lots\n"
            f"    Hard cap: {max_lot} lots max per order\n"
            f"    SL distance: {sl_distance / self._get_pip_value(symbol) if sl_distance > 0 else 0:.1f} pips\n"
            f"    Final: {lot_size} lots (capped & conservative)"
        )

        return lot_size

    # ─────────────────────────────────────────────────────────────────
    #  STOP-LOSS PLACEMENT — BEHIND THE STOP HUNT WICK
    # ─────────────────────────────────────────────────────────────────

    def calculate_stop_loss(
        self,
        direction: TradeDirection,
        stop_hunt_extreme: float,
        symbol: str = "EURUSD",
        entry_price: float = 0.0,
    ) -> float:
        """
        Calculate stop-loss placement — FIXED 20 pips from entry.
        
        Strategy mandate: All trades get exactly 20 pip stop-loss.
        This provides tight risk control while allowing room for noise.
        
        Args:
            direction: BUY or SELL
            stop_hunt_extreme: The wick extreme (legacy, used as fallback)
            symbol: Used to determine pip value
            entry_price: Current entry price for fixed-pip SL calculation
        
        Returns: stop-loss price
        """
        sl_pips = self.config.stop_loss_buffer_pips  # 20 pips
        pip_val = self._get_pip_value(symbol)
        sl_distance = sl_pips * pip_val

        if entry_price > 0:
            # FIXED SL: Exactly sl_pips (20) from entry
            if direction == TradeDirection.BUY:
                sl = entry_price - sl_distance
            else:
                sl = entry_price + sl_distance
            logger.info(
                f"══╡ STOP-LOSS ({direction.value}) — {sl:.5f} ╞══\n"
                f"    Entry: {entry_price:.5f}\n"
                f"    SL: FIXED {sl_pips:.0f} pips from entry\n"
                f"    Strategy: Tight 20-pip risk control"
            )
        else:
            # Fallback: buffer from stop hunt extreme
            if direction == TradeDirection.BUY:
                sl = stop_hunt_extreme - sl_distance
            else:
                sl = stop_hunt_extreme + sl_distance
            logger.info(
                f"══╡ STOP-LOSS ({direction.value}) — {sl:.5f} ╞══\n"
                f"    Hunt extreme: {stop_hunt_extreme:.5f}\n"
                f"    Buffer: {sl_pips:.0f} pips\n"
                f"    Fallback mode (no entry price)"
            )

        return round(sl, 5)

    # ─────────────────────────────────────────────────────────────────
    #  TAKE-PROFIT CALCULATION — MINIMUM 1:3 R:R
    # ─────────────────────────────────────────────────────────────────

    def calculate_take_profit(
        self,
        direction: TradeDirection,
        entry_price: float,
        stop_loss: float,
        target_liquidity: Optional[float] = None,
        symbol: str = "EURUSD"
    ) -> float:
        """
        Calculate take-profit target — FIXED 80 pips from entry.
        
        Strategy mandate: All trades target 80 pips TP (4:1 R:R with 20 pip SL).
        This gives excellent risk-to-reward while being achievable on major pairs.
        """
        risk = abs(entry_price - stop_loss)
        pip_value = self._get_pip_value(symbol)

        # FIXED TP: Always use take_profit_pips (80 pips)
        fixed_tp_pips = getattr(self.config, 'take_profit_pips', 80.0)
        if fixed_tp_pips <= 0:
            fixed_tp_pips = 80.0  # Enforce minimum

        tp_distance = fixed_tp_pips * pip_value
        if direction == TradeDirection.BUY:
            tp = entry_price + tp_distance
        else:
            tp = entry_price - tp_distance

        actual_rr = abs(tp - entry_price) / risk if risk > 0 else 0
        logger.info(
            f"══╡ TAKE-PROFIT (FIXED) — {tp:.5f} ╞══\n"
            f"    Entry: {entry_price:.5f}\n"
            f"    TP: {fixed_tp_pips:.0f} pips (fixed mode)\n"
            f"    Risk: {risk / pip_value:.1f} pips\n"
            f"    R:R Ratio: 1:{actual_rr:.2f}\n"
            f"    Strategy: Fixed 20 SL / 80 TP — 4:1 R:R"
        )
        return round(tp, 5)

        # Ratio-based fallback no longer used — all trades use fixed TP above
        # This code is unreachable but kept for reference
        min_tp_distance = risk * self.config.take_profit_ratio

        if direction == TradeDirection.BUY:
            min_tp = entry_price + min_tp_distance
            tp = max(min_tp, target_liquidity) if target_liquidity else min_tp
        else:
            min_tp = entry_price - min_tp_distance
            tp = min(min_tp, target_liquidity) if target_liquidity else min_tp

        actual_rr = abs(tp - entry_price) / risk if risk > 0 else 0

        logger.info(
            f"══╡ TAKE-PROFIT — {tp:.5f} ╞══\n"
            f"    Entry: {entry_price:.5f}\n"
            f"    Risk: {risk * 10000:.1f} pips\n"
            f"    Reward: {abs(tp - entry_price) * 10000:.1f} pips\n"
            f"    R:R Ratio: 1:{actual_rr:.1f}\n"
            f"    {'Target: Opposite liquidity pool' if target_liquidity else 'Target: Ratio-based'}"
        )

        return round(tp, 5)

    # ─────────────────────────────────────────────────────────────────
    #  TRADE VALIDATION — PRE-EXECUTION CHECKS
    # ─────────────────────────────────────────────────────────────────

    def validate_trade(
        self,
        account: AccountState,
        lot_size: float,
        spread_pips: float = 0
    ) -> Tuple[bool, str]:
        """
        Final pre-execution validation.
        
        Checks:
          1. Daily loss limit not exceeded (circuit breaker)
          2. Max concurrent trades not exceeded
          3. Spread is acceptable (no wild spreads)
          4. Sufficient margin available
          5. Position size is within bounds
        
        Returns:
            (approved, reason)
        """
        # Check 1: Daily loss circuit breaker
        if self._daily_loss_triggered:
            return (False, "DAILY LOSS LIMIT HIT — Circuit breaker active. "
                          "No more trades today. Protect the account.")

        daily_loss_limit = account.balance * (self.config.max_daily_loss_percent / 100)
        if abs(self._daily_pnl) >= daily_loss_limit and self._daily_pnl < 0:
            self._daily_loss_triggered = True
            logger.warning(
                f"══╡ CIRCUIT BREAKER — Daily loss ${abs(self._daily_pnl):.2f} "
                f"exceeds limit ${daily_loss_limit:.2f} ╞══\n"
                "    ALL TRADING HALTED for the rest of the day."
            )
            return (False, f"Daily loss limit exceeded: "
                          f"${abs(self._daily_pnl):.2f} / ${daily_loss_limit:.2f}")

        # Check 2: Max concurrent trades
        if account.open_trades >= self.config.max_concurrent_trades:
            return (False, f"Max concurrent trades reached: "
                          f"{account.open_trades}/{self.config.max_concurrent_trades}")

        # Check 3: Spread check — reject wild spreads
        if spread_pips > self.config.max_spread_pips:
            return (False, f"Spread too wide: {spread_pips:.1f} pips "
                          f"(max: {self.config.max_spread_pips}). "
                          "Market conditions unfavorable.")

        # Check 4: Minimum lot size
        if lot_size < 0.01:
            return (False, f"Lot size {lot_size} below minimum 0.01")

        # Check 5: Free margin (rough check)
        if account.free_margin < 50:  # Minimum $50 free margin
            return (False, f"Insufficient free margin: ${account.free_margin:.2f}")

        logger.info(
            f"══╡ TRADE VALIDATED — Approved ╞══\n"
            f"    Lots: {lot_size} | Spread: {spread_pips:.1f}p | "
            f"    Open trades: {account.open_trades}/{self.config.max_concurrent_trades} | "
            f"    Daily P&L: ${self._daily_pnl:.2f}"
        )
        return (True, "Trade approved — all risk checks passed")

    # ─────────────────────────────────────────────────────────────────
    #  COMPLETE RISK PACKAGE — ONE-CALL SOLUTION
    # ─────────────────────────────────────────────────────────────────

    def build_risk_package(
        self,
        account: AccountState,
        direction: TradeDirection,
        entry_price: float,
        stop_hunt_extreme: float,
        symbol: str = "EURUSD",
        target_liquidity: Optional[float] = None,
        spread_pips: float = 0
    ) -> Optional[dict]:
        """
        Build a complete risk package for trade execution.
        
        Calculates SL first, then lot size (risk-based), then TP.
        Returns None if the trade fails validation.
        
        Returns:
            {lot_size, stop_loss, take_profit, risk_pips, reward_pips, rr_ratio}
            or None if rejected.
        """
        # SL must be calculated FIRST — lot sizing depends on SL distance
        stop_loss = self.calculate_stop_loss(direction, stop_hunt_extreme, symbol, entry_price=entry_price)
        lot_size = self.calculate_lot_size(
            account, entry_price, stop_loss, symbol
        )
        take_profit = self.calculate_take_profit(
            direction, entry_price, stop_loss, target_liquidity, symbol
        )

        # Validate before returning
        approved, reason = self.validate_trade(account, lot_size, spread_pips)
        if not approved:
            logger.warning(f"TRADE REJECTED: {reason}")
            return None

        risk_pips = abs(entry_price - stop_loss) / self._get_pip_value(symbol)
        reward_pips = abs(take_profit - entry_price) / self._get_pip_value(symbol)
        rr_ratio = reward_pips / risk_pips if risk_pips > 0 else 0

        return {
            "lot_size": lot_size,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_pips": round(risk_pips, 1),
            "reward_pips": round(reward_pips, 1),
            "rr_ratio": round(rr_ratio, 2),
            "direction": direction,
            "entry_price": entry_price,
            "validation": reason,
        }

    # ─────────────────────────────────────────────────────────────────
    #  DAILY TRACKING
    # ─────────────────────────────────────────────────────────────────

    def record_trade_result(self, pnl: float):
        """Record a closed trade's P&L for daily tracking."""
        self._daily_pnl += pnl
        self._trades_today += 1
        logger.info(
            f"Trade result recorded: ${pnl:.2f} | "
            f"Daily P&L: ${self._daily_pnl:.2f} | "
            f"Trades today: {self._trades_today}"
        )

    def reset_daily(self):
        """Reset daily P&L and circuit breaker for a new trading day."""
        self._daily_pnl = 0.0
        self._trades_today = 0
        self._daily_loss_triggered = False
        logger.info("Risk Manager daily reset — Circuit breaker cleared")

    # ─────────────────────────────────────────────────────────────────
    #  UTILITIES
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _get_pip_value(symbol: str) -> float:
        """
        Get the pip value for a symbol.
        Standard: 0.0001 for most pairs, 0.01 for JPY pairs.
        """
        if "JPY" in symbol:
            return 0.01
        return 0.0001

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    @property
    def is_circuit_breaker_active(self) -> bool:
        return self._daily_loss_triggered
