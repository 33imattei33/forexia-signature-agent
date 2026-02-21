/**
 * Standalone entry point for the Super Admin Dashboard.
 * Completely separate from App.jsx — no hooks, no PIN gate, no HMR issues.
 * Access via: http://localhost:3000/admin.html
 */
import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';

/* ═══════════════════════════════════════════════════
 *  INLINE SUPER ADMIN — self-contained, no external component imports
 *  This avoids any Vite Fast Refresh / module transform issues
 * ═══════════════════════════════════════════════════ */

function StatBox({ label, value, sub, color = 'white' }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 18, fontWeight: 900, color }}>{value}</div>
      <div style={{ fontSize: 9, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</div>
      {sub && <div style={{ fontSize: 9, color: '#4b5563', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function ActionBtn({ label, onClick, color = '#3b82f6', disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{ padding: '6px 12px', borderRadius: 4, fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', background: `${color}20`, color, border: `1px solid ${color}40`, cursor: disabled ? 'wait' : 'pointer', opacity: disabled ? 0.6 : 1 }}
    >
      {label}
    </button>
  );
}

function QuickActions({ refreshOverview }) {
  const [busy, setBusy] = React.useState(null);
  const [msg, setMsg] = React.useState('');

  const exec = async (label, url, confirm_msg) => {
    if (confirm_msg && !window.confirm(confirm_msg)) return;
    setBusy(label);
    setMsg('');
    try {
      const res = await fetch(url, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'OK') {
        const detail = data.message || (data.pairs_scanned != null ? `Scanned ${data.pairs_scanned} pairs, ${data.signals_found} signals, ${data.trades_executed} trades` : 'Done');
        setMsg(`✅ ${label}: ${detail}`);
        refreshOverview();
      } else {
        setMsg(`❌ ${label}: ${JSON.stringify(data)}`);
      }
    } catch (err) {
      setMsg(`❌ ${label}: ${err.message}`);
    }
    setBusy(null);
    setTimeout(() => setMsg(''), 6000);
  };

  return (
    <div style={{ background: 'rgba(17,24,39,0.8)', border: '1px solid rgba(30,41,59,0.6)', borderRadius: 8, padding: 16 }}>
      <h3 style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#3b82f6', marginBottom: 12 }}>Quick Actions</h3>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <ActionBtn label={busy === 'Force Scan' ? 'Scanning...' : 'Force Scan'} onClick={() => exec('Force Scan', '/api/bot/scan')} disabled={!!busy} />
        <ActionBtn label={busy === 'Toggle Bot' ? 'Toggling...' : 'Toggle Bot'} onClick={() => exec('Toggle Bot', '/api/bot/toggle')} color="#10b981" disabled={!!busy} />
        <ActionBtn label={busy === 'Daily Reset' ? 'Resetting...' : 'Daily Reset'} onClick={() => exec('Daily Reset', '/api/reset/daily')} disabled={!!busy} />
        <ActionBtn label={busy === 'Close All' ? 'Closing...' : 'Close All'} onClick={() => exec('Close All', '/api/close-all', 'Close ALL positions?')} color="#ef4444" disabled={!!busy} />
      </div>
      {msg && <div style={{ marginTop: 8, fontSize: 10, color: msg.startsWith('✅') ? '#10b981' : '#ef4444', lineHeight: 1.5 }}>{msg}</div>}
    </div>
  );
}

function AdminDashboard() {
  const [data, setData] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [tab, setTab] = React.useState('overview');
  const [logs, setLogs] = React.useState([]);
  const [aiWorkflow, setAiWorkflow] = React.useState(null);

  const refreshOverview = React.useCallback(() => {
    fetch('/api/admin/overview')
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d => setData(d))
      .catch(e => { if (!data) setError(e.message); });
  }, [data]);

  React.useEffect(() => {
    refreshOverview();
    const iv = setInterval(refreshOverview, 5000);
    return () => clearInterval(iv);
  }, [refreshOverview]);

  if (error) {
    return (
      <div style={{ minHeight: '100vh', background: '#0a0e17', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
        <div style={{ fontSize: 24, fontWeight: 900, color: '#ef4444', marginBottom: 16 }}>API ERROR</div>
        <div style={{ fontSize: 14, color: '#9ca3af', marginBottom: 20 }}>{error}</div>
        <button onClick={() => window.location.reload()} style={{ padding: '8px 20px', background: '#374151', color: '#9ca3af', border: '1px solid #4b5563', borderRadius: 6, cursor: 'pointer' }}>Reload</button>
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ minHeight: '100vh', background: '#0a0e17', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
        <div style={{ fontSize: 24, fontWeight: 900, color: '#f59e0b', marginBottom: 16 }}>SUPER ADMIN</div>
        <div style={{ fontSize: 14, color: '#6b7280' }}>Loading...</div>
        <div style={{ marginTop: 20, width: 40, height: 40, border: '3px solid #f59e0b', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  const overview = data;
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
          <a href="/" style={{ color: '#6b7280', fontSize: 12, textDecoration: 'none' }}>← Back to Dashboard</a>
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
                padding: '10px 16px', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em',
                background: 'none', border: 'none', borderBottom: `2px solid ${tab === t.id ? '#f59e0b' : 'transparent'}`,
                color: tab === t.id ? '#f59e0b' : '#6b7280', cursor: 'pointer',
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
              <QuickActions refreshOverview={refreshOverview} />
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

        {tab === 'ai' && <AIWorkflowTab overview={overview} aiWorkflow={aiWorkflow} setAiWorkflow={setAiWorkflow} refreshOverview={refreshOverview} />}

        {tab === 'settings' && (
          <div style={{ background: 'rgba(17,24,39,0.8)', border: '1px solid rgba(30,41,59,0.6)', borderRadius: 8, padding: 16 }}>
            <h3 style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#f59e0b', marginBottom: 12 }}>Settings</h3>
            <pre style={{ fontSize: 9, color: '#9ca3af', whiteSpace: 'pre-wrap' }}>{JSON.stringify(overview?.settings, null, 2)}</pre>
          </div>
        )}

        {tab === 'logs' && <LogsTab logs={logs} setLogs={setLogs} />}
      </div>

      {/* Footer */}
      <div style={{ borderTop: '1px solid rgba(31,41,55,0.4)', padding: '8px 24px', display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#374151' }}>
        <span>Forexia Super Admin · Full System Control</span>
        <span>{new Date().toUTCString()}</span>
      </div>
    </div>
  );
}

function AIWorkflowTab({ overview, aiWorkflow, setAiWorkflow, refreshOverview }) {
  const [scanInterval, setScanInterval] = React.useState(150);
  const [dailyLimit, setDailyLimit] = React.useState(1400);
  const [saving, setSaving] = React.useState(false);
  const [saveMsg, setSaveMsg] = React.useState('');
  const [userEdited, setUserEdited] = React.useState(false);

  const refreshWorkflow = React.useCallback(() => {
    fetch('/api/admin/ai-workflow')
      .then(r => r.json())
      .then(d => {
        setAiWorkflow(d);
        if (!userEdited) {
          setScanInterval(d.scan_interval || 150);
          setDailyLimit(d.daily_limit || 1400);
        }
      })
      .catch(() => {});
  }, [userEdited]);

  const handleUpdateConfig = async () => {
    setSaving(true);
    setSaveMsg('');
    try {
      const res = await fetch('/api/admin/ai-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scan_interval: scanInterval, daily_limit: dailyLimit }),
      });
      const data = await res.json();
      if (data.status === 'OK') {
        setSaveMsg(`✅ Saved! Interval: ${data.scan_interval}s, Limit: ${data.daily_limit}`);
        setScanInterval(data.scan_interval);
        setDailyLimit(data.daily_limit);
        setUserEdited(false);
        refreshWorkflow();
        refreshOverview();
      } else {
        setSaveMsg('❌ Server error');
      }
    } catch (err) {
      setSaveMsg('❌ Network error: ' + err.message);
    }
    setSaving(false);
    setTimeout(() => setSaveMsg(''), 5000);
  };

  // Poll AI workflow every 5s
  React.useEffect(() => {
    refreshWorkflow();
    const iv = setInterval(refreshWorkflow, 5000);
    return () => clearInterval(iv);
  }, [refreshWorkflow]);

  // Prefer aiWorkflow.status (polled every 5s) over overview (may be stale)
  const status = aiWorkflow?.status || overview?.ai_state?.status || {};

  return (
    <div style={{ background: 'rgba(17,24,39,0.8)', border: '1px solid rgba(30,41,59,0.6)', borderRadius: 8, padding: 16 }}>
      <h3 style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#8b5cf6', marginBottom: 12 }}>AI Agent Workflow</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 16 }}>
        <StatBox label="Model" value={status.model || '?'} color="#3b82f6" />
        <StatBox label="Daily Calls" value={`${status.daily_calls || 0}/${status.daily_limit || 1400}`} color="#f59e0b" />
        <StatBox label="Scan Interval" value={`${status.scan_interval || 150}s`} />
        <StatBox label="Status" value={status.enabled ? 'ACTIVE' : 'OFF'} color={status.enabled ? '#10b981' : '#ef4444'} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <div>
          <label style={{ fontSize: 9, color: '#6b7280', textTransform: 'uppercase', display: 'block', marginBottom: 4 }}>Scan Interval (sec)</label>
          <input type="number" value={scanInterval} onChange={e => { setScanInterval(parseInt(e.target.value)); setUserEdited(true); }} min="30"
            style={{ width: '100%', background: '#1f2937', border: '1px solid #374151', borderRadius: 4, padding: '6px 12px', fontSize: 10, color: 'white', outline: 'none', boxSizing: 'border-box' }} />
        </div>
        <div>
          <label style={{ fontSize: 9, color: '#6b7280', textTransform: 'uppercase', display: 'block', marginBottom: 4 }}>Daily API Limit</label>
          <input type="number" value={dailyLimit} onChange={e => { setDailyLimit(parseInt(e.target.value)); setUserEdited(true); }} min="10"
            style={{ width: '100%', background: '#1f2937', border: '1px solid #374151', borderRadius: 4, padding: '6px 12px', fontSize: 10, color: 'white', outline: 'none', boxSizing: 'border-box' }} />
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <ActionBtn label={saving ? 'Saving...' : 'Update AI Config'} onClick={handleUpdateConfig} color="#8b5cf6" />
        {saveMsg && <span style={{ fontSize: 10, color: saveMsg.startsWith('✅') ? '#10b981' : '#ef4444' }}>{saveMsg}</span>}
      </div>

      {/* AI Analyses */}
      {overview?.ai_state?.analyses && Object.keys(overview.ai_state.analyses).length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 9, color: '#6b7280', textTransform: 'uppercase', marginBottom: 8 }}>Latest AI Analyses</div>
          {Object.entries(overview.ai_state.analyses).map(([sym, a]) => (
            <div key={sym} style={{ padding: 10, background: 'rgba(0,0,0,0.3)', borderRadius: 6, border: '1px solid rgba(31,41,55,0.5)', marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <span style={{ fontSize: 11, fontWeight: 700 }}>{sym}</span>
                <span style={{ fontSize: 10, color: '#f59e0b' }}>{((a.confidence ?? 0) * 100).toFixed(0)}%</span>
              </div>
              <p style={{ fontSize: 9, color: '#9ca3af', lineHeight: 1.5, margin: 0 }}>{a.narrative}</p>
            </div>
          ))}
        </div>
      )}

      {/* Market Structure */}
      {aiWorkflow?.market_structure && Object.keys(aiWorkflow.market_structure).length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 9, color: '#6b7280', textTransform: 'uppercase', marginBottom: 8 }}>⚡ Market Structure</div>
          {Object.entries(aiWorkflow.market_structure).map(([sym, ms]) => (
            <div key={sym} style={{ padding: 10, background: 'rgba(0,0,0,0.3)', borderRadius: 6, border: '1px solid rgba(31,41,55,0.5)', marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <span style={{ fontSize: 11, fontWeight: 700 }}>{sym}</span>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 3, background: ms.trend === 'bullish' ? 'rgba(16,185,129,0.15)' : ms.trend === 'bearish' ? 'rgba(239,68,68,0.15)' : 'rgba(107,114,128,0.15)', color: ms.trend === 'bullish' ? '#10b981' : ms.trend === 'bearish' ? '#ef4444' : '#6b7280', fontWeight: 700, textTransform: 'uppercase' }}>{ms.trend}</span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: ms.bias_score > 0.2 ? '#10b981' : ms.bias_score < -0.2 ? '#ef4444' : '#6b7280' }}>{ms.bias_score > 0 ? '+' : ''}{ms.bias_score}</span>
                </div>
              </div>
              <div style={{ fontSize: 9, color: '#9ca3af', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                <span>Structure: {(ms.current_structure||'').replace(/_/g, ' ')}</span>
                <span>ATR: {ms.atr_pips ?? '—'} pips</span>
                <span>Strength: {((ms.trend_strength ?? 0) * 100).toFixed(0)}%</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LogsTab({ logs, setLogs }) {
  const [loading, setLoading] = React.useState(false);

  const refresh = () => {
    setLoading(true);
    fetch('/api/admin/logs')
      .then(r => r.json())
      .then(d => { if (d?.logs) setLogs(d.logs); })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  React.useEffect(() => { refresh(); }, []);

  return (
    <div style={{ background: 'rgba(17,24,39,0.8)', border: '1px solid rgba(30,41,59,0.6)', borderRadius: 8, padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#6b7280', margin: 0 }}>Server Logs</h3>
        <ActionBtn label={loading ? 'Loading...' : 'Refresh'} onClick={refresh} />
      </div>
      <div style={{ maxHeight: 400, overflowY: 'auto', background: 'rgba(0,0,0,0.4)', borderRadius: 6, padding: 12, fontFamily: 'monospace', fontSize: 9, color: '#9ca3af' }}>
        {logs.slice(-100).map((line, i) => (
          <div key={i} style={{ color: line.includes('ERROR') ? '#ef4444' : line.includes('WARNING') ? '#f59e0b' : line.includes('EXECUTED') ? '#10b981' : '#9ca3af', marginBottom: 2 }}>
            {line}
          </div>
        ))}
        {logs.length === 0 && <div style={{ color: '#4b5563' }}>No logs</div>}
      </div>
    </div>
  );
}

/* ═══ MOUNT ═══ */
const root = document.getElementById('admin-root');
if (root) {
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <AdminDashboard />
    </React.StrictMode>
  );
} else {
  document.body.innerHTML = '<div style="color:red;padding:40px;font-size:20px;">ERROR: admin-root element not found</div>';
}
