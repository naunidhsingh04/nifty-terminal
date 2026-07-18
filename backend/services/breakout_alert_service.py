"""
Breakout Alert Service
Fires a BUY alert when today's closing price > highest high of last 4 trading days.
Runs at 3:35 PM IST (just after market close) every weekday.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Callable, Optional
import pytz

IST = pytz.timezone("Asia/Kolkata")

_fired_today: set = set()
_last_check_date: Optional[str] = None
_alert_callback: Optional[Callable] = None

def set_breakout_callback(cb: Callable):
    global _alert_callback
    _alert_callback = cb

async def check_breakout_alerts(db, symbols: dict):
    """
    For each stock:
      1. Get last 5 daily candles from MongoDB
      2. Today's close = candles[-1].close
      3. Last 4 days high = max(candles[-5:-1].high)
      4. If today's close > last 4 days high → BUY alert
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
            # Get last 6 daily candles (need 5 full days)
            cutoff = datetime.now(IST) - timedelta(days=10)
            cutoff_ts = int(cutoff.timestamp())

            candles = await db["candles_1day"].find(
                {"symbol": sym, "time": {"$gte": cutoff_ts}},
                sort=[("time", 1)]
            ).to_list(length=10)

            if len(candles) < 5:
                continue

            # Today's candle = last one
            today_candle = candles[-1]
            today_close = today_candle.get("close", 0)

            # Last 4 days = candles before today
            last_4 = candles[-5:-1]
            last_4_high = max(c.get("high", 0) for c in last_4)

            if today_close <= 0 or last_4_high <= 0:
                continue

            if today_close > last_4_high:
                _fired_today.add(sym)
                fired_count += 1

                name = symbols[sym].get("name", sym)
                pct_above = ((today_close - last_4_high) / last_4_high) * 100
                msg = (
                    f"Close ₹{today_close:,.2f} broke above 4-day high of "
                    f"₹{last_4_high:,.2f} (+{pct_above:.2f}%). "
                    f"Potential breakout."
                )
                alert = {
                    "type": "RSI_ALERT",  # reuse existing type so frontend handles it
                    "alertType": "BUY",
                    "symbol": sym,
                    "name": name,
                    "message": msg,
                    "timestamp": now_ist.strftime("%d %b %Y %H:%M"),
                    "todayClose": today_close,
                    "last4High": last_4_high,
                    "pctAbove": round(pct_above, 2),
                }
                if _alert_callback:
                    await _alert_callback(alert)

        except Exception as e:
            pass

    if fired_count:
        print(f"🚀 Breakout alerts fired: {fired_count} stocks")
    return fired_count

async def breakout_alert_loop(db, symbols: dict):
    """Run breakout check at 3:35 PM IST on weekdays."""
    print("🚀 Breakout alert service started")
    while True:
        try:
            now = datetime.now(IST)
            # Run at 3:35 PM IST Mon-Fri
            target = now.replace(hour=15, minute=35, second=0, microsecond=0)

            if now.weekday() < 5:  # Mon-Fri
                if now >= target:
                    await check_breakout_alerts(db, symbols)
                    # Wait until next day 3:35 PM
                    await asyncio.sleep(60 * 60 * 20)
                else:
                    wait_secs = (target - now).total_seconds()
                    await asyncio.sleep(min(wait_secs, 300))
            else:
                # Weekend
                await asyncio.sleep(60 * 60 * 6)

        except Exception as e:
            print(f"⚠ Breakout alert loop error: {e}")
            await asyncio.sleep(60)