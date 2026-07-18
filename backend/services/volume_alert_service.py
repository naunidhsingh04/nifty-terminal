"""
Volume Alert Service
Fires a WATCH alert when a stock's 7-day avg volume >= 10x its 30-day avg volume.
Runs once per day after market close (or on startup if not run today).
"""
import asyncio
from datetime import datetime, timedelta
from typing import Callable, Optional
import pytz

IST = pytz.timezone("Asia/Kolkata")

# Track which stocks already fired today so we don't spam
_fired_today: set = set()
_last_check_date: Optional[str] = None
_alert_callback: Optional[Callable] = None

def set_alert_callback(cb: Callable):
    global _alert_callback
    _alert_callback = cb

async def check_volume_alerts(db, symbols: dict):
    """
    For each stock, compare:
      - 7-day avg daily volume
      - 30-day avg daily volume (excluding last 7 days)
    Fire WATCH alert if 7d_avg >= 10x 30d_avg
    """
    global _fired_today, _last_check_date

    now_ist = datetime.now(IST)
    today_str = now_ist.strftime("%Y-%m-%d")

    # Reset fired set each new day
    if _last_check_date != today_str:
        _fired_today = set()
        _last_check_date = today_str

    fired_count = 0

    for sym in symbols:
        if sym in _fired_today:
            continue
        try:
            # Get last 37 days of daily candles from MongoDB
            cutoff_37d = datetime.now(IST) - timedelta(days=37)
            cutoff_37d_ts = int(cutoff_37d.timestamp())

            candles = await db["candles_1day"].find(
                {"symbol": sym, "time": {"$gte": cutoff_37d_ts}},
                sort=[("time", 1)]
            ).to_list(length=50)

            if len(candles) < 15:
                continue

            # Split: last 7 trading days vs previous 30
            recent_7 = candles[-7:]
            prior_30 = candles[:-7]

            if len(prior_30) < 8:
                continue

            avg_7d = sum(c.get("volume", 0) for c in recent_7) / len(recent_7)
            avg_30d = sum(c.get("volume", 0) for c in prior_30) / len(prior_30)

            if avg_30d <= 0:
                continue

            ratio = avg_7d / avg_30d

            if ratio >= 10.0:
                _fired_today.add(sym)
                fired_count += 1

                name = symbols[sym].get("name", sym)
                msg = (
                    f"7-day avg vol ({int(avg_7d):,}) is "
                    f"{ratio:.1f}x the prior 30-day avg ({int(avg_30d):,}). "
                    f"Unusual volume spike detected."
                )
                alert = {
                    "type": "VOLUME_ALERT",
                    "symbol": sym,
                    "name": name,
                    "message": msg,
                    "volumeRatio": round(ratio, 2),
                    "timestamp": now_ist.strftime("%d %b %Y %H:%M"),
                }
                if _alert_callback:
                    await _alert_callback(alert)

        except Exception as e:
            pass

    if fired_count:
        print(f"📊 Volume alerts fired: {fired_count} stocks")

async def volume_alert_loop(db, symbols: dict):
    """Run volume check once per day after market close (3:45 PM IST)."""
    print("📊 Volume alert service started")
    while True:
        try:
            now = datetime.now(IST)
            # Run at 3:45 PM IST on weekdays
            target = now.replace(hour=15, minute=45, second=0, microsecond=0)

            if now.weekday() < 5:  # Mon-Fri
                if now >= target:
                    await check_volume_alerts(db, symbols)
                    # Wait until next day
                    await asyncio.sleep(60 * 60 * 20)
                else:
                    # Wait until 3:45 PM
                    wait_secs = (target - now).total_seconds()
                    await asyncio.sleep(min(wait_secs, 300))
            else:
                # Weekend — wait 6 hours
                await asyncio.sleep(60 * 60 * 6)

        except Exception as e:
            print(f"⚠ Volume alert loop error: {e}")
            await asyncio.sleep(60)