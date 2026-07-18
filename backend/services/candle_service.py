import time
from typing import List, Optional, Dict
from db.database import get_db
from models.stocks import INTERVAL_SECONDS

_live_candles: Dict[str, Dict[str, dict]] = {}

def init_live_candles(symbols: list, base_prices: dict):
    now = int(time.time())
    for sym in symbols:
        base = base_prices[sym]
        _live_candles[sym] = {}
        for iv, gap in INTERVAL_SECONDS.items():
            bucket = (now // gap) * gap
            _live_candles[sym][iv] = {
                "symbol": sym, "time": bucket,
                "open": base, "high": base,
                "low": base, "close": base, "volume": 0,
            }

def update_live_candle(sym: str, price: float, tick_vol: int):
    now = int(time.time())
    result, closed = {}, []
    for iv, gap in INTERVAL_SECONDS.items():
        c = _live_candles[sym][iv]
        new_bucket = (now // gap) * gap
        if new_bucket > c["time"]:
            closed.append((iv, dict(c)))
            _live_candles[sym][iv] = {
                "symbol": sym, "time": new_bucket,
                "open": price, "high": price,
                "low": price, "close": price, "volume": tick_vol,
            }
        else:
            c["high"]   = max(c["high"], price)
            c["low"]    = min(c["low"], price)
            c["close"]  = price
            c["volume"] += tick_vol
        c = _live_candles[sym][iv]
        result[iv] = {
            "time": c["time"], "open": round(c["open"], 2),
            "high": round(c["high"], 2), "low": round(c["low"], 2),
            "close": round(c["close"], 2), "volume": c["volume"],
        }
    return result, closed

async def save_closed_candles(closed: list):
    db = get_db()
    for iv, candle in closed:
        try:
            await db.aexecute("""
                INSERT INTO candles (symbol, interval, time, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, interval, time) DO UPDATE SET
                    open=excluded.open, high=excluded.high,
                    low=excluded.low, close=excluded.close, volume=excluded.volume
            """, (
                candle["symbol"], iv, int(candle["time"]),
                round(float(candle["open"]), 2), round(float(candle["high"]), 2),
                round(float(candle["low"]), 2), round(float(candle["close"]), 2),
                int(candle["volume"]),
            ))
        except Exception:
            pass

async def save_tick(sym: str, price: float, volume: int):
    db  = get_db()
    now = int(time.time())
    try:
        await db.aexecute(
            "INSERT INTO ticks (symbol, time, price, volume) VALUES (?, ?, ?, ?)",
            (sym, now, price, volume)
        )
        cutoff = now - 7 * 24 * 3600
        await db.aexecute("DELETE FROM ticks WHERE time < ?", (cutoff,))
    except Exception:
        pass

async def get_candles(sym: str, interval: str, limit: int = 500) -> List[dict]:
    db = get_db()
    try:
        rows = await db.afetchall("""
            SELECT time, open, high, low, close, volume FROM candles
            WHERE symbol = ? AND interval = ?
            ORDER BY time ASC LIMIT ?
        """, (sym, interval, limit))
        return [{"time": r[0], "open": r[1], "high": r[2],
                 "low": r[3], "close": r[4], "volume": r[5]} for r in rows]
    except Exception:
        return []

def get_live_candle(sym: str, interval: str) -> Optional[dict]:
    c = _live_candles.get(sym, {}).get(interval)
    if not c:
        return None
    return {
        "time": int(c["time"]), "open": round(float(c["open"]), 2),
        "high": round(float(c["high"]), 2), "low": round(float(c["low"]), 2),
        "close": round(float(c["close"]), 2), "volume": int(c["volume"]),
    }