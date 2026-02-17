"""
FOREXIA — MT5 Multi-Account System
===================================

Multi-account prop firm trading with Signature Trade V2 strategy.

Modules:
  - account_manager:    Multi-MT5 terminal management + drawdown monitoring
  - market_adapter:     FX vs NASDAQ handling (trade windows, SL, order types)
  - prop_risk_manager:  Prop firm compliance (daily loss, trailing DD, news)
  - signature_v2:       Wedge + Liquidity Grab detector (NO FVG)
  - multi_orchestrator: Main loop tying everything together
"""

from backend.mt5_multi.account_manager import (
    MultiAccountManager,
    AccountConfig,
    PropFirmType,
    PropFirmRules,
    PROP_FIRM_PRESETS,
    AccountTracker,
)
from backend.mt5_multi.market_adapter import (
    MarketAdapter,
    MarketType,
    MarketProfile,
)
from backend.mt5_multi.prop_risk_manager import (
    PropFirmRiskManager,
    RiskVerdict,
)
from backend.mt5_multi.signature_v2 import (
    SignatureTradeV2,
    SignalPhase,
    SignatureSignal,
    WedgePattern,
    StopHunt,
)
from backend.mt5_multi.multi_orchestrator import (
    MultiAccountOrchestrator,
)

__all__ = [
    "MultiAccountManager",
    "AccountConfig",
    "PropFirmType",
    "PropFirmRules",
    "PROP_FIRM_PRESETS",
    "AccountTracker",
    "MarketAdapter",
    "MarketType",
    "MarketProfile",
    "PropFirmRiskManager",
    "RiskVerdict",
    "SignatureTradeV2",
    "SignalPhase",
    "SignatureSignal",
    "WedgePattern",
    "StopHunt",
    "MultiAccountOrchestrator",
]
