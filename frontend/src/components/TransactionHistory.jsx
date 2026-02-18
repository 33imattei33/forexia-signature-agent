/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — TRANSACTION HISTORY PANEL
 *  Full trade history: open positions, closed trades, agent signals
 *  Close buttons for every open position (manual & bot-placed)
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
  const [closingIds, setClosingIds] = useState(new Set());   // IDs currently being closed
  const [closingAll, setClosingAll] = useState(false);        // "Close All" in progress
  const [toast, setToast] = useState(null);                   // {type: 'ok'|'err', msg: '...'}

  // Auto-dismiss toast after 4 seconds
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

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

  /* ── Close a single position ── */
  const handleClose = useCallback(async (row) => {
    const key = row.id || String(row.ticket);
    if (!key || closingIds.has(key)) return;

    const sym = (row.symbol || '').replace('.', '');
    setClosingIds((prev) => new Set(prev).add(key));
    try {
      const body = {};
      if (row.id) body.id = row.id;
      if (row.ticket) body.ticket = row.ticket;

      console.log('[CLOSE] Sending close request:', JSON.stringify(body));
      const res = await fetch('/api/trade/close', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      console.log('[CLOSE] Response:', JSON.stringify(data));
      if (data.status === 'OK') {
        setToast({ type: 'ok', msg: `${sym} ${row.side} closed successfully` });
        await fetchHistory();
      } else {
        setToast({ type: 'err', msg: `Close failed: ${data.message || 'Unknown error'}` });
        console.error('Close failed:', data.message);
      }
    } catch (err) {
      setToast({ type: 'err', msg: `Close error: ${err.message}` });
      console.error('Close error:', err);
    } finally {
      setClosingIds((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  }, [closingIds, fetchHistory]);

  /* ── Close ALL open positions ── */
  const handleCloseAll = useCallback(async () => {
    if (closingAll) return;
    setClosingAll(true);
    try {
      console.log('[CLOSE-ALL] Sending close-all request');
      const res = await fetch('/api/close-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json();
      console.log('[CLOSE-ALL] Response:', JSON.stringify(data));
      if (data.status === 'OK') {
        const n = data.closed_count || 0;
        setToast({ type: 'ok', msg: `All positions closed (${n})` });
        await fetchHistory();
      } else {
        setToast({ type: 'err', msg: `Close-all failed: ${data.message || 'Unknown error'}` });
        console.error('Close-all failed:', data);
      }
    } catch (err) {
      setToast({ type: 'err', msg: `Close-all error: ${err.message}` });
      console.error('Close-all error:', err);
    } finally {
      setClosingAll(false);
    }
  }, [closingAll, fetchHistory]);

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

        {/* Summary pills + Close All */}
        <div className="flex items-center gap-2">
          {openRows.length > 0 && (
            <button
              onClick={handleCloseAll}
              disabled={closingAll}
              className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border transition-all ${
                closingAll
                  ? 'bg-gray-800 text-gray-600 border-gray-700 cursor-wait'
                  : 'bg-forexia-red/10 text-forexia-red border-forexia-red/30 hover:bg-forexia-red/20 hover:border-forexia-red/50 cursor-pointer'
              }`}
            >
              {closingAll ? (
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 border border-forexia-red border-t-transparent rounded-full animate-spin" />
                  Closing…
                </span>
              ) : (
                `Close All (${openRows.length})`
              )}
            </button>
          )}
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

      {/* Toast notification */}
      {toast && (
        <div className={`mb-2 px-3 py-1.5 rounded text-[10px] font-bold border transition-all ${
          toast.type === 'ok'
            ? 'bg-forexia-green/10 text-forexia-green border-forexia-green/20'
            : 'bg-forexia-red/10 text-forexia-red border-forexia-red/20'
        }`}>
          {toast.type === 'ok' ? '✓ ' : '✗ '}{toast.msg}
        </div>
      )}

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
                <th className="py-1.5 px-2 text-center w-12"></th>
              </tr>
            </thead>
            <tbody>
              {displayRows.map((row, i) => (
                <TradeRow
                  key={`${row._type}-${row.id || row.ticket || i}`}
                  row={row}
                  onClose={handleClose}
                  isClosing={closingIds.has(row.id || String(row.ticket))}
                />
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
function TradeRow({ row, onClose, isClosing }) {
  const dec = getPrecision(row.symbol);
  const isBuy = (row.side || '').toUpperCase() === 'BUY';
  const pnl = row.net_profit ?? row.profit ?? 0;
  const pnlPos = pnl >= 0;

  // Status badge
  let statusColor, statusLabel;
  switch (row._type) {
    case 'open':
      if (row.is_bot) {
        statusColor = 'bg-forexia-accent/15 text-forexia-accent border-forexia-accent/25';
        statusLabel = 'BOT';
      } else {
        statusColor = 'bg-forexia-gold/15 text-forexia-gold border-forexia-gold/25';
        statusLabel = 'MANUAL';
      }
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

      {/* Close button — only for open positions */}
      <td className="py-1.5 px-2 text-center">
        {row._type === 'open' ? (
          <button
            onClick={() => onClose(row)}
            disabled={isClosing}
            title={`Close ${(row.symbol || '').replace('.', '')} ${row.side}`}
            className={`inline-flex items-center justify-center w-5 h-5 rounded transition-all ${
              isClosing
                ? 'bg-gray-800 cursor-wait'
                : 'bg-forexia-red/10 hover:bg-forexia-red/30 border border-forexia-red/20 hover:border-forexia-red/50 cursor-pointer group'
            }`}
          >
            {isClosing ? (
              <span className="w-2.5 h-2.5 border border-forexia-red border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="w-3 h-3 text-forexia-red/70 group-hover:text-forexia-red"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                  clipRule="evenodd"
                />
              </svg>
            )}
          </button>
        ) : null}
      </td>
    </tr>
  );
}
