/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — TRANSACTION HISTORY PANEL
 *  Full trade history: open positions, closed trades, agent signals
 * ═══════════════════════════════════════════════════════════════════
 */
import React, { useState, useEffect, useCallback } from 'react';

const TABS = ['All', 'Open', 'Closed', 'Signals'];

function getPrecision(sym) {
  if (!sym) return 5;
  if (sym.includes('JPY')) return 3;
  if (sym.includes('XAU')) return 2;
  return 5;
}

function formatTime(ts) {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    if (isNaN(d)) return String(ts).slice(0, 19);
    return d.toISOString().slice(5, 16).replace('T', ' ');
  } catch {
    return String(ts).slice(0, 16);
  }
}

export default function TransactionHistory({ brokerConnected, signals = [] }) {
  const [tab, setTab] = useState('All');
  const [history, setHistory] = useState({ open: [], closed: [], agent_trades: [] });
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch('/api/trade-history?days=30');
      if (!res.ok) return;
      const data = await res.json();
      setHistory(data);
    } catch { /* silent */ }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchHistory();
    const id = setInterval(fetchHistory, 5000);
    return () => clearInterval(id);
  }, [fetchHistory]);

  // Combine all items
  const openRows = (history.open || []).map((t) => ({ ...t, _type: 'open' }));
  const closedRows = (history.closed || []).map((t) => ({ ...t, _type: 'closed' }));
  const agentRows = (history.agent_trades || []).map((t) => ({ ...t, _type: 'agent' }));

  let rows = [];
  if (tab === 'All') rows = [...openRows, ...closedRows, ...agentRows];
  else if (tab === 'Open') rows = openRows;
  else if (tab === 'Closed') rows = closedRows;
  else if (tab === 'Signals') rows = agentRows.length > 0 ? agentRows : signals.map((s) => ({
    id: s.signal_id,
    symbol: s.symbol,
    side: s.direction,
    volume: s.lot_size,
    open_price: s.entry_price,
    sl: s.stop_loss,
    tp: s.take_profit,
    profit: 0,
    status: 'signal',
    confidence: s.confidence,
    signal_type: s.signal_type,
    _type: 'signal',
  }));

  // Limit display
  const maxRows = expanded ? 50 : 8;
  const displayRows = rows.slice(0, maxRows);

  // Summary
  const totalPnl = openRows.reduce((s, r) => s + (r.profit || 0), 0);
  const closedPnl = closedRows.reduce((s, r) => s + (r.net_profit || r.profit || 0), 0);

  return (
    <div className="glass-panel rounded-xl p-4 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <h2 className="text-xs uppercase tracking-widest text-gray-500 font-bold">
            Transaction History
          </h2>
          <div className="flex items-center gap-1">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider transition-all ${
                  tab === t
                    ? 'bg-forexia-accent/15 text-forexia-accent border border-forexia-accent/25'
                    : 'text-gray-500 hover:text-gray-400 border border-transparent'
                }`}
              >
                {t}
                {t === 'Open' && openRows.length > 0 && (
                  <span className="ml-1 text-[8px] text-forexia-accent">{openRows.length}</span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Summary pills */}
        <div className="flex items-center gap-2">
          {openRows.length > 0 && (
            <div className={`px-2 py-0.5 rounded text-[9px] font-bold font-mono border ${
              totalPnl >= 0
                ? 'bg-forexia-green/10 text-forexia-green border-forexia-green/20'
                : 'bg-forexia-red/10 text-forexia-red border-forexia-red/20'
            }`}>
              Open: {totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(2)}
            </div>
          )}
          {closedRows.length > 0 && (
            <div className={`px-2 py-0.5 rounded text-[9px] font-bold font-mono border ${
              closedPnl >= 0
                ? 'bg-forexia-green/10 text-forexia-green border-forexia-green/20'
                : 'bg-forexia-red/10 text-forexia-red border-forexia-red/20'
            }`}>
              Closed: {closedPnl >= 0 ? '+' : ''}{closedPnl.toFixed(2)}
            </div>
          )}
        </div>
      </div>

      {/* Table */}
      {rows.length === 0 ? (
        <div className="text-center py-6 text-gray-600 text-xs">
          {loading ? (
            <div className="flex items-center justify-center gap-2">
              <div className="w-3 h-3 border border-forexia-accent border-t-transparent rounded-full animate-spin" />
              <span>Loading transactions...</span>
            </div>
          ) : (
            'No transactions yet. Waiting for trades...'
          )}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="text-[9px] uppercase tracking-wider text-gray-600 border-b border-forexia-border/40">
                <th className="py-1.5 px-2">Status</th>
                <th className="py-1.5 px-2">Symbol</th>
                <th className="py-1.5 px-2">Side</th>
                <th className="py-1.5 px-2">Volume</th>
                <th className="py-1.5 px-2">Entry</th>
                <th className="py-1.5 px-2">SL/TP</th>
                <th className="py-1.5 px-2">Exit</th>
                <th className="py-1.5 px-2 text-right">P&L</th>
                <th className="py-1.5 px-2">Info</th>
              </tr>
            </thead>
            <tbody>
              {displayRows.map((row, i) => (
                <TradeRow key={`${row._type}-${row.id || row.ticket || i}`} row={row} />
              ))}
            </tbody>
          </table>

          {/* Show more */}
          {rows.length > maxRows && !expanded && (
            <button
              onClick={() => setExpanded(true)}
              className="w-full py-1.5 text-[10px] text-forexia-accent hover:text-white transition mt-1"
            >
              Show {rows.length - maxRows} more →
            </button>
          )}
          {expanded && rows.length > 8 && (
            <button
              onClick={() => setExpanded(false)}
              className="w-full py-1.5 text-[10px] text-gray-500 hover:text-gray-400 transition mt-1"
            >
              Show less ↑
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Individual row ── */
function TradeRow({ row }) {
  const dec = getPrecision(row.symbol);
  const isBuy = (row.side || '').toUpperCase() === 'BUY';
  const pnl = row.net_profit ?? row.profit ?? 0;
  const pnlPos = pnl >= 0;

  // Status badge
  let statusColor, statusLabel;
  switch (row._type) {
    case 'open':
      statusColor = 'bg-forexia-accent/15 text-forexia-accent border-forexia-accent/25';
      statusLabel = 'OPEN';
      break;
    case 'closed':
      statusColor = pnlPos
        ? 'bg-forexia-green/10 text-forexia-green border-forexia-green/20'
        : 'bg-forexia-red/10 text-forexia-red border-forexia-red/20';
      statusLabel = 'CLOSED';
      break;
    case 'agent':
      statusColor = 'bg-forexia-purple/10 text-forexia-purple border-forexia-purple/20';
      statusLabel = (row.status || 'SIGNAL').toUpperCase().slice(0, 8);
      break;
    case 'signal':
      statusColor = 'bg-forexia-gold/10 text-forexia-gold border-forexia-gold/20';
      statusLabel = 'SIGNAL';
      break;
    default:
      statusColor = 'bg-gray-800 text-gray-400 border-gray-700';
      statusLabel = '—';
  }

  return (
    <tr className="border-b border-forexia-border/20 hover:bg-white/[0.015] transition-colors text-[10px]">
      {/* Status */}
      <td className="py-1.5 px-2">
        <span className={`inline-block px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider border ${statusColor}`}>
          {statusLabel}
        </span>
      </td>

      {/* Symbol */}
      <td className="py-1.5 px-2 font-bold text-white text-[11px]">
        {(row.symbol || '').replace('.', '')}
      </td>

      {/* Side */}
      <td className={`py-1.5 px-2 font-bold ${isBuy ? 'text-forexia-green' : 'text-forexia-red'}`}>
        {isBuy ? '▲ BUY' : '▼ SELL'}
      </td>

      {/* Volume */}
      <td className="py-1.5 px-2 text-gray-400 font-mono">
        {(row.volume || row.lots || 0).toFixed(2)}
      </td>

      {/* Entry */}
      <td className="py-1.5 px-2 text-gray-300 font-mono">
        {row.open_price ? row.open_price.toFixed(dec) : '—'}
      </td>

      {/* SL / TP */}
      <td className="py-1.5 px-2 font-mono">
        {row.sl && row.sl > 0 ? (
          <span className="text-forexia-red text-[9px]">{row.sl.toFixed(dec)}</span>
        ) : null}
        {row.sl && row.tp ? <span className="text-gray-700 mx-0.5">/</span> : null}
        {row.tp && row.tp > 0 ? (
          <span className="text-forexia-green text-[9px]">{row.tp.toFixed(dec)}</span>
        ) : null}
        {(!row.sl || row.sl === 0) && (!row.tp || row.tp === 0) ? (
          <span className="text-gray-700">—</span>
        ) : null}
      </td>

      {/* Exit price */}
      <td className="py-1.5 px-2 text-gray-400 font-mono">
        {row.close_price && row.close_price > 0 ? row.close_price.toFixed(dec) : '—'}
      </td>

      {/* P&L */}
      <td className={`py-1.5 px-2 text-right font-mono font-bold ${pnlPos ? 'text-forexia-green' : 'text-forexia-red'}`}>
        {row._type === 'signal' ? (
          <span className="text-forexia-gold font-normal">{((row.confidence || 0) * 100).toFixed(0)}%</span>
        ) : (
          <span>{pnlPos ? '+' : ''}{pnl.toFixed(2)}</span>
        )}
      </td>

      {/* Info */}
      <td className="py-1.5 px-2 text-[9px] text-gray-600 truncate max-w-[120px]">
        {row._type === 'open' && row.swap ? `swap: ${row.swap.toFixed(2)}` : ''}
        {row._type === 'closed' && row.close_time ? formatTime(row.close_time) : ''}
        {row._type === 'agent' && row.signal_type ? row.signal_type.replace(/_/g, ' ') : ''}
        {row._type === 'signal' && row.signal_type ? row.signal_type.replace(/_/g, ' ') : ''}
      </td>
    </tr>
  );
}
