/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — AUTO-TRADE BOT PANEL
 *  Controls for the automated Signature Trade analysis bot
 * ═══════════════════════════════════════════════════════════════════
 */
import React, { useState, useEffect, useCallback } from 'react';

export default function AutoTradeBot({ brokerConnected }) {
  const [botStatus, setBotStatus] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [scanResult, setScanResult] = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/bot/status');
      const data = await res.json();
      setBotStatus(data);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const toggleBot = useCallback(async () => {
    setToggling(true);
    try {
      const res = await fetch('/api/bot/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !botStatus?.auto_trade }),
      });
      const data = await res.json();
      if (data.status === 'OK') {
        setBotStatus((prev) => prev ? { ...prev, auto_trade: data.auto_trade } : prev);
      }
    } catch { /* silent */ }
    finally { setToggling(false); }
  }, [botStatus]);

  const runScan = useCallback(async () => {
    setScanning(true);
    setScanResult(null);
    try {
      const res = await fetch('/api/bot/scan', { method: 'POST' });
      const data = await res.json();
      setScanResult(data);
    } catch (e) {
      setScanResult({ status: 'ERROR', message: e.message });
    } finally {
      setScanning(false);
    }
  }, []);

  const isOn = botStatus?.auto_trade ?? false;

  return (
    <div className="glass-panel rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xs uppercase tracking-widest text-gray-500 flex items-center gap-2">
          <span className="text-forexia-gold">⚙</span> Auto-Trade Bot
        </h2>

        {/* ON/OFF Toggle */}
        <button
          onClick={toggleBot}
          disabled={toggling || !brokerConnected}
          className={`
            relative w-14 h-7 rounded-full transition-all duration-300 border
            ${isOn
              ? 'bg-forexia-green/20 border-forexia-green/40'
              : 'bg-gray-800 border-gray-700'
            }
            disabled:opacity-40 disabled:cursor-not-allowed
          `}
        >
          <span
            className={`
              absolute top-0.5 w-6 h-6 rounded-full transition-all duration-300 flex items-center justify-center text-[8px] font-bold
              ${isOn
                ? 'left-7 bg-forexia-green text-black'
                : 'left-0.5 bg-gray-600 text-gray-400'
              }
            `}
          >
            {isOn ? 'ON' : 'OFF'}
          </span>
        </button>
      </div>

      {/* Bot Status Info */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-gray-900/50 rounded px-3 py-2 border border-gray-800">
          <p className="text-[9px] uppercase tracking-wider text-gray-600">Mode</p>
          <p className={`text-xs font-bold ${isOn ? 'text-forexia-green' : 'text-gray-500'}`}>
            {isOn ? 'AUTO + AI' : 'MANUAL'}
          </p>
        </div>
        <div className="bg-gray-900/50 rounded px-3 py-2 border border-gray-800">
          <p className="text-[9px] uppercase tracking-wider text-gray-600">Min Conf.</p>
          <p className="text-xs font-bold text-forexia-gold">
            {((botStatus?.min_confidence ?? 0.6) * 100).toFixed(0)}%
          </p>
        </div>
        <div className="bg-gray-900/50 rounded px-3 py-2 border border-gray-800">
          <p className="text-[9px] uppercase tracking-wider text-gray-600">Signals</p>
          <p className="text-xs font-bold text-forexia-accent">
            {botStatus?.active_signals ?? 0}
          </p>
        </div>
      </div>

      {/* AI Status */}
      {botStatus?.ai_enabled && (
        <div className="mb-3 flex items-center gap-2 px-2 py-1.5 rounded bg-purple-500/5 border border-purple-500/15">
          <span className={`w-2 h-2 rounded-full ${
            botStatus?.ai_scanning ? 'bg-purple-400 animate-pulse' : 'bg-gray-600'
          }`} />
          <span className="text-[9px] text-purple-400 font-mono">
            Gemini AI: {botStatus?.ai_scanning ? 'SCANNING' : 'STANDBY'}
            {botStatus?.ai_trades_generated > 0 && (
              <> · {botStatus.ai_trades_generated} signals generated</>
            )}
          </span>
        </div>
      )}

      {/* Pairs Being Monitored */}
      <div className="mb-4">
        <p className="text-[9px] uppercase tracking-wider text-gray-600 mb-1.5">Monitored Pairs</p>
        <div className="flex flex-wrap gap-1">
          {(botStatus?.pairs || ['EURUSD', 'GBPUSD', 'USDCHF', 'USDJPY']).map((pair) => (
            <span
              key={pair}
              className="px-2 py-0.5 rounded text-[9px] font-bold tracking-wider bg-forexia-accent/10 text-forexia-accent border border-forexia-accent/20"
            >
              {pair}
            </span>
          ))}
        </div>
      </div>

      {/* Scan Button */}
      <button
        onClick={runScan}
        disabled={scanning || !brokerConnected}
        className="w-full py-2.5 rounded font-bold text-xs uppercase tracking-wider transition-all
          bg-forexia-accent/15 text-forexia-accent border border-forexia-accent/30
          hover:bg-forexia-accent/25 hover:border-forexia-accent/50
          disabled:opacity-30 disabled:cursor-not-allowed
          active:scale-[0.98]"
      >
        {scanning ? (
          <span className="flex items-center justify-center gap-2">
            <span className="w-3 h-3 border-2 border-forexia-accent border-t-transparent rounded-full animate-spin" />
            Scanning {botStatus?.pairs?.length || 4} pairs...
          </span>
        ) : (
          <>🔍 Run Analysis Scan</>
        )}
      </button>

      {/* Scan Results */}
      {scanResult && (
        <div className="mt-3 space-y-1.5">
          {/* Market context info */}
          {(scanResult.weekly_act || scanResult.session_phase) && (
            <div className="flex items-center gap-3 text-[9px] font-mono px-2 py-1.5 rounded bg-gray-900/50 border border-gray-800">
              {scanResult.weekly_act && (
                <span className="text-forexia-purple">
                  📅 {scanResult.weekly_act.replace(/_/g, ' ')}
                </span>
              )}
              {scanResult.session_phase && (
                <span className="text-forexia-cyan">
                  🕐 {scanResult.session_phase.replace(/_/g, ' ')}
                </span>
              )}
              {scanResult.trading_permitted === false && (
                <span className="text-forexia-gold animate-pulse">
                  ⚠ No-trade day (force-scanned)
                </span>
              )}
            </div>
          )}

          <div className="flex items-center justify-between text-[10px]">
            <span className="text-gray-500">
              Scanned: {scanResult.pairs_scanned} pairs
            </span>
            <span className={scanResult.signals_found > 0 ? 'text-forexia-gold font-bold' : 'text-gray-600'}>
              {scanResult.signals_found} signal{scanResult.signals_found !== 1 ? 's' : ''}
            </span>
            {scanResult.trades_executed > 0 && (
              <span className="text-forexia-green font-bold">
                {scanResult.trades_executed} executed
              </span>
            )}
          </div>

          {/* Signal results */}
          {scanResult.results?.filter(r => r.signal_id).map((r, i) => (
            <div
              key={r.signal_id || i}
              className={`px-3 py-2 rounded text-[10px] font-mono border ${
                r.executed
                  ? 'bg-forexia-green/10 border-forexia-green/20 text-forexia-green'
                  : r.source === 'gemini_ai'
                    ? 'bg-purple-500/10 border-purple-500/20 text-purple-400'
                    : 'bg-forexia-gold/10 border-forexia-gold/20 text-forexia-gold'
              }`}
            >
              <div className="flex justify-between">
                <span className="font-bold">
                  {r.source === 'gemini_ai' ? '🤖 ' : ''}{r.symbol} {r.direction}
                </span>
                <span>{(r.confidence * 100).toFixed(0)}% conf</span>
              </div>
              <div className="text-gray-400 mt-0.5">
                {r.type?.replace(/_/g, ' ')} · {r.lots} lots · R:R 1:{r.rr_ratio || '?'}
              </div>
              <div className="text-gray-500 mt-0.5 flex justify-between">
                <span>Entry: {r.entry?.toFixed(5)}</span>
                <span className="text-forexia-red">SL: {r.sl?.toFixed(5)}</span>
                <span className="text-forexia-green">TP: {r.tp?.toFixed(5)}</span>
              </div>
              <div className="text-gray-500 mt-0.5">
                {r.risk_pips && <>Risk: {r.risk_pips}p · Reward: {r.reward_pips}p · </>}
                {r.executed ? `✓ Ticket #${r.ticket}` : (r.confidence < (botStatus?.min_confidence ?? 0.6) ? `Below ${((botStatus?.min_confidence ?? 0.6) * 100).toFixed(0)}% threshold` : 'Signal only')}
              </div>
            </div>
          ))}

          {/* Per-pair breakdown when no signals */}
          {scanResult.results?.filter(r => !r.signal_id).length > 0 && scanResult.signals_found === 0 && (
            <div className="space-y-1">
              {scanResult.results?.map((r, i) => (
                <div key={i} className="flex items-center justify-between px-2 py-1 rounded bg-gray-900/30 text-[9px] font-mono">
                  <span className="text-gray-500">{r.symbol}</span>
                  <span className={r.message?.includes('Error') ? 'text-forexia-red' : 'text-gray-600'}>
                    {r.message || 'No signal'}
                  </span>
                </div>
              ))}
            </div>
          )}

          {scanResult.status === 'ERROR' && (
            <div className="px-3 py-2 rounded text-[10px] font-mono bg-forexia-red/10 border border-forexia-red/20 text-forexia-red">
              ✗ {scanResult.message}
            </div>
          )}
        </div>
      )}

      {/* Auto-trade info */}
      {isOn && (
        <div className="mt-3 px-3 py-2 rounded bg-forexia-green/5 border border-forexia-green/15">
          <p className="text-[9px] text-forexia-green font-mono">
            ✓ Auto-trade is ON — Rule engine + AI Advisor scanning every 2 min.
            Signals above {((botStatus?.min_confidence ?? 0.6) * 100).toFixed(0)}%
            confidence will be executed automatically.
          </p>
        </div>
      )}
    </div>
  );
}
