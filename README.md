# FOREXIA SIGNATURE AGENT

> An elite institutional Python trading bot modeled after Dylan Shilts' methodology.
> Trades market manipulation, not retail trends.

```
NO FVG · NO RSI · NO MACD · NO Moving Average Crossovers · NO Retail Indicators
```

---

## Architecture

```
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  TradingView     │──────▶│  FastAPI Server   │──────▶│  MT4 Terminal    │
│  Webhook Alerts  │ POST  │  (Orchestrator)   │ ZMQ   │  (Expert Advisor)│
└──────────────────┘       └────────┬─────────┘       └──────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
              ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
              │ Hegelian   │  │ Signature │  │ Weekly    │
              │ Dialectic  │  │ Trade     │  │ 5-Act     │
              │ Engine     │  │ Detector  │  │ Structure │
              └────────────┘  └───────────┘  └───────────┘
                    │               │               │
              ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
              │ News       │  │ Trauma    │  │ Candle    │
              │ Catalyst   │  │ Filter    │  │ Scanner   │
              └────────────┘  └───────────┘  └───────────┘
                    │               │               │
              ┌─────▼─────┐  ┌─────▼─────┐
              │ Multi-Pair │  │ Risk      │
              │ Sync       │  │ Manager   │
              └────────────┘  └───────────┘
```

## Engines

| Engine | Purpose |
|--------|---------|
| **Hegelian Dialectic** | Asian Problem → London Reaction → NY Solution cycle detection |
| **Signature Trade** | Wedge/Triangle → False Breakout → Stop Hunt → Exhaustion Reversal |
| **Weekly 5-Act** | Sun Connector → Mon Induction → Tue Accumulation → Wed Reversal → Thu Distribution → Fri Epilogue |
| **News Catalyst** | ForexFactory Red Folder scraper — event timing only, NO numbers |
| **Trauma Filter** | God Candle detection + post-spike exhaustion reversal |
| **Candlestick Scanner** | Railroad Tracks + Star patterns at psychological levels |
| **Multi-Pair Sync** | Dollar basket correlation verification (EUR, GBP, CHF, JPY) |
| **Risk Manager** | 0.01 lots per $100 equity, min 1:3 R:R, daily circuit breaker |

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- MetaTrader 4 (for live execution)

### 1. Clone & Setup Backend

```bash
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
uvicorn backend.server:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Setup & Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard will be available at `http://localhost:3000`

### 4. MT4 Expert Advisor

The ZeroMQ EA template is embedded in `backend/bridges/mt4_bridge.py` as `MT4_EA_TEMPLATE`. To use:

1. Open MT4 → MetaEditor
2. Create new Expert Advisor
3. Paste the template code
4. Compile and attach to a chart
5. Ensure "Allow DLL imports" is checked in EA settings

### 5. TradingView Webhook

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

Actions: `ANALYZE` (analyze and auto-trade if confidence ≥ 60%), `FORCE_ENTRY`, `CLOSE`

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhook` | TradingView webhook receiver |
| GET | `/api/dashboard` | Full dashboard state |
| GET | `/api/account` | Account balance/equity |
| GET | `/api/signals` | Active signals |
| GET | `/api/trades` | Trade history |
| GET | `/api/news` | Red Folder events |
| GET | `/api/liquidity` | Mapped liquidity zones |
| GET | `/api/session` | Current session phase |
| GET | `/api/multi-pair` | Dollar basket analysis |
| POST | `/api/close-all` | Emergency close all positions |
| POST | `/api/reset/daily` | Reset daily counters |
| POST | `/api/reset/weekly` | Reset weekly structure |
| POST | `/api/scrape-news` | Force news scrape |
| POST | `/api/trauma/arm` | Arm trauma filter |
| POST | `/api/trauma/disarm` | Disarm trauma filter |
| GET | `/health` | Health check |

## Risk Rules (Non-Negotiable)

1. **Lot size**: 0.01 per $100 equity — no exceptions
2. **Stop loss**: Beyond the stop hunt wick + buffer — always
3. **Take profit**: Minimum 1:3 risk-to-reward ratio
4. **Daily loss**: Circuit breaker at 3% account loss
5. **Max concurrent**: 3 trades maximum
6. **No-trade days**: Sunday connector, Monday induction
7. **Friday cutoff**: No new trades after 18:00 UTC Friday

## Project Structure

```
forexia-signature-agent/
├── backend/
│   ├── __init__.py
│   ├── config.py              # Master configuration
│   ├── orchestrator.py         # Central nervous system
│   ├── server.py               # FastAPI application
│   ├── bridges/
│   │   ├── __init__.py
│   │   └── mt4_bridge.py       # ZeroMQ MT4 bridge + EA template
│   ├── engines/
│   │   ├── __init__.py
│   │   ├── hegelian_engine.py  # 3-phase daily cycle
│   │   ├── signature_trade.py  # Pattern detector
│   │   ├── weekly_structure.py # 5-Act weekly cycle
│   │   ├── trauma_filter.py    # God Candle + exhaustion
│   │   ├── candle_scanner.py   # Railroad Tracks + Stars
│   │   ├── multi_pair_sync.py  # Dollar basket correlation
│   │   └── risk_manager.py     # Position sizing + validation
│   ├── scrapers/
│   │   ├── __init__.py
│   │   └── news_catalyst.py    # ForexFactory Red Folder
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py          # Pydantic models + enums
│   └── utils/
│       └── __init__.py
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── index.css
│       ├── App.jsx
│       ├── hooks/
│       │   └── useForexia.js
│       └── components/
│           ├── AccountPanel.jsx
│           ├── WeeklyActDisplay.jsx
│           ├── InductionMeter.jsx
│           ├── SessionPhasePanel.jsx
│           ├── TradeHistory.jsx
│           ├── NewsCatalystPanel.jsx
│           └── LiquidityPanel.jsx
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Philosophy

This bot does not predict price. It reads the **manipulation signature** that banks leave behind when engineering liquidity. Every trade is a response to institutional behavior, never a forecast.

> *"The market doesn't move to where price should go. It moves to where the stops are."*

---

**Built on the methodology of Dylan Shilts.**
