# FOREXIA SIGNATURE AGENT

> An elite institutional Python trading bot modeled after Dylan Shilts' methodology.
> Trades market manipulation, not retail trends.
> Powered by Google Gemini AI with autonomous execution.

```
NO FVG · NO RSI · NO MACD · NO Moving Average Crossovers · NO Retail Indicators
```

---

## Features at a Glance

- **AI-Powered Trading** — Google Gemini 2.5 Pro analyzes markets and executes trades autonomously
- **Multi-Broker** — MatchTrader (E8 Markets), MetaTrader 4 (ZeroMQ), MetaTrader 5, Remote MT5
- **Multi-Account** — Run simultaneously across APEX, GetLeveraged, DNA Funded, E8 Markets, and any Generic MT5 prop firm
- **Prop Firm Compliance** — Per-account risk rules: daily loss limits, trailing drawdown, news lockout, Friday deadlines
- **TradingView Charts** — Embedded Advanced Chart widgets with multi-timeframe grid (all 8 TFs at once)
- **Market Structure Engine** — Trend detection, order blocks, psychological levels, liquidity zones, session ranges
- **Real-Time Dashboard** — React/Vite/Tailwind frontend with live positions, trade history, AI analysis, settings panel
- **Complete API** — 40+ REST endpoints for full programmatic control

---

## Architecture

```
┌──────────────────┐       ┌──────────────────────────────────────────────┐
│  TradingView     │──────▶│           FastAPI Server (Orchestrator)      │
│  Webhook Alerts  │ POST  │                                              │
└──────────────────┘       │  ┌──────────────────────────────────────┐   │
                           │  │         Gemini AI Agent               │   │
┌──────────────────┐       │  │   (gemini-2.5-pro / 2.5-flash)       │   │
│  React Dashboard │◀─────▶│  │   Autonomous Scan + Execution        │   │
│  (Vite + TW CSS) │ REST  │  └──────────────────────────────────────┘   │
└──────────────────┘       │                    │                         │
                           │  ┌─────────────────┼──────────────────┐     │
                           │  │                 │                  │     │
                           │  ▼                 ▼                  ▼     │
                           │  ┌────────┐ ┌───────────┐ ┌───────────┐   │
                           │  │Hegelian│ │ Signature │ │ Weekly    │   │
                           │  │Dialect.│ │ Trade     │ │ 5-Act     │   │
                           │  └────────┘ └───────────┘ └───────────┘   │
                           │  ┌────────┐ ┌───────────┐ ┌───────────┐   │
                           │  │ Market │ │ Trauma    │ │ Candle    │   │
                           │  │Structure│ │ Filter   │ │ Scanner   │   │
                           │  └────────┘ └───────────┘ └───────────┘   │
                           │  ┌────────┐ ┌───────────┐ ┌───────────┐   │
                           │  │News    │ │Multi-Pair │ │ Risk      │   │
                           │  │Catalyst│ │Sync       │ │ Manager   │   │
                           │  └────────┘ └───────────┘ └───────────┘   │
                           └──────────────────┬───────────────────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
              ┌─────▼──────┐         ┌────────▼────────┐       ┌───────▼───────┐
              │ MatchTrader│         │  MetaTrader 5   │       │  MetaTrader 4 │
              │ REST API   │         │  (MT5 / Remote) │       │  (ZeroMQ EA)  │
              │ (E8, etc.) │         │  APEX, GL, DNA  │       │               │
              └────────────┘         └─────────────────┘       └───────────────┘
```

---

## Broker Integrations

| Bridge | Platform | Connection | Use Case |
|--------|----------|------------|----------|
| **MatchTrader** | MatchTrader Platform REST API | HTTPS (cross-platform) | E8 Markets and any MatchTrader-based broker |
| **MT4** | MetaTrader 4 | ZeroMQ (localhost) | Any MT4 broker via Expert Advisor |
| **MT5** | MetaTrader 5 | Native Python API | Any MT5 broker (Windows with terminal) |
| **Remote MT5** | MetaTrader 5 | HTTP REST (self-hosted) | Cross-platform MT5 access without terminal |

### MatchTrader (Primary — E8 Markets)

Connects to any broker running on the MatchTrader platform via their official REST API. Works from macOS, Linux, and Windows — no MetaTrader terminal required.

- Full trading: open, close, modify positions
- Account data: balance, equity, margin, leverage
- Historical candles (all timeframes, up to 10,000 per request)
- Real-time quotations (bid/ask)
- Instrument discovery
- Auto token refresh (15-min sessions)

**Tested with:** E8 Markets (`https://mtr.e8markets.com`)

---

## Prop Firm Multi-Account Support

Run the Signature Trade strategy across **multiple prop firm accounts simultaneously**, each with its own risk compliance rules.

| Prop Firm | Type | Bridge | Status |
|-----------|------|--------|--------|
| **E8 Markets** | MatchTrader | `matchtrader_bridge.py` | ✅ Live |
| **APEX** | MT5 | `mt5_bridge.py` / `remote_mt5_bridge.py` | ✅ Ready |
| **GetLeveraged** | MT5 | `mt5_bridge.py` / `remote_mt5_bridge.py` | ✅ Ready |
| **DNA Funded** | MT5 | `mt5_bridge.py` / `remote_mt5_bridge.py` | ✅ Ready |
| **Generic MT5** | MT5 | Any MT5 bridge | ✅ Ready |

### Per-Account Prop Firm Risk Management

Each account gets independent risk enforcement:
- Daily loss limit (hard stop)
- Max trailing drawdown (APEX-style)
- News lockout (no trades N minutes before/after high-impact events)
- Position sizing (per-account equity × prop firm lot rules)
- Friday close deadline
- Max concurrent positions

```
Signal → PropFirmRiskManager.evaluate() → RiskVerdict → Execute / Block
```

---

## AI Integration — Google Gemini

The Gemini AI Agent is the brain of Forexia. It analyzes markets autonomously and executes trades when high-probability institutional setups are identified.

| Feature | Description |
|---------|-------------|
| **Model** | `gemini-2.5-pro` (best reasoning) or `gemini-2.5-flash` (fast + free) |
| **Market Analysis** | Real-time commentary for each scanned pair |
| **Strategy Validation** | Reviews rule-based engine signals before execution |
| **Market Regime Detection** | Trending, ranging, volatile, calm |
| **Multi-TF Narrative** | H1/H4/D1 context synthesis |
| **Risk Commentary** | Open position risk assessment |
| **Autonomous Execution** | Generates and executes trade signals independently |
| **Scan Frequency** | Every 150 seconds with deep analysis |

The AI works alongside the rule-based engine:
- Rule engine scans every 2 minutes (pattern detection pipeline)
- AI Agent scans every 2.5 minutes with deeper contextual analysis
- Both route through the risk manager for proper position sizing
- All safety guards apply: max trades, spread check, session gate, cooldown

### Market Structure Engine

Feeds concrete structural data into the AI prompt (no raw OHLC guessing):
- **Trend Detection** — Higher highs/lower lows, trend strength scoring
- **Order Blocks** — Institutional supply/demand zones
- **Psychological Levels** — Round numbers and key price levels
- **Liquidity Zones** — Buy-side and sell-side liquidity pools
- **Session Ranges** — Asian, London, New York high/low mapping
- **Volatility State** — ATR-based (low, normal, high, extreme)
- **Swing Structure** — Swing highs and swing lows identification

---

## Engines

| Engine | Purpose |
|--------|---------|
| **Gemini AI Agent** | Autonomous market analysis + trade execution via Google Gemini 2.5 Pro |
| **Market Structure** | Trend, order blocks, psychological levels, liquidity zones, session ranges |
| **Hegelian Dialectic** | Asian Problem → London Reaction → NY Solution cycle detection |
| **Signature Trade** | Wedge/Triangle → False Breakout → Stop Hunt → Exhaustion Reversal |
| **Weekly 5-Act** | Sun Connector → Mon Induction → Tue Accumulation → Wed Reversal → Thu Distribution → Fri Epilogue |
| **News Catalyst** | ForexFactory Red Folder scraper — event timing only, NO numbers |
| **Trauma Filter** | God Candle detection + post-spike exhaustion reversal |
| **Candlestick Scanner** | Railroad Tracks + Star patterns at psychological levels |
| **Multi-Pair Sync** | Dollar basket correlation verification (EUR, GBP, CHF, JPY) |
| **Risk Manager** | 0.01 lots per $100 equity, breakeven + trailing stop, daily circuit breaker |

---

## Dashboard (React Frontend)

Real-time trading dashboard built with React, Vite, and Tailwind CSS.

| Component | Description |
|-----------|-------------|
| **Account Panel** | Live balance, equity, free margin, leverage |
| **TradingView Charts** | Embedded Advanced Chart widgets — dark theme, all 9 pairs |
| **Multi-TF Grid** | All 8 timeframes displayed simultaneously (W1 → M1 top-down) |
| **Open Positions** | Live positions with P&L, SL/TP levels, position management |
| **Transaction History** | Full trade history with pagination, symbol filter, win-rate stats |
| **Auto Trade Bot** | Toggle auto-execution, trigger manual scans, view scan results |
| **Gemini AI Panel** | AI market analysis, regime detection, signal reviews, trade ideas |
| **Session Phase** | Current Hegelian phase (Asian/London/NY) with kill zone indicator |
| **Weekly Act Display** | Current weekly act (Connector → Induction → Accumulation → Reversal → Distribution → Epilogue) |
| **Induction Meter** | Real-time induction percentage for signature trade detection |
| **News Catalyst** | Upcoming high-impact Red Folder events |
| **Liquidity Panel** | Mapped liquidity zones and order blocks |
| **Settings Panel** | Full configuration UI — broker, risk, agent, AI settings |
| **Super Admin** | Advanced administration panel |
| **Trading Panel** | Manual trade entry with lot sizing |

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Google Gemini API key (free at [aistudio.google.com/apikey](https://aistudio.google.com/apikey))
- One of: MatchTrader account, MT4 terminal, MT5 terminal, or Remote MT5 server

### 1. Clone & Setup Backend

```bash
git clone https://github.com/33imattei33/forexia-signature-agent.git
cd forexia-signature-agent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env
```

### 2. Start Backend

```bash
python3 -m uvicorn backend.server:app --host 0.0.0.0 --port 8000
```

### 3. Setup & Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at `http://localhost:3000`

### 4. Configure via Settings UI

Open the dashboard → Settings tab and configure:
- **Broker**: MatchTrader URL, login credentials (or MT4/MT5 settings)
- **Risk**: Lot sizing, SL/TP parameters, breakeven/trailing settings
- **Agent**: Pairs to monitor, auto-trade toggle, Gemini API key

### 5. MatchTrader Setup (E8 Markets)

In Settings → Broker:
- Platform: `matchtrader`
- MatchTrader URL: `https://mtr.e8markets.com`
- Login: your email
- Password: your password
- Partner ID: leave empty (auto-discovered)

### 6. MT4 Expert Advisor (Optional)

The ZeroMQ EA template is embedded in `backend/bridges/mt4_bridge.py` as `MT4_EA_TEMPLATE`. To use:

1. Open MT4 → MetaEditor
2. Create new Expert Advisor
3. Paste the template code
4. Compile and attach to a chart
5. Ensure "Allow DLL imports" is checked

### 7. TradingView Webhook (Optional)

Point your TradingView alerts to:

```
POST http://YOUR_SERVER:8000/webhook
```

Payload format:
```json
{
  "action": "ANALYZE",
  "symbol": "EURUSD",
  "timeframe": "M15",
  "price": 1.08500,
  "source": "tradingview"
}
```

Actions: `ANALYZE` (auto-trade if confidence ≥ 60%), `FORCE_ENTRY`, `CLOSE`

---

## API Endpoints

### Core Dashboard
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/dashboard` | Full dashboard state |
| GET | `/api/account` | Account balance/equity/margin |
| GET | `/api/signals` | Active signals |
| GET | `/api/session` | Current session phase |
| GET | `/api/news` | Red Folder events |
| GET | `/api/liquidity` | Mapped liquidity zones |
| GET | `/api/multi-pair` | Dollar basket analysis |
| GET | `/api/instruments` | Available trading symbols |

### Trading
| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhook` | TradingView webhook receiver |
| POST | `/api/trade/open` | Open manual trade |
| POST | `/api/trade/close` | Close a single trade |
| POST | `/api/trade/modify` | Modify SL/TP on a trade |
| POST | `/api/close-all` | Emergency close all positions |
| GET | `/api/positions` | Open positions |
| GET | `/api/trades` | Recent trades |
| GET | `/api/trade-history` | Full trade history (pagination) |

### Charts & Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/candles` | Historical candle data (up to 10,000) |
| GET | `/api/chart/positions` | Position overlay data for charts |

### AI Agent
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ai/status` | Gemini AI agent status |
| GET | `/api/ai/analysis/{symbol}` | AI analysis for a specific pair |
| GET | `/api/ai/overview` | AI overview of all pairs |
| GET | `/api/ai/signal-reviews` | AI reviews of rule-based signals |
| GET | `/api/ai/trade-signals` | AI-generated trade signals |
| POST | `/api/ai/trade/{symbol}` | Trigger AI trade on a symbol |

### Bot Control
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/bot/auto-trade` | Toggle auto-trade on/off |
| POST | `/api/bot/scan` | Trigger manual scan cycle |
| GET | `/api/bot/status` | Bot scan status and results |

### Multi-Account (Prop Firms)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/multi/status` | All prop firm account statuses |
| POST | `/api/multi/start` | Start multi-account scanning |
| POST | `/api/multi/stop` | Stop multi-account scanning |
| POST | `/api/multi/scan` | Force scan across all accounts |
| POST | `/api/multi/add` | Add a new prop firm account |
| DELETE | `/api/multi/remove/{id}` | Remove a prop firm account |
| GET | `/api/multi/trades` | Trade log across all accounts |
| GET | `/api/multi/risk/{id}` | Risk status for an account |

### Settings & Admin
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings` | Current settings |
| POST | `/api/settings` | Update settings |
| POST | `/api/scrape-news` | Force news scrape |

---

## Risk Rules (Non-Negotiable)

1. **Lot size**: 0.01 per $100 equity — no exceptions
2. **Stop loss**: Beyond the stop hunt wick + 30 pip buffer — always
3. **Breakeven**: SL moves to entry + 1 pip after 6 pips profit
4. **Trailing stop**: Activates at 12 pips profit, trails 5 pips behind price
5. **Daily loss**: Circuit breaker at 5% account loss
6. **Max spread**: Rejects entries with spread > 2 pips
7. **Max concurrent**: 3 trades maximum
8. **No-trade days**: Sunday connector, Monday induction
9. **Primary targets**: Wednesday reversal, Thursday distribution
10. **Friday cutoff**: Close all positions by 18:00 UTC Friday
11. **Stale trade cleanup**: Close negative trades after 60 minutes (configurable)

---

## Traded Pairs

### ⭐ Star Pairs (Highest Priority)
| Pair | Description |
|------|-------------|
| GBPJPY | Primary — highest volatility JPY cross |
| USDJPY | Core JPY pair |
| EURJPY | Euro-Yen cross |

### Neutral Pairs
| Pair | Description |
|------|-------------|
| GBPUSD | Cable |
| EURUSD | Fiber |
| USDCHF | Swissy |
| EURAUD | Euro-Aussie |
| EURGBP | Euro-Pound |
| GBPAUD | Pound-Aussie |

---

## Project Structure

```
forexia-signature-agent/
├── backend/
│   ├── config.py                    # Master configuration (all dataclasses)
│   ├── settings.py                  # Persistent JSON settings + Settings UI models
│   ├── orchestrator.py              # Central nervous system — main scan loop
│   ├── server.py                    # FastAPI application (40+ endpoints)
│   ├── bridges/
│   │   ├── matchtrader_bridge.py    # MatchTrader Platform REST API (E8 Markets)
│   │   ├── mt4_bridge.py           # ZeroMQ MT4 bridge + EA template
│   │   ├── mt5_bridge.py           # Native MT5 Python bridge
│   │   └── remote_mt5_bridge.py    # Cross-platform remote MT5 via HTTP
│   ├── engines/
│   │   ├── gemini_advisor.py       # Google Gemini AI Agent (analysis + execution)
│   │   ├── market_structure.py     # Trend, OBs, psych levels, liquidity zones
│   │   ├── hegelian_engine.py      # 3-phase daily cycle (Asian→London→NY)
│   │   ├── signature_trade.py      # Wedge/Triangle pattern detector
│   │   ├── weekly_structure.py     # 5-Act weekly manipulation cycle
│   │   ├── trauma_filter.py        # God Candle + exhaustion reversal
│   │   ├── candle_scanner.py       # Railroad Tracks + Star patterns
│   │   ├── multi_pair_sync.py      # Dollar basket correlation
│   │   └── risk_manager.py         # Position sizing + validation + breakeven/trailing
│   ├── mt5_multi/
│   │   ├── account_manager.py      # Multi-account connection manager
│   │   ├── multi_orchestrator.py   # Multi-account scan → evaluate → execute loop
│   │   ├── prop_risk_manager.py    # Per-account prop firm risk compliance
│   │   ├── market_adapter.py       # FX vs index market handling
│   │   └── signature_v2.py         # V2 pattern detector for multi-account
│   ├── scrapers/
│   │   └── news_catalyst.py        # ForexFactory Red Folder scraper
│   └── models/
│       └── schemas.py              # Pydantic models + enums
├── frontend/
│   ├── vite.config.js              # Vite config with API proxy to :8000
│   ├── tailwind.config.js          # Forexia dark theme config
│   └── src/
│       ├── App.jsx                 # Main app with tab navigation
│       ├── hooks/
│       │   ├── useForexia.js       # Dashboard data hook (polling)
│       │   └── useAdmin.js         # Admin panel hook
│       └── components/
│           ├── AccountPanel.jsx         # Balance, equity, margin
│           ├── LiveChart.jsx            # TradingView charts (single + multi-TF grid)
│           ├── OpenPositions.jsx        # Live positions with P&L
│           ├── TransactionHistory.jsx   # Full history + pagination + stats
│           ├── AutoTradeBot.jsx         # Bot controls + scan results
│           ├── GeminiAdvisorPanel.jsx   # AI analysis + signal reviews
│           ├── SessionPhasePanel.jsx    # Hegelian phase indicator
│           ├── WeeklyActDisplay.jsx     # Weekly act tracker
│           ├── InductionMeter.jsx       # Induction percentage gauge
│           ├── NewsCatalystPanel.jsx    # Upcoming red folder events
│           ├── LiquidityPanel.jsx       # Liquidity zones display
│           ├── SettingsPanel.jsx        # Full settings configuration UI
│           ├── TradingPanel.jsx         # Manual trade entry
│           └── SuperAdmin.jsx           # Advanced admin panel
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.10+, FastAPI, Uvicorn, Pydantic v2 |
| **AI** | Google Gemini 2.5 Pro / 2.5 Flash via REST API |
| **Frontend** | React 18, Vite 6, Tailwind CSS |
| **Charts** | TradingView Advanced Chart (embedded widgets) |
| **MatchTrader** | curl_cffi (TLS fingerprint bypass) |
| **MT4 Bridge** | PyZMQ (ZeroMQ) |
| **MT5 Bridge** | MetaTrader5 Python package + custom HTTP wrapper |
| **Scraping** | httpx, BeautifulSoup4 (ForexFactory) |
| **Math** | NumPy (pattern detection, ATR, swing calculations) |

---

## Philosophy

This bot does not predict price. It reads the **manipulation signature** that banks leave behind when engineering liquidity. Every trade is a response to institutional behavior, never a forecast.

The AI agent (Gemini) provides contextual intelligence — market regime, multi-timeframe narrative, risk assessment — but every execution must pass through the rule-based risk manager. No amount of AI confidence overrides the hardcoded risk rules.

> *"The market doesn't move to where price should go. It moves to where the stops are."*

---

**Built on the methodology of Dylan Shilts.**
**AI-powered by Google Gemini.**
