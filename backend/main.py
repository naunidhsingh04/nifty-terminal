import asyncio
import time
from datetime import datetime
import pytz
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from db.database import connect as db_connect, disconnect as db_disconnect
from models.stocks import NIFTY50, SYMBOLS
from services.candle_service import init_live_candles, update_live_candle, save_closed_candles, save_tick
from services.volume_alert_service import volume_alert_loop, set_alert_callback, check_volume_alerts
from services.breakout_alert_service import breakout_alert_loop, set_breakout_callback, check_breakout_alerts
from services.market_deals_service import deals_monitor_loop, set_deals_callback
from services.rsi_service import load_rsi_states, process_4h_rsi, get_live_rsi
from services.telegram_service import notify_session_expired, notify_session_refreshed
from services.ws_manager import manager
from routes.api import router
import breeze_creds as config

IST = pytz.timezone("Asia/Kolkata")

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DIST_DIR   = os.path.abspath(os.path.join(BASE_DIR, "..", "dist"))
ASSETS_DIR = os.path.join(DIST_DIR, "assets")

# Get public URL for Telegram links
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8000")

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Nifty Terminal")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Static assets ──────────────────────────────────────────────────────────────
if os.path.exists(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
    print(f"✅ Serving frontend from {DIST_DIR}")
else:
    print(f"⚠ No dist/assets — run 'npm run build' first")

app.include_router(router)

@app.get("/favicon.svg")
async def favicon():
    p = os.path.join(DIST_DIR, "favicon.svg")
    return FileResponse(p) if os.path.exists(p) else HTMLResponse("", 404)

@app.get("/")
async def serve_root():
    index = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return HTMLResponse("Frontend not built. Run: npm run build", 404)

# ── State ──────────────────────────────────────────────────────────────────────
price_cache = {}
session_active = False

def _is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    total_mins = now.hour * 60 + now.minute
    return 555 <= total_mins <= 930

# ── Tick handler ───────────────────────────────────────────────────────────────
async def on_tick(sym: str, q: dict):
    global session_active
    session_active = True
    ltp    = q["ltp"]
    volume = q.get("volume", 0)
    market_open = _is_market_open()

    price_cache[sym] = {
        "type": "TICK", "symbol": sym, "name": NIFTY50[sym]["name"],
        "ltp": ltp, "open": q.get("open", ltp),
        "high": q.get("high", ltp), "low": q.get("low", ltp),
        "change": q.get("change", 0),
        "change_percent": q.get("change_percent", 0),
        "volume": volume, "marketOpen": market_open,
    }
    await manager.broadcast(price_cache[sym])
    await manager.broadcast({
        "type": "PRICE_TICK", "symbol": sym, "price": ltp,
        "change": q.get("change", 0),
        "change_percent": q.get("change_percent", 0),
    })
    tick_vol = volume // 375 if volume > 0 else 0
    candle_update, closed = update_live_candle(sym, ltp, tick_vol)
    if closed:
        await save_closed_candles(closed)
    asyncio.create_task(save_tick(sym, ltp, tick_vol))
    safe_candles = {iv: {**c, "time": int(c["time"])} for iv, c in candle_update.items()}
    await manager.broadcast({"type": "CANDLE_UPDATE", "symbol": sym, "candles": safe_candles})
    rsi_update, alert = await process_4h_rsi(sym, ltp)
    await manager.broadcast(rsi_update)
    if alert:
        await manager.broadcast(alert)

# ── Startup ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await db_connect()
    base_prices = {sym: NIFTY50[sym]["base"] for sym in SYMBOLS}
    init_live_candles(SYMBOLS, base_prices)
    await load_rsi_states(SYMBOLS)

    from db.database import get_db
    db = get_db()

    for sym in SYMBOLS:
        last_price = NIFTY50[sym]["base"]
        try:
            doc = await db["candles_1day"].find_one({"symbol": sym}, sort=[("time", -1)])
            if doc and doc.get("close", 0) > 0:
                last_price = doc["close"]
        except Exception:
            pass
        price_cache[sym] = {
            "type": "TICK", "symbol": sym, "name": NIFTY50[sym]["name"],
            "ltp": last_price, "open": last_price,
            "high": last_price, "low": last_price,
            "change": 0.0, "change_percent": 0.0,
            "volume": 0, "marketOpen": False,
        }
    print(f"✅ Loaded last known prices for {len(SYMBOLS)} stocks")

    # Volume alert
    async def on_volume_alert(alert: dict):
        await manager.broadcast(alert)
    set_alert_callback(on_volume_alert)
    asyncio.create_task(check_volume_alerts(db, NIFTY50))
    asyncio.create_task(volume_alert_loop(db, NIFTY50))

    # Breakout alert
    async def on_breakout_alert(alert: dict):
        await manager.broadcast(alert)
    set_breakout_callback(on_breakout_alert)
    asyncio.create_task(check_breakout_alerts(db, NIFTY50))
    asyncio.create_task(breakout_alert_loop(db, NIFTY50))

    # Market deals monitor
    async def on_deal_alert(alert: dict):
        await manager.broadcast(alert)
    set_deals_callback(on_deal_alert)
    asyncio.create_task(deals_monitor_loop(NIFTY50))

    # Breeze
    from services.breeze_service import set_tick_callback, set_event_loop, load_session
    set_tick_callback(on_tick)
    set_event_loop(asyncio.get_event_loop())

    session = load_session() or config.BREEZE_SESSION
    if session:
        asyncio.create_task(connect_and_monitor(session))
    else:
        print("⚠ No session — visit /login")

    asyncio.create_task(session_watchdog())
    print("🚀 Nifty Terminal started")

async def connect_and_monitor(session: str):
    from services.breeze_service import connect_breeze, is_connected
    while True:
        if not is_connected():
            print("🔌 Connecting to Breeze...")
            connected = await connect_breeze(session)
            if connected:
                print("✅ Breeze connected")
            else:
                print("⚠ Breeze failed — retrying in 30s")
                await asyncio.sleep(30)
                continue
        await asyncio.sleep(10)

async def session_watchdog():
    """
    Watches for session expiry.
    At 8:00 AM IST every day, sends Telegram notification to refresh session.
    Also broadcasts session_expired to all connected frontends.
    """
    global session_active
    notified_today = False

    while True:
        await asyncio.sleep(60)
        now = datetime.now(IST)

        # Reset at midnight
        if now.hour == 0 and now.minute == 0:
            notified_today = False
            session_active = False
            await manager.broadcast({
                "type": "SESSION_EXPIRED",
                "message": "Breeze session expired. Please login to refresh.",
                "loginUrl": f"{PUBLIC_URL}/login",
            })

        # Send Telegram reminder at 8:00 AM
        if now.hour == 8 and now.minute == 0 and not notified_today:
            notified_today = True
            await notify_session_expired(PUBLIC_URL)
            await manager.broadcast({
                "type": "SESSION_EXPIRED",
                "message": "Breeze session expired. Please login to refresh.",
                "loginUrl": f"{PUBLIC_URL}/login",
            })
            print("📱 Telegram session reminder sent")

@app.on_event("shutdown")
async def shutdown():
    from services.breeze_service import disconnect
    await disconnect()
    await db_disconnect()

# ── WebSocket ──────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    for sym in SYMBOLS:
        cache = price_cache.get(sym)
        if cache:
            await manager.send_to(ws, cache)
        await manager.send_to(ws, {"type": "RSI_UPDATE", "symbol": sym, "rsi": get_live_rsi(sym)})
    # Send session status
    if not session_active:
        await manager.send_to(ws, {
            "type": "SESSION_EXPIRED",
            "message": "Breeze session expired. Please login to refresh.",
            "loginUrl": f"{PUBLIC_URL}/login",
        })
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)

# ── Login + Callback ───────────────────────────────────────────────────────────
@app.get("/login")
async def login_page():
    url = f"https://api.icicidirect.com/apiuser/login?api_key={config.BREEZE_API_KEY}"
    return HTMLResponse(f"""
    <html><head><title>Nifty Terminal — Login</title>
    <style>body{{font-family:monospace;background:#0d1117;color:#c9d1d9;
    display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:20px;}}
    a{{color:#58a6ff;font-size:18px;padding:12px 24px;border:1px solid #58a6ff;border-radius:8px;text-decoration:none;}}
    a:hover{{background:#1e3a5f;}}</style></head>
    <body><h2>🔐 Nifty Terminal — Login</h2>
    <a href="{url}">👉 Login with ICICI Direct</a>
    </body></html>""")

@app.get("/callback")
async def breeze_callback(request: Request):
    global session_active
    session_token = request.query_params.get("apisession", "")
    if not session_token:
        return HTMLResponse("<h2>❌ No session token.</h2>")
    config.BREEZE_SESSION = session_token
    from services.breeze_service import save_session, connect_breeze, set_tick_callback, set_event_loop
    save_session(session_token)
    set_tick_callback(on_tick)
    set_event_loop(asyncio.get_event_loop())
    connected = await connect_breeze(session_token)
    if connected:
        session_active = True
        # Notify all frontends session is back
        await manager.broadcast({"type": "SESSION_RESTORED"})
        # Send Telegram confirmation
        await notify_session_refreshed()
        return HTMLResponse("""
        <html><head><style>body{font-family:monospace;background:#0d1117;color:#26a69a;
        display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:16px;}</style></head>
        <body><h2>✅ Session refreshed! Live prices active.</h2>
        <p style="color:#8b9ab0">You can close this tab.</p>
        <script>setTimeout(()=>window.close(),2000);</script></body></html>""")
    return HTMLResponse("<html><body style='background:#0d1117;color:#ef5350;font-family:monospace;display:flex;align-items:center;justify-content:center;height:100vh'><h2>❌ Connection failed. Try again.</h2></body></html>")

# ── Session status API ─────────────────────────────────────────────────────────
@app.get("/api/session-status")
def session_status():
    return {"active": session_active, "loginUrl": f"{PUBLIC_URL}/login"}

if __name__ == "__main__":
    print("=" * 55)
    print("  🚀 NIFTY TERMINAL")
    print("  ⚡ Real-time prices via Breeze WebSocket")
    print("  📊 Charts via Breeze historical data")
    print(f"  🌐 Frontend: http://localhost:8000")
    print("  🔐 Login: http://localhost:8000/login")
    print("=" * 55)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, log_level="warning")