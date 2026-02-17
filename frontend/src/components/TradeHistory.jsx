/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — TRADE HISTORY TABLE
 *  Shows recent signals and executed trades
 * ═══════════════════════════════════════════════════════════════════
 */
import React from 'react';

function SignalRow({ signal }) {
  const dirColor = signal.direction === 'BUY' ? 'text-forexia-green' : 'text-forexia-red';
  const confColor = signal.confidence >= 0.7 ? 'text-forexia-green' : signal.confidence >= 0.5 ? 'text-forexia-gold' : 'text-gray-500';

  return (
    <tr className="border-b border-forexia-border/50 hover:bg-white/[0.02] transition-colors">
      <td className="py-2 px-3 text-[10px] text-gray-500 font-mono">{signal.signal_id}</td>
      <td className="py-2 px-3 text-xs font-bold text-white">{signal.symbol}</td>
      <td className={`py-2 px-3 text-xs font-bold ${dirColor}`}>{signal.direction}</td>
      <td className="py-2 px-3 text-xs text-gray-300">{signal.entry_price?.toFixed(5)}</td>
      <td className="py-2 px-3 text-xs text-forexia-red">{signal.stop_loss?.toFixed(5)}</td>
      <td className="py-2 px-3 text-xs text-forexia-green">{signal.take_profit?.toFixed(5)}</td>
      <td className="py-2 px-3 text-xs text-gray-400">{signal.lot_size}</td>
      <td className={`py-2 px-3 text-xs font-bold ${confColor}`}>{(signal.confidence * 100).toFixed(0)}%</td>
      <td className="py-2 px-3 text-[10px] text-gray-500">
        {signal.signal_type?.replace(/_/g, ' ')}
      </td>
    </tr>
  );
}

export default function TradeHistory({ signals = [], trades = [] }) {
  return (
    <div className="glass-panel rounded-xl p-6 overflow-hidden">
      <h2 className="text-xs uppercase tracking-widest text-gray-500 mb-4">
        Active Signals & Trade History
      </h2>

      {signals.length === 0 && trades.length === 0 ? (
        <div className="text-center py-8 text-gray-600 text-xs">
          No signals or trades yet. Waiting for the Signature Trade...
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-gray-500 border-b border-forexia-border">
                <th className="py-2 px-3">ID</th>
                <th className="py-2 px-3">Symbol</th>
                <th className="py-2 px-3">Dir</th>
                <th className="py-2 px-3">Entry</th>
                <th className="py-2 px-3">SL</th>
                <th className="py-2 px-3">TP</th>
                <th className="py-2 px-3">Lots</th>
                <th className="py-2 px-3">Conf</th>
                <th className="py-2 px-3">Type</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((signal, i) => (
                <SignalRow key={signal.signal_id || i} signal={signal} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
