/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — GEMINI AI ADVISOR PANEL
 *  Real-time AI market intelligence powered by Google Gemini
 * ═══════════════════════════════════════════════════════════════════
 */
import React, { useState, useEffect, useCallback } from 'react';

/* ───── Regime color mapping ───── */
const REGIME_COLORS = {
  trending_up: { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/25', label: '▲ TRENDING UP' },
  trending_down: { bg: 'bg-red-500/15', text: 'text-red-400', border: 'border-red-500/25', label: '▼ TRENDING DOWN' },
  ranging: { bg: 'bg-amber-500/15', text: 'text-amber-400', border: 'border-amber-500/25', label: '◆ RANGING' },
  volatile: { bg: 'bg-purple-500/15', text: 'text-purple-400', border: 'border-purple-500/25', label: '⚡ VOLATILE' },
  calm: { bg: 'bg-blue-500/15', text: 'text-blue-400', border: 'border-blue-500/25', label: '○ CALM' },
};

const BIAS_ICONS = {
  bullish: { icon: '🟢', label: 'BULLISH' },
  bearish: { icon: '🔴', label: 'BEARISH' },
  neutral: { icon: '⚪', label: 'NEUTRAL' },
};

const MOOD_COLORS = {
  risk_on: 'text-emerald-400',
  risk_off: 'text-red-400',
  mixed: 'text-amber-400',
  uncertain: 'text-gray-400',
};

/* ───── Confidence bar ───── */
function ConfidenceBar({ value, label }) {
  const pct = Math.round(value * 100);
  const color = pct >= 70 ? 'bg-emerald-500' : pct >= 40 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      {label && <span className="text-[9px] text-gray-500 w-14 shrink-0">{label}</span>}
      <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[9px] text-gray-400 w-8 text-right">{pct}%</span>
    </div>
  );
}

/* ───── Analysis Card for a single pair ───── */
function PairAnalysisCard({ analysis, onRefresh }) {
  const [expanded, setExpanded] = useState(false);
  const regime = REGIME_COLORS[analysis.market_regime] || REGIME_COLORS.calm;
  const bias = BIAS_ICONS[analysis.bias] || BIAS_ICONS.neutral;

  return (
    <div className="bg-gray-900/50 rounded border border-gray-800/60 p-3 hover:border-gray-700/60 transition-colors">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-white">{analysis.symbol}</span>
          <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold ${regime.bg} ${regime.text} border ${regime.border}`}>
            {regime.label}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-gray-500">{bias.icon} {bias.label}</span>
          <button
            onClick={() => onRefresh(analysis.symbol)}
            className="text-[9px] text-gray-600 hover:text-forexia-accent transition-colors"
            title="Refresh analysis"
          >
            ↻
          </button>
        </div>
      </div>

      {/* Confidence */}
      <ConfidenceBar value={analysis.confidence} label="AI Conf" />

      {/* Narrative */}
      <p className="text-[10px] text-gray-300 mt-2 leading-relaxed">{analysis.narrative}</p>

      {/* Expandable details */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-[9px] text-forexia-accent/60 hover:text-forexia-accent mt-1 transition-colors"
      >
        {expanded ? '▴ Less' : '▾ More details'}
      </button>

      {expanded && (
        <div className="mt-2 space-y-1.5 border-t border-gray-800/40 pt-2">
          {analysis.strategy_notes && (
            <div>
              <span className="text-[8px] text-gray-600 uppercase tracking-wider">Strategy</span>
              <p className="text-[10px] text-gray-400">{analysis.strategy_notes}</p>
            </div>
          )}
          {analysis.trade_idea && (
            <div>
              <span className="text-[8px] text-gray-600 uppercase tracking-wider">Trade Idea</span>
              <p className="text-[10px] text-forexia-accent/80">{analysis.trade_idea}</p>
            </div>
          )}
          {analysis.risk_warning && (
            <div>
              <span className="text-[8px] text-gray-600 uppercase tracking-wider">Risk Warning</span>
              <p className="text-[10px] text-forexia-red/80">{analysis.risk_warning}</p>
            </div>
          )}
          {analysis.timeframe_context && (
            <div>
              <span className="text-[8px] text-gray-600 uppercase tracking-wider">TF Context</span>
              <p className="text-[10px] text-gray-400">{analysis.timeframe_context}</p>
            </div>
          )}
          {analysis.key_levels?.length > 0 && (
            <div>
              <span className="text-[8px] text-gray-600 uppercase tracking-wider">Key Levels</span>
              <div className="flex flex-wrap gap-1 mt-0.5">
                {analysis.key_levels.map((lv, i) => (
                  <span key={i} className="text-[9px] bg-gray-800 text-gray-300 px-1.5 py-0.5 rounded">
                    {typeof lv === 'number' ? lv.toFixed(5) : lv}
                  </span>
                ))}
              </div>
            </div>
          )}
          <div className="text-[8px] text-gray-700 text-right">
            {analysis.timestamp ? new Date(analysis.timestamp).toLocaleTimeString() : ''}
          </div>
        </div>
      )}
    </div>
  );
}

/* ───── Signal Review Card ───── */
function SignalReviewCard({ review }) {
  const agreeColor = review.ai_agrees ? 'text-emerald-400' : 'text-red-400';
  const agreeBg = review.ai_agrees ? 'bg-emerald-500/10' : 'bg-red-500/10';
  const scorePct = Math.round((review.agreement_score + 1) * 50); // -1..+1 → 0..100

  return (
    <div className={`rounded border border-gray-800/40 p-2 ${agreeBg}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-white">{review.symbol}</span>
          <span className="text-[9px] text-gray-400">{review.signal_direction} · {review.signal_type}</span>
        </div>
        <span className={`text-[9px] font-bold ${agreeColor}`}>
          {review.ai_agrees ? '✓ AGREES' : '✗ DISAGREES'} ({review.agreement_score > 0 ? '+' : ''}{review.agreement_score.toFixed(1)})
        </span>
      </div>
      <p className="text-[9px] text-gray-400 mt-1">{review.reasoning}</p>
      {review.concerns && (
        <p className="text-[9px] text-forexia-red/70 mt-0.5">⚠ {review.concerns}</p>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════════════
 *  MAIN COMPONENT
 * ═══════════════════════════════════════════════════════════════════ */
export default function GeminiAdvisorPanel({ brokerConnected }) {
  const [aiState, setAiState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(null); // symbol being refreshed
  const [activeTab, setActiveTab] = useState('analyses'); // analyses | overview | reviews

  /* ───── Fetch AI state ───── */
  const fetchAI = useCallback(async () => {
    try {
      const res = await fetch('/api/ai/status');
      const data = await res.json();
      setAiState(data);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchAI();
    const interval = setInterval(fetchAI, 15000); // refresh every 15s
    return () => clearInterval(interval);
  }, [fetchAI]);

  /* ───── Trigger analysis for one pair ───── */
  const triggerAnalysis = useCallback(async (symbol) => {
    setRefreshing(symbol);
    try {
      const res = await fetch(`/api/ai/analyze/${symbol}`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'OK' && data.analysis) {
        setAiState((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            analyses: { ...prev.analyses, [symbol]: data.analysis },
          };
        });
      }
    } catch { /* silent */ }
    finally { setRefreshing(null); }
  }, []);

  const status = aiState?.status || {};
  const analyses = aiState?.analyses || {};
  const overview = aiState?.overview || null;
  const reviews = aiState?.signal_reviews || [];
  const isEnabled = status.enabled;

  /* ───── Not configured state ───── */
  if (!isEnabled && !loading) {
    return (
      <div className="bg-forexia-panel rounded-lg border border-gray-800/60 p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-sm">🤖</span>
          <h2 className="text-xs font-bold text-white uppercase tracking-wider">AI Advisor</h2>
          <span className="text-[8px] text-gray-600 bg-gray-800 px-1.5 py-0.5 rounded">GEMINI</span>
        </div>
        <div className="text-center py-6">
          <div className="text-2xl mb-2">🔑</div>
          <p className="text-[11px] text-gray-400 mb-1">Gemini AI Advisor is not configured</p>
          <p className="text-[9px] text-gray-600 mb-3">
            Add your Google Gemini API key in Settings → Agent → Gemini API Key
          </p>
          <a
            href="https://aistudio.google.com/apikey"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[9px] text-forexia-accent hover:underline"
          >
            Get a free API key at aistudio.google.com →
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-forexia-panel rounded-lg border border-gray-800/60 p-4">
      {/* ───── Header ───── */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm">🤖</span>
          <h2 className="text-xs font-bold text-white uppercase tracking-wider">AI Advisor</h2>
          <span className="text-[8px] text-forexia-accent bg-forexia-accent/10 px-1.5 py-0.5 rounded border border-forexia-accent/20">
            {status.model || 'GEMINI'}
          </span>
          <span className="text-[8px] text-gray-600">
            {status.daily_calls}/{status.daily_limit} calls
          </span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[8px] text-gray-500">LIVE</span>
        </div>
      </div>

      {/* ───── Tabs ───── */}
      <div className="flex gap-1 mb-3 border-b border-gray-800/40 pb-2">
        {[
          { key: 'analyses', label: 'PAIR ANALYSIS', count: Object.keys(analyses).length },
          { key: 'overview', label: 'MARKET OVERVIEW' },
          { key: 'reviews', label: 'SIGNAL REVIEWS', count: reviews.length },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-2.5 py-1 rounded text-[9px] font-bold uppercase tracking-wider transition-all ${
              activeTab === tab.key
                ? 'bg-forexia-accent/15 text-forexia-accent border border-forexia-accent/25'
                : 'text-gray-500 hover:text-gray-300 border border-transparent'
            }`}
          >
            {tab.label}{tab.count != null ? ` (${tab.count})` : ''}
          </button>
        ))}
      </div>

      {/* ───── TAB: Pair Analyses ───── */}
      {activeTab === 'analyses' && (
        <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1 scrollbar-thin">
          {Object.keys(analyses).length === 0 ? (
            <div className="text-center py-6">
              <div className="text-lg mb-1">📊</div>
              <p className="text-[10px] text-gray-500">
                {loading ? 'Loading AI analyses...' : 'Waiting for first AI scan cycle (every 5 min)'}
              </p>
            </div>
          ) : (
            Object.values(analyses).map((a) => (
              <PairAnalysisCard
                key={a.symbol}
                analysis={a}
                onRefresh={triggerAnalysis}
              />
            ))
          )}
          {refreshing && (
            <div className="text-center py-2">
              <span className="text-[9px] text-forexia-accent animate-pulse">
                Analyzing {refreshing}...
              </span>
            </div>
          )}
        </div>
      )}

      {/* ───── TAB: Market Overview ───── */}
      {activeTab === 'overview' && (
        <div>
          {!overview ? (
            <div className="text-center py-6">
              <div className="text-lg mb-1">🌍</div>
              <p className="text-[10px] text-gray-500">Market overview generating...</p>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Market Mood + Dollar */}
              <div className="flex gap-3">
                <div className="flex-1 bg-gray-900/50 rounded border border-gray-800/40 p-2.5">
                  <span className="text-[8px] text-gray-600 uppercase tracking-wider">Market Mood</span>
                  <p className={`text-sm font-bold uppercase ${MOOD_COLORS[overview.market_mood] || 'text-gray-400'}`}>
                    {(overview.market_mood || 'unknown').replace('_', ' ')}
                  </p>
                </div>
                <div className="flex-1 bg-gray-900/50 rounded border border-gray-800/40 p-2.5">
                  <span className="text-[8px] text-gray-600 uppercase tracking-wider">USD Bias</span>
                  <p className="text-sm font-bold text-white uppercase">
                    {overview.dollar_bias || '—'}
                  </p>
                </div>
              </div>

              {/* Best Opportunities */}
              {overview.best_opportunities?.length > 0 && (
                <div>
                  <span className="text-[8px] text-gray-600 uppercase tracking-wider">Best Opportunities</span>
                  <div className="flex gap-1 mt-1">
                    {overview.best_opportunities.map((sym) => (
                      <span key={sym} className="text-[9px] bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/20">
                        {sym}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Avoid */}
              {overview.avoid_pairs?.length > 0 && (
                <div>
                  <span className="text-[8px] text-gray-600 uppercase tracking-wider">Avoid</span>
                  <div className="flex gap-1 mt-1">
                    {overview.avoid_pairs.map((sym) => (
                      <span key={sym} className="text-[9px] bg-red-500/10 text-red-400 px-2 py-0.5 rounded border border-red-500/20">
                        {sym}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Overview text */}
              <div>
                <span className="text-[8px] text-gray-600 uppercase tracking-wider">Overview</span>
                <p className="text-[10px] text-gray-300 mt-1 leading-relaxed">{overview.overview}</p>
              </div>

              {/* Session Outlook */}
              {overview.session_outlook && (
                <div>
                  <span className="text-[8px] text-gray-600 uppercase tracking-wider">Session Outlook</span>
                  <p className="text-[10px] text-forexia-accent/80 mt-1">{overview.session_outlook}</p>
                </div>
              )}

              <div className="text-[8px] text-gray-700 text-right">
                {overview.timestamp ? new Date(overview.timestamp).toLocaleTimeString() : ''}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ───── TAB: Signal Reviews ───── */}
      {activeTab === 'reviews' && (
        <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1 scrollbar-thin">
          {reviews.length === 0 ? (
            <div className="text-center py-6">
              <div className="text-lg mb-1">🔍</div>
              <p className="text-[10px] text-gray-500">No signal reviews yet</p>
              <p className="text-[9px] text-gray-600">AI will review signals as they are generated</p>
            </div>
          ) : (
            reviews.slice().reverse().map((r, i) => (
              <SignalReviewCard key={i} review={r} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
