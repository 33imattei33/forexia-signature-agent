/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — SESSION PHASE PANEL
 *  Shows the Hegelian Dialectic phase (Asian/London/NY)
 * ═══════════════════════════════════════════════════════════════════
 */
import React from 'react';

const PHASE_CONFIG = {
  ASIAN_CONSOLIDATION: {
    label: 'THESIS — Asian Consolidation',
    sublabel: 'The Problem',
    desc: 'Retail is setting stops at range edges. The trap is being built.',
    color: 'text-forexia-purple',
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/30',
    icon: '🌙',
  },
  LONDON_INDUCTION: {
    label: 'ANTITHESIS — London Induction',
    sublabel: 'The Reaction',
    desc: 'False breakout in progress. Retail is being trapped.',
    color: 'text-forexia-red',
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    icon: '⚡',
  },
  NEWYORK_REVERSAL: {
    label: 'SYNTHESIS — New York Reversal',
    sublabel: 'The Solution',
    desc: 'EXECUTION WINDOW. Smart Money reverses the trap.',
    color: 'text-forexia-green',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    icon: '🎯',
  },
  MARKET_CLOSED: {
    label: 'MARKET CLOSED',
    sublabel: '',
    desc: 'No active session. Analysis only.',
    color: 'text-gray-500',
    bg: 'bg-gray-500/5',
    border: 'border-gray-600/30',
    icon: '⏸',
  },
};

/**
 * Determine session phase from UTC time (client-side fallback).
 * Ensures we never show "MARKET CLOSED" on weekdays.
 */
function getClientSidePhase() {
  const now = new Date();
  const day = now.getUTCDay(); // 0=Sun, 6=Sat
  if (day === 0 || day === 6) return 'MARKET_CLOSED';
  const h = now.getUTCHours();
  if (h >= 0 && h < 8) return 'ASIAN_CONSOLIDATION';
  if (h >= 8 && h < 13) return 'LONDON_INDUCTION';
  return 'NEWYORK_REVERSAL';
}

export default function SessionPhasePanel({ sessionPhase, inKillzone, tradingPermitted }) {
  // Use server phase if valid, otherwise compute from UTC clock
  const resolvedPhase =
    sessionPhase && PHASE_CONFIG[sessionPhase]
      ? sessionPhase
      : getClientSidePhase();
  const config = PHASE_CONFIG[resolvedPhase];

  return (
    <div className="glass-panel rounded-xl p-6">
      <h2 className="text-xs uppercase tracking-widest text-gray-500 mb-3">
        Hegelian Dialectic Phase
      </h2>

      <div className={`${config.bg} ${config.border} border rounded-lg p-4`}>
        <div className="flex items-start gap-3">
          <span className="text-2xl">{config.icon}</span>
          <div>
            <p className={`text-sm font-bold ${config.color}`}>
              {config.label}
            </p>
            {config.sublabel && (
              <p className="text-xs text-gray-500 mt-0.5">{config.sublabel}</p>
            )}
            <p className="text-[11px] text-gray-400 mt-2">{config.desc}</p>
          </div>
        </div>
      </div>

      {/* Status indicators */}
      <div className="flex gap-3 mt-4">
        <div className={`flex items-center gap-1.5 text-[10px] ${
          inKillzone ? 'text-forexia-green' : 'text-gray-600'
        }`}>
          <span className={`w-2 h-2 rounded-full ${
            inKillzone ? 'bg-forexia-green animate-pulse' : 'bg-gray-700'
          }`} />
          NY Kill Zone
        </div>
        <div className={`flex items-center gap-1.5 text-[10px] ${
          tradingPermitted ? 'text-forexia-green' : 'text-forexia-red'
        }`}>
          <span className={`w-2 h-2 rounded-full ${
            tradingPermitted ? 'bg-forexia-green' : 'bg-forexia-red'
          }`} />
          {tradingPermitted ? 'Trading Active' : 'Trading Blocked'}
        </div>
      </div>
    </div>
  );
}
