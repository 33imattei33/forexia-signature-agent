"""
╔══════════════════════════════════════════════════════════════════════╗
║         FOREXIA SIGNATURE AGENT — SETTINGS MANAGER                  ║
║    Persistent configuration for broker, risk, and agent settings     ║
╚══════════════════════════════════════════════════════════════════════╝

Settings are stored in a JSON file and can be modified via the
Settings UI in the frontend dashboard. Changes take effect immediately.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field

logger = logging.getLogger("forexia.settings")

SETTINGS_FILE = Path(__file__).parent.parent / "settings.json"


class BrokerSettings(BaseModel):
    """MT4/MT5 broker connection settings."""
    platform: str = Field(default="remote_mt5", description="mt4, mt5, or remote_mt5")
    login: int = Field(default=0, description="Account login number")
    password: str = Field(default="", description="Account password")
    server: str = Field(default="", description="Broker server name")
    mt5_path: str = Field(default="", description="Path to MT5 terminal (optional)")
    # MT4-specific ZeroMQ settings
    zmq_host: str = Field(default="tcp://127.0.0.1", description="ZeroMQ host for MT4")
    zmq_push_port: int = Field(default=32768, description="ZeroMQ push port")
    zmq_pull_port: int = Field(default=32769, description="ZeroMQ pull port")
    # Remote MT5 Server settings (cross-platform — self-hosted)
    remote_mt5_url: str = Field(default="", description="URL of the MT5 Remote Server (e.g. http://192.168.1.10:8089)")
    remote_mt5_auth_key: str = Field(default="change_me", description="Auth key for the remote MT5 server")
    # MatchTrader settings (cross-platform — broker REST API)
    matchtrader_url: str = Field(default="", description="MatchTrader API base URL")
    matchtrader_login: str = Field(default="", description="MatchTrader email address")
    matchtrader_password: str = Field(default="", description="MatchTrader account password")
    matchtrader_partner_id: str = Field(default="", description="Broker partner ID (auto-discovered if empty, E8 Markets = 2)")


class RiskSettings(BaseModel):
    """Risk management parameters."""
    lot_per_100_equity: float = Field(default=0.01, description="Lots per $100 equity")
    max_risk_percent: float = Field(default=2.0, description="Max risk % per trade")
    max_lot_size: float = Field(default=0.10, description="Absolute max lot size per order")
    stop_loss_buffer_pips: float = Field(default=3.0, description="Pips beyond stop hunt wick")
    take_profit_ratio: float = Field(default=3.0, description="Minimum R:R ratio")
    max_concurrent_trades: int = Field(default=3, description="Max open positions")
    max_daily_loss_percent: float = Field(default=5.0, description="Daily loss circuit breaker %")
    max_spread_pips: float = Field(default=3.0, description="Max spread to accept")


class AgentSettings(BaseModel):
    """Agent behavior settings."""
    auto_trade: bool = Field(default=False, description="Auto-execute signals above threshold")
    min_confidence: float = Field(default=0.6, description="Min confidence to auto-trade")
    webhook_secret: str = Field(default="change_me", description="Webhook auth token")
    pairs: list = Field(
        default=["EURUSD", "GBPUSD", "USDCHF", "USDJPY"],
        description="Pairs to monitor"
    )
    default_timeframe: str = Field(default="M15", description="Default chart timeframe")
    news_scraping_enabled: bool = Field(default=True, description="Enable ForexFactory scraping")
    news_scrape_interval_min: int = Field(default=60, description="News scrape interval (minutes)")


class ForexiaSettings(BaseModel):
    """Master settings container."""
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    last_modified: str = Field(default="")

    def save(self):
        """Persist settings to disk."""
        self.last_modified = datetime.now(timezone.utc).isoformat()
        SETTINGS_FILE.write_text(
            self.model_dump_json(indent=2),
            encoding="utf-8"
        )
        logger.info(f"Settings saved to {SETTINGS_FILE}")

    @classmethod
    def load(cls) -> "ForexiaSettings":
        """Load settings from disk, or return defaults."""
        if SETTINGS_FILE.exists():
            try:
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                settings = cls(**data)
                logger.info(f"Settings loaded from {SETTINGS_FILE}")
                return settings
            except Exception as e:
                logger.warning(f"Failed to load settings, using defaults: {e}")
        return cls()

    def to_safe_dict(self) -> Dict[str, Any]:
        """Return settings with password masked for frontend display."""
        data = self.model_dump()
        if data["broker"]["password"]:
            data["broker"]["password"] = "••••••••"
        if data["broker"]["matchtrader_password"]:
            data["broker"]["matchtrader_password"] = "••••••••"
        return data


# Global settings instance
SETTINGS = ForexiaSettings.load()
