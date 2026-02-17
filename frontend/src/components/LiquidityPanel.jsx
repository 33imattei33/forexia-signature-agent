/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — LIQUIDITY ZONES PANEL
 *  Shows where dumb money has parked their stop-losses
 * ═══════════════════════════════════════════════════════════════════
 */
import React from 'react';

const ZONE_COLORS = {
  HIGH_OF_DAY: 'text-forexia-red',
  LOW_OF_DAY: 'text-forexia-green',
  ASIAN_HIGH: 'text-forexia-purple',
  ASIAN_LOW: 'text-forexia-purple',
  WEEKLY_HIGH: 'text-forexia-gold',
  WEEKLY_LOW: 'text-forexia-gold',
  PSYCH_LEVEL: 'text-forexia-cyan',
};

export default function LiquidityPanel({ zones = [] }) {
  // Group by symbol
  const grouped = zones.reduce((acc, z) => {
    if (!acc[z.symbol]) acc[z.symbol] = [];
    acc[z.symbol].push(z);
    return acc;
  }, {});

  return (
    <div className="glass-panel rounded-xl p-6">
      <h2 className="text-xs uppercase tracking-widest text-gray-500 mb-4">
        Liquidity Zones
      </h2>
      <p className="text-[10px] text-gray-600 mb-3 italic">
        Retail stop-loss clusters — targets for institutional harvesting
      </p>

      {zones.length === 0 ? (
        <div className="text-center py-6 text-gray-600 text-xs">
          No liquidity zones mapped yet
        </div>
      ) : (
        <div className="space-y-3">
          {Object.entries(grouped).map(([symbol, symbolZones]) => (
            <div key={symbol}>
              <p className="text-[10px] text-gray-500 font-bold mb-1">{symbol || 'Global'}</p>
              <div className="space-y-1">
                {symbolZones.slice(0, 8).map((zone, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 px-2 rounded bg-gray-900/50">
                    <div className="flex items-center gap-2">
                      <span className={`w-1.5 h-1.5 rounded-full ${zone.swept ? 'bg-gray-600' : 'bg-forexia-accent'}`} />
                      <span className={`text-[10px] font-bold ${ZONE_COLORS[zone.zone_type] || 'text-gray-400'}`}>
                        {zone.zone_type?.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-white font-mono">
                        {zone.level?.toFixed(5)}
                      </span>
                      {zone.swept && (
                        <span className="text-[8px] text-forexia-red font-bold">SWEPT</span>
                      )}
                      <div className="flex gap-0.5">
                        {Array.from({ length: 10 }).map((_, j) => (
                          <span
                            key={j}
                            className={`w-1 h-3 rounded-sm ${
                              j < zone.strength ? 'bg-forexia-accent' : 'bg-gray-800'
                            }`}
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
