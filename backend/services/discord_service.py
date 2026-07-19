"""
Notification service using Discord webhooks.
"""
import aiohttp
import os

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")

async def send_discord(message: str) -> bool:
    if not DISCORD_WEBHOOK:
        return False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(DISCORD_WEBHOOK, json={
                "content": message,
                "username": "Nifty Terminal",
            }, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status in (200, 204)
    except Exception as e:
        print(f"⚠ Discord error: {e}")
        return False

async def notify_session_expired(login_url: str):
    msg = (
        "🔴 **Nifty Terminal — Session Expired**\n\n"
        "Your Breeze session has expired.\n"
        f"👉 Login here: {login_url}/login\n\n"
        "Takes 30 seconds. Live prices resume automatically."
    )
    await send_discord(msg)

async def notify_session_refreshed():
    await send_discord("✅ **Nifty Terminal** — Session refreshed! Live prices active.")