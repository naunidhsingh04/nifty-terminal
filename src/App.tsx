import { useState, useEffect } from "react";
import { Activity, Wifi, WifiOff, BarChart2 } from "lucide-react";
import { useMarketData } from "./hooks/useMarketData";
import Watchlist from "./components/dashboard/Watchlist";
import StockChart from "./components/dashboard/StockChart";
import AlertPanel, { AlertBadge } from "./components/shared/AlertPanel";

function useMarketStatus() {
  const [status, setStatus] = useState<{ isOpen: boolean; label: string }>({
    isOpen: false,
    label: "Checking...",
  });
  useEffect(() => {
    const check = async () => {
      try {
        const base = window.location.host.includes("localhost")
          ? ""
          : window.location.origin;
        const res = await fetch(`${base}/api/market-status`);
        const data = await res.json();
        const now = new Date();
        const day = now.toLocaleString("en-US", {
          timeZone: "Asia/Kolkata",
          weekday: "short",
        });
        setStatus({
          isOpen: data.isOpen,
          label: data.isOpen
            ? "NSE OPEN · 9:15 AM – 3:30 PM IST"
            : `NSE CLOSED · ${day}`,
        });
      } catch {
        setStatus({ isOpen: false, label: "Market status unknown" });
      }
    };
    check();
    const t = setInterval(check, 30000);
    return () => clearInterval(t);
  }, []);
  return status;
}

function useIST() {
  const [time, setTime] = useState("");
  useEffect(() => {
    const tick = () => {
      setTime(
        new Date().toLocaleTimeString("en-IN", {
          timeZone: "Asia/Kolkata",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }),
      );
    };
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);
  return time;
}

export default function App() {
  const {
    stocks,
    rsiMap,
    alerts,
    connected,
    dismissAlert,
    clearAlerts,
    liveCandles,
    priceTicks,
    sessionExpired,
    loginUrl,
  } = useMarketData();
  const [selected, setSelected] = useState("RELIANCE");
  const [showAlerts, setShowAlerts] = useState(false);
  const marketStatus = useMarketStatus();
  const time = useIST();

  const selectedStock = stocks[selected];
  const today = new Date().toLocaleDateString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
  });

  return (
    <div className="h-screen w-screen flex flex-col bg-[#0d1117] overflow-hidden font-mono">
      {/* Session Expired Banner */}
      {sessionExpired && (
        <div className="flex items-center justify-between px-4 py-2 bg-[#3d1a1a] border-b border-[#ef5350] text-sm font-mono shrink-0 z-30">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#ef5350] animate-pulse" />
            <span className="text-[#ef5350] font-bold text-[11px]">
              SESSION EXPIRED
            </span>
            <span className="text-[#8b9ab0] text-[10px]">
              — Live prices paused. Login to resume.
            </span>
          </div>
          <a
            href={loginUrl}
            target="_blank"
            rel="noreferrer"
            className="px-3 py-1 bg-[#ef5350] text-white rounded text-[10px] font-bold hover:bg-[#d32f2f] transition-colors"
          >
            🔐 Login Now
          </a>
        </div>
      )}

      {/* Top bar */}
      <header className="flex items-center justify-between px-4 py-2 bg-[#010409] border-b border-[#1e2d3d] shrink-0 z-20">
        <div className="flex items-center gap-3">
          <BarChart2 size={16} className="text-[#58a6ff]" />
          <span className="text-[#c9d1d9] text-[13px] font-bold tracking-widest uppercase">
            Nifty Terminal
          </span>
          <span className="hidden sm:block text-[#546e7a] text-[10px]">
            NSE · Nifty 500
          </span>
        </div>

        {selectedStock && (
          <div className="flex items-center gap-4">
            <div className="hidden md:flex flex-col items-end">
              <div className="flex items-center gap-2">
                <span className="text-[#c9d1d9] text-[12px] font-bold">
                  {selected}
                </span>
                <span className="text-[#546e7a] text-[10px]">
                  {selectedStock.name}
                </span>
              </div>
              <div className="flex items-center gap-3 text-[10px]">
                <span className="text-[#546e7a]">
                  O:{selectedStock.open?.toFixed(2)}
                </span>
                <span className="text-[#26a69a]">
                  H:{selectedStock.high?.toFixed(2)}
                </span>
                <span className="text-[#ef5350]">
                  L:{selectedStock.low?.toFixed(2)}
                </span>
                <span className="text-[#546e7a]">
                  Vol:{(selectedStock.volume ?? 0).toLocaleString("en-IN")}
                </span>
              </div>
            </div>
            <div className="text-right">
              <div
                className={`text-[18px] font-bold tabular-nums ${(selectedStock.change_percent ?? 0) >= 0 ? "text-[#26a69a]" : "text-[#ef5350]"}`}
              >
                ₹
                {selectedStock.ltp?.toLocaleString("en-IN", {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </div>
              <div
                className={`text-[10px] ${(selectedStock.change_percent ?? 0) >= 0 ? "text-[#26a69a]" : "text-[#ef5350]"}`}
              >
                {(selectedStock.change_percent ?? 0) >= 0 ? "▲" : "▼"}
                {Math.abs(selectedStock.change ?? 0).toFixed(2)} (
                {Math.abs(selectedStock.change_percent ?? 0).toFixed(2)}%)
              </div>
            </div>
          </div>
        )}

        <div className="flex items-center gap-4">
          <div className="hidden sm:flex flex-col items-end">
            <span className="text-[#c9d1d9] text-[11px] tabular-nums">
              {time} IST
            </span>
            <div className="flex items-center gap-1.5">
              <div
                className={`w-1.5 h-1.5 rounded-full ${marketStatus.isOpen ? "bg-[#26a69a] animate-pulse" : "bg-[#546e7a]"}`}
              />
              <span className="text-[9px] text-[#546e7a]">
                {marketStatus.label}
              </span>
            </div>
          </div>

          <button
            onClick={() => setShowAlerts((v) => !v)}
            className={`relative p-1.5 rounded transition-colors ${showAlerts ? "bg-[#1e2d3d]" : "hover:bg-[#161b22]"}`}
          >
            <AlertBadge alerts={alerts} />
          </button>

          <div className="flex items-center gap-1.5">
            {connected ? (
              <Wifi size={12} className="text-[#26a69a]" />
            ) : (
              <WifiOff size={12} className="text-[#ef5350]" />
            )}
            <Activity
              size={12}
              className={connected ? "text-[#26a69a]" : "text-[#ef5350]"}
            />
            <span className="text-[9px] text-[#546e7a]">
              {connected ? "LIVE" : "RECONNECTING"}
            </span>
          </div>
        </div>
      </header>

      {/* Main layout */}
      <div className="flex flex-1 min-h-0">
        <div className="w-52 shrink-0 min-h-0 overflow-hidden">
          <Watchlist
            stocks={stocks}
            selected={selected}
            onSelect={setSelected}
            rsiMap={rsiMap}
          />
        </div>

        <div
          className={`flex-1 min-w-0 min-h-0 flex flex-col transition-all ${showAlerts ? "mr-80" : ""}`}
        >
          <div className="flex items-center gap-3 px-3 py-1 bg-[#010409] border-b border-[#1e2d3d] text-[10px] text-[#546e7a] shrink-0">
            <span>{today}</span>
            <span>·</span>
            <span className="text-[#c9d1d9] font-bold">{selected}</span>
            {!marketStatus.isOpen && (
              <>
                <span>·</span>
                <span className="text-[#f7931a]">
                  Showing last known price (market closed)
                </span>
              </>
            )}
          </div>
          <div className="flex-1 min-h-0">
            {selectedStock ? (
              <StockChart
                key={selected}
                symbol={selected}
                name={selectedStock.name}
                ltp={priceTicks[selected] ?? selectedStock.ltp}
                change_percent={selectedStock.change_percent}
                liveCandles={liveCandles[selected] || {}}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-[#546e7a] text-sm">
                Select a stock from the watchlist
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Alert panel */}
      {showAlerts && (
        <AlertPanel
          alerts={alerts}
          onDismiss={dismissAlert}
          onClear={clearAlerts}
        />
      )}

      {/* Toast popups */}
      {!showAlerts &&
        alerts.slice(0, 3).map((alert, i) => (
          <div
            key={`toast-${i}`}
            className={`fixed bottom-${4 + i * 20} right-4 z-50 flex items-start gap-2 px-3 py-2 rounded-lg border shadow-xl max-w-xs ${
              alert.alertType === "BUY"
                ? "bg-[#0d2018] border-[#26a69a]/50"
                : alert.alertType === "WATCH"
                  ? "bg-[#1a1200] border-[#f7931a]/50"
                  : "bg-[#1a0808] border-[#ef5350]/50"
            }`}
          >
            <span
              className={`text-[10px] font-mono font-bold ${
                alert.alertType === "BUY"
                  ? "text-[#26a69a]"
                  : alert.alertType === "WATCH"
                    ? "text-[#f7931a]"
                    : "text-[#ef5350]"
              }`}
            >
              {alert.alertType}
            </span>
            <span className="text-[#c9d1d9] text-[10px] font-mono font-bold">
              {alert.symbol}
            </span>
            <span className="text-[#8b949e] text-[9px] font-mono flex-1">
              {alert.message}
            </span>
            <button
              onClick={() => dismissAlert(i)}
              className="text-[#546e7a] hover:text-[#c9d1d9]"
            >
              ×
            </button>
          </div>
        ))}
    </div>
  );
}
