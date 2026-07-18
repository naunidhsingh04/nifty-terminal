import { useState } from "react";
import { Bell, X, TrendingUp, Eye, TrendingDown, Clock } from "lucide-react";
import type { Alert } from "../../hooks/useMarketData";

interface AlertPanelProps {
  alerts: Alert[];
  onDismiss: (index: number) => void;
  onClear: () => void;
}

const ALERT_CONFIG = {
  BUY: {
    label: "BUY",
    color: "text-[#26a69a]",
    border: "border-[#26a69a]/40",
    bg: "bg-[#26a69a]/10",
    icon: TrendingUp,
  },
  WATCH: {
    label: "WATCH",
    color: "text-[#f7931a]",
    border: "border-[#f7931a]/40",
    bg: "bg-[#f7931a]/10",
    icon: Eye,
  },
  SELL: {
    label: "SELL",
    color: "text-[#ef5350]",
    border: "border-[#ef5350]/40",
    bg: "bg-[#ef5350]/10",
    icon: TrendingDown,
  },
};

type FilterType = "ALL" | "BUY" | "WATCH" | "SELL";

export default function AlertPanel({
  alerts,
  onDismiss,
  onClear,
}: AlertPanelProps) {
  const [filter, setFilter] = useState<FilterType>("ALL");

  const filtered =
    filter === "ALL" ? alerts : alerts.filter((a) => a.alertType === filter);
  const counts = {
    ALL: alerts.length,
    BUY: alerts.filter((a) => a.alertType === "BUY").length,
    WATCH: alerts.filter((a) => a.alertType === "WATCH").length,
    SELL: alerts.filter((a) => a.alertType === "SELL").length,
  };

  return (
    <div className="fixed top-12 right-0 z-50 w-80 h-[calc(100vh-48px)] bg-[#010409] border-l border-[#1e2d3d] flex flex-col shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[#1e2d3d] shrink-0">
        <div className="flex items-center gap-2">
          <Bell size={13} className="text-[#f7931a]" />
          <span className="text-[#c9d1d9] text-[11px] font-bold font-mono tracking-wider">
            ALERTS
          </span>
          <span className="text-[#546e7a] text-[10px] font-mono">
            ({alerts.length})
          </span>
        </div>
        {alerts.length > 0 && (
          <button
            onClick={onClear}
            className="text-[#546e7a] hover:text-[#ef5350] text-[9px] font-mono transition-colors"
          >
            CLEAR ALL
          </button>
        )}
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-[#1e2d3d] shrink-0">
        {(["ALL", "BUY", "WATCH", "SELL"] as FilterType[]).map((f) => {
          const cfg = f !== "ALL" ? ALERT_CONFIG[f] : null;
          const active = filter === f;
          return (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-mono font-bold transition-all ${
                active
                  ? cfg
                    ? `${cfg.bg} ${cfg.color} border ${cfg.border}`
                    : "bg-[#1e2d3d] text-[#c9d1d9] border border-[#30363d]"
                  : "text-[#546e7a] hover:text-[#c9d1d9]"
              }`}
            >
              {f}
              {counts[f] > 0 && (
                <span className={active && cfg ? cfg.color : "text-[#546e7a]"}>
                  {counts[f]}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Alert list */}
      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-[#546e7a]">
            <Bell size={24} className="opacity-30" />
            <span className="text-[10px] font-mono">
              No {filter !== "ALL" ? filter.toLowerCase() : ""} alerts
            </span>
          </div>
        ) : (
          <div className="flex flex-col divide-y divide-[#1e2d3d]">
            {filtered.map((alert, i) => {
              const cfg = ALERT_CONFIG[alert.alertType];
              const Icon = cfg.icon;
              const realIdx = alerts.indexOf(alert);
              return (
                <div
                  key={`${alert.symbol}-${alert.timestamp}-${i}`}
                  className="px-3 py-2.5 hover:bg-[#0d1117] transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-start gap-2 flex-1 min-w-0">
                      <div
                        className={`flex items-center gap-1 px-1.5 py-0.5 rounded ${cfg.bg} border ${cfg.border} shrink-0 mt-0.5`}
                      >
                        <Icon size={9} className={cfg.color} />
                        <span
                          className={`text-[8px] font-mono font-bold ${cfg.color}`}
                        >
                          {cfg.label}
                        </span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 mb-0.5">
                          <span className="text-[#c9d1d9] font-mono text-[11px] font-bold">
                            {alert.symbol}
                          </span>
                          <span className="text-[#546e7a] text-[9px] font-mono truncate">
                            {alert.name}
                          </span>
                        </div>
                        <p className="text-[#8b949e] text-[9px] font-mono leading-relaxed">
                          {alert.message}
                        </p>
                        <div className="flex items-center gap-1 mt-1">
                          <Clock size={8} className="text-[#546e7a]" />
                          <span className="text-[#546e7a] text-[8px] font-mono">
                            {alert.timestamp}
                          </span>
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => onDismiss(realIdx)}
                      className="text-[#546e7a] hover:text-[#c9d1d9] shrink-0 transition-colors mt-0.5"
                    >
                      <X size={10} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export function AlertBadge({ alerts }: { alerts: Alert[] }) {
  const buyCount = alerts.filter((a) => a.alertType === "BUY").length;
  const watchCount = alerts.filter((a) => a.alertType === "WATCH").length;
  const sellCount = alerts.filter((a) => a.alertType === "SELL").length;

  if (alerts.length === 0) return <Bell size={14} className="text-[#546e7a]" />;

  return (
    <div className="relative">
      <Bell size={14} className="text-[#f7931a]" />
      <div className="absolute -top-1.5 -right-1.5 flex gap-0.5">
        {buyCount > 0 && (
          <div className="w-2.5 h-2.5 bg-[#26a69a] rounded-full flex items-center justify-center">
            <span className="text-[6px] font-bold text-black">
              {Math.min(buyCount, 9)}
            </span>
          </div>
        )}
        {watchCount > 0 && (
          <div className="w-2.5 h-2.5 bg-[#f7931a] rounded-full flex items-center justify-center">
            <span className="text-[6px] font-bold text-black">
              {Math.min(watchCount, 9)}
            </span>
          </div>
        )}
        {sellCount > 0 && (
          <div className="w-2.5 h-2.5 bg-[#ef5350] rounded-full flex items-center justify-center">
            <span className="text-[6px] font-bold text-black">
              {Math.min(sellCount, 9)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
