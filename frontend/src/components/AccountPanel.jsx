/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — ACCOUNT PANEL
 *  Displays balance, equity, win rate, and daily P&L
 * ═══════════════════════════════════════════════════════════════════
 */
import React from 'react';

export default function AccountPanel({ account }) {
  if (!account) return null;

  const isDisconnected = !account.balance && !account.equity && !account.margin;

  const winRate = account.win_count + account.loss_count > 0
    ? ((account.win_count / (account.win_count + account.loss_count)) * 100).toFixed(1)
    : '0.0';

  const dailyPnlColor = account.daily_pnl >= 0 ? 'text-forexia-green glow-green' : 'text-forexia-red glow-red';

  return (
    <div className="glass-panel rounded-xl p-6">
      <h2 className="text-xs uppercase tracking-widest text-gray-500 mb-4">
        Account Status
        {isDisconnected && (
          <span className="ml-2 text-forexia-red animate-pulse">● DISCONNECTED</span>
        )}
      </h2>

      {isDisconnected && (
        <div className="mb-4 px-3 py-2 rounded bg-forexia-red/5 border border-forexia-red/20">
          <p className="text-[10px] text-forexia-red font-mono">
            Broker not connected — account data unavailable.
          </p>
          <p className="text-[9px] text-gray-500 mt-1">
            Open Settings → select "MatchTrader" or "Remote MT5 Server" → enter your credentials → click Save & Connect.
          </p>
        </div>
      )}
      <div className="grid grid-cols-2 gap-4">
        {/* Balance */}
        <div>
          <p className="text-[10px] uppercase tracking-wider text-gray-500">Balance</p>
          <p className="text-2xl font-bold text-white glow-blue">
            ${account.balance?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </p>
        </div>

        {/* Equity */}
        <div>
          <p className="text-[10px] uppercase tracking-wider text-gray-500">Equity</p>
          <p className="text-2xl font-bold text-forexia-cyan">
            ${account.equity?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </p>
        </div>

        {/* Win Rate */}
        <div>
          <p className="text-[10px] uppercase tracking-wider text-gray-500">Win Rate</p>
          <p className="text-2xl font-bold text-forexia-gold glow-gold">
            {winRate}%
          </p>
          <p className="text-[10px] text-gray-600">
            {account.win_count}W / {account.loss_count}L
          </p>
        </div>

        {/* Daily P&L */}
        <div>
          <p className="text-[10px] uppercase tracking-wider text-gray-500">Daily P&L</p>
          <p className={`text-2xl font-bold ${dailyPnlColor}`}>
            {account.daily_pnl >= 0 ? '+' : ''}
            ${account.daily_pnl?.toFixed(2)}
          </p>
          <p className="text-[10px] text-gray-600">
            {account.total_trades_today} trades today
          </p>
        </div>
      </div>

      {/* Margin info */}
      <div className="mt-4 pt-4 border-t border-forexia-border flex justify-between text-xs text-gray-500">
        <span>Margin: ${account.margin?.toFixed(2)}</span>
        <span>Free: ${account.free_margin?.toFixed(2)}</span>
        <span>Open: {account.open_trades}</span>
      </div>
    </div>
  );
}
