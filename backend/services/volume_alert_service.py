import asyncio
from datetime import datetime, timedelta
from typing import Callable, Optional
import pytz
from db.database import get_db

IST = pytz.timezone("Asia/Kolkata")
_fired_today: set = set()
_last_check_date: Optional[str] = None
_alert_callback: Optional[Callable] = None

def set_alert_callback(cb: Callable):
    global _alert_callback
    _alert_callback = cb

async def check_volume_alerts(db_unused, symbols: dict):
    global _fired_today, _last_check_date
    db = get_db()
    now_ist = datetime.now(IST)
    today_str = now_ist.strftime("%Y-%m-%d")
    if _last_check_date != today_str:
        _fired_today = set()
        _last_check_date = today_str

    cutoff = int((now_ist - timedelta(days=37)).timestamp())
    fired  = 0

    for sym in symbols:
        if sym in _fired_today:
            continue
        try:
            rows = await db.afetchall("""
                SELECT volume FROM candles
                WHERE symbol=? AND interval='1day' AND time>=?
                ORDER BY time ASC LIMIT 50
            """, (sym, cutoff))

            if len(rows) < 15:
                continue
            vols    = [r[0] or 0 for r in rows]
            recent7 = vols[-7:]
            prior30 = vols[:-7]
            if len(prior30) < 8:
                continue
            avg7  = sum(recent7) / len(recent7)
            avg30 = sum(prior30) / len(prior30)
            if avg30 <= 0 or avg7 / avg30 < 10.0:
                continue

            ratio = avg7 / avg30
            _fired_today.add(sym)
            fired += 1
            alert = {
                "type": "VOLUME_ALERT", "symbol": sym,
                "name": symbols[sym].get("name", sym),
                "message": (
                    f"7-day avg vol ({int(avg7):,}) is {ratio:.1f}x "
                    f"the prior 30-day avg ({int(avg30):,}). Unusual volume spike."
                ),
                "volumeRatio": round(ratio, 2),
                "timestamp": now_ist.strftime("%d %b %Y %H:%M"),
            }
            if _alert_callback:
                await _alert_callback(alert)
        except Exception:
            pass

    if fired:
        print(f"📊 Volume alerts fired: {fired} stocks")

async def volume_alert_loop(db_unused, symbols: dict):
    print("📊 Volume alert service started")
    while True:
        try:
            now    = datetime.now(IST)
            target = now.replace(hour=15, minute=45, second=0, microsecond=0)
            if now.weekday() < 5:
                if now >= target:
                    await check_volume_alerts(None, symbols)
                    await asyncio.sleep(60 * 60 * 20)
                else:
                    await asyncio.sleep(min((target - now).total_seconds(), 300))
            else:
                await asyncio.sleep(60 * 60 * 6)
        except Exception as e:
            print(f"⚠ Volume alert error: {e}")
            await asyncio.sleep(60)