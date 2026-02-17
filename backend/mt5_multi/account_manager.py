"""
╔══════════════════════════════════════════════════════════════════════╗
║    FOREXIA — MT5 MULTI-ACCOUNT MANAGER                              ║
║    Run the Signature Trade across APEX, GetLeveraged, DNA Funded     ║
╚══════════════════════════════════════════════════════════════════════╝

This module manages multiple MT5 prop firm accounts simultaneously.
Each account gets its own MT5 terminal connection, risk limits,
and independent trade tracking.

Architecture:
  ┌─────────────────────────────────────────────────────┐
  │              MultiAccountManager                     │
  │  ┌──────────┐ ┌──────────────┐ ┌──────────────────┐ │
  │  │ APEX     │ │ GetLeveraged │ │ DNA Funded       │ │
  │  │ (bridge) │ │ (bridge)     │ │ (bridge)         │ │
  │  └──────────┘ └──────────────┘ └──────────────────┘ │
  │             ↓            ↓             ↓             │
  │          PropFirmRiskManager (per-account)           │
  └─────────────────────────────────────────────────────┘
"""

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum

logger = logging.getLogger("forexia.multi_account")


# ─────────────────────────────────────────────────────────────────────
#  PROP FIRM DEFINITIONS
# ─────────────────────────────────────────────────────────────────────

class PropFirmType(str, Enum):
    """Supported prop firm types with their specific rules."""
    APEX = "APEX"
    GET_LEVERAGED = "GET_LEVERAGED"
    DNA_FUNDED = "DNA_FUNDED"
    E8_MARKETS = "E8_MARKETS"
    GENERIC_MT5 = "GENERIC_MT5"


@dataclass
class PropFirmRules:
    """
    Codified prop firm constraints.
    Every prop firm has different rules — violate them and you're out.
    """
    firm_type: PropFirmType
    daily_loss_limit_pct: float = 5.0       # Max daily drawdown %
    max_trailing_dd_pct: float = 6.0        # Max trailing drawdown % (APEX-style)
    max_total_dd_pct: float = 10.0          # Max total drawdown %
    max_positions: int = 3                  # Max concurrent trades
    lot_per_10k: float = 0.01              # 0.01 lots per $10k equity (FX)
    nasdaq_contract_per_10k: float = 0.1    # Point-value equiv for NQ
    use_trailing_dd: bool = False           # APEX uses trailing DD
    weekend_holding: bool = False           # Can we hold over weekend?
    news_lockout_minutes: int = 5           # Minutes before/after news = no trade
    max_lot_size: float = 5.0              # Absolute max lot size
    min_lot_size: float = 0.01             # Min lot size
    friday_close_utc: int = 20              # Close all by this hour on Friday


# Pre-configured prop firm rule sets
PROP_FIRM_PRESETS: Dict[PropFirmType, PropFirmRules] = {
    PropFirmType.APEX: PropFirmRules(
        firm_type=PropFirmType.APEX,
        daily_loss_limit_pct=3.0,
        max_trailing_dd_pct=6.0,
        max_total_dd_pct=8.0,
        max_positions=5,
        use_trailing_dd=True,          # APEX uses trailing drawdown
        weekend_holding=False,
        news_lockout_minutes=5,
        friday_close_utc=20,
    ),
    PropFirmType.GET_LEVERAGED: PropFirmRules(
        firm_type=PropFirmType.GET_LEVERAGED,
        daily_loss_limit_pct=5.0,
        max_trailing_dd_pct=0,         # No trailing DD
        max_total_dd_pct=10.0,
        max_positions=5,
        use_trailing_dd=False,
        weekend_holding=True,
        news_lockout_minutes=2,
        friday_close_utc=21,
    ),
    PropFirmType.DNA_FUNDED: PropFirmRules(
        firm_type=PropFirmType.DNA_FUNDED,
        daily_loss_limit_pct=5.0,
        max_trailing_dd_pct=0,
        max_total_dd_pct=10.0,
        max_positions=3,
        use_trailing_dd=False,
        weekend_holding=False,
        news_lockout_minutes=5,
        friday_close_utc=20,
    ),
    PropFirmType.E8_MARKETS: PropFirmRules(
        firm_type=PropFirmType.E8_MARKETS,
        daily_loss_limit_pct=5.0,
        max_trailing_dd_pct=0,
        max_total_dd_pct=8.0,
        max_positions=3,
        use_trailing_dd=False,
        weekend_holding=False,
        news_lockout_minutes=5,
        friday_close_utc=18,
    ),
    PropFirmType.GENERIC_MT5: PropFirmRules(
        firm_type=PropFirmType.GENERIC_MT5,
        daily_loss_limit_pct=5.0,
        max_trailing_dd_pct=0,
        max_total_dd_pct=10.0,
        max_positions=3,
        use_trailing_dd=False,
        weekend_holding=True,
        news_lockout_minutes=5,
        friday_close_utc=21,
    ),
}


# ─────────────────────────────────────────────────────────────────────
#  ACCOUNT CONFIGURATION
# ─────────────────────────────────────────────────────────────────────

@dataclass
class AccountConfig:
    """
    Configuration for a single prop firm MT5 account.
    
    If the prop firm uses a bridge (e.g. APEX → Rithmic → MT5),
    set mt5_path to the specific terminal installation path.
    """
    account_id: str                         # Unique label: "APEX_1", "GL_1", etc.
    firm_type: PropFirmType = PropFirmType.GENERIC_MT5
    login: int = 0                          # MT5 login number
    password: str = ""
    server: str = ""
    mt5_path: Optional[str] = None          # Path to specific MT5 terminal
    enabled: bool = True                    # Can toggle accounts on/off
    symbols: List[str] = field(default_factory=lambda: [
        "EURUSD", "GBPUSD", "USDCHF", "USDJPY"
    ])
    custom_rules: Optional[PropFirmRules] = None  # Override preset rules


# ─────────────────────────────────────────────────────────────────────
#  ACCOUNT STATE TRACKER
# ─────────────────────────────────────────────────────────────────────

@dataclass
class AccountTracker:
    """
    Per-account state tracking for drawdown monitoring.
    Updated in real-time by the heartbeat loop.
    """
    account_id: str
    firm_type: PropFirmType
    # Balance tracking
    starting_balance: float = 0.0           # Balance at start of day
    high_water_mark: float = 0.0            # Highest equity (for trailing DD)
    current_balance: float = 0.0
    current_equity: float = 0.0
    # Drawdown state
    daily_pnl: float = 0.0
    daily_loss_limit_hit: bool = False
    trailing_dd_limit_hit: bool = False
    total_dd_limit_hit: bool = False
    # Trade tracking
    trades_today: int = 0
    open_positions: int = 0
    # Connection
    connected: bool = False
    last_heartbeat: Optional[datetime] = None


# ─────────────────────────────────────────────────────────────────────
#  MULTI-ACCOUNT MANAGER
# ─────────────────────────────────────────────────────────────────────

class MultiAccountManager:
    """
    Manages multiple MT5 prop firm accounts simultaneously.
    
    Each account gets:
      - Its own MT5 terminal connection (via unique mt5_path)
      - Independent drawdown tracking (daily, trailing, total)
      - Per-account risk limits based on prop firm rules
      - Independent trade execution and monitoring
    
    Usage:
        manager = MultiAccountManager()
        manager.add_account(AccountConfig(...))
        manager.add_account(AccountConfig(...))
        await manager.connect_all()
        
        # Execute on all accounts
        results = await manager.execute_on_all(signal)
        
        # Or execute on specific account
        result = await manager.execute_on_account("APEX_1", signal)
    """

    def __init__(self):
        self._accounts: Dict[str, AccountConfig] = {}
        self._trackers: Dict[str, AccountTracker] = {}
        self._bridges: Dict[str, Any] = {}  # MT5Bridge or MatchTraderBridge instances
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}
        self._running = False

    # ─────────────────────── ACCOUNT MANAGEMENT ───────────────────────

    def add_account(self, config: AccountConfig):
        """Register a prop firm account."""
        self._accounts[config.account_id] = config
        rules = config.custom_rules or PROP_FIRM_PRESETS.get(
            config.firm_type, PROP_FIRM_PRESETS[PropFirmType.GENERIC_MT5]
        )
        self._trackers[config.account_id] = AccountTracker(
            account_id=config.account_id,
            firm_type=config.firm_type,
        )
        logger.info(
            f"Account registered: {config.account_id} "
            f"({config.firm_type.value}) — "
            f"Login: {config.login}, Server: {config.server}"
        )

    def remove_account(self, account_id: str):
        """Remove an account."""
        self._accounts.pop(account_id, None)
        self._trackers.pop(account_id, None)
        bridge = self._bridges.pop(account_id, None)
        task = self._heartbeat_tasks.pop(account_id, None)
        if task:
            task.cancel()
        logger.info(f"Account removed: {account_id}")

    def get_account_ids(self) -> List[str]:
        """Get all registered account IDs."""
        return list(self._accounts.keys())

    def get_enabled_accounts(self) -> List[str]:
        """Get only enabled account IDs."""
        return [
            aid for aid, cfg in self._accounts.items()
            if cfg.enabled
        ]

    def get_tracker(self, account_id: str) -> Optional[AccountTracker]:
        """Get real-time state for an account."""
        return self._trackers.get(account_id)

    def get_rules(self, account_id: str) -> PropFirmRules:
        """Get prop firm rules for an account."""
        cfg = self._accounts.get(account_id)
        if not cfg:
            return PROP_FIRM_PRESETS[PropFirmType.GENERIC_MT5]
        return cfg.custom_rules or PROP_FIRM_PRESETS.get(
            cfg.firm_type, PROP_FIRM_PRESETS[PropFirmType.GENERIC_MT5]
        )

    def get_bridge(self, account_id: str):
        """Get the broker bridge for an account."""
        return self._bridges.get(account_id)

    # ─────────────────────── CONNECTION ───────────────────────

    async def connect_all(self) -> Dict[str, bool]:
        """
        Connect all enabled accounts.
        Each account gets its own MT5 terminal or MatchTrader session.
        
        Returns dict of {account_id: connected_bool}
        """
        self._running = True
        results = {}

        for account_id in self.get_enabled_accounts():
            try:
                connected = await self._connect_account(account_id)
                results[account_id] = connected
            except Exception as e:
                logger.error(f"Failed to connect {account_id}: {e}")
                results[account_id] = False

        connected_count = sum(1 for v in results.values() if v)
        logger.info(
            f"╔══════════════════════════════════════════════════════╗\n"
            f"║  MULTI-ACCOUNT: {connected_count}/{len(results)} accounts connected  ║\n"
            f"╚══════════════════════════════════════════════════════╝"
        )
        return results

    async def _connect_account(self, account_id: str) -> bool:
        """Connect a single account and start its monitoring."""
        config = self._accounts.get(account_id)
        if not config:
            return False

        # Determine bridge type from settings
        # If it's E8 Markets or has matchtrader config, use MatchTrader bridge
        # Otherwise use MT5 bridge
        if config.firm_type == PropFirmType.E8_MARKETS:
            from backend.bridges.matchtrader_bridge import MatchTraderBridge
            bridge = MatchTraderBridge()
            bridge.configure(
                base_url=config.server,
                login=config.password.split(":")[0] if ":" in config.password else str(config.login),
                password=config.password.split(":")[-1] if ":" in config.password else config.password,
                partner_id=str(config.login),
            )
        else:
            from backend.bridges.mt5_bridge import MT5Bridge
            bridge = MT5Bridge()
            bridge.configure(
                login=config.login,
                password=config.password,
                server=config.server,
                mt5_path=config.mt5_path,
            )

        connected = await bridge.connect()
        if connected:
            self._bridges[account_id] = bridge
            tracker = self._trackers[account_id]
            tracker.connected = True

            # Get initial account state
            account_state = await bridge.get_account_state()
            tracker.current_balance = account_state.balance
            tracker.current_equity = account_state.equity
            tracker.starting_balance = account_state.balance
            tracker.high_water_mark = max(
                account_state.equity, account_state.balance
            )
            tracker.last_heartbeat = datetime.now(timezone.utc)

            # Start monitoring
            self._heartbeat_tasks[account_id] = asyncio.create_task(
                self._account_heartbeat(account_id)
            )

            logger.info(
                f"✓ {account_id} CONNECTED — "
                f"Balance: ${account_state.balance:.2f}, "
                f"Equity: ${account_state.equity:.2f}"
            )
            return True
        else:
            logger.warning(f"✗ {account_id} connection FAILED")
            return False

    async def disconnect_all(self):
        """Disconnect all accounts."""
        self._running = False

        for account_id in list(self._bridges.keys()):
            try:
                task = self._heartbeat_tasks.pop(account_id, None)
                if task:
                    task.cancel()
                bridge = self._bridges.pop(account_id, None)
                if bridge:
                    await bridge.disconnect()
                tracker = self._trackers.get(account_id)
                if tracker:
                    tracker.connected = False
                logger.info(f"Disconnected: {account_id}")
            except Exception as e:
                logger.error(f"Error disconnecting {account_id}: {e}")

    # ─────────────────────── DRAWDOWN MONITORING ───────────────────────

    async def _account_heartbeat(self, account_id: str):
        """
        Per-account monitoring loop (every 5 seconds).
        Tracks drawdown in real-time and triggers emergency close
        if any prop firm limit is breached.
        """
        while self._running:
            try:
                await asyncio.sleep(5)

                bridge = self._bridges.get(account_id)
                tracker = self._trackers.get(account_id)
                if not bridge or not tracker or not bridge.is_connected:
                    continue

                account_state = await bridge.get_account_state()
                tracker.current_balance = account_state.balance
                tracker.current_equity = account_state.equity
                tracker.open_positions = account_state.open_trades
                tracker.last_heartbeat = datetime.now(timezone.utc)

                # Update high water mark for trailing DD
                if account_state.equity > tracker.high_water_mark:
                    tracker.high_water_mark = account_state.equity

                # Calculate P&L
                tracker.daily_pnl = account_state.equity - tracker.starting_balance

                rules = self.get_rules(account_id)

                # ── CHECK 1: Daily Loss Limit ──
                daily_loss_limit = tracker.starting_balance * (rules.daily_loss_limit_pct / 100)
                if tracker.daily_pnl < 0 and abs(tracker.daily_pnl) >= daily_loss_limit:
                    if not tracker.daily_loss_limit_hit:
                        tracker.daily_loss_limit_hit = True
                        logger.warning(
                            f"🚨 {account_id} DAILY LOSS LIMIT — "
                            f"P&L: ${tracker.daily_pnl:.2f} / "
                            f"Limit: -${daily_loss_limit:.2f}"
                        )
                        await self._emergency_close(account_id, "DAILY_LOSS_LIMIT")

                # ── CHECK 2: Trailing Drawdown (APEX-style) ──
                if rules.use_trailing_dd and rules.max_trailing_dd_pct > 0:
                    trailing_dd = tracker.high_water_mark - account_state.equity
                    trailing_limit = tracker.high_water_mark * (rules.max_trailing_dd_pct / 100)
                    if trailing_dd >= trailing_limit:
                        if not tracker.trailing_dd_limit_hit:
                            tracker.trailing_dd_limit_hit = True
                            logger.warning(
                                f"🚨 {account_id} TRAILING DD LIMIT — "
                                f"DD: ${trailing_dd:.2f} / "
                                f"Limit: ${trailing_limit:.2f}"
                            )
                            await self._emergency_close(account_id, "TRAILING_DD")

                # ── CHECK 3: Total Drawdown ──
                if rules.max_total_dd_pct > 0:
                    total_dd = tracker.starting_balance - account_state.equity
                    total_limit = tracker.starting_balance * (rules.max_total_dd_pct / 100)
                    if total_dd > 0 and total_dd >= total_limit:
                        if not tracker.total_dd_limit_hit:
                            tracker.total_dd_limit_hit = True
                            logger.warning(
                                f"🚨 {account_id} TOTAL DD LIMIT — "
                                f"DD: ${total_dd:.2f} / "
                                f"Limit: ${total_limit:.2f}"
                            )
                            await self._emergency_close(account_id, "TOTAL_DD")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error for {account_id}: {e}")
                await asyncio.sleep(5)

    async def _emergency_close(self, account_id: str, reason: str):
        """Emergency close all positions on an account."""
        bridge = self._bridges.get(account_id)
        if not bridge:
            return

        logger.warning(
            f"═══ EMERGENCY CLOSE: {account_id} — {reason} ═══"
        )

        try:
            count = await bridge.close_all_trades()
            logger.info(f"Emergency close: {count} positions closed on {account_id}")
        except Exception as e:
            logger.error(f"Emergency close FAILED for {account_id}: {e}")

    # ─────────────────────── TRADE EXECUTION ───────────────────────

    def can_trade(self, account_id: str) -> tuple:
        """
        Check if an account is allowed to take a new trade.
        
        Returns: (allowed: bool, reason: str)
        """
        tracker = self._trackers.get(account_id)
        if not tracker:
            return (False, "Account not found")
        if not tracker.connected:
            return (False, "Account not connected")
        if tracker.daily_loss_limit_hit:
            return (False, "Daily loss limit hit — no more trades today")
        if tracker.trailing_dd_limit_hit:
            return (False, "Trailing drawdown limit hit — account locked")
        if tracker.total_dd_limit_hit:
            return (False, "Total drawdown limit hit — account locked")

        rules = self.get_rules(account_id)
        if tracker.open_positions >= rules.max_positions:
            return (False, f"Max positions reached: {tracker.open_positions}/{rules.max_positions}")

        return (True, "Trade allowed")

    async def execute_on_account(
        self,
        account_id: str,
        symbol: str,
        direction: str,
        lot_size: float,
        stop_loss: float,
        take_profit: float,
        comment: str = "FOREXIA_SIG"
    ) -> Optional[int]:
        """
        Execute a trade on a specific account with prop firm compliance.
        
        Returns ticket number or None.
        """
        # Pre-trade checks
        allowed, reason = self.can_trade(account_id)
        if not allowed:
            logger.warning(f"[{account_id}] Trade BLOCKED: {reason}")
            return None

        bridge = self._bridges.get(account_id)
        if not bridge:
            return None

        rules = self.get_rules(account_id)

        # Enforce lot size limits
        lot_size = max(rules.min_lot_size, min(lot_size, rules.max_lot_size))

        from backend.models.schemas import TradeDirection
        dir_enum = TradeDirection.BUY if direction == "BUY" else TradeDirection.SELL

        ticket = await bridge.execute_market_order(
            symbol=symbol,
            direction=dir_enum,
            lot_size=lot_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            comment=f"{comment}_{account_id}",
        )

        if ticket:
            tracker = self._trackers.get(account_id)
            if tracker:
                tracker.trades_today += 1
                tracker.open_positions += 1
            logger.info(
                f"[{account_id}] EXECUTED: {direction} {lot_size} {symbol} "
                f"SL={stop_loss:.5f} TP={take_profit:.5f} — Ticket #{ticket}"
            )
        else:
            logger.error(f"[{account_id}] Execution FAILED: {direction} {lot_size} {symbol}")

        return ticket

    async def execute_on_all(
        self,
        symbol: str,
        direction: str,
        lot_size: float,
        stop_loss: float,
        take_profit: float,
        comment: str = "FOREXIA_SIG",
        scale_by_equity: bool = True,
    ) -> Dict[str, Optional[int]]:
        """
        Execute the same signal across all enabled accounts.
        
        If scale_by_equity is True, lot_size is adjusted per account based
        on their equity and prop firm rules.
        """
        results = {}

        for account_id in self.get_enabled_accounts():
            try:
                actual_lots = lot_size
                if scale_by_equity:
                    tracker = self._trackers.get(account_id)
                    rules = self.get_rules(account_id)
                    if tracker and tracker.current_equity > 0:
                        # Scale lots based on per-account equity
                        actual_lots = round(
                            (tracker.current_equity / 10000) * rules.lot_per_10k, 2
                        )
                        actual_lots = max(rules.min_lot_size, min(actual_lots, rules.max_lot_size))

                ticket = await self.execute_on_account(
                    account_id=account_id,
                    symbol=symbol,
                    direction=direction,
                    lot_size=actual_lots,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    comment=comment,
                )
                results[account_id] = ticket
            except Exception as e:
                logger.error(f"Execute error on {account_id}: {e}")
                results[account_id] = None

        return results

    # ─────────────────────── DAILY RESET ───────────────────────

    def daily_reset(self):
        """Reset daily counters for all accounts."""
        for tracker in self._trackers.values():
            tracker.daily_pnl = 0.0
            tracker.daily_loss_limit_hit = False
            tracker.trades_today = 0
            # Update starting balance
            tracker.starting_balance = tracker.current_balance
        logger.info("Multi-Account daily reset complete")

    # ─────────────────────── STATUS ───────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Get status of all accounts for the dashboard."""
        accounts = {}
        for account_id, tracker in self._trackers.items():
            config = self._accounts.get(account_id)
            rules = self.get_rules(account_id)
            accounts[account_id] = {
                "firm_type": tracker.firm_type.value,
                "connected": tracker.connected,
                "enabled": config.enabled if config else False,
                "balance": round(tracker.current_balance, 2),
                "equity": round(tracker.current_equity, 2),
                "daily_pnl": round(tracker.daily_pnl, 2),
                "high_water_mark": round(tracker.high_water_mark, 2),
                "open_positions": tracker.open_positions,
                "trades_today": tracker.trades_today,
                "daily_loss_limit_hit": tracker.daily_loss_limit_hit,
                "trailing_dd_limit_hit": tracker.trailing_dd_limit_hit,
                "total_dd_limit_hit": tracker.total_dd_limit_hit,
                "symbols": config.symbols if config else [],
                "max_positions": rules.max_positions,
                "daily_loss_limit_pct": rules.daily_loss_limit_pct,
                "trailing_dd_pct": rules.max_trailing_dd_pct if rules.use_trailing_dd else None,
            }
        return {
            "total_accounts": len(self._accounts),
            "connected_accounts": sum(1 for t in self._trackers.values() if t.connected),
            "total_equity": round(sum(t.current_equity for t in self._trackers.values()), 2),
            "total_daily_pnl": round(sum(t.daily_pnl for t in self._trackers.values()), 2),
            "accounts": accounts,
        }
