import { useEffect, useRef, useState, useCallback } from "react";

export interface StockTick {
  symbol: string;
  name: string;
  ltp: number;
  open: number;
  high: number;
  low: number;
  change: number;
  change_percent: number;
  volume: number;
  marketOpen: boolean;
}

export interface LiveCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export type AlertType = "BUY" | "WATCH" | "SELL";

export interface Alert {
  alertType: AlertType;
  symbol: string;
  name: string;
  message: string;
  timestamp: string;
  rsi?: number;
  consecutiveCount?: number;
  volumeRatio?: number;
}

export type RSIAlert = Alert;

type WSMessage =
  | (StockTick & { type: "TICK" })
  | {
      type: "PRICE_TICK";
      symbol: string;
      price: number;
      change?: number;
      change_percent?: number;
    }
  | {
      type: "CANDLE_UPDATE";
      symbol: string;
      candles: Record<string, LiveCandle>;
    }
  | { type: "RSI_UPDATE"; symbol: string; rsi: number }
  | {
      type: "RSI_ALERT";
      symbol: string;
      name: string;
      rsi: number;
      message: string;
      consecutiveCount: number;
      timestamp: string;
    }
  | {
      type: "VOLUME_ALERT";
      symbol: string;
      name: string;
      message: string;
      volumeRatio: number;
      timestamp: string;
    }
  | {
      type: "SESSION_EXPIRED";
      message: string;
      loginUrl: string;
    }
  | { type: "SESSION_RESTORED" };

// ── Backend URL ────────────────────────────────────────────────────────────
// In production: set VITE_BACKEND_URL to your Railway URL
// In development: auto-detects localhost
const getBackendUrl = (): string => {
  // If env variable set (Vercel production build) use it
  if (import.meta.env.VITE_BACKEND_URL) {
    return import.meta.env.VITE_BACKEND_URL as string;
  }
  // Local dev — use localhost
  const host = window.location.host;
  if (host.includes("localhost") || host.includes("127.0.0.1")) {
    return "http://localhost:8000";
  }
  // Cloudflare tunnel / same-origin deployment
  return window.location.origin;
};

const getWsUrl = (): string => {
  const backend = getBackendUrl();
  return backend.replace(/^http/, "ws") + "/ws";
};

export const getApiBase = (): string => getBackendUrl();

export const useMarketData = () => {
  const wsUrl = getWsUrl();
  const [stocks, setStocks] = useState<Record<string, StockTick>>({});
  const [priceTicks, setPriceTicks] = useState<Record<string, number>>({});
  const [rsiMap, setRsiMap] = useState<Record<string, number>>({});
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [connected, setConnected] = useState(false);
  const [liveCandles, setLiveCandles] = useState<
    Record<string, Record<string, LiveCandle>>
  >({});
  const [sessionExpired, setSessionExpired] = useState(false);
  const [loginUrl, setLoginUrl] = useState("/login");

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connect, 3000);
    };
    ws.onerror = () => ws.close();

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);

        if (msg.type === "TICK") {
          setStocks((prev) => ({ ...prev, [msg.symbol]: msg }));
        } else if (msg.type === "PRICE_TICK") {
          setPriceTicks((prev) => ({ ...prev, [msg.symbol]: msg.price }));
          setStocks((prev) => {
            const existing = prev[msg.symbol];
            if (!existing) return prev;
            return {
              ...prev,
              [msg.symbol]: {
                ...existing,
                ltp: msg.price,
                change: msg.change ?? existing.change,
                change_percent: msg.change_percent ?? existing.change_percent,
              },
            };
          });
        } else if (msg.type === "CANDLE_UPDATE") {
          setLiveCandles((prev) => ({
            ...prev,
            [msg.symbol]: { ...(prev[msg.symbol] || {}), ...msg.candles },
          }));
        } else if (msg.type === "RSI_UPDATE") {
          setRsiMap((prev) => ({ ...prev, [msg.symbol]: msg.rsi }));
        } else if (msg.type === "RSI_ALERT") {
          const alert: Alert = {
            alertType: (msg as any).alertType || "BUY",
            symbol: msg.symbol,
            name: msg.name,
            message: msg.message,
            timestamp: msg.timestamp,
            rsi: msg.rsi,
            consecutiveCount: msg.consecutiveCount,
          };
          setAlerts((prev) => [alert, ...prev.slice(0, 99)]);
          if (
            "Notification" in window &&
            Notification.permission === "granted"
          ) {
            new Notification(`🟢 BUY Alert: ${msg.symbol}`, {
              body: msg.message,
              icon: "/favicon.svg",
            });
          }
        } else if (msg.type === "VOLUME_ALERT") {
          const alert: Alert = {
            alertType: "WATCH",
            symbol: msg.symbol,
            name: msg.name,
            message: msg.message,
            timestamp: msg.timestamp,
            volumeRatio: msg.volumeRatio,
          };
          setAlerts((prev) => [alert, ...prev.slice(0, 99)]);
          if (
            "Notification" in window &&
            Notification.permission === "granted"
          ) {
            new Notification(`👁 WATCH Alert: ${msg.symbol}`, {
              body: msg.message,
              icon: "/favicon.svg",
            });
          }
        } else if (msg.type === "SESSION_EXPIRED") {
          setSessionExpired(true);
          setLoginUrl(msg.loginUrl || "/login");
        } else if (msg.type === "SESSION_RESTORED") {
          setSessionExpired(false);
        }
      } catch {}
    };
  }, [wsUrl]);

  useEffect(() => {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const dismissAlert = useCallback((index: number) => {
    setAlerts((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const clearAlerts = useCallback(() => {
    setAlerts([]);
  }, []);

  return {
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
  };
};
