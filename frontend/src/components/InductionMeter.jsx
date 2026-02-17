/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — INDUCTION METER
 *  Gauge showing how much retail volume is trapped (0-100%)
 *  Higher = more dumb money trapped = higher reversal probability
 * ═══════════════════════════════════════════════════════════════════
 */
import React from 'react';

export default function InductionMeter({ value = 0 }) {
  // Clamp 0-100
  const clamped = Math.max(0, Math.min(100, value));

  // Color gradient based on trap depth
  const getColor = (v) => {
    if (v >= 80) return { ring: '#10b981', text: 'text-forexia-green', label: 'MAXIMUM TRAP' };
    if (v >= 60) return { ring: '#f59e0b', text: 'text-forexia-gold', label: 'HIGH INDUCTION' };
    if (v >= 40) return { ring: '#3b82f6', text: 'text-forexia-accent', label: 'MODERATE' };
    if (v >= 20) return { ring: '#8b5cf6', text: 'text-forexia-purple', label: 'BUILDING' };
    return { ring: '#6b7280', text: 'text-gray-500', label: 'LOW ACTIVITY' };
  };

  const colorConfig = getColor(clamped);

  // SVG circular gauge
  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (clamped / 100) * circumference;

  return (
    <div className="glass-panel rounded-xl p-6 flex flex-col items-center">
      <h2 className="text-xs uppercase tracking-widest text-gray-500 mb-4">
        Induction Meter
      </h2>

      {/* Circular Gauge */}
      <div className="relative w-40 h-40">
        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 140 140">
          {/* Background ring */}
          <circle
            cx="70" cy="70" r={radius}
            fill="none"
            stroke="#1e293b"
            strokeWidth="8"
          />
          {/* Progress ring */}
          <circle
            cx="70" cy="70" r={radius}
            fill="none"
            stroke={colorConfig.ring}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            style={{
              transition: 'stroke-dashoffset 1s ease-in-out, stroke 0.5s ease',
              filter: `drop-shadow(0 0 6px ${colorConfig.ring}80)`,
            }}
          />
        </svg>

        {/* Center value */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-3xl font-bold ${colorConfig.text}`}
                style={{ textShadow: `0 0 15px ${colorConfig.ring}60` }}>
            {clamped.toFixed(0)}
          </span>
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">
            percent
          </span>
        </div>
      </div>

      {/* Status label */}
      <p className={`text-xs font-bold mt-3 uppercase tracking-wider ${colorConfig.text}`}>
        {colorConfig.label}
      </p>
      <p className="text-[10px] text-gray-600 mt-1 text-center">
        Trapped retail volume estimation
      </p>
    </div>
  );
}
