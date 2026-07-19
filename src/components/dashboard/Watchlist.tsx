import { useState } from "react";
import { Search, TrendingUp, TrendingDown } from "lucide-react";
import type { StockTick } from "../../hooks/useMarketData";

interface WatchlistProps {
  stocks: Record<string, StockTick>;
  selected: string;
  onSelect: (symbol: string) => void;
  rsiMap: Record<string, number>;
}

export default function Watchlist({
  stocks,
  selected,
  onSelect,
  rsiMap,
}: WatchlistProps) {
  const [query, setQuery] = useState("");
  const [sortBy, setSortBy] = useState<"name" | "change" | "rsi">("name");

  const list = Object.values(stocks);
  const filtered = query
    ? list.filter(
        (s) =>
          s.symbol.toLowerCase().includes(query.toLowerCase()) ||
          s.name?.toLowerCase().includes(query.toLowerCase()),
      )
    : list;

  const stockList = [...filtered].sort((a, b) => {
    if (sortBy === "change") return b.change_percent - a.change_percent;
    if (sortBy === "rsi")
      return (rsiMap[b.symbol] ?? 50) - (rsiMap[a.symbol] ?? 50);
    return a.symbol.localeCompare(b.symbol);
  });

  const gainers = list.filter((s) => s.change_percent > 0).length;
  const losers = list.filter((s) => s.change_percent < 0).length;

  return (
    <div className="flex flex-col h-full bg-[#0d1117] border-r border-[#1e2d3d]">
      <div className="px-3 py-3 border-b border-[#1e2d3d]">
        <div className="flex items-center justify-between mb-2">
          <span className="font-mono text-[13px] font-bold text-[#c9d1d9] tracking-wider">
            NIFTY 509
          </span>
          <div className="flex gap-2 text-[10px] font-mono">
            <span className="text-[#26a69a]">▲{gainers}</span>
            <span className="text-[#ef5350]">▼{losers}</span>
          </div>
        </div>
        <div className="relative">
          <Search
            size={11}
            className="absolute left-2 top-1/2 -translate-y-1/2 text-[#546e7a]"
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search..."
            className="w-full pl-6 pr-2 py-1 bg-[#161b22] border border-[#1e2d3d] rounded text-[11px] font-mono text-[#c9d1d9] placeholder-[#546e7a] outline-none focus:border-[#1e3a5f]"
          />
        </div>
        <div className="flex gap-1 mt-2">
          {(["name", "change", "rsi"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSortBy(s)}
              className={`flex-1 py-0.5 text-[9px] font-mono uppercase rounded transition-all ${
                sortBy === s
                  ? "bg-[#1e3a5f] text-[#58a6ff]"
                  : "text-[#546e7a] hover:text-[#8b9ab0]"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {stockList.map((stock) => {
          const isUp = stock.change_percent >= 0;
          const isSelected = stock.symbol === selected;
          const rsi = rsiMap[stock.symbol];
          const rsiColor = rsi
            ? rsi >= 70
              ? "#ef5350"
              : rsi <= 30
                ? "#26a69a"
                : "#546e7a"
            : "#546e7a";

          return (
            <div
              key={stock.symbol}
              onClick={() => onSelect(stock.symbol)}
              className={`px-3 py-2 cursor-pointer border-b border-[#1a2030] hover:bg-[#161b22] ${
                isSelected
                  ? "bg-[#0f1e2e] border-l-2 border-l-[#58a6ff]"
                  : "border-l-2 border-l-transparent"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <span
                    className={`text-[11px] font-mono font-bold ${isSelected ? "text-[#58a6ff]" : "text-[#c9d1d9]"}`}
                  >
                    {stock.symbol}
                  </span>
                  <div className="text-[9px] font-mono text-[#546e7a] truncate mt-0.5">
                    {stock.name}
                  </div>
                </div>
                <div className="text-right ml-2 shrink-0">
                  <div
                    className={`text-[12px] font-mono font-bold tabular-nums ${isUp ? "text-[#26a69a]" : "text-[#ef5350]"}`}
                  >
                    ₹
                    {stock.ltp?.toLocaleString("en-IN", {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </div>
                  <div
                    className={`text-[9px] font-mono flex items-center justify-end gap-0.5 ${isUp ? "text-[#26a69a]" : "text-[#ef5350]"}`}
                  >
                    {isUp ? <TrendingUp size={8} /> : <TrendingDown size={8} />}
                    {isUp ? "+" : ""}
                    {stock.change_percent?.toFixed(2)}%
                  </div>
                </div>
              </div>
              {rsi !== undefined && (
                <div className="flex items-center gap-1 mt-1">
                  <div className="flex-1 h-0.5 bg-[#1a2030] rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.min(rsi, 100)}%`,
                        backgroundColor: rsiColor,
                      }}
                    />
                  </div>
                  <span
                    className="text-[8px] font-mono"
                    style={{ color: rsiColor }}
                  >
                    {rsi.toFixed(0)}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
