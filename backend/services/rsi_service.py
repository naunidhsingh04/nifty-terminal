import time
import random
from typing import List, Dict
from datetime import datetime
import pytz
from db.database import get_db
from models.stocks import NIFTY50

IST = pytz.timezone("Asia/Kolkata")

# ── In-memory 4H RSI tracker ───────────────────────────────────────────────────
_tracker: Dict[str, dict] = {}

def calc_rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = 0.0, 0.0
    for i in range(len(closes) - period, len(closes)):
        d = closes[i] - closes[i - 1]
        if d > 0:
            gains += d
        else:
            losses -= d
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_gain / avg_loss), 2)

async def load_rsi_states(symbols: list):
    """
    Load persisted RSI states from MongoDB on startup.
    If no state exists for a symbol, initialize with synthetic data.
    """
    db = get_db()
    now = int(time.time())

    for sym in symbols:
        base = NIFTY50[sym]["base"]
        doc  = await db.rsi_state.find_one({"symbol": sym})

        if doc:
            _tracker[sym] = {
                "closes":               doc.get("closes", []),
                "bucket":               doc.get("bucket", (now // 14400) * 14400),
                "open":                 doc.get("open",  base),
                "high":                 doc.get("high",  base),
                "low":                  doc.get("low",   base),
                "close":                doc.get("close", base),
                "consecutive_below_30": doc.get("consecutive_below_30", 0),
                "qualified":            doc.get("qualified", False),
                "alert_fired":          doc.get("alert_fired", False),
            }
        else:
            # Fresh state — seed with synthetic historical closes
            synthetic = [base * (1 + (random.random() - 0.5) * 0.02) for _ in range(30)]
            _tracker[sym] = {
                "closes":               synthetic,
                "bucket":               (now // 14400) * 14400,
                "open":                 base,
                "high":                 base,
                "low":                  base,
                "close":                base,
                "consecutive_below_30": 0,
                "qualified":            False,
                "alert_fired":          False,
            }

    print(f"✅ RSI states loaded for {len(symbols)} symbols")

async def save_rsi_state(sym: str):
    """Persist RSI state to MongoDB so it survives restarts."""
    db = get_db()
    t  = _tracker[sym]
    await db.rsi_state.update_one(
        {"symbol": sym},
        {"$set": {
            "symbol":               sym,
            "closes":               t["closes"][-60:],  # keep last 60
            "bucket":               t["bucket"],
            "open":                 t["open"],
            "high":                 t["high"],
            "low":                  t["low"],
            "close":                t["close"],
            "consecutive_below_30": t["consecutive_below_30"],
            "qualified":            t["qualified"],
            "alert_fired":          t["alert_fired"],
        }},
        upsert=True,
    )

async def process_4h_rsi(sym: str, price: float) -> tuple:
    """
    Process 4H RSI for a symbol.
    Returns (rsi_update_msg, alert_msg_or_None)
    """
    t   = _tracker[sym]
    now = int(time.time())
    new_bucket = (now // 14400) * 14400
    alert_msg  = None

    if new_bucket > t["bucket"]:
        # ── 4H candle just CLOSED ─────────────────────────────────────────────
        t["closes"].append(t["close"])
        if len(t["closes"]) > 60:
            t["closes"].pop(0)

        rsi = calc_rsi(t["closes"])

        if rsi < 30:
            # RSI still in oversold — increment streak
            t["consecutive_below_30"] += 1
            t["alert_fired"] = False
            if t["consecutive_below_30"] >= 4:
                t["qualified"] = True
        else:
            # RSI crossed ABOVE 30
            if t["qualified"] and not t["alert_fired"]:
                # ALERT — was oversold for 4+ candles, now recovering
                alert_msg = {
                    "type":             "RSI_ALERT",
                    "symbol":           sym,
                    "name":             NIFTY50[sym]["name"],
                    "rsi":              rsi,
                    "message":          (
                        f"🚨 {NIFTY50[sym]['name']} ({sym}): RSI crossed above 30 "
                        f"after {t['consecutive_below_30']} consecutive oversold 4H candles. "
                        f"RSI now: {rsi}. Bullish reversal signal!"
                    ),
                    "consecutiveCount": t["consecutive_below_30"],
                    "timestamp":        datetime.now(IST).strftime("%I:%M:%S %p IST"),
                }
                t["alert_fired"] = True

                # Save alert to MongoDB
                db = get_db()
                await db.rsi_alerts.insert_one({
                    "symbol":           sym,
                    "name":             NIFTY50[sym]["name"],
                    "rsi":              rsi,
                    "consecutiveCount": t["consecutive_below_30"],
                    "timestamp":        datetime.now(IST),
                })

            # Reset streak
            t["consecutive_below_30"] = 0
            t["qualified"]            = False

        # Start new 4H candle
        t["bucket"] = new_bucket
        t["open"]   = price
        t["high"]   = price
        t["low"]    = price
        t["close"]  = price

        # Persist state to MongoDB every time a 4H candle closes
        await save_rsi_state(sym)

    else:
        # 4H candle still in progress
        t["high"]  = max(t["high"],  price)
        t["low"]   = min(t["low"],   price)
        t["close"] = price

    # Live RSI of in-progress candle
    live_rsi = calc_rsi(t["closes"] + [t["close"]])
    rsi_update = {"type": "RSI_UPDATE", "symbol": sym, "rsi": live_rsi}

    return rsi_update, alert_msg

def get_live_rsi(sym: str) -> float:
    t = _tracker.get(sym)
    if not t:
        return 50.0
    return calc_rsi(t["closes"] + [t["close"]])
