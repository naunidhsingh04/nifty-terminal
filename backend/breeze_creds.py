# ── Breeze API Credentials ─────────────────────────────────────────────────────
# Get API Key and Secret from https://api.icicidirect.com
# Get Session Token daily by visiting:
# https://api.icicidirect.com/apiuser/login?api_key=YOUR_API_KEY

import os

BREEZE_API_KEY    = os.environ.get("BREEZE_API_KEY", "")
BREEZE_API_SECRET = os.environ.get("BREEZE_API_SECRET", "")
BREEZE_SESSION    = os.environ.get("BREEZE_SESSION", "")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")