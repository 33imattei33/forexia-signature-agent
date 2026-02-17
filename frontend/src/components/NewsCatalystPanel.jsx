/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — NEWS CATALYST PANEL
 *  Shows upcoming Red Folder events (NO economic numbers — BOGUS)
 * ═══════════════════════════════════════════════════════════════════
 */
import React from 'react';

export default function NewsCatalystPanel({ catalysts = [], traumaActive = false }) {
  return (
    <div className="glass-panel rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xs uppercase tracking-widest text-gray-500">
          Red Folder Catalysts
        </h2>
        {traumaActive && (
          <span className="text-[10px] font-bold text-forexia-red bg-red-900/30 px-2 py-0.5 rounded animate-pulse">
            TRAUMA FILTER ACTIVE
          </span>
        )}
      </div>

      <p className="text-[10px] text-gray-600 mb-3 italic">
        Pre-engineered volatility catalysts. Economic numbers STRIPPED — they are bogus retail bait.
      </p>

      {catalysts.length === 0 ? (
        <div className="text-center py-6 text-gray-600 text-xs">
          No upcoming Red Folder events
        </div>
      ) : (
        <div className="space-y-2">
          {catalysts.map((cat, i) => (
            <div
              key={i}
              className="flex items-center gap-3 p-3 rounded-lg bg-red-900/10 border border-red-900/20"
            >
              {/* Red folder icon */}
              <div className="w-8 h-8 rounded bg-red-600/20 flex items-center justify-center flex-shrink-0">
                <span className="text-forexia-red text-lg">📁</span>
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-white truncate">
                  {cat.event_title}
                </p>
                <p className="text-[10px] text-gray-500">
                  <span className="text-forexia-gold font-bold">{cat.currency}</span>
                  {' — '}
                  {cat.event_time} UTC
                </p>
              </div>

              {/* Currency badge */}
              <span className="text-[10px] font-bold text-forexia-gold bg-amber-900/30 px-2 py-0.5 rounded flex-shrink-0">
                {cat.currency}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="mt-3 pt-3 border-t border-forexia-border">
        <p className="text-[9px] text-gray-700 uppercase tracking-wider">
          ⚠ Forecast / Actual / Previous data intentionally DELETED — bogus retail noise
        </p>
      </div>
    </div>
  );
}
