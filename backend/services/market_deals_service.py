"""
Market Deals Alert Service
Monitors NSE bulk deals, block deals and BSE SAST disclosures.
Polls every 2 minutes during market hours + 30 mins after close.
Fires WATCH alerts for new deals involving Nifty 500 stocks.
"""
import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Callable, Optional, Set
import pytz

IST = pytz.timezone("Asia/Kolkata")

_alert_callback: Optional[Callable] = None
_seen_deals: Set[str] = set()  # Dedup key: symbol+client+qty+date
_nse_session: Optional[aiohttp.ClientSession] = None

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/market-data/bulk-block-deals",
    "X-Requested-With": "XMLHttpRequest",
}

BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/markets/MarketInfo/BulkDeals.aspx",
}

def set_deals_callback(cb: Callable):
    global _alert_callback
    _alert_callback = cb

def _is_monitoring_hours() -> bool:
    """Monitor during market hours + 30 mins after close."""
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    total_mins = now.hour * 60 + now.minute
    return 555 <= total_mins <= 960  # 9:15 AM to 4:00 PM

def _deal_key(deal: dict) -> str:
    return f"{deal.get('symbol','')}-{deal.get('client','')}-{deal.get('qty','')}-{deal.get('date','')}"

async def _get_nse_session() -> aiohttp.ClientSession:
    """Create a session with NSE cookies."""
    global _nse_session
    if _nse_session and not _nse_session.closed:
        return _nse_session

    connector = aiohttp.TCPConnector(ssl=False)
    _nse_session = aiohttp.ClientSession(
        connector=connector,
        headers=NSE_HEADERS,
        cookie_jar=aiohttp.CookieJar()
    )

    # Hit NSE homepage to get cookies
    try:
        async with _nse_session.get(
            "https://www.nseindia.com",
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            await resp.read()
    except Exception:
        pass

    return _nse_session

async def fetch_nse_bulk_deals(symbols: set) -> list:
    """Fetch today's NSE bulk deals."""
    try:
        session = await _get_nse_session()
        async with session.get(
            "https://www.nseindia.com/api/bulkdeals?type=bulk",
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json(content_type=None)
            deals = data if isinstance(data, list) else data.get("data", [])

            result = []
            for d in deals:
                sym = d.get("Symbol", d.get("symbol", "")).strip().upper()
                if sym not in symbols:
                    continue
                result.append({
                    "type": "BULK",
                    "exchange": "NSE",
                    "symbol": sym,
                    "client": d.get("Client Name", d.get("clientName", "Unknown")),
                    "buy_sell": d.get("Buy/Sell", d.get("buySell", "?")),
                    "qty": d.get("Quantity Traded", d.get("quantityTraded", 0)),
                    "price": d.get("Trade Price", d.get("tradePrice", 0)),
                    "date": d.get("Date", d.get("date", "")),
                    "remarks": d.get("Remarks", ""),
                })
            return result
    except Exception as e:
        return []

async def fetch_nse_block_deals(symbols: set) -> list:
    """Fetch today's NSE block deals."""
    try:
        session = await _get_nse_session()
        async with session.get(
            "https://www.nseindia.com/api/blockdeals",
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json(content_type=None)
            deals = data if isinstance(data, list) else data.get("data", [])

            result = []
            for d in deals:
                sym = d.get("Symbol", d.get("symbol", "")).strip().upper()
                if sym not in symbols:
                    continue
                result.append({
                    "type": "BLOCK",
                    "exchange": "NSE",
                    "symbol": sym,
                    "client": d.get("Client Name", d.get("clientName", "Unknown")),
                    "buy_sell": d.get("Buy/Sell", d.get("buySell", "?")),
                    "qty": d.get("Quantity Traded", d.get("quantityTraded", 0)),
                    "price": d.get("Trade Price", d.get("tradePrice", 0)),
                    "date": d.get("Date", d.get("date", "")),
                    "remarks": d.get("Remarks", ""),
                })
            return result
    except Exception as e:
        return []

async def fetch_bse_bulk_deals(symbols: set) -> list:
    """Fetch today's BSE bulk deals."""
    try:
        today = datetime.now(IST).strftime("%Y%m%d")
        async with aiohttp.ClientSession(headers=BSE_HEADERS) as session:
            async with session.get(
                f"https://api.bseindia.com/BseIndiaAPI/api/BulkDeal/w?strDate={today}&endDate={today}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)
                deals = data if isinstance(data, list) else data.get("Table", data.get("data", []))

                result = []
                for d in deals:
                    sym = d.get("scrip_cd", d.get("SCRIP_CD", d.get("Symbol", ""))).strip().upper()
                    # BSE uses scrip code, try name match
                    scrip_name = d.get("scrip_name", d.get("SCRIP_NAME", "")).strip().upper()

                    # Match against our symbols
                    matched_sym = sym if sym in symbols else (scrip_name if scrip_name in symbols else None)
                    if not matched_sym:
                        continue

                    result.append({
                        "type": "BULK",
                        "exchange": "BSE",
                        "symbol": matched_sym,
                        "client": d.get("client_name", d.get("CLIENT_NAME", "Unknown")),
                        "buy_sell": d.get("deal_type", d.get("DEAL_TYPE", "?")),
                        "qty": d.get("quantity", d.get("QUANTITY", 0)),
                        "price": d.get("price", d.get("PRICE", 0)),
                        "date": d.get("deal_date", d.get("DEAL_DATE", "")),
                        "remarks": "",
                    })
                return result
    except Exception as e:
        return []

async def fetch_nse_sast(symbols: set) -> list:
    """Fetch recent SAST disclosures from NSE."""
    try:
        session = await _get_nse_session()
        async with session.get(
            "https://www.nseindia.com/api/sast-tran",
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json(content_type=None)
            deals = data if isinstance(data, list) else data.get("data", [])

            result = []
            for d in deals:
                sym = d.get("symbol", d.get("Symbol", "")).strip().upper()
                if sym not in symbols:
                    continue
                result.append({
                    "type": "SAST",
                    "exchange": "NSE",
                    "symbol": sym,
                    "client": d.get("acquirerName", d.get("name", "Unknown")),
                    "buy_sell": "ACQUIRE" if float(d.get("totalSharesAcquired", 0) or 0) > 0 else "DISPOSE",
                    "qty": d.get("totalSharesAcquired", d.get("shares", 0)),
                    "price": d.get("price", 0),
                    "date": d.get("dateOfAcquisition", d.get("date", "")),
                    "remarks": f"Holding after: {d.get('totalShareholdingPostAcquisition', '?')}%",
                })
            return result
    except Exception as e:
        return []

def _format_value(qty, price) -> str:
    try:
        val = float(qty) * float(price)
        if val >= 1e9:
            return f"₹{val/1e9:.1f}B"
        elif val >= 1e7:
            return f"₹{val/1e7:.1f} Cr"
        elif val >= 1e5:
            return f"₹{val/1e5:.1f} L"
        return f"₹{val:,.0f}"
    except:
        return ""

async def process_deals(deals: list, nifty50: dict):
    """Process new deals and fire alerts."""
    global _seen_deals
    now_ist = datetime.now(IST).strftime("%d %b %Y %H:%M")
    fired = 0

    for deal in deals:
        key = _deal_key(deal)
        if key in _seen_deals:
            continue
        _seen_deals.add(key)

        sym = deal["symbol"]
        name = nifty50.get(sym, {}).get("name", sym)
        deal_type = deal["type"]
        exchange = deal["exchange"]
        client = deal["client"]
        buy_sell = deal["buy_sell"].upper()
        qty = deal["qty"]
        price = deal["price"]
        value_str = _format_value(qty, price)
        remarks = deal.get("remarks", "")

        # Format qty
        try:
            qty_fmt = f"{int(float(qty)):,}"
        except:
            qty_fmt = str(qty)

        # Format price
        try:
            price_fmt = f"₹{float(price):,.2f}"
        except:
            price_fmt = str(price)

        emoji = "🐋" if deal_type == "BLOCK" else "📦" if deal_type == "BULK" else "📋"
        bs_emoji = "🟢" if "BUY" in buy_sell or "ACQUI" in buy_sell else "🔴"

        msg = (
            f"{emoji} {deal_type} DEAL on {exchange} | {bs_emoji} {buy_sell} | "
            f"{client} | {qty_fmt} shares @ {price_fmt}"
        )
        if value_str:
            msg += f" | {value_str}"
        if remarks:
            msg += f" | {remarks}"

        alert = {
            "type": "RSI_ALERT",
            "alertType": "WATCH",
            "symbol": sym,
            "name": name,
            "message": msg,
            "timestamp": now_ist,
            "dealType": deal_type,
            "exchange": exchange,
            "client": client,
            "buySell": buy_sell,
            "qty": qty,
            "price": price,
        }

        if _alert_callback:
            await _alert_callback(alert)
        fired += 1
        print(f"🐋 Deal alert: {sym} — {client} {buy_sell} {qty_fmt} @ {price_fmt}")

    return fired

async def deals_monitor_loop(symbols_dict: dict):
    """Main monitoring loop — polls every 2 minutes during market hours."""
    symbols = set(symbols_dict.keys())
    print("🐋 Market deals monitor started")

    while True:
        try:
            if _is_monitoring_hours():
                # Fetch from all sources concurrently
                nse_bulk, nse_block, bse_bulk, sast = await asyncio.gather(
                    fetch_nse_bulk_deals(symbols),
                    fetch_nse_block_deals(symbols),
                    fetch_bse_bulk_deals(symbols),
                    fetch_nse_sast(symbols),
                    return_exceptions=True
                )

                all_deals = []
                for result in [nse_bulk, nse_block, bse_bulk, sast]:
                    if isinstance(result, list):
                        all_deals.extend(result)

                if all_deals:
                    fired = await process_deals(all_deals, symbols_dict)

                await asyncio.sleep(120)  # Poll every 2 minutes
            else:
                # Outside market hours — check every 10 minutes
                # Reset seen deals at midnight
                now = datetime.now(IST)
                if now.hour == 0 and now.minute < 10:
                    _seen_deals.clear()
                    print("🔄 Deal dedup cache reset for new day")
                await asyncio.sleep(600)

        except Exception as e:
            print(f"⚠ Deals monitor error: {e}")
            await asyncio.sleep(120)