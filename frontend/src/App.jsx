/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA SIGNATURE AGENT — MAIN DASHBOARD
 *
 *  This is the nerve center.
 *  Every pixel here exists because it earns its place.
 *  No decorative nonsense, no retail indicator clutter.
 *
 *  Layout:
 *  ┌───────────────────────────────────────────────────────────────┐
 *  │  HEADER — System Name · Health · Connection · Bot Toggle      │
 *  ├────────────────┬──────────────┬───────────────────────────────┤
 *  │ Account Panel  │ Induction    │ Session / Hegelian Phase      │
 *  │                │ Meter        │                               │
 *  ├────────────────┴──────────────┴───────────────────────────────┤
 *  │ Weekly 5-Act Timeline                                        │
 *  ├──────────────────┬──────────────────┬─────────────────────────┤
 *  │ Quick Trade +    │ Open Positions   │ Auto-Trade Bot          │
 *  │ Manual Orders    │ (Live P&L)       │ (Scan & Execute)        │
 *  ├──────────────────┴──────────────────┴─────────────────────────┤
 *  │ Trade History / Signals │ News Catalyst + Liquidity           │
 *  └───────────────────────────┴───────────────────────────────────┘
 * ═══════════════════════════════════════════════════════════════════
 */
import React, { useCallback, useState } from 'react';
import { useDashboard, useSession, useControls, useHealth } from './hooks/useForexia';

import AccountPanel from './components/AccountPanel';
import WeeklyActDisplay from './components/WeeklyActDisplay';
import InductionMeter from './components/InductionMeter';
import SessionPhasePanel from './components/SessionPhasePanel';
import TransactionHistory from './components/TransactionHistory';
import NewsCatalystPanel from './components/NewsCatalystPanel';
import LiquidityPanel from './components/LiquidityPanel';
import SettingsPanel from './components/SettingsPanel';
import TradingPanel from './components/TradingPanel';
import OpenPositions from './components/OpenPositions';
import AutoTradeBot from './components/AutoTradeBot';
import LiveChart from './components/LiveChart';

/* ───── Status indicator dot ───── */
function StatusDot({ ok }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${
        ok ? 'bg-forexia-green animate-pulse' : 'bg-forexia-red'
      }`}
    />
  );
}

/* ───── Control button ───── */
function ControlButton({ label, onClick, variant = 'default', disabled = false }) {
  const base = 'px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-all duration-200 disabled:opacity-30 disabled:cursor-not-allowed';
  const variants = {
    default: 'bg-gray-800 text-gray-300 hover:bg-gray-700 border border-gray-700',
    danger: 'bg-red-900/40 text-forexia-red hover:bg-red-900/60 border border-red-900/50',
    accent: 'bg-forexia-accent/20 text-forexia-accent hover:bg-forexia-accent/30 border border-forexia-accent/30',
  };
  return (
    <button
      className={`${base} ${variants[variant]}`}
      onClick={onClick}
      disabled={disabled}
    >
      {label}
    </button>
  );
}

/* ═══════════════════════════════════════════════════════════════════
 *  APP — Root Component
 * ═══════════════════════════════════════════════════════════════════ */
export default function App() {
  const { dashboard, signals, trades, news, liquidity, loading, error } = useDashboard();
  const { session, multiPair } = useSession();
  const { closeAll, resetDaily, resetWeekly, scrapeNews, armTrauma, disarmTrauma } = useControls();
  const { healthy, latency } = useHealth();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [tradeRefreshKey, setTradeRefreshKey] = useState(0);

  /* ───── Derived state ───── */
  const account = dashboard?.account || {};
  const phase = dashboard?.current_session || session?.session_phase || 'UNKNOWN';
  const weeklyAct = dashboard?.current_weekly_act || session?.weekly_act || 'CONNECTOR';
  const inductionScore = dashboard?.induction_meter ?? 0;
  const tradingPermitted = session?.trading_permitted ?? false;
  const activeSignals = signals?.length ?? 0;
  const todayTrades = account?.total_trades_today ?? 0;
  const dailyPnL = account?.daily_pnl ?? 0;
  const isKillzone = session?.in_killzone ?? false;
  const brokerConnected = dashboard?.broker_connected || (account?.balance > 0 || account?.equity > 0);

  /* ───── Controls ───── */
  const handleCloseAll = useCallback(async () => {
    if (window.confirm('Close ALL open positions?')) {
      await closeAll();
    }
  }, [closeAll]);

  const handleResetDaily = useCallback(async () => {
    await resetDaily();
  }, [resetDaily]);

  const handleResetWeekly = useCallback(async () => {
    if (window.confirm('Reset weekly structure? This clears all weekly data.')) {
      await resetWeekly();
    }
  }, [resetWeekly]);

  /* ───── Loading / Error states ───── */
  if (loading && !dashboard) {
    return (
      <div className="min-h-screen bg-forexia-bg flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-2 border-forexia-accent border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-xs text-gray-500 uppercase tracking-widest">
            Connecting to Forexia Engine...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-forexia-bg text-white">
      {/* ═══ HEADER ═══ */}
      <header className="border-b border-gray-800/60 px-6 py-3">
        <div className="flex items-center justify-between max-w-[1920px] mx-auto">
          {/* Logo + Title */}
          <div className="flex items-center gap-4">
            <div className="flex items-baseline gap-2">
              <h1 className="text-lg font-black tracking-tight">
                <span className="text-forexia-accent">FOREXIA</span>
                <span className="text-gray-500 font-light ml-1">SIGNATURE</span>
              </h1>
              <span className="text-[9px] text-gray-600 uppercase tracking-widest">Agent</span>
            </div>
            <div className="h-4 w-px bg-gray-800" />
            <div className="flex items-center gap-2">
              <StatusDot ok={healthy} />
              <span className="text-[10px] text-gray-500">
                {healthy ? `LIVE · ${latency}ms` : 'DISCONNECTED'}
              </span>
            </div>
          </div>

          {/* Status Pills */}
          <div className="flex items-center gap-3">
            <div className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${
              tradingPermitted
                ? 'bg-forexia-green/10 text-forexia-green border border-forexia-green/20'
                : 'bg-forexia-red/10 text-forexia-red border border-forexia-red/20'
            }`}>
              {tradingPermitted ? 'TRADING ACTIVE' : 'TRADING PAUSED'}
            </div>
            {isKillzone && (
              <div className="px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-forexia-gold/10 text-forexia-gold border border-forexia-gold/20 animate-pulse">
                KILLZONE
              </div>
            )}
            <div className="text-[10px] text-gray-600">
              Signals: {activeSignals} · Trades: {todayTrades}
            </div>
          </div>

          {/* Control Buttons */}
          <div className="flex items-center gap-2">
            <ControlButton label="Settings" onClick={() => setSettingsOpen(true)} variant="accent" />
            <ControlButton label="Scrape News" onClick={scrapeNews} variant="default" />
            <ControlButton label="Arm Trauma" onClick={armTrauma} variant="default" />
            <ControlButton label="Daily Reset" onClick={handleResetDaily} variant="default" />
            <ControlButton label="Close All" onClick={handleCloseAll} variant="danger" />
          </div>
        </div>
      </header>

      {/* ═══ ERROR BANNER ═══ */}
      {error && (
        <div className="bg-red-900/20 border-b border-red-900/30 px-6 py-2">
          <p className="text-[10px] text-forexia-red font-mono max-w-[1920px] mx-auto">
            ⚠ {error}
          </p>
        </div>
      )}

      {/* ═══ MAIN GRID ═══ */}
      <main className="p-6 max-w-[1920px] mx-auto">
        {/* ─── ROW 1: Account · Induction Meter · Session Phase ─── */}
        <div className="grid grid-cols-12 gap-4 mb-4">
          <div className="col-span-4">
            <AccountPanel account={account} />
          </div>
          <div className="col-span-3 flex items-center justify-center">
            <InductionMeter value={inductionScore} />
          </div>
          <div className="col-span-5">
            <SessionPhasePanel
              sessionPhase={phase}
              isKillzone={isKillzone}
              tradingPermitted={tradingPermitted}
              multiPair={multiPair}
            />
          </div>
        </div>

        {/* ─── ROW 2: Weekly 5-Act Timeline ─── */}
        <div className="mb-4">
          <WeeklyActDisplay currentAct={weeklyAct} />
        </div>

        {/* ─── ROW 2.5: Live Market Chart ─── */}
        <div className="mb-4">
          <LiveChart brokerConnected={brokerConnected} />
        </div>

        {/* ─── ROW 3: Trading Panel · Open Positions · Auto-Trade Bot ─── */}
        <div className="grid grid-cols-12 gap-4 mb-4">
          <div className="col-span-3">
            <TradingPanel
              brokerConnected={brokerConnected}
              onTradeExecuted={() => setTradeRefreshKey((k) => k + 1)}
            />
          </div>
          <div className="col-span-5">
            <OpenPositions
              brokerConnected={brokerConnected}
              refreshKey={tradeRefreshKey}
            />
          </div>
          <div className="col-span-4">
            <AutoTradeBot brokerConnected={brokerConnected} />
          </div>
        </div>

        {/* ─── ROW 4: Transaction History · News & Liquidity ─── */}
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-7">
            <TransactionHistory brokerConnected={brokerConnected} signals={signals} />
          </div>
          <div className="col-span-5 space-y-4">
            <NewsCatalystPanel catalysts={news} traumaActive={dashboard?.trauma_filter_active} />
            <LiquidityPanel zones={liquidity} />
          </div>
        </div>
      </main>

      {/* ═══ FOOTER ═══ */}
      <footer className="border-t border-gray-800/40 px-6 py-2">
        <div className="flex items-center justify-between max-w-[1920px] mx-auto text-[9px] text-gray-700">
          <span>Forexia Signature Agent · Dylan Shilts Methodology · Institutional Execution</span>
          <span>
            NO FVG · NO RSI · NO MACD · NO Retail Indicators
          </span>
          <span>
            {new Date().toUTCString()}
          </span>
        </div>
      </footer>

      {/* ═══ SETTINGS MODAL ═══ */}
      <SettingsPanel isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
