from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel
import asyncio

MONGO_URI = "mongodb://localhost:27017"
DB_NAME   = "nifty_terminal"

client: AsyncIOMotorClient = None
db = None

# ── Collections ────────────────────────────────────────────────────────────────
# ticks          → raw price every 1 second per symbol
# candles_{iv}   → pre-aggregated OHLCV per timeframe per symbol
# rsi_state      → 4H RSI tracker state per symbol (persists across restarts)

async def connect():
    global client, db
    client = AsyncIOMotorClient(MONGO_URI)
    db     = client[DB_NAME]
    await create_indexes()
    print(f"✅ MongoDB connected → {DB_NAME}")

async def disconnect():
    if client:
        client.close()

async def create_indexes():
    # ticks: query by symbol + time
    await db.ticks.create_indexes([
        IndexModel([("symbol", ASCENDING), ("time", DESCENDING)]),
        IndexModel([("time",   DESCENDING)]),
        # TTL index — auto-delete ticks older than 7 days to save space
        IndexModel([("time", ASCENDING)], expireAfterSeconds=7 * 24 * 3600),
    ])

    # candles per timeframe
    INTERVALS = [
        "1minute","2minute","3minute","4minute","5minute",
        "10minute","15minute","30minute","1hour","2hour",
        "4hour","1day","1week","1month","1year","5year",
    ]
    for iv in INTERVALS:
        coll = f"candles_{iv}"
        await db[coll].create_indexes([
            IndexModel([("symbol", ASCENDING), ("time", DESCENDING)]),
            IndexModel([("symbol", ASCENDING), ("time", ASCENDING)],
                       unique=True),
        ])

    # rsi_state: one doc per symbol
    await db.rsi_state.create_indexes([
        IndexModel([("symbol", ASCENDING)], unique=True),
    ])

    print("✅ MongoDB indexes created")

def get_db():
    return db
