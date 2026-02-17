/**
 * ═══════════════════════════════════════════════════════════════════
 *  FOREXIA — PROFESSIONAL LIVE MARKET CHART
 *  TradingView-grade candlestick chart with position overlays
 *  Uses lightweight-charts v4 from CDN
 * ═══════════════════════════════════════════════════════════════════
 */
import React, { useEffect, useRef, useState, useCallback } from 'react';

/* ── CDN loader (singleton) ── */
const LWC_CDN = 'https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js';
let lwcPromise = null;
function loadLWC() {
  if (window.LightweightCharts) return Promise.resolve(window.LightweightCharts);
  if (lwcPromise) return lwcPromise;
  lwcPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = LWC_CDN;
    s.onload = () => resolve(window.LightweightCharts);
    s.onerror = () => reject(new Error('Failed to load chart library'));
    document.head.appendChild(s);
  });
  return lwcPromise;
}

/* ── Price precision per symbol ── */
function getPrecision(sym) {
  if (sym.includes('JPY')) return { decimals: 3, minMove: 0.001 };
  if (sym.includes('XAU')) return { decimals: 2, minMove: 0.01 };
  return { decimals: 5, minMove: 0.00001 };
}

/* ── Constants ── */
const TIMEFRAMES = [
  { value: 'M1',  short: '1' },
  { value: 'M5',  short: '5' },
  { value: 'M15', short: '15' },
  { value: 'M30', short: '30' },
  { value: 'H1',  short: 'H1' },
  { value: 'H4',  short: 'H4' },
  { value: 'D1',  short: 'D' },
  { value: 'W1',  short: 'W' },
];

const SYMBOLS = [
  { value: 'EURUSD', flag: '🇪🇺' },
  { value: 'GBPUSD', flag: '🇬🇧' },
  { value: 'USDCHF', flag: '🇨🇭' },
  { value: 'USDJPY', flag: '🇯🇵' },
  { value: 'XAUUSD', flag: '🥇' },
];

/* ═══════════════════════════════════════════════════════════════════ */
export default function LiveChart({ brokerConnected }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const priceLinesRef = useRef([]);
  const pollRef = useRef(null);
  const isFirstLoadRef = useRef(true);

  const [symbol, setSymbol] = useState('GBPUSD');
  const [timeframe, setTimeframe] = useState('H1');
  const [loading, setLoading] = useState(true);
  const [lastBar, setLastBar] = useState(null);
  const [prevClose, setPrevClose] = useState(null);
  const [positions, setPositions] = useState([]);
  const [lwcReady, setLwcReady] = useState(false);
  const [error, setError] = useState(null);
  const [crosshairData, setCrosshairData] = useState(null);
  const [utcTime, setUtcTime] = useState('');

  // UTC clock
  useEffect(() => {
    const tick = () => {
      const d = new Date();
      setUtcTime(d.toUTCString().slice(17, 25) + ' UTC');
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  /* ── Load library ── */
  useEffect(() => {
    loadLWC().then(() => setLwcReady(true)).catch(() => setError('Chart library failed'));
  }, []);

  /* ── Create chart (rebuilds on symbol change for precision) ── */
  useEffect(() => {
    if (!lwcReady || !containerRef.current) return;
    const LWC = window.LightweightCharts;
    if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; }

    const { decimals, minMove } = getPrecision(symbol);

    const chart = LWC.createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      layout: {
        background: { type: 'solid', color: '#0a0e17' },
        textColor: '#6b7280',
        fontSize: 11,
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
      },
      grid: {
        vertLines: { color: '#1e293b44', style: 1 },
        horzLines: { color: '#1e293b44', style: 1 },
      },
      crosshair: {
        mode: 0,
        vertLine: {
          color: 'rgba(59,130,246,0.3)',
          width: 1,
          style: 0,
          labelBackgroundColor: '#3b82f6',
        },
        horzLine: {
          color: 'rgba(59,130,246,0.3)',
          width: 1,
          style: 0,
          labelBackgroundColor: '#3b82f6',
        },
      },
      rightPriceScale: {
        borderVisible: true,
        borderColor: '#1e293b',
        entireTextOnly: true,
        scaleMargins: { top: 0.02, bottom: 0.15 },
        mode: 0,
        autoScale: true,
      },
      timeScale: {
        borderColor: '#1e293b',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 12,
        barSpacing: 7,
        minBarSpacing: 2,
        fixLeftEdge: false,
        fixRightEdge: false,
        lockVisibleTimeRangeOnResize: true,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { axisPressedMouseMove: { time: true, price: true }, mouseWheel: true, pinch: true },
      localization: {
        priceFormatter: (price) => price.toFixed(decimals),
      },
    });

    // Candlestick series — Forexia green/red
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
      priceFormat: {
        type: 'price',
        precision: decimals,
        minMove,
      },
    });

    // Volume histogram
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
    });
    chart.priceScale('vol').applyOptions({
      scaleMargins: { top: 0.88, bottom: 0 },
      drawTicks: false,
      borderVisible: false,
    });

    // Crosshair → OHLCV at cursor position
    chart.subscribeCrosshairMove((param) => {
      if (!param || !param.time) {
        setCrosshairData(null);
        return;
      }
      const bar = param.seriesData?.get(candleSeries);
      if (bar) {
        setCrosshairData({
          open: bar.open,
          high: bar.high,
          low: bar.low,
          close: bar.close,
        });
      }
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // Auto-resize
    const ro = new ResizeObserver(([entry]) => {
      if (chartRef.current && entry) {
        chartRef.current.applyOptions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; }
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      priceLinesRef.current = [];
    };
  }, [lwcReady, symbol]);

  /* ── Fetch candles ── */
  const fetchCandles = useCallback(async () => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current) return;
    try {
      const res = await fetch(`/api/candles?symbol=${symbol}&timeframe=${timeframe}&count=500`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!Array.isArray(data) || data.length === 0) return;

      candleSeriesRef.current.setData(data);

      const volData = data.map((bar) => ({
        time: bar.time,
        value: bar.volume || 0,
        color: bar.close >= bar.open ? 'rgba(16,185,129,0.18)' : 'rgba(239,68,68,0.18)',
      }));
      volumeSeriesRef.current.setData(volData);

      setLastBar(data[data.length - 1]);
      if (data.length > 1) setPrevClose(data[data.length - 2].close);
      setLoading(false);
      setError(null);

      if (isFirstLoadRef.current && chartRef.current) {
        chartRef.current.timeScale().fitContent();
        isFirstLoadRef.current = false;
      }
    } catch (e) {
      console.error('Candle fetch error:', e);
      setError('Could not load market data');
    }
  }, [symbol, timeframe]);

  /* ── Fetch positions ── */
  const fetchPositions = useCallback(async () => {
    if (!brokerConnected) { setPositions([]); return; }
    try {
      const res = await fetch(`/api/chart/positions?symbol=${symbol}`);
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) setPositions(data);
    } catch { /* silent */ }
  }, [symbol, brokerConnected]);

  /* ── Draw position lines (entry / SL / TP) ── */
  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;
    const { decimals } = getPrecision(symbol);

    priceLinesRef.current.forEach((line) => {
      try { series.removePriceLine(line); } catch {}
    });
    priceLinesRef.current = [];

    positions.forEach((pos) => {
      let lineStyle = 2; // Dashed
      let lineWidth = 1;
      let title = '';
      let color = pos.color;

      if (pos.type === 'entry') {
        const pnl = pos.profit >= 0 ? `+$${pos.profit.toFixed(2)}` : `-$${Math.abs(pos.profit).toFixed(2)}`;
        title = `${pos.direction} ${pos.lots} | ${pnl}`;
        lineWidth = 2;
        lineStyle = 2;
        color = pos.direction === 'BUY' ? '#10b981' : '#ef4444';
      } else if (pos.type === 'sl') {
        title = `SL ${pos.price.toFixed(decimals)}`;
        color = '#ef4444';
      } else if (pos.type === 'tp') {
        title = `TP ${pos.price.toFixed(decimals)}`;
        color = '#10b981';
      }

      try {
        const priceLine = series.createPriceLine({
          price: pos.price,
          color,
          lineWidth,
          lineStyle,
          axisLabelVisible: true,
          title,
        });
        priceLinesRef.current.push(priceLine);
      } catch {}
    });
  }, [positions, symbol]);

  /* ── Load on symbol/tf change ── */
  useEffect(() => {
    setLoading(true);
    setLastBar(null);
    setPrevClose(null);
    setCrosshairData(null);
    isFirstLoadRef.current = true;
    fetchCandles();
    fetchPositions();
  }, [symbol, timeframe, fetchCandles, fetchPositions]);

  /* ── Live polling ── */
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(() => {
      fetchCandles();
      fetchPositions();
    }, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [fetchCandles, fetchPositions]);

  /* ── Toolbar ── */
  const handleFitContent = () => chartRef.current?.timeScale().fitContent();
  const handleScrollToEnd = () => chartRef.current?.timeScale().scrollToRealTime();

  /* ── Computed ── */
  const { decimals } = getPrecision(symbol);
  const displayBar = crosshairData || lastBar;
  const dailyChange = lastBar && prevClose ? lastBar.close - prevClose : 0;
  const dailyChangePct = prevClose ? ((dailyChange / prevClose) * 100) : 0;
  const isUp = dailyChange >= 0;
  const entryPositions = positions.filter((p) => p.type === 'entry');
  const currentSymbol = SYMBOLS.find((s) => s.value === symbol);
  const barChange = displayBar ? displayBar.close - displayBar.open : 0;
  const barUp = barChange >= 0;

  return (
    <div className="glass-panel rounded-xl overflow-hidden flex flex-col" style={{ height: '560px' }}>

      {/* ═══ TOP BAR ═══ */}
      <div className="flex items-center gap-0 border-b border-forexia-border/60 shrink-0 bg-forexia-panel/80">

        {/* Symbol tabs */}
        <div className="flex items-center border-r border-forexia-border/60">
          {SYMBOLS.map((s) => (
            <button
              key={s.value}
              onClick={() => setSymbol(s.value)}
              className={`px-3 py-2 text-[11px] font-semibold tracking-wide transition-all border-b-2 ${
                symbol === s.value
                  ? 'text-white border-forexia-accent bg-forexia-accent/5'
                  : 'text-gray-500 border-transparent hover:text-gray-300 hover:bg-white/[0.02]'
              }`}
            >
              <span className="mr-1 text-[10px]">{s.flag}</span>{s.value}
            </button>
          ))}
        </div>

        {/* OHLC */}
        <div className="flex items-center gap-2.5 px-3 border-r border-forexia-border/60 py-2 font-mono text-[11px]">
          {displayBar ? (
            <>
              <span className="text-gray-500">O <span className="text-gray-400">{displayBar.open?.toFixed(decimals)}</span></span>
              <span className="text-gray-500">H <span className="text-forexia-green">{displayBar.high?.toFixed(decimals)}</span></span>
              <span className="text-gray-500">L <span className="text-forexia-red">{displayBar.low?.toFixed(decimals)}</span></span>
              <span className="text-gray-500">C <span className={barUp ? 'text-forexia-green' : 'text-forexia-red'}>{displayBar.close?.toFixed(decimals)}</span></span>
            </>
          ) : (
            <span className="text-gray-700">—</span>
          )}
        </div>

        {/* Daily change pill */}
        {lastBar && prevClose && (
          <div className={`flex items-center gap-1.5 px-3 border-r border-forexia-border/60 py-2 text-[11px] font-mono font-bold ${isUp ? 'text-forexia-green' : 'text-forexia-red'}`}>
            <span>{isUp ? '▲' : '▼'}</span>
            <span>{isUp ? '+' : ''}{dailyChange.toFixed(decimals)}</span>
            <span className="text-gray-700">/</span>
            <span>{isUp ? '+' : ''}{dailyChangePct.toFixed(2)}%</span>
          </div>
        )}

        <div className="flex-1" />

        {/* Tools */}
        <div className="flex items-center gap-0 px-1 border-l border-forexia-border/60">
          <ToolBtn title="Go to latest" onClick={handleScrollToEnd}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
          </ToolBtn>
          <ToolBtn title="Fit all data" onClick={handleFitContent}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
          </ToolBtn>
          <ToolBtn title="Reset zoom" onClick={() => { handleFitContent(); }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/><path d="M8 11h6"/></svg>
          </ToolBtn>
        </div>

        {/* Timeframe tabs */}
        <div className="flex items-center border-l border-forexia-border/60">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf.value}
              onClick={() => setTimeframe(tf.value)}
              className={`px-2.5 py-2 text-[11px] font-semibold tracking-wide transition-all border-b-2 ${
                timeframe === tf.value
                  ? 'text-white border-forexia-accent bg-forexia-accent/5'
                  : 'text-gray-500 border-transparent hover:text-gray-300 hover:bg-white/[0.02]'
              }`}
            >
              {tf.short}
            </button>
          ))}
        </div>

        {/* Clock */}
        <div className="px-3 py-2 text-[10px] text-gray-500 font-mono border-l border-forexia-border/60 whitespace-nowrap">
          {utcTime}
        </div>
      </div>

      {/* ═══ POSITION BADGES ═══ */}
      {entryPositions.length > 0 && (
        <div className="flex items-center gap-2 px-3 py-1 border-b border-forexia-border/30 bg-forexia-bg shrink-0">
          <span className="text-[9px] text-gray-500 uppercase tracking-widest mr-1">Open:</span>
          {entryPositions.map((pos, i) => {
            const isBuy = pos.direction === 'BUY';
            const pnlPos = pos.profit >= 0;
            return (
              <div
                key={`${pos.ticket}-${i}`}
                className={`flex items-center gap-1.5 px-2 py-0.5 rounded text-[9px] font-semibold border ${
                  isBuy ? 'bg-forexia-green/8 border-forexia-green/15' : 'bg-forexia-red/8 border-forexia-red/15'
                }`}
              >
                <span className={isBuy ? 'text-forexia-green' : 'text-forexia-red'}>
                  {isBuy ? '▲' : '▼'} {pos.direction}
                </span>
                <span className="text-gray-400">{pos.lots}</span>
                <span className="text-gray-700">@</span>
                <span className="text-gray-400 font-mono">{pos.price?.toFixed(decimals)}</span>
                <span className={`font-mono font-bold ${pnlPos ? 'text-forexia-green' : 'text-forexia-red'}`}>
                  {pnlPos ? '+' : ''}{pos.profit?.toFixed(2)}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* ═══ CHART CANVAS ═══ */}
      <div ref={containerRef} className="flex-1 relative min-h-0">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-forexia-bg/95 z-10">
            <div className="text-center">
              <div className="w-5 h-5 border-2 border-forexia-accent border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              <p className="text-[10px] text-gray-500 font-mono">{currentSymbol?.flag} {symbol} · {timeframe}</p>
            </div>
          </div>
        )}
        {error && !loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-forexia-bg/95 z-10">
            <div className="text-center">
              <p className="text-[11px] text-forexia-red mb-2 font-mono">{error}</p>
              <button
                onClick={() => { setError(null); setLoading(true); fetchCandles(); }}
                className="px-3 py-1 rounded text-[10px] bg-forexia-border text-gray-400 hover:bg-gray-700 transition font-mono"
              >
                Retry
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ═══ BOTTOM STATUS BAR ═══ */}
      <div className="flex items-center justify-between px-3 py-1 border-t border-forexia-border/60 bg-forexia-bg shrink-0 text-[9px] font-mono">
        <div className="flex items-center gap-2.5 text-gray-500">
          <span className={`flex items-center gap-1 ${brokerConnected ? 'text-forexia-green' : 'text-forexia-red'}`}>
            <span className={`w-1.5 h-1.5 rounded-full inline-block ${brokerConnected ? 'bg-forexia-green' : 'bg-forexia-red'}`} />
            {brokerConnected ? 'LIVE' : 'OFFLINE'}
          </span>
          <span className="text-forexia-border">│</span>
          <span>{currentSymbol?.flag} {symbol}</span>
          <span className="text-forexia-border">│</span>
          <span>{timeframe}</span>
          {entryPositions.length > 0 && (
            <>
              <span className="text-forexia-border">│</span>
              <span className="text-gray-400">{entryPositions.length} position{entryPositions.length !== 1 ? 's' : ''}</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-2 text-gray-600">
          <span>Auto-refresh 3s</span>
          <span className="text-forexia-border">│</span>
          <span>Scroll ↕ zoom · Drag ↔ pan · Price axis drag ↕ scale</span>
        </div>
      </div>
    </div>
  );
}

/* ── Tiny tool button component ── */
function ToolBtn({ children, onClick, title }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="p-1.5 text-gray-500 rounded hover:text-gray-200 hover:bg-white/[0.04] transition-all flex items-center justify-center"
    >
      {children}
    </button>
  );
}
