import time
import json
import random
from typing import List, Dict
from datetime import datetime
import pytz
from db.database import get_db
from models.stocks import NIFTY50

IST = pytz.timezone("Asia/Kolkata")
_tracker: Dict[str, dict] = {}

def calc_rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = 0.0, 0.0
    for i in range(len(closes) - period, len(closes)):
        d = closes[i] - closes[i - 1]
        if d > 0: gains += d
        else: losses -= d
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_gain / avg_loss), 2)

async def load_rsi_states(symbols: list):
    db  = get_db()
    now = int(time.time())
    for sym in symbols:
        base = NIFTY50[sym]["base"]
        try:
            row = await db.afetchone(
                "SELECT closes, bucket, open, high, low, close, "
                "consecutive_below30, qualified, alert_fired "
                "FROM rsi_states WHERE symbol = ?", (sym,)
            )
        except Exception:
            row = None

        if row:
            _tracker[sym] = {
                "closes": json.loads(row[0]), "bucket": row[1],
                "open": row[2], "high": row[3], "low": row[4], "close": row[5],
                "consecutive_below_30": row[6],
                "qualified": bool(row[7]), "alert_fired": bool(row[8]),
            }
        else:
            synthetic = [base * (1 + (random.random() - 0.5) * 0.02) for _ in range(30)]
            _tracker[sym] = {
                "closes": synthetic, "bucket": (now // 14400) * 14400,
                "open": base, "high": base, "low": base, "close": base,
                "consecutive_below_30": 0, "qualified": False, "alert_fired": False,
            }
    print(f"✅ RSI states loaded for {len(symbols)} symbols")

async def save_rsi_state(sym: str):
    db = get_db()
    t  = _tracker[sym]
    try:
        await db.aexecute("""
            INSERT INTO rsi_states
                (symbol, closes, bucket, open, high, low, close,
                 consecutive_below30, qualified, alert_fired)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                closes=excluded.closes, bucket=excluded.bucket,
                open=excluded.open, high=excluded.high,
                low=excluded.low, close=excluded.close,
                consecutive_below30=excluded.consecutive_below30,
                qualified=excluded.qualified, alert_fired=excluded.alert_fired
        """, (
            sym, json.dumps(t["closes"][-60:]), t["bucket"],
            t["open"], t["high"], t["low"], t["close"],
            t["consecutive_below_30"], int(t["qualified"]), int(t["alert_fired"]),
        ))
    except Exception as e:
        pass

async def process_4h_rsi(sym: str, price: float) -> tuple:
    t = _tracker[sym]
    now = int(time.time())
    new_bucket = (now // 14400) * 14400
    alert_msg = None

    if new_bucket > t["bucket"]:
        t["closes"].append(t["close"])
        if len(t["closes"]) > 60:
            t["closes"].pop(0)
        rsi = calc_rsi(t["closes"])

        if rsi < 30:
            t["consecutive_below_30"] += 1
            t["alert_fired"] = False
            if t["consecutive_below_30"] >= 4:
                t["qualified"] = True
        else:
            if t["qualified"] and not t["alert_fired"]:
                alert_msg = {
                    "type": "RSI_ALERT", "symbol": sym,
                    "name": NIFTY50[sym]["name"], "rsi": rsi,
                    "message": (
                        f"🚨 {NIFTY50[sym]['name']} ({sym}): RSI crossed above 30 "
                        f"after {t['consecutive_below_30']} consecutive oversold 4H candles. "
                        f"RSI now: {rsi}. Bullish reversal signal!"
                    ),
                    "consecutiveCount": t["consecutive_below_30"],
                    "timestamp": datetime.now(IST).strftime("%I:%M:%S %p IST"),
                }
                t["alert_fired"] = True
            t["consecutive_below_30"] = 0
            t["qualified"] = False

        t["bucket"] = new_bucket
        t["open"] = t["high"] = t["low"] = t["close"] = price
        await save_rsi_state(sym)
    else:
        t["high"]  = max(t["high"], price)
        t["low"]   = min(t["low"], price)
        t["close"] = price

    live_rsi = calc_rsi(t["closes"] + [t["close"]])
    return {"type": "RSI_UPDATE", "symbol": sym, "rsi": live_rsi}, alert_msg

def get_live_rsi(sym: str) -> float:
    t = _tracker.get(sym)
    if not t:
        return 50.0
    return calc_rsi(t["closes"] + [t["close"]])