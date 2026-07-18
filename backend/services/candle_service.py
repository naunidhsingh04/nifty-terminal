import time
from typing import List, Optional, Dict
from db.database import get_db
from models.stocks import INTERVAL_SECONDS, INTERVALS

# ── In-memory current candle per symbol per interval ──────────────────────────
# This avoids writing to MongoDB every single second for the live candle.
# We only write to MongoDB when a candle CLOSES (bucket changes).
_live_candles: Dict[str, Dict[str, dict]] = {}

def init_live_candles(symbols: list, base_prices: dict):
    now = int(time.time())
    for sym in symbols:
        base = base_prices[sym]
        _live_candles[sym] = {}
        for iv, gap in INTERVAL_SECONDS.items():
            bucket = (now // gap) * gap
            _live_candles[sym][iv] = {
                "symbol": sym,
                "time":   bucket,
                "open":   base,
                "high":   base,
                "low":    base,
                "close":  base,
                "volume": 0,
                "closed": False,
            }

def update_live_candle(sym: str, price: float, tick_vol: int) -> dict:
    """
    Update in-memory live candle for all intervals.
    Returns dict of {interval: candle} for broadcasting.
    Saves CLOSED candles to MongoDB.
    """
    now     = int(time.time())
    result  = {}
    closed  = []   # candles that just closed this tick

    for iv, gap in INTERVAL_SECONDS.items():
        c          = _live_candles[sym][iv]
        new_bucket = (now // gap) * gap

        if new_bucket > c["time"]:
            # Current candle CLOSED — mark for DB write
            closed.append((iv, dict(c)))
            # Start fresh candle
            _live_candles[sym][iv] = {
                "symbol": sym,
                "time":   new_bucket,
                "open":   price,
                "high":   price,
                "low":    price,
                "close":  price,
                "volume": tick_vol,
                "closed": False,
            }
        else:
            # Update current live candle
            c["high"]   = max(c["high"], price)
            c["low"]    = min(c["low"],  price)
            c["close"]  = price
            c["volume"] += tick_vol

        c = _live_candles[sym][iv]
        result[iv] = {
            "time":   c["time"],
            "open":   round(c["open"],  2),
            "high":   round(c["high"],  2),
            "low":    round(c["low"],   2),
            "close":  round(c["close"], 2),
            "volume": c["volume"],
        }

    return result, closed

async def save_closed_candles(closed: list):
    """Write closed candles to MongoDB (upsert by symbol+time)."""
    db = get_db()
    for iv, candle in closed:
        coll = f"candles_{iv}"
        doc  = {k: v for k, v in candle.items() if k != "closed"}
        try:
            await db[coll].update_one(
                {"symbol": candle["symbol"], "time": candle["time"]},
                {"$set": doc},
                upsert=True,
            )
        except Exception as e:
            pass  # don't crash on DB write errors

async def save_tick(sym: str, price: float, volume: int):
    """Save raw tick to MongoDB ticks collection."""
    db  = get_db()
    now = int(time.time())
    try:
        await db.ticks.insert_one({
            "symbol": sym,
            "time":   now,
            "price":  price,
            "volume": volume,
        })
    except Exception:
        pass

async def get_candles(sym: str, interval: str, limit: int = 500) -> List[dict]:
    """
    Fetch candles from MongoDB for a symbol+interval.
    Falls back to empty list if collection is empty.
    """
    db   = get_db()
    coll = f"candles_{interval}"
    cursor = db[coll].find(
        {"symbol": sym},
        {"_id": 0, "symbol": 0, "closed": 0},
    ).sort("time", 1).limit(limit)
    candles = await cursor.to_list(length=limit)
    return candles

async def get_latest_tick(sym: str) -> Optional[dict]:
    """Get the most recent tick for a symbol."""
    db  = get_db()
    doc = await db.ticks.find_one(
        {"symbol": sym},
        sort=[("time", -1)],
        projection={"_id": 0},
    )
    return doc

def get_live_candle(sym: str, interval: str) -> Optional[dict]:
    """Get current in-progress (not yet closed) candle."""
    c = _live_candles.get(sym, {}).get(interval)
    if not c:
        return None
    return {
        "time":   int(c["time"]),
        "open":   round(float(c["open"]),  2),
        "high":   round(float(c["high"]),  2),
        "low":    round(float(c["low"]),   2),
        "close":  round(float(c["close"]), 2),
        "volume": int(c["volume"]),
    }
