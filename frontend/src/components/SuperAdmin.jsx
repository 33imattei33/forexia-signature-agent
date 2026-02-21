/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — SUPER ADMIN DASHBOARD
 *  Full bot management, settings, analytics, AI workflow control
 * ═══════════════════════════════════════════════════════════════════
 */
import React, { useState, useEffect, useCallback } from 'react';

/* ───── Shared UI atoms ───── */
const Card = ({ title, children, accent, className = '' }) => (
  <div className={`glass-panel rounded-lg p-4 ${className}`}>
    {title && (
      <h3 className={`text-[11px] font-bold uppercase tracking-widest mb-3 ${
        accent === 'green' ? 'text-forexia-green' :
        accent === 'red' ? 'text-forexia-red' :
        accent === 'gold' ? 'text-forexia-gold' :
        accent === 'purple' ? 'text-forexia-purple' :
        accent === 'cyan' ? 'text-forexia-cyan' : 'text-forexia-accent'
      }`}>
        {title}
      </h3>
    )}
    {children}
  </div>
);

const Stat = ({ label, value, sub, color = 'text-white' }) => (
  <div className="text-center">
    <div className={`text-lg font-black ${color}`}>{value}</div>
    <div className="text-[9px] text-gray-500 uppercase tracking-wider">{label}</div>
    {sub && <div className="text-[9px] text-gray-600 mt-0.5">{sub}</div>}
  </div>
);

const Badge = ({ text, variant = 'default' }) => {
  const v = {
    success: 'bg-forexia-green/15 text-forexia-green border-forexia-green/30',
    danger: 'bg-forexia-red/15 text-forexia-red border-forexia-red/30',
    warning: 'bg-forexia-gold/15 text-forexia-gold border-forexia-gold/30',
    info: 'bg-forexia-accent/15 text-forexia-accent border-forexia-accent/30',
    default: 'bg-gray-800 text-gray-400 border-gray-700',
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border ${v[variant]}`}>
      {text}
    </span>
  );
};

const Button = ({ children, onClick, variant = 'default', size = 'sm', disabled = false }) => {
  const base = 'rounded font-bold uppercase tracking-wider transition-all duration-200 disabled:opacity-30';
  const sizes = { sm: 'px-3 py-1.5 text-[10px]', md: 'px-4 py-2 text-[11px]' };
  const variants = {
    default: 'bg-gray-800 text-gray-300 hover:bg-gray-700 border border-gray-700',
    primary: 'bg-forexia-accent/20 text-forexia-accent hover:bg-forexia-accent/30 border border-forexia-accent/30',
    danger: 'bg-red-900/30 text-forexia-red hover:bg-red-900/50 border border-red-900/40',
    success: 'bg-green-900/30 text-forexia-green hover:bg-green-900/50 border border-green-900/40',
  };
  return (
    <button className={`${base} ${sizes[size]} ${variants[variant]}`} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
};

const ProgressBar = ({ value, max = 100, color = 'forexia-accent' }) => (
  <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
    <div
      className={`h-full bg-${color} rounded-full transition-all duration-500`}
      style={{ width: `${Math.min(100, (value / max) * 100)}%` }}
    />
  </div>
);

/* ═══════════════════════════════════════════════════
 *  TOP-LEVEL SECTIONS
 * ═══════════════════════════════════════════════════ */

function SystemHeader({ system, account, onBack }) {
  const upHours = system?.uptime ? Math.floor(system.uptime / 3600) : 0;
  const upMins = system?.uptime ? Math.floor((system.uptime % 3600) / 60) : 0;

  return (
    <header className="border-b border-gray-800/60 px-6 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button onClick={onBack} className="text-gray-500 hover:text-white text-xs">
            ← Back to Dashboard
          </button>
          <div className="h-4 w-px bg-gray-800" />
          <h1 className="text-lg font-black tracking-tight">
            <span className="text-forexia-gold">SUPER</span>
            <span className="text-white ml-1">ADMIN</span>
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <Badge text={system?.session || 'UNKNOWN'} variant="info" />
          <Badge text={system?.weekly_act || 'UNKNOWN'} variant="warning" />
          <Badge
            text={system?.broker_connected ? 'CONNECTED' : 'DISCONNECTED'}
            variant={system?.broker_connected ? 'success' : 'danger'}
          />
          <span className="text-[10px] text-gray-600">Uptime: {upHours}h {upMins}m</span>
        </div>
      </div>
    </header>
  );
}

/* ───── Account & Performance Overview ───── */
function PerformanceOverview({ overview, performance }) {
  const perf = overview?.performance || {};
  const acct = overview?.account || {};

  return (
    <Card title="Performance Overview" accent="green">
      <div className="grid grid-cols-6 gap-4 mb-4">
        <Stat label="Balance" value={`$${(acct.balance||0).toLocaleString(undefined, {minimumFractionDigits: 2})}`} color="text-white" />
        <Stat label="Equity" value={`$${(acct.equity||0).toLocaleString(undefined, {minimumFractionDigits: 2})}`} color="text-white" />
        <Stat label="Net P&L" value={`$${(perf.net_pnl||0).toFixed(2)}`} color={perf.net_pnl >= 0 ? 'text-forexia-green glow-green' : 'text-forexia-red glow-red'} />
        <Stat label="Win Rate" value={`${(perf.win_rate||0).toFixed(1)}%`} color={perf.win_rate >= 50 ? 'text-forexia-green' : 'text-forexia-gold'} />
        <Stat label="Profit Factor" value={(perf.profit_factor||0).toFixed(2)} color={perf.profit_factor >= 1.5 ? 'text-forexia-green' : 'text-forexia-gold'} />
        <Stat label="Total Trades" value={perf.total_trades||0} sub={`W:${perf.wins||0} L:${perf.losses||0}`} />
      </div>

      {/* Equity Curve (ASCII-style) */}
      {performance?.equity_curve && performance.equity_curve.length > 0 && (
        <div className="mt-3">
          <div className="text-[9px] text-gray-500 uppercase tracking-wider mb-2">Equity Curve</div>
          <EquityCurveChart data={performance.equity_curve} />
        </div>
      )}
    </Card>
  );
}

/* Mini equity curve using CSS bars */
function EquityCurveChart({ data }) {
  if (!data || !Array.isArray(data) || data.length === 0) return null;
  const vals = data.map(d => Number(d.cumulative) || 0);
  const maxVal = Math.max(...vals);
  const minVal = Math.min(...vals);
  const range = Math.max(maxVal - minVal, 1);

  return (
    <div className="flex items-end gap-px h-20 bg-gray-900/50 rounded p-1 overflow-hidden">
      {data.slice(-80).map((d, i) => {
        const cum = Number(d.cumulative) || 0;
        const pnl = Number(d.pnl) || 0;
        const h = ((cum - minVal) / range) * 100;
        return (
          <div
            key={i}
            className={`flex-1 min-w-[2px] rounded-t ${pnl >= 0 ? 'bg-forexia-green/70' : 'bg-forexia-red/70'}`}
            style={{ height: `${Math.max(2, h)}%` }}
            title={`#${d.trade_num || i}: ${d.symbol || '?'} ${d.direction || ''} → $${pnl} (Total: $${cum})`}
          />
        );
      })}
    </div>
  );
}

/* ───── Per-Pair Performance Table ───── */
function PairPerformanceTable({ pairs }) {
  if (!pairs || !Array.isArray(pairs) || pairs.length === 0) return <div className="text-[10px] text-gray-600">No trade data</div>;

  return (
    <Card title="Performance by Pair" accent="cyan">
      <div className="overflow-x-auto">
        <table className="w-full text-[10px]">
          <thead>
            <tr className="text-gray-500 uppercase border-b border-gray-800">
              <th className="text-left py-1 px-2">Symbol</th>
              <th className="text-right py-1 px-2">P&L</th>
              <th className="text-right py-1 px-2">Trades</th>
              <th className="text-right py-1 px-2">Win%</th>
              <th className="text-right py-1 px-2">Lots</th>
              <th className="text-left py-1 px-2">Rating</th>
            </tr>
          </thead>
          <tbody>
            {pairs.map((p, i) => {
              const profit = p.profit ?? 0;
              const count = p.count ?? 0;
              const wins = p.wins ?? 0;
              const totalLots = p.total_lots ?? 0;
              const wr = count > 0 ? (wins / count * 100) : 0;
              const rating = profit > 50 ? '★★★' : profit > 0 ? '★★' : profit > -50 ? '★' : '✗';
              return (
                <tr key={i} className="border-b border-gray-800/40 hover:bg-gray-800/30">
                  <td className="py-1.5 px-2 font-bold text-white">{p.symbol}</td>
                  <td className={`py-1.5 px-2 text-right font-bold ${profit >= 0 ? 'text-forexia-green' : 'text-forexia-red'}`}>
                    ${profit.toFixed(2)}
                  </td>
                  <td className="py-1.5 px-2 text-right text-gray-400">{count}</td>
                  <td className="py-1.5 px-2 text-right text-gray-400">{wr.toFixed(0)}%</td>
                  <td className="py-1.5 px-2 text-right text-gray-400">{totalLots.toFixed(2)}</td>
                  <td className="py-1.5 px-2 text-forexia-gold">{rating}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* ───── Direction Performance ───── */
function DirectionPerformance({ byDirection }) {
  if (!byDirection) return null;
  return (
    <Card title="BUY vs SELL" accent="purple">
      <div className="grid grid-cols-2 gap-4">
        {['BUY', 'SELL'].map(dir => {
          const d = byDirection[dir] || {};
          const wr = d.count > 0 ? (d.wins / d.count * 100) : 0;
          return (
            <div key={dir} className={`p-3 rounded border ${
              dir === 'BUY' ? 'border-forexia-green/20 bg-forexia-green/5' : 'border-forexia-red/20 bg-forexia-red/5'
            }`}>
              <div className="text-[11px] font-bold mb-2">{dir}</div>
              <div className={`text-lg font-black ${d.profit >= 0 ? 'text-forexia-green' : 'text-forexia-red'}`}>
                ${(d.profit||0).toFixed(2)}
              </div>
              <div className="text-[9px] text-gray-500 mt-1">
                {d.count||0} trades · {wr.toFixed(0)}% WR · {d.wins||0}W {(d.count||0)-(d.wins||0)}L
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ───── Risk State Panel ───── */
function RiskStatePanel({ riskState, actions }) {
  if (!riskState) return null;

  return (
    <Card title="Risk & Anti-Tilt" accent="red">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-gray-400">Consecutive Losses</span>
          <div className="flex items-center gap-2">
            <span className={`text-lg font-black ${
              riskState.consecutive_losses >= 5 ? 'text-forexia-red glow-red' :
              riskState.consecutive_losses >= 3 ? 'text-forexia-gold' : 'text-forexia-green'
            }`}>
              {riskState.consecutive_losses}
            </span>
            {riskState.consecutive_losses > 0 && (
              <Button variant="danger" onClick={actions.resetConsecutiveLosses}>Reset</Button>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-[10px] text-gray-400">Anti-Tilt Status</span>
          <Badge
            text={riskState.anti_tilt_active ? `ACTIVE — ${riskState.lot_reduction} lots` : 'INACTIVE'}
            variant={riskState.anti_tilt_active ? 'danger' : 'success'}
          />
        </div>

        {/* SL Cooldowns */}
        {Object.keys(riskState.sl_cooldowns || {}).length > 0 && (
          <div>
            <div className="text-[9px] text-gray-500 uppercase tracking-wider mb-1">SL Cooldowns Active</div>
            {Object.entries(riskState.sl_cooldowns).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between text-[10px] py-0.5">
                <span className="text-gray-400">{k}</span>
                <Badge text={v.direction} variant="warning" />
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

/* ───── Settings Editor ───── */
function SettingsEditor({ settings, onSave }) {
  const [editing, setEditing] = useState(null);
  const [values, setValues] = useState({});

  useEffect(() => {
    if (settings) setValues(JSON.parse(JSON.stringify(settings)));
  }, [settings]);

  const handleSave = async () => {
    await onSave(values);
    setEditing(null);
  };

  if (!values?.risk) return null;

  const RiskField = ({ field, label, type = 'number', step = '0.01' }) => (
    <div className="flex items-center justify-between py-1.5 border-b border-gray-800/30">
      <label className="text-[10px] text-gray-400">{label}</label>
      <input
        type={type}
        step={step}
        value={values.risk?.[field] ?? ''}
        onChange={e => setValues(prev => ({
          ...prev, risk: { ...prev.risk, [field]: type === 'number' ? parseFloat(e.target.value) : e.target.value }
        }))}
        className="w-24 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-[10px] text-white text-right focus:border-forexia-accent outline-none"
      />
    </div>
  );

  const AgentField = ({ field, label, type = 'number', step = '0.01' }) => (
    <div className="flex items-center justify-between py-1.5 border-b border-gray-800/30">
      <label className="text-[10px] text-gray-400">{label}</label>
      {type === 'boolean' ? (
        <button
          onClick={() => setValues(prev => ({
            ...prev, agent: { ...prev.agent, [field]: !prev.agent[field] }
          }))}
          className={`px-3 py-1 rounded text-[10px] font-bold ${
            values.agent?.[field] ? 'bg-forexia-green/20 text-forexia-green' : 'bg-gray-800 text-gray-500'
          }`}
        >
          {values.agent?.[field] ? 'ON' : 'OFF'}
        </button>
      ) : (
        <input
          type={type}
          step={step}
          value={values.agent?.[field] ?? ''}
          onChange={e => setValues(prev => ({
            ...prev, agent: { ...prev.agent, [field]: type === 'number' ? parseFloat(e.target.value) : e.target.value }
          }))}
          className="w-24 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-[10px] text-white text-right focus:border-forexia-accent outline-none"
        />
      )}
    </div>
  );

  return (
    <Card title="Bot Settings" accent="gold">
      <div className="grid grid-cols-2 gap-6">
        {/* Risk Settings */}
        <div>
          <div className="text-[9px] text-gray-500 uppercase tracking-wider mb-2">Risk Management</div>
          <RiskField field="lot_per_100_equity" label="Lots per $100" step="0.001" />
          <RiskField field="max_risk_percent" label="Max Risk %" step="0.5" />
          <RiskField field="max_lot_size" label="Max Lot Size" step="0.01" />
          <RiskField field="stop_loss_buffer_pips" label="SL Buffer (pips)" step="1" />
          <RiskField field="max_concurrent_trades" label="Max Concurrent" step="1" />
          <RiskField field="max_daily_loss_percent" label="Daily Loss Limit %" step="0.5" />
          <RiskField field="max_spread_pips" label="Max Spread (pips)" step="0.1" />
          <RiskField field="breakeven_trigger_pips" label="BE Trigger (pips)" step="1" />
          <RiskField field="trailing_start_pips" label="Trail Start (pips)" step="1" />
          <RiskField field="trailing_step_pips" label="Trail Step (pips)" step="1" />
          <RiskField field="stale_trade_minutes" label="Stale Trade (min)" step="5" />
        </div>

        {/* Agent Settings */}
        <div>
          <div className="text-[9px] text-gray-500 uppercase tracking-wider mb-2">Agent Behavior</div>
          <AgentField field="auto_trade" label="Auto Trade" type="boolean" />
          <AgentField field="min_confidence" label="Min Confidence" step="0.05" />
          <AgentField field="default_timeframe" label="Timeframe" type="text" />
          <AgentField field="news_scraping_enabled" label="News Scraping" type="boolean" />

          <div className="text-[9px] text-gray-500 uppercase tracking-wider mb-2 mt-4">Monitored Pairs</div>
          <div className="flex flex-wrap gap-1">
            {(values.agent?.pairs || []).map((p, i) => (
              <span key={i} className="px-2 py-0.5 bg-gray-800 border border-gray-700 rounded text-[9px] text-forexia-accent">
                {p}
              </span>
            ))}
          </div>
        </div>
      </div>
      <div className="mt-4 flex justify-end">
        <Button variant="primary" size="md" onClick={handleSave}>Save Settings</Button>
      </div>
    </Card>
  );
}

/* ───── Pair Blacklist Editor ───── */
function BlacklistEditor({ initialBlacklist, onSave }) {
  const [blacklist, setBlacklist] = useState([]);
  const [newPair, setNewPair] = useState('');

  useEffect(() => {
    if (initialBlacklist) setBlacklist(initialBlacklist);
  }, [initialBlacklist]);

  const addPair = () => {
    const p = newPair.trim().toUpperCase();
    if (p && !blacklist.includes(p)) {
      const next = [...blacklist, p];
      setBlacklist(next);
      onSave(next);
      setNewPair('');
    }
  };

  const removePair = (pair) => {
    const next = blacklist.filter(p => p !== pair);
    setBlacklist(next);
    onSave(next);
  };

  return (
    <Card title="Pair Blacklist" accent="red">
      <div className="flex flex-wrap gap-2 mb-3">
        {blacklist.map(p => (
          <span key={p} className="flex items-center gap-1 px-2 py-1 bg-red-900/20 border border-red-900/30 rounded text-[10px] text-forexia-red">
            {p}
            <button onClick={() => removePair(p)} className="text-red-400 hover:text-red-300 ml-1 font-bold">×</button>
          </span>
        ))}
        {blacklist.length === 0 && <span className="text-[10px] text-gray-600">No pairs blacklisted</span>}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={newPair}
          onChange={e => setNewPair(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && addPair()}
          placeholder="AUDNZD"
          className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-[10px] text-white focus:border-forexia-accent outline-none"
        />
        <Button onClick={addPair}>Add</Button>
      </div>
    </Card>
  );
}

/* ───── AI Workflow Panel ───── */
function AIWorkflowPanel({ aiState, actions }) {
  const [aiWorkflow, setAiWorkflow] = useState(null);
  const [scanInterval, setScanInterval] = useState(150);
  const [dailyLimit, setDailyLimit] = useState(1400);

  useEffect(() => {
    actions.getAiWorkflow().then(d => {
      if (d) {
        setAiWorkflow(d);
        setScanInterval(d.scan_interval || 150);
        setDailyLimit(d.daily_limit || 1400);
      }
    });
  }, []);

  const saveAiConfig = async () => {
    await actions.updateAiConfig({ scan_interval: scanInterval, daily_limit: dailyLimit });
    const d = await actions.getAiWorkflow();
    if (d) setAiWorkflow(d);
  };

  const status = aiState?.status || aiWorkflow?.status || {};

  return (
    <Card title="AI Agent Workflow" accent="purple">
      <div className="space-y-4">
        {/* Status */}
        <div className="grid grid-cols-4 gap-3">
          <Stat label="Model" value={status.model || '?'} color="text-forexia-accent" />
          <Stat label="Daily Calls" value={`${status.daily_calls || 0}/${status.daily_limit || 1400}`} color="text-forexia-gold" />
          <Stat label="Scan Interval" value={`${status.scan_interval || 150}s`} />
          <Stat label="Status" value={status.enabled ? 'ACTIVE' : 'OFF'} color={status.enabled ? 'text-forexia-green' : 'text-forexia-red'} />
        </div>

        {/* Config */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-[9px] text-gray-500 uppercase tracking-wider block mb-1">Scan Interval (sec)</label>
            <input
              type="number"
              value={scanInterval}
              onChange={e => setScanInterval(parseInt(e.target.value))}
              min="30"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-[10px] text-white focus:border-forexia-accent outline-none"
            />
          </div>
          <div>
            <label className="text-[9px] text-gray-500 uppercase tracking-wider block mb-1">Daily API Limit</label>
            <input
              type="number"
              value={dailyLimit}
              onChange={e => setDailyLimit(parseInt(e.target.value))}
              min="10"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-[10px] text-white focus:border-forexia-accent outline-none"
            />
          </div>
        </div>
        <Button variant="primary" onClick={saveAiConfig}>Update AI Config</Button>

        {/* Exhausted Models */}
        {aiWorkflow?.models_exhausted && Object.keys(aiWorkflow.models_exhausted).length > 0 && (
          <div className="mt-2">
            <div className="text-[9px] text-gray-500 uppercase tracking-wider mb-1">Rate-Limited Models</div>
            {Object.entries(aiWorkflow.models_exhausted).map(([m, secs]) => (
              <div key={m} className="flex justify-between text-[10px] py-0.5">
                <span className="text-gray-400">{m}</span>
                <span className="text-forexia-red">{Math.round(secs)}s remaining</span>
              </div>
            ))}
          </div>
        )}

        {/* Recent AI Analyses */}
        {aiState?.analyses && Object.keys(aiState.analyses).length > 0 && (
          <div>
            <div className="text-[9px] text-gray-500 uppercase tracking-wider mb-2">Latest AI Analyses</div>
            <div className="space-y-2">
              {Object.entries(aiState.analyses).map(([sym, a]) => (
                <div key={sym} className="p-2 bg-gray-900/50 rounded border border-gray-800/50">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] font-bold text-white">{sym}</span>
                    <div className="flex items-center gap-2">
                      <Badge text={a.market_regime || 'unknown'} variant={a.bias === 'bullish' ? 'success' : a.bias === 'bearish' ? 'danger' : 'default'} />
                      <span className="text-[10px] text-forexia-gold">{((a.confidence ?? 0) * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  <p className="text-[9px] text-gray-400 leading-relaxed">{a.narrative}</p>
                  {a.trade_idea && (
                    <p className="text-[9px] text-forexia-accent mt-1">{a.trade_idea}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent Trade Signals */}
        {aiState?.ai_trade_signals && aiState.ai_trade_signals.length > 0 && (
          <div>
            <div className="text-[9px] text-gray-500 uppercase tracking-wider mb-2">Recent AI Trade Signals</div>
            <div className="space-y-1">
              {aiState.ai_trade_signals.slice(-10).reverse().map((s, i) => (
                <div key={i} className="flex items-center justify-between text-[10px] p-1.5 bg-gray-900/30 rounded">
                  <div className="flex items-center gap-2">
                    <Badge text={s.action || '?'} variant={s.action === 'BUY' ? 'success' : 'danger'} />
                    <span className="text-white font-bold">{s.symbol || '?'}</span>
                  </div>
                  <div className="flex items-center gap-3 text-gray-400">
                    <span>@ {s.entry_price ?? '—'}</span>
                    <span>SL: {s.stop_loss ?? '—'}</span>
                    <span>TP: {s.take_profit ?? '—'}</span>
                    <span className="text-forexia-gold">{((s.confidence ?? 0) * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Market Structure Analysis */}
        {aiWorkflow?.market_structure && Object.keys(aiWorkflow.market_structure).length > 0 && (
          <div>
            <div className="text-[9px] text-gray-500 uppercase tracking-wider mb-2">⚡ Computed Market Structure</div>
            <div className="space-y-2">
              {Object.entries(aiWorkflow.market_structure).map(([sym, ms]) => (
                <div key={sym} className="p-2.5 bg-gray-900/50 rounded border border-gray-800/50">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[11px] font-bold text-white">{sym}</span>
                    <div className="flex items-center gap-2">
                      <Badge
                        text={ms.trend}
                        variant={ms.trend === 'bullish' ? 'success' : ms.trend === 'bearish' ? 'danger' : 'default'}
                      />
                      <Badge text={ms.volatility_state} variant={ms.volatility_state === 'high' || ms.volatility_state === 'extreme' ? 'warning' : 'info'} />
                      <span className={`text-[10px] font-bold ${ms.bias_score > 0.2 ? 'text-forexia-green' : ms.bias_score < -0.2 ? 'text-forexia-red' : 'text-gray-400'}`}>
                        {ms.bias_score > 0 ? '+' : ''}{ms.bias_score}
                      </span>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-[9px]">
                    <div>
                      <span className="text-gray-500">Structure:</span>{' '}
                      <span className="text-gray-300">{(ms.current_structure || '').replace(/_/g, ' ')}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">ATR:</span>{' '}
                      <span className="text-gray-300">{ms.atr_pips ?? '—'} pips</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Strength:</span>{' '}
                      <span className="text-gray-300">{((ms.trend_strength ?? 0) * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  {ms.support_levels?.length > 0 && (
                    <div className="text-[9px] mt-1">
                      <span className="text-forexia-green">S: </span>
                      <span className="text-gray-400">{ms.support_levels.slice(0, 3).join(', ')}</span>
                    </div>
                  )}
                  {ms.resistance_levels?.length > 0 && (
                    <div className="text-[9px]">
                      <span className="text-forexia-red">R: </span>
                      <span className="text-gray-400">{ms.resistance_levels.slice(0, 3).join(', ')}</span>
                    </div>
                  )}
                  {ms.order_blocks?.length > 0 && (
                    <div className="text-[9px] mt-0.5">
                      <span className="text-forexia-purple">OBs: </span>
                      <span className="text-gray-400">
                        {ms.order_blocks.map(ob => `${ob.type.replace('_ob', '')} @ ${ob.price}`).join(', ')}
                      </span>
                    </div>
                  )}
                  {ms.fair_value_gaps?.length > 0 && (
                    <div className="text-[9px]">
                      <span className="text-forexia-cyan">FVGs: </span>
                      <span className="text-gray-400">
                        {ms.fair_value_gaps.map(fvg => `${fvg.type.replace('_fvg', '')} ${fvg.low}-${fvg.high}`).join(', ')}
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ───── Open Positions Panel ───── */
function AdminPositions({ positions }) {
  if (!positions || positions.length === 0) {
    return (
      <Card title="Open Positions">
        <div className="text-[10px] text-gray-600">No open positions</div>
      </Card>
    );
  }

  return (
    <Card title={`Open Positions (${positions.length})`}>
      <div className="overflow-x-auto">
        <table className="w-full text-[10px]">
          <thead>
            <tr className="text-gray-500 uppercase border-b border-gray-800">
              <th className="text-left py-1 px-2">Symbol</th>
              <th className="text-left py-1 px-2">Side</th>
              <th className="text-right py-1 px-2">Volume</th>
              <th className="text-right py-1 px-2">Entry</th>
              <th className="text-right py-1 px-2">Current</th>
              <th className="text-right py-1 px-2">SL</th>
              <th className="text-right py-1 px-2">TP</th>
              <th className="text-right py-1 px-2">P&L</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p, i) => {
              const pnl = parseFloat(p.profit || 0) + parseFloat(p.swap || 0);
              return (
                <tr key={i} className="border-b border-gray-800/40 hover:bg-gray-800/30">
                  <td className="py-1.5 px-2 font-bold text-white">{(p.symbol||'').replace('.','')}</td>
                  <td className="py-1.5 px-2">
                    <Badge text={p.type === 0 ? 'BUY' : 'SELL'} variant={p.type === 0 ? 'success' : 'danger'} />
                  </td>
                  <td className="py-1.5 px-2 text-right text-gray-400">{p.lots ?? p.volume ?? '—'}</td>
                  <td className="py-1.5 px-2 text-right text-gray-400">{parseFloat(p.open_price||0).toFixed(5)}</td>
                  <td className="py-1.5 px-2 text-right text-white">{parseFloat(p.current_price||p.open_price||0).toFixed(5)}</td>
                  <td className="py-1.5 px-2 text-right text-forexia-red">{parseFloat(p.sl||0).toFixed(5)}</td>
                  <td className="py-1.5 px-2 text-right text-forexia-green">{parseFloat(p.tp||0).toFixed(5)}</td>
                  <td className={`py-1.5 px-2 text-right font-bold ${pnl >= 0 ? 'text-forexia-green' : 'text-forexia-red'}`}>
                    ${pnl.toFixed(2)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* ───── Daily P&L Heatmap ───── */
function DailyPnLHeatmap({ dailyPnl }) {
  if (!dailyPnl || !Array.isArray(dailyPnl) || dailyPnl.length === 0) return null;
  const maxAbs = Math.max(...dailyPnl.map(d => Math.abs(d.pnl ?? 0)), 1);

  return (
    <Card title="Daily P&L" accent="gold">
      <div className="grid grid-cols-7 gap-1">
        {dailyPnl.slice(-21).map((d, i) => {
          const pnl = d.pnl ?? 0;
          const intensity = Math.min(1, Math.abs(pnl) / maxAbs);
          const bg = pnl >= 0
            ? `rgba(16, 185, 129, ${0.1 + intensity * 0.6})`
            : `rgba(239, 68, 68, ${0.1 + intensity * 0.6})`;
          return (
            <div
              key={i}
              className="aspect-square rounded flex flex-col items-center justify-center"
              style={{ background: bg }}
              title={`${d.date || '?'}: $${pnl.toFixed(2)}`}
            >
              <div className="text-[8px] text-gray-400">{(d.date || '').slice(5)}</div>
              <div className={`text-[9px] font-bold ${pnl >= 0 ? 'text-forexia-green' : 'text-forexia-red'}`}>
                ${pnl.toFixed(0)}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ───── Server Logs ───── */
function LogViewer({ actions }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    const data = await actions.getLogs();
    if (data?.logs) setLogs(data.logs);
    setLoading(false);
  };

  useEffect(() => { refresh(); }, []);

  return (
    <Card title="Server Logs">
      <div className="flex justify-end mb-2">
        <Button onClick={refresh} disabled={loading}>{loading ? 'Loading...' : 'Refresh'}</Button>
      </div>
      <div className="max-h-64 overflow-y-auto bg-gray-900/80 rounded p-2 font-mono text-[9px] text-gray-400 space-y-0.5">
        {logs.slice(-50).map((line, i) => (
          <div
            key={i}
            className={`${
              line.includes('ERROR') ? 'text-forexia-red' :
              line.includes('WARNING') ? 'text-forexia-gold' :
              line.includes('EXECUTED') ? 'text-forexia-green' : ''
            }`}
          >
            {line}
          </div>
        ))}
        {logs.length === 0 && <div className="text-gray-600">No logs available</div>}
      </div>
    </Card>
  );
}

/* ───── Quick Actions Bar ───── */
function QuickActions({ actions, overview }) {
  const [msg, setMsg] = useState('');

  const exec = async (fn, name) => {
    setMsg(`${name}...`);
    await fn();
    setMsg(`${name} — done!`);
    setTimeout(() => setMsg(''), 3000);
  };

  return (
    <Card title="Quick Actions">
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" onClick={() => exec(actions.triggerScan, 'Scan')}>Force Scan</Button>
        <Button variant="success" onClick={() => exec(actions.toggleBot, 'Toggle Bot')}>
          {overview?.system?.auto_trade ? 'Disable Bot' : 'Enable Bot'}
        </Button>
        <Button variant="default" onClick={() => exec(actions.resetDaily, 'Daily Reset')}>Daily Reset</Button>
        <Button variant="danger" onClick={() => {
          if (window.confirm('Close ALL open positions?')) exec(actions.closeAll, 'Close All');
        }}>Close All</Button>
        <Button variant="default" onClick={() => exec(actions.resetConsecutiveLosses, 'Reset Streak')}>Reset Loss Streak</Button>
      </div>
      {msg && <div className="mt-2 text-[10px] text-forexia-accent">{msg}</div>}
    </Card>
  );
}

/* ───── Hourly Performance ───── */
function HourlyPerformance({ hourly }) {
  if (!hourly || typeof hourly !== 'object' || Object.keys(hourly).length === 0) return null;
  const maxPnl = Math.max(...Object.values(hourly).map(h => Math.abs(h?.pnl ?? 0)), 1);

  return (
    <Card title="Performance by Hour (UTC)" accent="cyan">
      <div className="flex items-end gap-1 h-24">
        {Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0')).map(hour => {
          const h = hourly[hour] || { wins: 0, losses: 0, pnl: 0 };
          const hpnl = h.pnl ?? 0;
          const height = Math.max(5, (Math.abs(hpnl) / maxPnl) * 100);
          return (
            <div key={hour} className="flex-1 flex flex-col items-center">
              <div
                className={`w-full rounded-t ${hpnl >= 0 ? 'bg-forexia-green/60' : 'bg-forexia-red/60'}`}
                style={{ height: `${height}%` }}
                title={`${hour}:00 — $${hpnl.toFixed(2)} (${h.wins||0}W/${h.losses||0}L)`}
              />
              <div className="text-[7px] text-gray-600 mt-0.5">{hour}</div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ───── Stats Summary ───── */
function StatsSummary({ performance }) {
  if (!performance) return null;

  return (
    <Card title="Advanced Stats">
      <div className="grid grid-cols-4 gap-4">
        <Stat label="Max Drawdown" value={`$${(performance.max_drawdown||0).toFixed(2)}`} color="text-forexia-red" />
        <Stat label="Win Streak" value={performance.max_win_streak||0} color="text-forexia-green" />
        <Stat label="Loss Streak" value={performance.max_loss_streak||0} color="text-forexia-red" />
        <Stat
          label="Profitable Days"
          value={`${performance.profitable_days||0}/${(performance.profitable_days||0)+(performance.losing_days||0)}`}
          color="text-forexia-gold"
        />
      </div>
    </Card>
  );
}

/* ═══════════════════════════════════════════════════
 *  MAIN SUPER ADMIN COMPONENT
 * ═══════════════════════════════════════════════════ */
function SuperAdminInner({ onBack }) {
  const [apiData, setApiData] = useState(null);
  const [apiError, setApiError] = useState(null);
  const [tab, setTab] = useState('overview');

  // Simple direct fetch instead of hook — for debugging
  useEffect(() => {
    fetch('/api/admin/overview')
      .then(r => r.json())
      .then(d => setApiData(d))
      .catch(e => setApiError(e.message));
  }, []);

  // If we can't even render a basic div, the issue is in routing/import
  if (!apiData && !apiError) {
    return (
      <div style={{ minHeight: '100vh', background: '#0a0e17', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
        <div style={{ fontSize: 24, fontWeight: 'bold', marginBottom: 16, color: '#f59e0b' }}>SUPER ADMIN</div>
        <div style={{ fontSize: 14, color: '#6b7280' }}>Loading data from API...</div>
        <div style={{ marginTop: 20, width: 40, height: 40, border: '3px solid #f59e0b', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (apiError) {
    return (
      <div style={{ minHeight: '100vh', background: '#0a0e17', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
        <div style={{ fontSize: 24, fontWeight: 'bold', marginBottom: 16, color: '#ef4444' }}>API ERROR</div>
        <div style={{ fontSize: 14, color: '#9ca3af', marginBottom: 20 }}>{apiError}</div>
        <button onClick={onBack} style={{ padding: '8px 20px', background: '#374151', color: '#9ca3af', border: '1px solid #4b5563', borderRadius: 6, cursor: 'pointer' }}>← Back to Dashboard</button>
      </div>
    );
  }

  // Data loaded — render full admin dashboard
  const overview = apiData;
  const perf = overview?.performance || {};
  const acct = overview?.account || {};
  const system = overview?.system || {};

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'ai', label: 'AI Workflow' },
    { id: 'settings', label: 'Settings' },
    { id: 'logs', label: 'Logs' },
  ];

  return (
    <div style={{ minHeight: '100vh', background: '#0a0e17', color: 'white', fontFamily: 'JetBrains Mono, monospace' }}>
      {/* Header */}
      <div style={{ borderBottom: '1px solid rgba(31,41,55,0.6)', padding: '12px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <button onClick={onBack} style={{ color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>← Back to Dashboard</button>
          <div style={{ width: 1, height: 20, background: '#1f2937' }} />
          <span style={{ fontSize: 18, fontWeight: 900 }}>
            <span style={{ color: '#f59e0b' }}>SUPER</span>
            <span style={{ color: 'white', marginLeft: 6 }}>ADMIN</span>
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 10 }}>
          <span style={{ padding: '2px 8px', borderRadius: 4, background: system.broker_connected ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)', color: system.broker_connected ? '#10b981' : '#ef4444', border: `1px solid ${system.broker_connected ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`, fontWeight: 700, textTransform: 'uppercase' }}>
            {system.broker_connected ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
          <span style={{ color: '#4b5563' }}>{system.session || 'UNKNOWN'}</span>
        </div>
      </div>

      {/* Tab Bar */}
      <div style={{ borderBottom: '1px solid rgba(31,41,55,0.4)', padding: '0 24px' }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                padding: '10px 16px',
                fontSize: 10,
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                background: 'none',
                border: 'none',
                borderBottom: `2px solid ${tab === t.id ? '#f59e0b' : 'transparent'}`,
                color: tab === t.id ? '#f59e0b' : '#6b7280',
                cursor: 'pointer',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div style={{ padding: 24, maxWidth: 1920, margin: '0 auto' }}>
        {tab === 'overview' && (
          <div>
            {/* Stats Grid */}
            <div style={{ background: 'rgba(17,24,39,0.8)', border: '1px solid rgba(30,41,59,0.6)', borderRadius: 8, padding: 16, marginBottom: 16 }}>
              <h3 style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#10b981', marginBottom: 12 }}>Performance Overview</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 16 }}>
                <StatBox label="Balance" value={`$${(acct.balance||0).toLocaleString(undefined, {minimumFractionDigits: 2})}`} />
                <StatBox label="Equity" value={`$${(acct.equity||0).toLocaleString(undefined, {minimumFractionDigits: 2})}`} />
                <StatBox label="Net P&L" value={`$${(perf.net_pnl||0).toFixed(2)}`} color={perf.net_pnl >= 0 ? '#10b981' : '#ef4444'} />
                <StatBox label="Win Rate" value={`${(perf.win_rate||0).toFixed(1)}%`} color={perf.win_rate >= 50 ? '#10b981' : '#f59e0b'} />
                <StatBox label="Profit Factor" value={(perf.profit_factor||0).toFixed(2)} color={perf.profit_factor >= 1.5 ? '#10b981' : '#f59e0b'} />
                <StatBox label="Total Trades" value={perf.total_trades||0} sub={`W:${perf.wins||0} L:${perf.losses||0}`} />
              </div>
            </div>

            {/* Direction + Risk + Quick Actions */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 16 }}>
              {/* BUY vs SELL */}
              <div style={{ background: 'rgba(17,24,39,0.8)', border: '1px solid rgba(30,41,59,0.6)', borderRadius: 8, padding: 16 }}>
                <h3 style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#8b5cf6', marginBottom: 12 }}>BUY vs SELL</h3>
                {['BUY', 'SELL'].map(dir => {
                  const d = (overview?.by_direction || {})[dir] || {};
                  const wr = d.count > 0 ? (d.wins / d.count * 100) : 0;
                  return (
                    <div key={dir} style={{ padding: 12, borderRadius: 6, border: `1px solid ${dir === 'BUY' ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`, background: dir === 'BUY' ? 'rgba(16,185,129,0.05)' : 'rgba(239,68,68,0.05)', marginBottom: 8 }}>
                      <div style={{ fontSize: 11, fontWeight: 700 }}>{dir}</div>
                      <div style={{ fontSize: 18, fontWeight: 900, color: (d.profit||0) >= 0 ? '#10b981' : '#ef4444' }}>${(d.profit||0).toFixed(2)}</div>
                      <div style={{ fontSize: 9, color: '#6b7280', marginTop: 4 }}>{d.count||0} trades · {wr.toFixed(0)}% WR</div>
                    </div>
                  );
                })}
              </div>

              {/* Risk State */}
              <div style={{ background: 'rgba(17,24,39,0.8)', border: '1px solid rgba(30,41,59,0.6)', borderRadius: 8, padding: 16 }}>
                <h3 style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#ef4444', marginBottom: 12 }}>Risk State</h3>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <span style={{ fontSize: 10, color: '#9ca3af' }}>Consecutive Losses</span>
                  <span style={{ fontSize: 18, fontWeight: 900, color: (overview?.risk_state?.consecutive_losses||0) >= 3 ? '#ef4444' : '#10b981' }}>{overview?.risk_state?.consecutive_losses || 0}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 10, color: '#9ca3af' }}>Anti-Tilt</span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: overview?.risk_state?.anti_tilt_active ? '#ef4444' : '#10b981' }}>{overview?.risk_state?.anti_tilt_active ? 'ACTIVE' : 'INACTIVE'}</span>
                </div>
              </div>

              {/* Quick Actions */}
              <div style={{ background: 'rgba(17,24,39,0.8)', border: '1px solid rgba(30,41,59,0.6)', borderRadius: 8, padding: 16 }}>
                <h3 style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#3b82f6', marginBottom: 12 }}>Quick Actions</h3>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  <ActionBtn label="Force Scan" onClick={() => fetch('/api/bot/scan', {method:'POST'})} />
                  <ActionBtn label="Toggle Bot" onClick={() => fetch('/api/bot/toggle', {method:'POST'})} color="#10b981" />
                  <ActionBtn label="Daily Reset" onClick={() => fetch('/api/reset/daily', {method:'POST'})} />
                  <ActionBtn label="Close All" onClick={() => { if(window.confirm('Close ALL?')) fetch('/api/close-all', {method:'POST'}); }} color="#ef4444" />
                </div>
              </div>
            </div>

            {/* Open Positions */}
            <div style={{ background: 'rgba(17,24,39,0.8)', border: '1px solid rgba(30,41,59,0.6)', borderRadius: 8, padding: 16, marginBottom: 16 }}>
              <h3 style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#3b82f6', marginBottom: 12 }}>Open Positions ({(overview?.open_positions||[]).length})</h3>
              {(overview?.open_positions||[]).length === 0 ? (
                <div style={{ fontSize: 10, color: '#4b5563' }}>No open positions</div>
              ) : (
                <table style={{ width: '100%', fontSize: 10, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ color: '#6b7280', textTransform: 'uppercase', borderBottom: '1px solid #1f2937' }}>
                      <th style={{ textAlign: 'left', padding: '4px 8px' }}>Symbol</th>
                      <th style={{ textAlign: 'left', padding: '4px 8px' }}>Side</th>
                      <th style={{ textAlign: 'right', padding: '4px 8px' }}>Lots</th>
                      <th style={{ textAlign: 'right', padding: '4px 8px' }}>Entry</th>
                      <th style={{ textAlign: 'right', padding: '4px 8px' }}>SL</th>
                      <th style={{ textAlign: 'right', padding: '4px 8px' }}>TP</th>
                      <th style={{ textAlign: 'right', padding: '4px 8px' }}>P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(overview?.open_positions||[]).map((p, i) => {
                      const pnl = parseFloat(p.profit||0) + parseFloat(p.swap||0);
                      return (
                        <tr key={i} style={{ borderBottom: '1px solid rgba(31,41,55,0.4)' }}>
                          <td style={{ padding: '6px 8px', fontWeight: 700 }}>{(p.symbol||'').replace('.','')}</td>
                          <td style={{ padding: '6px 8px', color: p.type === 0 ? '#10b981' : '#ef4444', fontWeight: 700 }}>{p.type === 0 ? 'BUY' : 'SELL'}</td>
                          <td style={{ padding: '6px 8px', textAlign: 'right', color: '#9ca3af' }}>{p.lots ?? p.volume ?? '—'}</td>
                          <td style={{ padding: '6px 8px', textAlign: 'right', color: '#9ca3af' }}>{parseFloat(p.open_price||0).toFixed(5)}</td>
                          <td style={{ padding: '6px 8px', textAlign: 'right', color: '#ef4444' }}>{parseFloat(p.sl||0).toFixed(5)}</td>
                          <td style={{ padding: '6px 8px', textAlign: 'right', color: '#10b981' }}>{parseFloat(p.tp||0).toFixed(5)}</td>
                          <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 700, color: pnl >= 0 ? '#10b981' : '#ef4444' }}>${pnl.toFixed(2)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>

            {/* Pair Performance */}
            <div style={{ background: 'rgba(17,24,39,0.8)', border: '1px solid rgba(30,41,59,0.6)', borderRadius: 8, padding: 16 }}>
              <h3 style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#06b6d4', marginBottom: 12 }}>Performance by Pair</h3>
              {(overview?.by_pair||[]).length === 0 ? (
                <div style={{ fontSize: 10, color: '#4b5563' }}>No trade data</div>
              ) : (
                <table style={{ width: '100%', fontSize: 10, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ color: '#6b7280', textTransform: 'uppercase', borderBottom: '1px solid #1f2937' }}>
                      <th style={{ textAlign: 'left', padding: '4px 8px' }}>Symbol</th>
                      <th style={{ textAlign: 'right', padding: '4px 8px' }}>P&L</th>
                      <th style={{ textAlign: 'right', padding: '4px 8px' }}>Trades</th>
                      <th style={{ textAlign: 'right', padding: '4px 8px' }}>Win%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(overview?.by_pair||[]).map((p, i) => {
                      const profit = p.profit ?? 0;
                      const count = p.count ?? 0;
                      const wins = p.wins ?? 0;
                      const wr = count > 0 ? (wins / count * 100) : 0;
                      return (
                        <tr key={i} style={{ borderBottom: '1px solid rgba(31,41,55,0.4)' }}>
                          <td style={{ padding: '6px 8px', fontWeight: 700 }}>{p.symbol}</td>
                          <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 700, color: profit >= 0 ? '#10b981' : '#ef4444' }}>${profit.toFixed(2)}</td>
                          <td style={{ padding: '6px 8px', textAlign: 'right', color: '#9ca3af' }}>{count}</td>
                          <td style={{ padding: '6px 8px', textAlign: 'right', color: '#9ca3af' }}>{wr.toFixed(0)}%</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {tab === 'ai' && (
          <AIWorkflowPanel aiState={overview?.ai_state} actions={{ getAiWorkflow: () => fetch('/api/admin/ai-workflow').then(r=>r.json()).catch(()=>null), updateAiConfig: (c) => fetch('/api/admin/ai-config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(c)}).then(r=>r.json()).catch(()=>null) }} />
        )}

        {tab === 'settings' && (
          <div style={{ background: 'rgba(17,24,39,0.8)', border: '1px solid rgba(30,41,59,0.6)', borderRadius: 8, padding: 16 }}>
            <h3 style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#f59e0b', marginBottom: 12 }}>Settings</h3>
            <pre style={{ fontSize: 9, color: '#9ca3af', whiteSpace: 'pre-wrap' }}>{JSON.stringify(overview?.settings, null, 2)}</pre>
          </div>
        )}

        {tab === 'logs' && (
          <LogViewer actions={{ getLogs: () => fetch('/api/admin/logs').then(r=>r.json()).catch(()=>null) }} />
        )}
      </div>

      {/* Footer */}
      <div style={{ borderTop: '1px solid rgba(31,41,55,0.4)', padding: '8px 24px', display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#374151' }}>
        <span>Forexia Super Admin · Full System Control</span>
        <span>{new Date().toUTCString()}</span>
      </div>
    </div>
  );
}

/* Simple inline stat component */
function StatBox({ label, value, sub, color = 'white' }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 18, fontWeight: 900, color }}>{value}</div>
      <div style={{ fontSize: 9, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</div>
      {sub && <div style={{ fontSize: 9, color: '#4b5563', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

/* Simple action button */
function ActionBtn({ label, onClick, color = '#3b82f6' }) {
  return (
    <button
      onClick={onClick}
      style={{ padding: '6px 12px', borderRadius: 4, fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', background: `${color}20`, color, border: `1px solid ${color}40`, cursor: 'pointer' }}
    >
      {label}
    </button>
  );
}

/* Default export — no class-based error boundary (breaks Vite Fast Refresh) */
export default function SuperAdmin({ onBack }) {
  const [crashed, setCrashed] = useState(false);
  const [crashMsg, setCrashMsg] = useState('');

  useEffect(() => {
    const handler = (event) => {
      if (event.error) {
        setCrashed(true);
        setCrashMsg(event.error.message || 'Unknown error');
      }
    };
    window.addEventListener('error', handler);
    return () => window.removeEventListener('error', handler);
  }, []);

  if (crashed) {
    return (
      <div style={{ minHeight: '100vh', background: '#0a0e17', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 32 }}>
        <div style={{ maxWidth: 480, width: '100%', background: '#111827', border: '1px solid rgba(127,29,29,0.4)', borderRadius: 12, padding: 24 }}>
          <h2 style={{ fontSize: 18, fontWeight: 900, color: '#f87171', marginBottom: 12 }}>Admin Dashboard Error</h2>
          <p style={{ fontSize: 13, color: '#9ca3af', marginBottom: 16 }}>{crashMsg}</p>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => { setCrashed(false); setCrashMsg(''); }} style={{ padding: '8px 16px', background: 'rgba(30,58,138,0.3)', color: '#60a5fa', border: '1px solid rgba(30,58,138,0.4)', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>Retry</button>
            <button onClick={onBack} style={{ padding: '8px 16px', background: '#374151', color: '#9ca3af', border: '1px solid #4b5563', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>← Back</button>
          </div>
        </div>
      </div>
    );
  }

  return <SuperAdminInner onBack={onBack} />;
}
