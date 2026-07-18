import { useEffect, useRef, useCallback, useState } from "react";
import {
  createChart,
  ColorType,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
} from "lightweight-charts";
import type { IChartApi, ISeriesApi, Time } from "lightweight-charts";
import { computeRSI } from "../../utils/indicators";
import type { LiveCandle } from "../../hooks/useMarketData";

interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface StockChartProps {
  symbol: string;
  name: string;
  ltp: number;
  change_percent: number;
  liveCandles: Record<string, LiveCandle>;
}

const INTERVALS = [
  { label: "1m", value: "1minute" },
  { label: "2m", value: "2minute" },
  { label: "3m", value: "3minute" },
  { label: "4m", value: "4minute" },
  { label: "5m", value: "5minute" },
  { label: "10m", value: "10minute" },
  { label: "15m", value: "15minute" },
  { label: "30m", value: "30minute" },
  { label: "1H", value: "1hour" },
  { label: "2H", value: "2hour" },
  { label: "4H", value: "4hour" },
  { label: "1D", value: "1day" },
  { label: "1W", value: "1week" },
  { label: "1M", value: "1month" },
  { label: "1Y", value: "1year" },
  { label: "5Y", value: "5year" },
];

const C = {
  bg: "#0d1117",
  bgPane: "#0a0e14",
  grid: "#1a2030",
  border: "#1e2d3d",
  text: "#8b9ab0",
  up: "#26a69a",
  down: "#ef5350",
  upAlpha: "rgba(38,166,154,0.15)",
  downAlpha: "rgba(239,83,80,0.12)",
  rsi: "#f7931a",
  cross: "#334155",
};

const getApiBase = () => {
  const host = window.location.host;
  if (host.includes("localhost") || host.includes("127.0.0.1")) {
    return "http://localhost:8000";
  }
  return window.location.origin;
};

function toTime(val: unknown): number {
  if (typeof val === "number" && !isNaN(val) && val > 0) return val;
  if (typeof val === "string") {
    const n = parseInt(val, 10);
    if (!isNaN(n) && n > 0) return n;
  }
  if (val instanceof Date) return Math.floor(val.getTime() / 1000);
  return 0;
}

export default function StockChart({
  symbol,
  ltp,
  change_percent,
  liveCandles,
}: StockChartProps) {
  const mainRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const rsiChartRef = useRef<IChartApi | null>(null);
  const candleSeries = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volSeries = useRef<ISeriesApi<"Histogram"> | null>(null);
  const rsiSeries = useRef<ISeriesApi<"Line"> | null>(null);
  const priceLineRef = useRef<ReturnType<
    ISeriesApi<"Candlestick">["createPriceLine"]
  > | null>(null);

  const [interval, setInterval] = useState("1day");
  const [histCandles, setHistCandles] = useState<Candle[]>([]);
  const [loading, setLoading] = useState(false);
  const [ohlc, setOhlc] = useState<Candle | null>(null);
  const [currentRSI, setCurrentRSI] = useState<number | null>(null);

  const is4H = interval === "4hour";
  const ltpRef = useRef<number>(ltp);
  const lastRealPrice = useRef<number>(ltp);

  // ── Fetch history ───────────────────────────────────────────────────────────
  const fetchHistory = useCallback(async (sym: string, intv: string) => {
    setLoading(true);
    try {
      const base = getApiBase();
      const res = await fetch(
        `${base}/api/history?symbol=${sym}&interval=${intv}`,
      );
      const data = await res.json();
      const cleaned: Candle[] = (Array.isArray(data) ? data : [])
        .map((c: Candle) => ({ ...c, time: toTime(c.time) }))
        .filter((c) => c.time > 0 && c.open > 0 && c.close > 0)
        .sort((a, b) => a.time - b.time);
      setHistCandles(cleaned);
    } catch {
      setHistCandles([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setHistCandles([]);
    setOhlc(null);
    fetchHistory(symbol, interval);
  }, [symbol, interval, fetchHistory]);

  // ── Create charts (once) ────────────────────────────────────────────────────
  useEffect(() => {
    if (!mainRef.current || !rsiRef.current) return;

    chartRef.current = createChart(mainRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: C.bg },
        textColor: C.text,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11,
      },
      grid: { vertLines: { color: C.grid }, horzLines: { color: C.grid } },
      crosshair: {
        vertLine: { color: C.cross, labelBackgroundColor: "#1e2d3d" },
        horzLine: { color: C.cross, labelBackgroundColor: "#1e2d3d" },
      },
      rightPriceScale: {
        borderColor: C.border,
        scaleMargins: { top: 0.06, bottom: 0.28 },
      },
      timeScale: {
        borderColor: C.border,
        timeVisible: true,
        secondsVisible: false,
      },
    });

    candleSeries.current = chartRef.current.addSeries(CandlestickSeries, {
      upColor: C.up,
      downColor: C.down,
      borderUpColor: C.up,
      borderDownColor: C.down,
      wickUpColor: C.up,
      wickDownColor: C.down,
    });

    volSeries.current = chartRef.current.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    chartRef.current
      .priceScale("vol")
      .applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

    priceLineRef.current = candleSeries.current.createPriceLine({
      price: 0,
      color: "#f7931a",
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
      title: "LTP",
    });

    chartRef.current.subscribeCrosshairMove((param) => {
      if (!param.time || !candleSeries.current) return;
      const d = param.seriesData.get(candleSeries.current) as unknown as
        | Candle
        | undefined;
      if (d) setOhlc(d);
    });

    rsiChartRef.current = createChart(rsiRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: C.bgPane },
        textColor: C.text,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: C.grid },
        horzLines: { color: "transparent" },
      },
      crosshair: {
        vertLine: { color: C.cross, labelBackgroundColor: "#1e2d3d" },
        horzLine: { color: C.cross, labelBackgroundColor: "#1e2d3d" },
      },
      rightPriceScale: {
        borderColor: C.border,
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: C.border,
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: false,
      handleScale: false,
    });

    rsiSeries.current = rsiChartRef.current.addSeries(LineSeries, {
      color: C.rsi,
      lineWidth: 1,
      priceFormat: { type: "custom", formatter: (p: number) => p.toFixed(1) },
      lastValueVisible: true,
      priceLineVisible: false,
    });

    chartRef.current.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (range) rsiChartRef.current?.timeScale().setVisibleLogicalRange(range);
    });
    rsiChartRef.current
      .timeScale()
      .subscribeVisibleLogicalRangeChange((range) => {
        if (range) chartRef.current?.timeScale().setVisibleLogicalRange(range);
      });

    const ro1 = new ResizeObserver((e) => {
      chartRef.current?.applyOptions({ width: e[0].contentRect.width });
    });
    const ro2 = new ResizeObserver((e) => {
      rsiChartRef.current?.applyOptions({ width: e[0].contentRect.width });
    });
    ro1.observe(mainRef.current);
    ro2.observe(rsiRef.current);

    return () => {
      ro1.disconnect();
      ro2.disconnect();
      chartRef.current?.remove();
      rsiChartRef.current?.remove();
      chartRef.current = null;
      rsiChartRef.current = null;
      candleSeries.current = null;
      volSeries.current = null;
      rsiSeries.current = null;
      priceLineRef.current = null;
    };
  }, []);

  // ── Load historical candles into chart ──────────────────────────────────────
  useEffect(() => {
    if (!candleSeries.current || !volSeries.current || !rsiSeries.current)
      return;

    // Clear chart when candles reset
    if (histCandles.length === 0) {
      try {
        candleSeries.current.setData([]);
        volSeries.current.setData([]);
        rsiSeries.current.setData([]);
      } catch (_) {}
      return;
    }

    try {
      console.log(
        "Setting chart data:",
        histCandles.length,
        "candles for",
        symbol,
      );
      candleSeries.current.setData(
        histCandles.map((c) => ({
          time: c.time as Time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        })),
      );
      volSeries.current.setData(
        histCandles.map((c) => ({
          time: c.time as Time,
          value: c.volume,
          color: c.close >= c.open ? C.upAlpha : C.downAlpha,
        })),
      );
      const closes = histCandles.map((c) => c.close);
      const rsiValues = computeRSI(closes, 14);
      rsiSeries.current.setData(
        histCandles
          .map((c, i) => ({ time: c.time as Time, value: rsiValues[i] ?? 0 }))
          .filter((d) => d.value > 0),
      );
      chartRef.current?.timeScale().fitContent();
      rsiChartRef.current?.timeScale().fitContent();
      const last = rsiValues[rsiValues.length - 1];
      if (last) setCurrentRSI(last);
    } catch (_) {}
  }, [histCandles]);

  // ── Live candle update ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!candleSeries.current || !volSeries.current || !rsiSeries.current)
      return;
    if (histCandles.length === 0) return;
    const liveCandle = liveCandles?.[interval];
    if (!liveCandle) return;
    const t = toTime(liveCandle.time);
    if (t <= 0) return;
    try {
      candleSeries.current.update({
        time: t as Time,
        open: liveCandle.open,
        high: liveCandle.high,
        low: liveCandle.low,
        close: liveCandle.close,
      });
      volSeries.current.update({
        time: t as Time,
        value: liveCandle.volume,
        color: liveCandle.close >= liveCandle.open ? C.upAlpha : C.downAlpha,
      });
      const closes = [
        ...histCandles.map((c) => c.close).slice(-50),
        liveCandle.close,
      ];
      const rsiValues = computeRSI(closes, 14);
      const liveRSI = rsiValues[rsiValues.length - 1];
      if (liveRSI && liveRSI > 0) {
        rsiSeries.current.update({ time: t as Time, value: liveRSI });
        setCurrentRSI(liveRSI);
      }
    } catch (_) {}
  }, [liveCandles, interval, histCandles]);

  // ── Price line update ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!ltp || ltp <= 0) return;
    lastRealPrice.current = ltp;
  }, [ltp]);

  useEffect(() => {
    if (histCandles.length === 0) return;

    const intervalId = setInterval(() => {
      const realPrice = lastRealPrice.current;
      if (!realPrice || realPrice <= 0) return;

      const current = ltpRef.current;
      const diff = realPrice - current;
      const newPrice = Math.abs(diff) < 0.01 ? realPrice : current + diff * 0.4;
      ltpRef.current = newPrice;

      try {
        priceLineRef.current?.applyOptions({ price: newPrice });
      } catch (_) {}

      if (candleSeries.current && histCandles.length > 0) {
        const last = histCandles[histCandles.length - 1];
        const t = toTime(last.time);
        if (t > 0) {
          try {
            candleSeries.current.update({
              time: t as Time,
              open: last.open,
              high: Math.max(last.high, newPrice),
              low: Math.min(last.low, newPrice),
              close: newPrice,
            });
          } catch (_) {}
        }
      }
    }, 500);

    ltpRef.current = ltp;
    return () => clearInterval(intervalId);
  }, [histCandles]);

  const rsiColor = currentRSI
    ? currentRSI >= 70
      ? "#ef5350"
      : currentRSI <= 30
        ? "#26a69a"
        : "#f7931a"
    : "#f7931a";

  return (
    <div className="flex flex-col h-full bg-[#0d1117]">
      {/* Interval tabs */}
      <div className="flex items-center gap-1 px-3 py-2 border-b border-[#1e2d3d] flex-wrap shrink-0">
        {INTERVALS.map((iv) => (
          <button
            key={iv.value}
            onClick={() => setInterval(iv.value)}
            className={`px-2.5 py-0.5 text-[11px] font-mono rounded transition-all ${
              interval === iv.value
                ? "bg-[#1e3a5f] text-[#58a6ff] border border-[#2d5a9f]"
                : "text-[#8b9ab0] hover:text-[#c9d1d9] hover:bg-[#161b22]"
            }`}
          >
            {iv.label}
          </button>
        ))}
        {currentRSI !== null && (
          <div className="ml-auto flex items-center gap-2 text-[11px] font-mono">
            <span className="text-[#546e7a]">RSI(14)</span>
            <span style={{ color: rsiColor }} className="font-bold">
              {currentRSI.toFixed(2)}
              {currentRSI >= 70 && (
                <span className="ml-1 text-[#ef5350]">⚠ OB</span>
              )}
              {currentRSI <= 30 && (
                <span className="ml-1 text-[#26a69a]">⚡ OS</span>
              )}
            </span>
            {is4H && (
              <span className="text-[#26a69a] text-[9px] border border-[#26a69a]/30 px-1.5 py-0.5 rounded">
                4H REVERSAL MONITOR ON
              </span>
            )}
          </div>
        )}
      </div>

      {/* OHLC bar */}
      <div className="flex items-center gap-4 px-3 py-1 border-b border-[#1a2030] shrink-0 text-[10px] font-mono min-h-[24px]">
        {ohlc ? (
          <>
            <span className="text-[#546e7a]">
              O <span className="text-[#c9d1d9]">{ohlc.open?.toFixed(2)}</span>
            </span>
            <span className="text-[#546e7a]">
              H <span className="text-[#26a69a]">{ohlc.high?.toFixed(2)}</span>
            </span>
            <span className="text-[#546e7a]">
              L <span className="text-[#ef5350]">{ohlc.low?.toFixed(2)}</span>
            </span>
            <span className="text-[#546e7a]">
              C{" "}
              <span
                className={
                  change_percent >= 0 ? "text-[#26a69a]" : "text-[#ef5350]"
                }
              >
                {ohlc.close?.toFixed(2)}
              </span>
            </span>
          </>
        ) : (
          <span className="text-[#546e7a]">Hover over chart to see OHLC</span>
        )}
      </div>

      {/* Main chart */}
      <div className="relative flex-1 min-h-0">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0d1117]/80 z-10">
            <div className="flex items-center gap-2 text-[#58a6ff] text-sm font-mono">
              <div className="w-4 h-4 border-2 border-[#58a6ff] border-t-transparent rounded-full animate-spin" />
              Loading {interval} chart...
            </div>
          </div>
        )}
        <div ref={mainRef} className="w-full h-full" />
      </div>

      {/* RSI panel */}
      <div
        className="relative border-t border-[#1e2d3d] shrink-0"
        style={{ height: "130px" }}
      >
        <div className="absolute top-1 left-3 z-10 flex items-center gap-3 text-[10px] font-mono pointer-events-none">
          <span className="text-[#546e7a]">RSI(14)</span>
          <span className="text-[#ef5350]">— 70</span>
          <span className="text-[#26a69a]">— 30</span>
          {is4H && (
            <span className="text-[#26a69a]">
              Alert: RSI crosses above 30 after 4+ oversold candles
            </span>
          )}
        </div>
        <div ref={rsiRef} className="w-full h-full" />
      </div>
    </div>
  );
}
