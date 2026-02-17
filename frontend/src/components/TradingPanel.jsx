/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — MANUAL TRADING PANEL
 *  Execute BUY/SELL orders with symbol, lot size, SL, TP
 * ═══════════════════════════════════════════════════════════════════
 */
import React, { useState, useCallback, useEffect } from 'react';

const DEFAULT_SYMBOLS = ['EURUSD', 'GBPUSD', 'USDCHF', 'USDJPY', 'XAUUSD', 'GBPJPY', 'EURJPY', 'AUDUSD', 'NZDUSD', 'USDCAD'];

export default function TradingPanel({ brokerConnected, onTradeExecuted }) {
  const [symbol, setSymbol] = useState('EURUSD');
  const [lotSize, setLotSize] = useState('0.01');
  const [stopLoss, setStopLoss] = useState('');
  const [takeProfit, setTakeProfit] = useState('');
  const [loading, setLoading] = useState(null); // 'BUY' | 'SELL' | null
  const [result, setResult] = useState(null);
  const [availableSymbols, setAvailableSymbols] = useState(DEFAULT_SYMBOLS);

  // Fetch real instruments from broker on mount
  useEffect(() => {
    if (!brokerConnected) return;
    fetch('/api/instruments')
      .then(r => r.json())
      .then(data => {
        if (data.map && Object.keys(data.map).length > 0) {
          // Use the clean names (keys) from the instrument map
          const clean = Object.keys(data.map);
          // Filter to common forex + gold pairs for UI
          const preferred = DEFAULT_SYMBOLS.filter(s => clean.includes(s));
          // Add any other pairs we know about
          if (preferred.length > 0) {
            setAvailableSymbols(preferred);
          }
        }
      })
      .catch(() => {});
  }, [brokerConnected]);

  const executeTrade = useCallback(async (direction) => {
    if (!brokerConnected) return;
    setLoading(direction);
    setResult(null);

    try {
      const res = await fetch('/api/trade/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          direction,
          lot_size: parseFloat(lotSize) || 0.01,
          stop_loss: parseFloat(stopLoss) || 0,
          take_profit: parseFloat(takeProfit) || 0,
        }),
      });
      const data = await res.json();

      if (data.status === 'OK') {
        setResult({ type: 'success', msg: `${direction} ${lotSize} ${symbol} — Ticket #${data.ticket}` });
        if (onTradeExecuted) onTradeExecuted();
      } else {
        setResult({ type: 'error', msg: data.message || 'Order rejected' });
      }
    } catch (e) {
      setResult({ type: 'error', msg: `Network error: ${e.message}` });
    } finally {
      setLoading(null);
    }
  }, [symbol, lotSize, stopLoss, takeProfit, brokerConnected, onTradeExecuted]);

  return (
    <div className="glass-panel rounded-xl p-5">
      <h2 className="text-xs uppercase tracking-widest text-gray-500 mb-4 flex items-center gap-2">
        <span className="text-forexia-accent">⚡</span> Quick Trade
        {!brokerConnected && (
          <span className="text-forexia-red animate-pulse text-[9px]">● OFFLINE</span>
        )}
      </h2>

      {/* Symbol Selector */}
      <div className="mb-3">
        <div className="flex flex-wrap gap-1.5">
          {availableSymbols.map((s) => (
            <button
              key={s}
              onClick={() => setSymbol(s)}
              className={`px-2 py-1 rounded text-[10px] font-bold tracking-wider transition-all
                ${symbol === s
                  ? 'bg-forexia-accent/20 text-forexia-accent border border-forexia-accent/40'
                  : 'bg-gray-800/60 text-gray-500 border border-gray-800 hover:text-gray-300 hover:border-gray-600'
                }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Lot Size + SL + TP */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div>
          <label className="text-[9px] uppercase tracking-wider text-gray-600 block mb-1">Lots</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            value={lotSize}
            onChange={(e) => setLotSize(e.target.value)}
            className="w-full bg-gray-900/80 border border-gray-700 rounded px-2 py-1.5 text-xs text-white font-mono focus:border-forexia-accent focus:outline-none"
          />
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-gray-600 block mb-1">Stop Loss</label>
          <input
            type="number"
            step="0.00001"
            value={stopLoss}
            onChange={(e) => setStopLoss(e.target.value)}
            placeholder="0 = none"
            className="w-full bg-gray-900/80 border border-gray-700 rounded px-2 py-1.5 text-xs text-white font-mono placeholder:text-gray-700 focus:border-forexia-red focus:outline-none"
          />
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-gray-600 block mb-1">Take Profit</label>
          <input
            type="number"
            step="0.00001"
            value={takeProfit}
            onChange={(e) => setTakeProfit(e.target.value)}
            placeholder="0 = none"
            className="w-full bg-gray-900/80 border border-gray-700 rounded px-2 py-1.5 text-xs text-white font-mono placeholder:text-gray-700 focus:border-forexia-green focus:outline-none"
          />
        </div>
      </div>

      {/* BUY / SELL Buttons */}
      <div className="grid grid-cols-2 gap-2 mb-2">
        <button
          onClick={() => executeTrade('BUY')}
          disabled={!brokerConnected || loading}
          className="py-2.5 rounded font-black text-sm uppercase tracking-wider transition-all
            bg-forexia-green/15 text-forexia-green border border-forexia-green/30
            hover:bg-forexia-green/25 hover:border-forexia-green/50
            disabled:opacity-30 disabled:cursor-not-allowed
            active:scale-[0.98]"
        >
          {loading === 'BUY' ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-3 h-3 border-2 border-forexia-green border-t-transparent rounded-full animate-spin" />
              BUYING...
            </span>
          ) : (
            `▲ BUY ${symbol}`
          )}
        </button>
        <button
          onClick={() => executeTrade('SELL')}
          disabled={!brokerConnected || loading}
          className="py-2.5 rounded font-black text-sm uppercase tracking-wider transition-all
            bg-forexia-red/15 text-forexia-red border border-forexia-red/30
            hover:bg-forexia-red/25 hover:border-forexia-red/50
            disabled:opacity-30 disabled:cursor-not-allowed
            active:scale-[0.98]"
        >
          {loading === 'SELL' ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-3 h-3 border-2 border-forexia-red border-t-transparent rounded-full animate-spin" />
              SELLING...
            </span>
          ) : (
            `▼ SELL ${symbol}`
          )}
        </button>
      </div>

      {/* Result Feedback */}
      {result && (
        <div className={`mt-2 px-3 py-2 rounded text-[10px] font-mono ${
          result.type === 'success'
            ? 'bg-forexia-green/10 text-forexia-green border border-forexia-green/20'
            : 'bg-forexia-red/10 text-forexia-red border border-forexia-red/20'
        }`}>
          {result.type === 'success' ? '✓' : '✗'} {result.msg}
        </div>
      )}
    </div>
  );
}
