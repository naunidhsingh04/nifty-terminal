import asyncio
from datetime import datetime, timedelta
from typing import Callable, Optional
import pytz
from db.database import get_db

IST = pytz.timezone("Asia/Kolkata")
_fired_today: set = set()
_last_check_date: Optional[str] = None
_alert_callback: Optional[Callable] = None

def set_breakout_callback(cb: Callable):
    global _alert_callback
    _alert_callback = cb

async def check_breakout_alerts(db_unused, symbols: dict):
    global _fired_today, _last_check_date
    db = get_db()
    now_ist = datetime.now(IST)
    today_str = now_ist.strftime("%Y-%m-%d")
    if _last_check_date != today_str:
        _fired_today = set()
        _last_check_date = today_str

    cutoff = int((now_ist - timedelta(days=10)).timestamp())
    fired  = 0

    for sym in symbols:
        if sym in _fired_today:
            continue
        try:
            rows = await db.afetchall("""
                SELECT time, high, close FROM candles
                WHERE symbol=? AND interval='1day' AND time>=?
                ORDER BY time ASC LIMIT 10
            """, (sym, cutoff))

            if len(rows) < 5:
                continue
            today_close = rows[-1][2]
            last4_high  = max(r[1] for r in rows[-5:-1])
            if today_close <= 0 or last4_high <= 0 or today_close <= last4_high:
                continue

            _fired_today.add(sym)
            fired += 1
            pct = ((today_close - last4_high) / last4_high) * 100
            alert = {
                "type": "RSI_ALERT", "alertType": "BUY",
                "symbol": sym, "name": symbols[sym].get("name", sym),
                "message": (
                    f"Close ₹{today_close:,.2f} broke above 4-day high of "
                    f"₹{last4_high:,.2f} (+{pct:.2f}%). Potential breakout."
                ),
                "timestamp": now_ist.strftime("%d %b %Y %H:%M"),
                "pctAbove": round(pct, 2),
            }
            if _alert_callback:
                await _alert_callback(alert)
        except Exception:
            pass

    if fired:
        print(f"🚀 Breakout alerts fired: {fired} stocks")
    return fired

async def breakout_alert_loop(db_unused, symbols: dict):
    print("🚀 Breakout alert service started")
    while True:
        try:
            now    = datetime.now(IST)
            target = now.replace(hour=15, minute=35, second=0, microsecond=0)
            if now.weekday() < 5:
                if now >= target:
                    await check_breakout_alerts(None, symbols)
                    await asyncio.sleep(60 * 60 * 20)
                else:
                    await asyncio.sleep(min((target - now).total_seconds(), 300))
            else:
                await asyncio.sleep(60 * 60 * 6)
        except Exception as e:
            print(f"⚠ Breakout alert error: {e}")
            await asyncio.sleep(60)