/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — WEEKLY ACT DISPLAY
 *  Shows the current 5-Act weekly structure phase (Sun–Fri)
 * ═══════════════════════════════════════════════════════════════════
 */
import React from 'react';

const ACT_CONFIG = {
  SUNDAY_CONNECTOR:       { label: 'ACT 1 — CONNECTOR',     color: 'text-gray-500',        bg: 'bg-gray-800',    desc: 'Gap analysis. No trading.' },
  MONDAY_INDUCTION:       { label: 'ACT 2 — INDUCTION',     color: 'text-forexia-red',     bg: 'bg-red-900/20',  desc: 'Retail takes the bait. We observe.' },
  TUESDAY_ACCUMULATION:   { label: 'ACT 3 — ACCUMULATION',  color: 'text-forexia-purple',  bg: 'bg-purple-900/20', desc: 'Smart Money builds positions.' },
  WEDNESDAY_REVERSAL:     { label: 'ACT 4 — REVERSAL',      color: 'text-forexia-gold',    bg: 'bg-amber-900/20',  desc: 'WTF Pattern — PRIMARY trade day.' },
  THURSDAY_DISTRIBUTION:  { label: 'ACT 5 — DISTRIBUTION',  color: 'text-forexia-green',   bg: 'bg-emerald-900/20', desc: 'Continuation. SECONDARY trade day.' },
  FRIDAY_EPILOGUE:        { label: 'EPILOGUE',               color: 'text-forexia-cyan',    bg: 'bg-cyan-900/20',   desc: 'Profit-taking. Close by 18:00 UTC.' },
};

const DAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI'];
const DAY_ACTS = [
  'SUNDAY_CONNECTOR', 'MONDAY_INDUCTION', 'TUESDAY_ACCUMULATION',
  'WEDNESDAY_REVERSAL', 'THURSDAY_DISTRIBUTION', 'FRIDAY_EPILOGUE'
];

export default function WeeklyActDisplay({ currentAct }) {
  const config = ACT_CONFIG[currentAct] || ACT_CONFIG.SUNDAY_CONNECTOR;

  return (
    <div className="glass-panel rounded-xl p-6">
      <h2 className="text-xs uppercase tracking-widest text-gray-500 mb-3">
        Weekly 5-Act Structure
      </h2>

      {/* Current Act Banner */}
      <div className={`${config.bg} rounded-lg p-4 mb-4 border border-forexia-border`}>
        <p className={`text-lg font-bold ${config.color}`}>
          {config.label}
        </p>
        <p className="text-xs text-gray-400 mt-1">{config.desc}</p>
      </div>

      {/* Timeline */}
      <div className="flex justify-between items-center gap-1">
        {DAYS.map((day, i) => {
          const actKey = DAY_ACTS[i];
          const isActive = actKey === currentAct;
          const actConfig = ACT_CONFIG[actKey];
          const isPast = DAY_ACTS.indexOf(currentAct) > i;

          return (
            <div
              key={day}
              className={`flex-1 text-center py-2 rounded-md text-[10px] font-bold transition-all ${
                isActive
                  ? `${actConfig.bg} ${actConfig.color} border border-current pulse-active`
                  : isPast
                    ? 'bg-gray-800/50 text-gray-600'
                    : 'bg-gray-900/50 text-gray-600'
              }`}
            >
              {day}
            </div>
          );
        })}
      </div>
    </div>
  );
}
