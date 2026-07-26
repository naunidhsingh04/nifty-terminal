"""
Day High Alert Service
Fires a WATCH alert at 3:20 PM IST for stocks trading at or near their day high.
Threshold: current price >= today's high * 0.995 (within 0.5% of day high)
"""
import asyncio
from datetime import datetime
from typing import Callable, Optional
import pytz

IST = pytz.timezone("Asia/Kolkata")

_alert_callback: Optional[Callable] = None
_fired_today: bool = False
_last_check_date: Optional[str] = None

def set_day_high_callback(cb: Callable):
    global _alert_callback
    _alert_callback = cb

async def check_day_high_alerts(price_cache: dict, symbols: dict):
    """
    Check all stocks and fire WATCH alert for those trading at/near day high.
    price_cache: the live price_cache dict from main.py
    """
    global _fired_today, _last_check_date

    now_ist   = datetime.now(IST)
    today_str = now_ist.strftime("%Y-%m-%d")

    if _last_check_date != today_str:
        _fired_today     = False
        _last_check_date = today_str

    if _fired_today:
        return

    _fired_today = True
    fired        = 0
    results      = []

    for sym, data in price_cache.items():
        try:
            ltp  = data.get("ltp", 0)
            high = data.get("high", 0)
            if ltp <= 0 or high <= 0:
                continue
            # Within 0.5% of day high
            if ltp >= high * 0.995:
                pct_from_high = ((high - ltp) / high) * 100
                results.append({
                    "symbol":      sym,
                    "name":        data.get("name", sym),
                    "ltp":         ltp,
                    "high":        high,
                    "pctFromHigh": round(pct_from_high, 2),
                })
                fired += 1
        except Exception:
            pass

    # Sort by closest to high
    results.sort(key=lambda x: x["pctFromHigh"])

    if results and _alert_callback:
        # Send individual alerts for each stock
        for r in results:
            alert = {
                "type":      "VOLUME_ALERT",  # reuse WATCH type
                "alertType": "WATCH",
                "symbol":    r["symbol"],
                "name":      r["name"],
                "message":   (
                    f"Trading at ₹{r['ltp']:,.2f} — "
                    f"near day high of ₹{r['high']:,.2f} "
                    f"({r['pctFromHigh']:.2f}% below high). 📈 Day High Alert!"
                ),
                "volumeRatio": 0,
                "timestamp":   now_ist.strftime("%d %b %Y %H:%M"),
                "tag":         "DAY_HIGH",
            }
            await _alert_callback(alert)

        print(f"📈 Day high alerts fired: {fired} stocks")

    return results

async def day_high_alert_loop(price_cache: dict, symbols: dict):
    """Run day high check at 3:20 PM IST on weekdays."""
    print("📈 Day high alert service started")
    while True:
        try:
            now    = datetime.now(IST)
            target = now.replace(hour=15, minute=20, second=0, microsecond=0)

            if now.weekday() < 5:  # Mon-Fri
                if now >= target:
                    await check_day_high_alerts(price_cache, symbols)
                    # Wait until next day
                    await asyncio.sleep(60 * 60 * 20)
                else:
                    wait_secs = (target - now).total_seconds()
                    await asyncio.sleep(min(wait_secs, 300))
            else:
                # Weekend
                await asyncio.sleep(60 * 60 * 6)
        except Exception as e:
            print(f"⚠ Day high alert loop error: {e}")
            await asyncio.sleep(60)