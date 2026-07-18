import random
import time
import asyncio
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from services.candle_service import get_candles, get_live_candle
from services.breeze_service import fetch_breeze_history, is_connected
from models.stocks import NIFTY50, SYMBOLS, INTERVAL_SECONDS
from db.database import get_db

router = APIRouter(prefix="/api")

_mem_cache: dict = {}
_mem_cache_time: dict = {}

CACHE_TTL = {
    "1minute": 30, "2minute": 30, "3minute": 30, "4minute": 30,
    "5minute": 60, "10minute": 60, "15minute": 120, "30minute": 120,
    "1hour": 300, "2hour": 300, "4hour": 600, "1day": 3600,
    "1week": 3600, "1month": 7200, "1year": 7200, "5year": 7200,
}

@router.get("/history")
async def get_history(symbol: str, interval: str = "1day"):
    if symbol not in NIFTY50:
        return JSONResponse({"error": "Invalid symbol"}, status_code=400)

    cache_key = f"{symbol}_{interval}"
    now = time.time()
    ttl = CACHE_TTL.get(interval, 300)

    # 1. Memory cache
    if cache_key in _mem_cache:
        age = now - _mem_cache_time.get(cache_key, 0)
        if age < ttl:
            candles = _mem_cache[cache_key]
            live = get_live_candle(symbol, interval)
            if live:
                result = [c for c in candles if c["time"] != live["time"]]
                result.append(live)
            else:
                result = candles
            return result

    # 2. MongoDB cache
    db_candles = await get_candles(symbol, interval, limit=500)
    if db_candles and len(db_candles) >= 10:
        _mem_cache[cache_key] = db_candles
        _mem_cache_time[cache_key] = now
        live = get_live_candle(symbol, interval)
        if live:
            result = [c for c in db_candles if c["time"] != live["time"]]
            result.append(live)
        else:
            result = db_candles
        print(f"📦 MongoDB: {symbol} {interval} ({len(result)} candles)")
        return result

    # 3. Breeze REST API for real historical data
    if is_connected():
        print(f"📡 Breeze: fetching {symbol} {interval}...")
        candles = await fetch_breeze_history(symbol, interval)
        if candles and len(candles) >= 2:
            db = get_db()
            coll = f"candles_{interval}"
            ops = [{"updateOne": {"filter": {"symbol": symbol, "time": c["time"]},
                    "update": {"$set": {**c, "symbol": symbol}}, "upsert": True}}
                   for c in candles]
            if ops:
                try:
                    await db[coll].bulk_write(ops, ordered=False)
                except Exception:
                    pass
            _mem_cache[cache_key] = candles
            _mem_cache_time[cache_key] = now
            live = get_live_candle(symbol, interval)
            if live:
                result = [c for c in candles if c["time"] != live["time"]]
                result.append(live)
            else:
                result = candles
            print(f"✅ Breeze: {symbol} {interval} ({len(result)} candles)")
            return result

    # 4. Fallback synthetic candles
    print(f"⚠ Fallback: {symbol} {interval}")
    fallback = _generate_fallback(symbol, interval)
    _mem_cache[cache_key] = fallback
    _mem_cache_time[cache_key] = now
    return fallback

@router.get("/symbols")
def get_symbols():
    return [{"symbol": s, "name": NIFTY50[s]["name"]} for s in SYMBOLS]

@router.get("/market-status")
def get_market_status():
    from services.breeze_service import is_market_open
    return {"isOpen": is_market_open()}

@router.get("/health")
def health():
    return {"status": "ok", "stocks": len(SYMBOLS), "cached": len(_mem_cache)}

def _generate_fallback(sym: str, interval: str):
    base = NIFTY50[sym]["base"]
    gap = INTERVAL_SECONDS.get(interval, 86400)
    count = 200 if gap < 3600 else 150 if gap < 86400 else 100
    now = int(time.time())
    latest = (now // gap) * gap
    price = base * (1 + (random.random() - 0.5) * 0.04)
    trend = (random.random() - 0.5) * 0.0002
    candles = []
    for i in range(count):
        t = latest - (count - 1 - i) * gap
        vol = base * 0.003 * (gap / 3600 + 0.3)
        open_ = price
        close = open_ * (1 + trend + (random.random() - 0.49) * (vol / open_))
        high = max(open_, close) * (1 + random.random() * 0.002)
        low = min(open_, close) * (1 - random.random() * 0.002)
        price = close
        candles.append({"time": t, "open": round(open_, 2), "high": round(high, 2),
                        "low": round(low, 2), "close": round(close, 2),
                        "volume": random.randint(50000, 800000)})
    return candles