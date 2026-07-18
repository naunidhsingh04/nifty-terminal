"""
Telegram notification service.
Sends session expiry reminders and deal alerts via Telegram bot.
"""
import aiohttp
import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "")

async def send_telegram(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"⚠ Telegram error: {e}")
        return False

async def notify_session_expired(login_url: str):
    msg = (
        "🔴 <b>Nifty Terminal — Session Expired</b>\n\n"
        "Your Breeze session has expired.\n"
        "Tap the link below to refresh it:\n\n"
        f"👉 <a href='{login_url}/login'>{login_url}/login</a>\n\n"
        "Takes 30 seconds. All prices will resume automatically."
    )
    await send_telegram(msg)

async def notify_session_refreshed():
    msg = "✅ <b>Nifty Terminal</b> — Session refreshed! Live prices active."
    await send_telegram(msg)