"""
Shared utility functions for the Discord bot
"""
import statistics
from datetime import date
import aiohttp
from utils import fmt_btc, fmt_usd, pct
from commands import buy, sell, balance

# Constants
START_CASH = 100_000
DIGEST_HOUR = 8
BUY_DISCOUNT = 0.90
SELL_PREMIUM = 1.15

COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    "?vs_currency=usd&days=90&interval=daily"
)

async def fetch_price_data():
    """Fetch current BTC price and calculate SMA"""
    async with aiohttp.ClientSession() as session:
        async with session.get(COINGECKO_URL) as response:
            if response.status == 200:
                data = await response.json()
                series = [p for _, p in data["prices"]]
                price = series[-1]
                sma30 = sum(series[-30:]) / 30
                return series, price, sma30
    return None, None, None

def make_daily_digest(series, today, sma30, pool):
    """Generate daily market digest message"""
    yday, week = series[-2], series[-8]
    vol30 = statistics.pstdev(series[-30:])
    lo90, hi90 = min(series), max(series)
    gap = pct(today, sma30)
    trend = "📈" if gap > 0 else "📉"
    
    return (
        f"📊 **BTC Daily Digest — {date.today()}**\n"
        f"Price: **${today:,.0f}** ({pct(today,yday):+.2f}% 24h, {pct(today,week):+.2f}% 7d) {trend}\n"
        f"SMA30: ${sma30:,.0f} (gap {gap:+.1f}%)\n"
        f"30‑day σ: ${vol30:,.0f}\n"
        f"90‑day range: ${lo90:,.0f} → ${hi90:,.0f}\n"
    )

async def process_command(pool, ctx, cmd, arg, price, price_cents, sma30):
    """Process a single command"""
    if cmd == "buy":
        try:
            amount_cents = int(float(arg) * 100) if arg else None
            return await buy(pool, ctx, amount_cents, price, price_cents, sma30)
        except ValueError:
            return False
            
    elif cmd == "sell":
        return await sell(pool, ctx, arg or "all", price, price_cents, sma30)
            
    elif cmd == "balance":
        return await balance(pool, ctx, price, price_cents, sma30)
    
    return False 