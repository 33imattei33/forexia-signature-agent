"""
╔══════════════════════════════════════════════════════════════════════╗
║        FOREXIA SIGNATURE AGENT — WEEKLY 5-ACT STRUCTURE             ║
║         The Institutional Playbook: Sun–Fri Cycle Control            ║
╚══════════════════════════════════════════════════════════════════════╝

Markets are a theatre. The weekly structure is a 5-act play written
by Smart Money before the week even begins:

  ACT 1 (Sunday):    THE CONNECTOR — Gap analysis. The week's script
                     is set. We observe but NEVER trade.

  ACT 2 (Monday):    RETAIL INDUCTION — The "trend" is established.
                     Dumb money takes the bait. We observe the herd.
                     NEVER trade Mondays.

  ACT 3 (Tuesday):   ACCUMULATION — Smart Money quietly builds the
                     real position. The trend may continue but the
                     foundation for reversal is laid.

  ACT 4 (Wednesday): THE MIDWEEK REVERSAL (WTF Pattern) — The week
                     reverses. Monday's "trend" was the trap. This is
                     our PRIMARY entry day.

  ACT 5 (Thursday):  DISTRIBUTION — Continuation of Wednesday's
                     reversal. SECONDARY entry or scale-in day.

  EPILOGUE (Friday): PROFIT-TAKING — Reduce exposure before weekend.
                     Close everything by 18:00 UTC.
"""

import logging
from datetime import datetime
from typing import Optional

from backend.config import CONFIG
from backend.models.schemas import WeeklyAct

logger = logging.getLogger("forexia.weekly_structure")


class WeeklyStructureEngine:
    """
    Controls the weekly 5-Act trading cycle.
    
    This engine determines WHICH day of the week we are in,
    whether trading is permitted, and what type of action
    (if any) should be taken.
    
    The WTF (Wednesday-Thursday-Friday) Pattern is the bread and butter.
    """

    def __init__(self):
        self.config = CONFIG.weekly
        self._current_act: WeeklyAct = WeeklyAct.ACT_1_CONNECTOR
        self._weekly_trend_direction: Optional[str] = None  # Monday's induced trend
        self._monday_high: Optional[float] = None
        self._monday_low: Optional[float] = None

    # ─────────────────────────────────────────────────────────────────
    #  ACT DETERMINATION
    # ─────────────────────────────────────────────────────────────────

    def get_current_act(self, utc_now: Optional[datetime] = None) -> WeeklyAct:
        """
        Determine which Act of the weekly play is currently running.
        Returns the institutional phase of the week.
        """
        utc_now = utc_now or datetime.utcnow()
        day_name = utc_now.strftime("%A")

        act_map = {
            "Sunday": WeeklyAct.ACT_1_CONNECTOR,
            "Monday": WeeklyAct.ACT_2_INDUCTION,
            "Tuesday": WeeklyAct.ACT_3_ACCUMULATION,
            "Wednesday": WeeklyAct.ACT_4_REVERSAL,
            "Thursday": WeeklyAct.ACT_5_DISTRIBUTION,
            "Friday": WeeklyAct.EPILOGUE,
            "Saturday": WeeklyAct.ACT_1_CONNECTOR,  # Weekend = connector
        }

        self._current_act = act_map.get(day_name, WeeklyAct.ACT_1_CONNECTOR)
        return self._current_act

    def is_trading_permitted(self, utc_now: Optional[datetime] = None) -> bool:
        """
        Check if trading is allowed on the current day.
        
        RULE: No trading on Sundays or Mondays.
        Sunday = The Connector (gap observation only)
        Monday = Retail Induction (dumb money takes the bait, we watch)
        
        Primary trading: Wednesday, Thursday (WTF Pattern)
        Secondary: Tuesday (accumulation)
        Reduced: Friday (profit-taking, close by 18:00 UTC)
        """
        utc_now = utc_now or datetime.utcnow()
        day_name = utc_now.strftime("%A")

        if day_name in self.config.no_trade_days:
            logger.info(
                f"══╡ TRADING BLOCKED — {day_name} is a no-trade day. "
                f"{'Connector phase, observing gaps.' if day_name == 'Sunday' else 'Retail induction day — let dumb money set the trap.'} ╞══"
            )
            return False

        # Friday time check — close shop by 18:00 UTC
        if day_name == self.config.reduce_exposure_day:
            if utc_now.hour >= self.config.friday_close_hour_utc:
                logger.info(
                    "══╡ TRADING BLOCKED — Friday wind-down. "
                    "All positions should be closed. ╞══"
                )
                return False

        return True

    def is_primary_trade_day(self, utc_now: Optional[datetime] = None) -> bool:
        """
        Check if today is a PRIMARY trade day (Wednesday/Thursday).
        The WTF Pattern — Midweek Reversal — lives here.
        """
        utc_now = utc_now or datetime.utcnow()
        day_name = utc_now.strftime("%A")
        return day_name in self.config.primary_trade_days

    # ─────────────────────────────────────────────────────────────────
    #  MONDAY INDUCTION TRACKING — READING THE BAIT
    # ─────────────────────────────────────────────────────────────────

    def record_monday_range(self, high: float, low: float, close: float):
        """
        Record Monday's range — this IS the induction.
        
        Monday's trend is the BAIT that Smart Money uses to trap retail
        for the rest of the week. We record:
          - Monday high/low (future liquidity targets)
          - Monday's trend direction (what we will trade AGAINST)
        """
        self._monday_high = high
        self._monday_low = low

        # Monday's trend direction = the WRONG direction for the week
        range_midpoint = (high + low) / 2
        if close > range_midpoint:
            self._weekly_trend_direction = "UP"  # Retail thinks bullish week
            logger.info(
                f"══╡ ACT 2 — Monday Induction recorded: BULLISH trap ╞══\n"
                f"    Dumb money sees an uptrend. We anticipate REVERSAL.\n"
                f"    Monday High: {high:.5f} (target liquidity pool)\n"
                f"    Monday Low: {low:.5f}"
            )
        else:
            self._weekly_trend_direction = "DOWN"  # Retail thinks bearish week
            logger.info(
                f"══╡ ACT 2 — Monday Induction recorded: BEARISH trap ╞══\n"
                f"    Dumb money sees a downtrend. We anticipate REVERSAL.\n"
                f"    Monday High: {high:.5f}\n"
                f"    Monday Low: {low:.5f} (target liquidity pool)"
            )

    # ─────────────────────────────────────────────────────────────────
    #  WTF PATTERN DETECTION — MIDWEEK REVERSAL
    # ─────────────────────────────────────────────────────────────────

    def detect_wtf_pattern(
        self,
        current_price: float,
        utc_now: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Detect the WTF (Wednesday-Thursday-Friday) Midweek Reversal.
        
        The WTF Pattern confirms when Wednesday's price action REVERSES
        Monday's induced trend direction. If:
          - Monday was bullish → Wednesday breaks Monday's low = SELL
          - Monday was bearish → Wednesday breaks Monday's high = BUY
        
        This is the highest-probability Forexia trade of the week.
        
        Returns:
            Trade direction ("BUY" or "SELL") or None
        """
        utc_now = utc_now or datetime.utcnow()

        if not self.is_primary_trade_day(utc_now):
            return None

        if not self._weekly_trend_direction or \
           self._monday_high is None or self._monday_low is None:
            return None

        # WTF Pattern: Price reverses against Monday's trap
        if self._weekly_trend_direction == "UP":
            # Monday was bullish bait → week should reverse BEARISH
            # Trigger: price breaks below Monday's low
            if current_price < self._monday_low:
                logger.info(
                    f"══╡ WTF PATTERN CONFIRMED — SELL ╞══\n"
                    f"    Monday lured retail LONG (bullish induction).\n"
                    f"    Wednesday price {current_price:.5f} broke Monday Low "
                    f"{self._monday_low:.5f}.\n"
                    f"    Midweek Reversal: SELL — punishing dumb money longs."
                )
                return "SELL"

        elif self._weekly_trend_direction == "DOWN":
            # Monday was bearish bait → week should reverse BULLISH
            # Trigger: price breaks above Monday's high
            if current_price > self._monday_high:
                logger.info(
                    f"══╡ WTF PATTERN CONFIRMED — BUY ╞══\n"
                    f"    Monday lured retail SHORT (bearish induction).\n"
                    f"    Wednesday price {current_price:.5f} broke Monday High "
                    f"{self._monday_high:.5f}.\n"
                    f"    Midweek Reversal: BUY — squeezing dumb money shorts."
                )
                return "BUY"

        return None

    # ─────────────────────────────────────────────────────────────────
    #  WEEKLY LIQUIDITY TARGETS
    # ─────────────────────────────────────────────────────────────────

    def get_weekly_liquidity_targets(self) -> dict:
        """
        Return the week's key liquidity targets derived from Monday's range.
        These are the pools where retail stops are clustered for the week.
        """
        return {
            "monday_high": self._monday_high,
            "monday_low": self._monday_low,
            "induced_direction": self._weekly_trend_direction,
            "reversal_direction": (
                "SELL" if self._weekly_trend_direction == "UP" else
                "BUY" if self._weekly_trend_direction == "DOWN" else None
            )
        }

    # ─────────────────────────────────────────────────────────────────
    #  FRIDAY CLOSE LOGIC
    # ─────────────────────────────────────────────────────────────────

    def should_close_all(self, utc_now: Optional[datetime] = None) -> bool:
        """
        Check if we should close all positions (Friday wind-down).
        We don't hold over the weekend — gaps are uncontrolled risk.
        """
        utc_now = utc_now or datetime.utcnow()
        if utc_now.strftime("%A") == "Friday":
            return utc_now.hour >= self.config.friday_close_hour_utc
        return False

    def reset_weekly(self):
        """Reset all weekly state for a new trading week."""
        self._weekly_trend_direction = None
        self._monday_high = None
        self._monday_low = None
        logger.info("═══ Weekly Structure Reset — New 5-Act cycle begins ═══")

    @property
    def current_act(self) -> WeeklyAct:
        return self._current_act

    @property
    def weekly_trend_direction(self) -> Optional[str]:
        return self._weekly_trend_direction
