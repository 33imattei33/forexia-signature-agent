/**
 * FOREXIA - TRADINGVIEW CHARTS
 * Professional TradingView Advanced Chart embeds
 * Single chart + Multi-TF grid views
 * Position overlay badges
 */
import React, { useEffect, useRef, useState, useCallback, memo } from "react";

/* Available symbols */
const SYMBOLS = [
  { value: "GBPJPY", tv: "FX:GBPJPY", flag: "\ud83c\uddec\ud83c\udde7\ud83c\uddef\ud83c\uddf5", tier: "star" },
  { value: "USDJPY", tv: "FX:USDJPY", flag: "\ud83c\uddfa\ud83c\uddf8\ud83c\uddef\ud83c\uddf5", tier: "star" },
  { value: "EURJPY", tv: "FX:EURJPY", flag: "\ud83c\uddea\ud83c\uddfa\ud83c\uddef\ud83c\uddf5", tier: "star" },
  { value: "GBPUSD", tv: "FX:GBPUSD", flag: "\ud83c\uddec\ud83c\udde7\ud83c\uddfa\ud83c\uddf8", tier: "neutral" },
  { value: "EURUSD", tv: "FX:EURUSD", flag: "\ud83c\uddea\ud83c\uddfa\ud83c\uddfa\ud83c\uddf8", tier: "neutral" },
  { value: "USDCHF", tv: "FX:USDCHF", flag: "\ud83c\uddfa\ud83c\uddf8\ud83c\udde8\ud83c\udded", tier: "neutral" },
  { value: "EURAUD", tv: "FX:EURAUD", flag: "\ud83c\uddea\ud83c\uddfa\ud83c\udde6\ud83c\uddfa", tier: "neutral" },
  { value: "EURGBP", tv: "FX:EURGBP", flag: "\ud83c\uddea\ud83c\uddfa\ud83c\uddec\ud83c\udde7", tier: "neutral" },
  { value: "GBPAUD", tv: "FX:GBPAUD", flag: "\ud83c\uddec\ud83c\udde7\ud83c\udde6\ud83c\uddfa", tier: "neutral" },
];

const TIMEFRAMES = [
  { value: "1", short: "1m", tv: "1" },
  { value: "5", short: "5m", tv: "5" },
  { value: "15", short: "15m", tv: "15" },
  { value: "30", short: "30m", tv: "30" },
  { value: "60", short: "1H", tv: "60" },
  { value: "240", short: "4H", tv: "240" },
  { value: "D", short: "1D", tv: "D" },
  { value: "W", short: "1W", tv: "W" },
];

/* Multi-TF grid: institutional top-down */
const MULTI_TF_ORDER = [
  { value: "W", short: "Weekly", label: "W1", tv: "W" },
  { value: "D", short: "Daily", label: "D1", tv: "D" },
  { value: "240", short: "4 Hour", label: "H4", tv: "240" },
  { value: "60", short: "1 Hour", label: "H1", tv: "60" },
  { value: "30", short: "30 Min", label: "M30", tv: "30" },
  { value: "15", short: "15 Min", label: "M15", tv: "15" },
  { value: "5", short: "5 Min", label: "M5", tv: "5" },
  { value: "1", short: "1 Min", label: "M1", tv: "1" },
];

function getPrecision(sym) {
  if (!sym) return 5;
  if (sym.includes("JPY")) return 3;
  if (sym.includes("XAU")) return 2;
  return 5;
}

/* Build TradingView Advanced Chart widget URL */
function buildTvUrl(tvSymbol, interval, compact) {
  const params = new URLSearchParams({
    symbol: tvSymbol,
    interval: interval,
    theme: "dark",
    style: "1",
    locale: "en",
    hide_top_toolbar: compact ? "true" : "false",
    hide_side_toolbar: compact ? "true" : "false",
    hide_legend: compact ? "true" : "false",
    allow_symbol_change: "false",
    save_image: "false",
    backgroundColor: "rgba(10, 14, 23, 1)",
    gridColor: "rgba(30, 41, 59, 0.15)",
    withdateranges: compact ? "false" : "true",
    range: "ALL",
    details: "false",
    calendar: "false",
    support_host: "https://www.tradingview.com",
  });
  return "https://www.tradingview.com/widgetembed/?" + params.toString();
}

/* TradingView Chart iframe component */
const TradingViewWidget = memo(function TradingViewWidget({ tvSymbol, interval, compact }) {
  const url = buildTvUrl(tvSymbol, interval, compact);
  return (
    <iframe
      src={url}
      style={{ width: "100%", height: "100%", border: "none" }}
      allow="clipboard-write"
      loading="lazy"
      referrerPolicy="no-referrer"
    />
  );
});


/* MAIN COMPONENT - LiveChart */
export default function LiveChart({ brokerConnected }) {
  const [symbol, setSymbol] = useState("GBPJPY");
  const [timeframe, setTimeframe] = useState("60");
  const [viewMode, setViewMode] = useState("single");
  const [positions, setPositions] = useState([]);
  const [utcTime, setUtcTime] = useState("");

  useEffect(() => {
    const tick = () => {
      const d = new Date();
      setUtcTime(d.toUTCString().slice(17, 25) + " UTC");
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const fetchPositions = useCallback(async () => {
    if (!brokerConnected) { setPositions([]); return; }
    try {
      const res = await fetch("/api/chart/positions?symbol=" + symbol);
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) setPositions(data);
    } catch(e) {}
  }, [symbol, brokerConnected]);

  useEffect(() => {
    fetchPositions();
    const id = setInterval(fetchPositions, 5000);
    return () => clearInterval(id);
  }, [fetchPositions]);

  const entryPositions = positions.filter((p) => p.type === "entry");
  const currentSymbol = SYMBOLS.find((s) => s.value === symbol);
  const currentTf = TIMEFRAMES.find((t) => t.value === timeframe);
  const decimals = getPrecision(symbol);
  const isMulti = viewMode === "multi";
  const tvSymbol = currentSymbol?.tv || "FX:GBPJPY";

  return (
    <div className="glass-panel rounded-xl overflow-hidden flex flex-col" style={{ height: isMulti ? "1080px" : "620px" }}>
      {/* TOP BAR */}
      <div className="flex items-center gap-0 border-b border-forexia-border/60 shrink-0 bg-forexia-panel/80">
        <div className="flex items-center overflow-x-auto scrollbar-none border-r border-forexia-border/60">
          {SYMBOLS.map((s) => (
            <button
              key={s.value}
              onClick={() => setSymbol(s.value)}
              className={
                "px-2.5 py-2 text-[10px] font-semibold tracking-wide transition-all border-b-2 whitespace-nowrap " +
                (symbol === s.value
                  ? "text-white border-forexia-accent bg-forexia-accent/5"
                  : s.tier === "star"
                    ? "text-forexia-gold/70 border-transparent hover:text-forexia-gold hover:bg-white/[0.02]"
                    : "text-gray-500 border-transparent hover:text-gray-300 hover:bg-white/[0.02]")
              }
              title={s.tier === "star" ? "\u2605 Star Pair" : "Neutral Pair"}
            >
              <span className="mr-0.5 text-[9px]">{s.flag}</span>
              {s.value}
              {s.tier === "star" && symbol !== s.value && (
                <span className="ml-0.5 text-[8px] text-forexia-gold/50">{"\u2605"}</span>
              )}
            </button>
          ))}
        </div>
        <div className="flex-1" />
        <div className="flex items-center border-l border-forexia-border/60">
          <button
            onClick={() => setViewMode("single")}
            className={
              "px-2.5 py-2 text-[10px] font-bold tracking-wide transition-all border-b-2 " +
              (!isMulti
                ? "text-forexia-accent border-forexia-accent bg-forexia-accent/5"
                : "text-gray-500 border-transparent hover:text-gray-300 hover:bg-white/[0.02]")
            }
            title="Single chart view"
          >{"\u25fb"} Single</button>
          <button
            onClick={() => setViewMode("multi")}
            className={
              "px-2.5 py-2 text-[10px] font-bold tracking-wide transition-all border-b-2 " +
              (isMulti
                ? "text-forexia-accent border-forexia-accent bg-forexia-accent/5"
                : "text-gray-500 border-transparent hover:text-gray-300 hover:bg-white/[0.02]")
            }
            title="All timeframes grid"
          >{"\u25eb"} All TF</button>
        </div>
        {!isMulti && (
          <div className="flex items-center border-l border-forexia-border/60">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf.value}
                onClick={() => setTimeframe(tf.value)}
                className={
                  "px-2.5 py-2 text-[10px] font-semibold tracking-wide transition-all border-b-2 " +
                  (timeframe === tf.value
                    ? "text-white border-forexia-accent bg-forexia-accent/5"
                    : "text-gray-500 border-transparent hover:text-gray-300 hover:bg-white/[0.02]")
                }
              >{tf.short}</button>
            ))}
          </div>
        )}
        <div className="px-3 py-2 text-[10px] text-gray-500 font-mono border-l border-forexia-border/60 whitespace-nowrap">
          {utcTime}
        </div>
      </div>

      {/* POSITION BADGES */}
      {entryPositions.length > 0 && (
        <div className="flex items-center gap-2 px-3 py-1 border-b border-forexia-border/30 bg-forexia-bg shrink-0">
          <span className="text-[9px] text-gray-500 uppercase tracking-widest mr-1">Open:</span>
          {entryPositions.map((pos, i) => {
            const isBuy = pos.direction === "BUY";
            const pnlPos = pos.profit >= 0;
            return (
              <div
                key={(pos.ticket || i) + "-" + i}
                className={
                  "flex items-center gap-1.5 px-2 py-0.5 rounded text-[9px] font-semibold border " +
                  (isBuy ? "bg-forexia-green/8 border-forexia-green/15" : "bg-forexia-red/8 border-forexia-red/15")
                }
              >
                <span className={isBuy ? "text-forexia-green" : "text-forexia-red"}>
                  {isBuy ? "\u25b2" : "\u25bc"} {pos.direction}
                </span>
                <span className="text-gray-400">{pos.lots}</span>
                <span className="text-gray-700">@</span>
                <span className="text-gray-400 font-mono">{pos.price?.toFixed(decimals)}</span>
                <span className={"font-mono font-bold " + (pnlPos ? "text-forexia-green" : "text-forexia-red")}>
                  {pnlPos ? "+" : ""}{pos.profit?.toFixed(2)}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* CHART AREA */}
      <div className="flex-1 relative min-h-0">
        {!isMulti && (
          <TradingViewWidget tvSymbol={tvSymbol} interval={timeframe} compact={false} />
        )}
        {isMulti && (
          <div className="grid grid-cols-4 grid-rows-2 gap-[1px] h-full bg-forexia-border/30">
            {MULTI_TF_ORDER.map((tf) => (
              <div key={tf.value} className="relative bg-forexia-bg overflow-hidden">
                <div className="absolute top-1 left-1.5 z-10 px-1.5 py-0.5 rounded bg-forexia-bg/90 border border-forexia-border/40 backdrop-blur-sm pointer-events-none">
                  <span className="text-[10px] font-black text-forexia-accent tracking-wide">{tf.label}</span>
                  <span className="text-[8px] text-gray-600 ml-1">{tf.short}</span>
                </div>
                <TradingViewWidget tvSymbol={tvSymbol} interval={tf.tv} compact={true} />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* BOTTOM STATUS BAR */}
      <div className="flex items-center justify-between px-3 py-1 border-t border-forexia-border/60 bg-forexia-bg shrink-0 text-[9px] font-mono">
        <div className="flex items-center gap-2.5 text-gray-500">
          <span className={"flex items-center gap-1 " + (brokerConnected ? "text-forexia-green" : "text-forexia-red")}>
            <span className={"w-1.5 h-1.5 rounded-full inline-block " + (brokerConnected ? "bg-forexia-green" : "bg-forexia-red")} />
            {brokerConnected ? "LIVE" : "OFFLINE"}
          </span>
          <span className="text-forexia-border">{"\u2502"}</span>
          <span>{currentSymbol?.flag} {symbol}</span>
          <span className="text-forexia-border">{"\u2502"}</span>
          <span className="text-forexia-accent">{isMulti ? "All 8 Timeframes" : (currentTf?.short || timeframe)}</span>
          <span className="text-forexia-border">{"\u2502"}</span>
          <span className="text-forexia-green">TradingView Data</span>
          {currentSymbol?.tier === "star" && (
            <>
              <span className="text-forexia-border">{"\u2502"}</span>
              <span className="text-forexia-gold">{"\u2605"} Star Pair</span>
            </>
          )}
          {entryPositions.length > 0 && (
            <>
              <span className="text-forexia-border">{"\u2502"}</span>
              <span className="text-gray-400">{entryPositions.length} position{entryPositions.length !== 1 ? "s" : ""}</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-2 text-gray-600">
          <span>{isMulti ? "W1 \u00b7 D1 \u00b7 H4 \u00b7 H1 \u00b7 M30 \u00b7 M15 \u00b7 M5 \u00b7 M1" : "TradingView \u00b7 Scroll to zoom \u00b7 Drag to pan"}</span>
        </div>
      </div>
    </div>
  );
}
