"""
╔══════════════════════════════════════════════════════════════════════╗
║         FOREXIA SIGNATURE AGENT — NEWS CATALYST ENGINE              ║
║    ForexFactory Red Folder Scraper — Volatility Catalyst Detector    ║
╚══════════════════════════════════════════════════════════════════════╝

CRITICAL PHILOSOPHY:
  Red Folder events are NOT "economic data releases."
  They are PRE-ENGINEERED VOLATILITY CATALYSTS.

  The economic numbers (Forecast, Actual, Previous) are BOGUS —
  meaningless noise manufactured for retail consumption. The numbers
  don't move the market; the ALGORITHM moves the market using the
  news event as COVER for the stop hunt.

WHAT WE STORE:
  ✓ Currency (which pair will be manipulated)
  ✓ Date (when the catalyst fires)
  ✓ Time (the exact moment of engineered volatility)
  ✓ Event Title (identification only)

WHAT WE DELETE:
  ✗ Forecast — BOGUS retail bait
  ✗ Actual — BOGUS after-the-fact narrative
  ✗ Previous — BOGUS historical noise
"""

import logging
import asyncio
import re
from datetime import datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from backend.config import CONFIG
from backend.models.schemas import NewsCatalyst

logger = logging.getLogger("forexia.news_catalyst")


class NewsCatalystEngine:
    """
    Scrapes ForexFactory for Red Folder events ONLY.
    
    These events are treated as pre-engineered volatility catalysts —
    moments when the algorithm has PERMISSION to make its big move.
    
    The bot uses these timestamps to:
      1. Lock out new trades before the catalyst fires
      2. Activate the Trauma Filter during the spike
      3. Target the post-spike exhaustion for reversal entries
    
    ALL economic numbers are STRIPPED and DELETED.
    We store ONLY: Currency, Date, Time, Event Title.
    """

    def __init__(self):
        self.config = CONFIG.news
        self._catalysts: List[NewsCatalyst] = []
        self._last_scrape: Optional[datetime] = None
        self._scrape_lock = asyncio.Lock()

    @property
    def catalysts(self) -> List[NewsCatalyst]:
        """All currently loaded Red Folder catalysts."""
        return self._catalysts

    # ─────────────────────────────────────────────────────────────────
    #  FOREXFACTORY SCRAPER — RED FOLDER ONLY
    # ─────────────────────────────────────────────────────────────────

    async def scrape_red_folder_events(
        self, target_date: Optional[datetime] = None
    ) -> List[NewsCatalyst]:
        """
        Scrape ForexFactory calendar for Red Folder (high-impact) events.
        
        CRITICAL: We strip ALL economic numbers.
        No Forecast. No Actual. No Previous.
        That data is retail bait — completely bogus.
        
        We extract ONLY:
          - Currency (e.g., "USD")
          - Event Title (e.g., "Non-Farm Payrolls")
          - Date
          - Time (UTC)
        
        These are the WHEN and WHAT of institutional volatility engineering.
        """
        async with self._scrape_lock:
            target_date = target_date or datetime.utcnow()
            
            # Format date for ForexFactory URL
            date_str = target_date.strftime("%b%d.%Y").lower()
            url = f"{self.config.forexfactory_url}?day={date_str}"

            try:
                async with httpx.AsyncClient(
                    timeout=30,
                    follow_redirects=True,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/131.0.0.0 Safari/537.36"
                        ),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Cache-Control": "no-cache",
                        "Pragma": "no-cache",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "Upgrade-Insecure-Requests": "1",
                        "Referer": "https://www.forexfactory.com/",
                    },
                    cookies={"fftimezoneoffset": "0"},
                ) as client:
                    response = await client.get(url)
                    response.raise_for_status()

                    catalysts = self._parse_calendar_html(
                        response.text, target_date
                    )

                    # ═══════════════════════════════════════════════════
                    # CRITICAL: Strip ALL economic numbers
                    # Forecast, Actual, Previous are BOGUS retail noise
                    # We store ONLY currency, date, time, title
                    # ═══════════════════════════════════════════════════

                    self._catalysts = catalysts
                    self._last_scrape = datetime.utcnow()

                    logger.info(
                        f"══╡ NEWS CATALYST ENGINE — Scraped {len(catalysts)} "
                        f"Red Folder events for {target_date.strftime('%Y-%m-%d')} ╞══\n"
                        f"    ALL economic numbers STRIPPED (Forecast/Actual/Previous = BOGUS)\n"
                        f"    Stored: Currency + Date + Time ONLY"
                    )

                    for cat in catalysts:
                        logger.info(
                            f"    ▸ [{cat.currency}] {cat.event_time} UTC — "
                            f"{cat.event_title}"
                        )

                    return catalysts

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    logger.warning(
                        "ForexFactory blocked scraping (403 Forbidden). "
                        "News catalyst data unavailable — agent will continue "
                        "without catalyst timing. Consider using a VPN or "
                        "configuring your own news data source."
                    )
                else:
                    logger.error(f"ForexFactory HTTP error: {e.response.status_code}")
                return self._catalysts  # Return existing catalysts instead of empty
            except Exception as e:
                logger.error(f"ForexFactory scrape failed: {e}")
                return self._catalysts

    def _parse_calendar_html(
        self, html: str, target_date: datetime
    ) -> List[NewsCatalyst]:
        """
        Parse ForexFactory calendar HTML.
        Extract Red Folder events ONLY — strip all economic numbers.
        """
        soup = BeautifulSoup(html, "html.parser")
        catalysts = []
        current_time = ""

        # Find calendar table rows
        calendar_rows = soup.select("tr.calendar__row")

        for row in calendar_rows:
            try:
                # Check impact — RED FOLDER ONLY
                impact_cell = row.select_one("td.calendar__impact span")
                if not impact_cell:
                    continue

                impact_classes = impact_cell.get("class", [])
                # ForexFactory uses 'icon--ff-impact-red' for high impact
                is_red = any(
                    "red" in cls.lower() or "high" in cls.lower()
                    for cls in impact_classes
                )

                if not is_red:
                    continue  # Skip non-Red events — we don't care

                # Extract currency
                currency_cell = row.select_one("td.calendar__currency")
                currency = currency_cell.get_text(strip=True) if currency_cell else ""

                if not currency:
                    continue

                # Extract time (some rows inherit time from previous row)
                time_cell = row.select_one("td.calendar__time")
                if time_cell:
                    time_text = time_cell.get_text(strip=True)
                    if time_text and time_text != "":
                        current_time = time_text

                # Extract event title
                event_cell = row.select_one("td.calendar__event span")
                title = event_cell.get_text(strip=True) if event_cell else "Unknown Event"

                # ═══════════════════════════════════════════════════
                # STRIP economic numbers — they are BOGUS
                # We intentionally DO NOT read:
                #   td.calendar__forecast
                #   td.calendar__actual
                #   td.calendar__previous
                # These cells contain retail bait data that is
                # completely irrelevant to how the algorithm moves price.
                # ═══════════════════════════════════════════════════

                # Convert time to UTC (ForexFactory uses ET by default)
                event_time_utc = self._convert_ff_time_to_utc(current_time)

                catalyst = NewsCatalyst(
                    currency=currency.upper(),
                    event_title=title,
                    event_date=target_date,
                    event_time=event_time_utc,
                )
                catalysts.append(catalyst)

            except Exception as e:
                logger.debug(f"Error parsing calendar row: {e}")
                continue

        return catalysts

    @staticmethod
    def _convert_ff_time_to_utc(time_str: str) -> str:
        """
        Convert ForexFactory time (Eastern Time) to UTC.
        ForexFactory displays times in US Eastern timezone.
        """
        if not time_str or time_str in ("", "All Day", "Tentative"):
            return time_str or "All Day"

        try:
            # Clean up the time string
            time_str = time_str.strip().upper()
            
            # Parse "8:30am" or "2:00pm" format
            match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", time_str)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2))
                ampm = match.group(3)

                if ampm == "PM" and hour != 12:
                    hour += 12
                elif ampm == "AM" and hour == 12:
                    hour = 0

                # Convert ET to UTC (ET = UTC-5, EDT = UTC-4)
                # Using EST as default — adjust for DST as needed
                et_time = datetime.now().replace(hour=hour, minute=minute)
                et_tz = ZoneInfo("America/New_York")
                utc_tz = ZoneInfo("UTC")
                et_aware = et_time.replace(tzinfo=et_tz)
                utc_time = et_aware.astimezone(utc_tz)
                return utc_time.strftime("%H:%M")
        except Exception:
            pass

        return time_str

    # ─────────────────────────────────────────────────────────────────
    #  CATALYST PROXIMITY CHECK — IS A BOMB ABOUT TO GO OFF?
    # ─────────────────────────────────────────────────────────────────

    def is_catalyst_imminent(
        self, utc_now: Optional[datetime] = None
    ) -> tuple[bool, Optional[NewsCatalyst]]:
        """
        Check if a Red Folder catalyst is about to fire.
        
        Returns True if we are within the pre-event lockout window.
        When a catalyst is imminent:
          - NO new trades should be opened
          - The Trauma Filter should be ARMED
          - We prepare to trade the post-spike exhaustion
        
        Returns:
            (is_imminent, catalyst_details)
        """
        utc_now = utc_now or datetime.utcnow()
        lockout_minutes = self.config.pre_event_lockout_minutes

        for catalyst in self._catalysts:
            event_time = self._parse_catalyst_time(catalyst)
            if event_time is None:
                continue

            time_to_event = (event_time - utc_now).total_seconds()

            # Within pre-event lockout window
            if 0 < time_to_event <= lockout_minutes * 60:
                logger.info(
                    f"══╡ CATALYST IMMINENT — {catalyst.currency} "
                    f"{catalyst.event_title} in {time_to_event:.0f}s ╞══\n"
                    f"    Trading LOCKED OUT. Trauma Filter ARMING.\n"
                    f"    This is a pre-engineered volatility catalyst.\n"
                    f"    The algorithm will use this as cover for the stop hunt."
                )
                return (True, catalyst)

            # Within post-event window (Trauma Filter active zone)
            if -self.config.post_event_window_minutes * 60 <= time_to_event <= 0:
                logger.info(
                    f"══╡ CATALYST ACTIVE — {catalyst.currency} "
                    f"{catalyst.event_title} fired {abs(time_to_event):.0f}s ago ╞══\n"
                    f"    Trauma Filter is ACTIVE. Watching for exhaustion wick."
                )
                return (True, catalyst)

        return (False, None)

    def get_upcoming_catalysts(
        self, hours_ahead: int = 24
    ) -> List[NewsCatalyst]:
        """Get catalysts happening in the next N hours."""
        utc_now = datetime.utcnow()
        upcoming = []

        for catalyst in self._catalysts:
            event_time = self._parse_catalyst_time(catalyst)
            if event_time is None:
                continue

            time_diff = (event_time - utc_now).total_seconds()
            if 0 < time_diff <= hours_ahead * 3600:
                upcoming.append(catalyst)

        return upcoming

    def _parse_catalyst_time(
        self, catalyst: NewsCatalyst
    ) -> Optional[datetime]:
        """Parse catalyst event_time string into a datetime."""
        if catalyst.event_time in ("All Day", "Tentative", ""):
            return None

        try:
            parts = catalyst.event_time.split(":")
            hour = int(parts[0])
            minute = int(parts[1])
            return catalyst.event_date.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
        except (ValueError, IndexError):
            return None

    # ─────────────────────────────────────────────────────────────────
    #  AUTO-REFRESH LOOP
    # ─────────────────────────────────────────────────────────────────

    async def auto_refresh_loop(self):
        """
        Background task that periodically re-scrapes ForexFactory.
        Runs every `scrape_interval_minutes` to ensure we have
        the latest Red Folder events for the current and next day.
        """
        while True:
            try:
                # Scrape today
                await self.scrape_red_folder_events()

                # Also scrape tomorrow to catch overnight events
                tomorrow = datetime.utcnow() + timedelta(days=1)
                tomorrow_catalysts = await self.scrape_red_folder_events(tomorrow)
                self._catalysts.extend(tomorrow_catalysts)

                # De-duplicate
                seen = set()
                unique = []
                for c in self._catalysts:
                    key = f"{c.currency}_{c.event_title}_{c.event_time}_{c.event_date}"
                    if key not in seen:
                        seen.add(key)
                        unique.append(c)
                self._catalysts = unique

            except Exception as e:
                logger.error(f"Auto-refresh failed: {e}")

            try:
                await asyncio.sleep(self.config.scrape_interval_minutes * 60)
            except asyncio.CancelledError:
                break
