/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — OPEN POSITIONS PANEL
 *  Shows live open positions with close & modify controls
 * ═══════════════════════════════════════════════════════════════════
 */
import React, { useState, useEffect, useCallback } from 'react';

export default function OpenPositions({ brokerConnected, refreshKey }) {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [closingTicket, setClosingTicket] = useState(null);
  const [closeAllLoading, setCloseAllLoading] = useState(false);

  const fetchPositions = useCallback(async () => {
    if (!brokerConnected) {
      setPositions([]);
      return;
    }
    try {
      const res = await fetch('/api/positions');
      const data = await res.json();
      if (Array.isArray(data)) setPositions(data);
    } catch {
      /* silent */
    }
  }, [brokerConnected]);

  // Poll positions every 5 seconds
  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 5000);
    return () => clearInterval(interval);
  }, [fetchPositions, refreshKey]);

  const closePosition = useCallback(async (pos) => {
    const closeId = pos.id || pos.ticket;
    setClosingTicket(closeId);
    try {
      const res = await fetch('/api/trade/close', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticket: pos.ticket, id: pos.id }),
      });
      const data = await res.json();
      if (data.status === 'OK') {
        setPositions((prev) => prev.filter((p) => p.ticket !== pos.ticket));
      }
    } catch {
      /* silent */
    } finally {
      setClosingTicket(null);
    }
  }, []);

  const closeAll = useCallback(async () => {
    if (!window.confirm('Close ALL open positions?')) return;
    setCloseAllLoading(true);
    try {
      await fetch('/api/close-all', { method: 'POST' });
      setPositions([]);
    } catch {
      /* silent */
    } finally {
      setCloseAllLoading(false);
    }
  }, []);

  const totalProfit = positions.reduce((sum, p) => sum + (p.profit || 0), 0);
  const profitColor = totalProfit >= 0 ? 'text-forexia-green' : 'text-forexia-red';

  return (
    <div className="glass-panel rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs uppercase tracking-widest text-gray-500 flex items-center gap-2">
          <span className="text-forexia-cyan">◉</span> Open Positions
          {positions.length > 0 && (
            <span className="text-forexia-accent font-bold">({positions.length})</span>
          )}
        </h2>
        <div className="flex items-center gap-3">
          {positions.length > 0 && (
            <>
              <span className={`text-xs font-bold font-mono ${profitColor}`}>
                P&L: {totalProfit >= 0 ? '+' : ''}{totalProfit.toFixed(2)}
              </span>
              <button
                onClick={closeAll}
                disabled={closeAllLoading}
                className="px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider
                  bg-forexia-red/10 text-forexia-red border border-forexia-red/20
                  hover:bg-forexia-red/20 disabled:opacity-30"
              >
                {closeAllLoading ? 'Closing...' : 'Close All'}
              </button>
            </>
          )}
        </div>
      </div>

      {positions.length === 0 ? (
        <div className="text-center py-6 text-gray-600 text-[10px] uppercase tracking-wider">
          {brokerConnected ? 'No open positions' : 'Broker disconnected'}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="text-[9px] uppercase tracking-wider text-gray-600 border-b border-forexia-border/50">
                <th className="py-1.5 px-2">Symbol</th>
                <th className="py-1.5 px-2">Dir</th>
                <th className="py-1.5 px-2">Lots</th>
                <th className="py-1.5 px-2">Open</th>
                <th className="py-1.5 px-2">SL</th>
                <th className="py-1.5 px-2">TP</th>
                <th className="py-1.5 px-2">Swap</th>
                <th className="py-1.5 px-2 text-right">P&L</th>
                <th className="py-1.5 px-2"></th>
              </tr>
            </thead>
            <tbody>
              {positions.map((pos) => {
                const isBuy = pos.type === 0;
                const dirColor = isBuy ? 'text-forexia-green' : 'text-forexia-red';
                const plColor = (pos.profit || 0) >= 0 ? 'text-forexia-green' : 'text-forexia-red';
                const isClosing = closingTicket === (pos.id || pos.ticket);

                return (
                  <tr key={pos.id || pos.ticket} className="border-b border-forexia-border/30 hover:bg-white/[0.02] transition-colors">
                    <td className="py-2 px-2 text-xs font-bold text-white">{(pos.symbol || '').replace(/\.$/, '')}</td>
                    <td className={`py-2 px-2 text-[10px] font-black ${dirColor}`}>
                      {isBuy ? '▲ BUY' : '▼ SELL'}
                    </td>
                    <td className="py-2 px-2 text-xs text-gray-300 font-mono">{pos.lots}</td>
                    <td className="py-2 px-2 text-xs text-gray-400 font-mono">{pos.open_price?.toFixed(5)}</td>
                    <td className="py-2 px-2 text-[10px] text-forexia-red font-mono">
                      {pos.sl ? pos.sl.toFixed(5) : '—'}
                    </td>
                    <td className="py-2 px-2 text-[10px] text-forexia-green font-mono">
                      {pos.tp ? pos.tp.toFixed(5) : '—'}
                    </td>
                    <td className="py-2 px-2 text-[10px] text-gray-500 font-mono">{pos.swap?.toFixed(2)}</td>
                    <td className={`py-2 px-2 text-xs font-bold font-mono text-right ${plColor}`}>
                      {(pos.profit || 0) >= 0 ? '+' : ''}{(pos.profit || 0).toFixed(2)}
                    </td>
                    <td className="py-2 px-2">
                      <button
                        onClick={() => closePosition(pos)}
                        disabled={isClosing}
                        className="px-2 py-0.5 rounded text-[9px] font-bold uppercase
                          bg-red-900/30 text-forexia-red border border-red-900/40
                          hover:bg-red-900/50 disabled:opacity-30 transition-all"
                      >
                        {isClosing ? '...' : '✕'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
