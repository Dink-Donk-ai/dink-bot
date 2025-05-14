#!/usr/bin/env python3
"""
Dink‑Bot - A Discord bot for simulated Bitcoin trading
"""
import json
import statistics
from datetime import datetime, timezone, date
import aiohttp
import asyncio
from db import init_db

from config import settings
from commands import buy, sell, balance
from utils import fmt_btc, fmt_usd, pct
from discord_client import start_discord_client

# Constants from original bot
START_CASH = 100_000  # Moved from commands to here as a global constant
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
            processed_arg = arg
            if arg and ',' in arg and '.' not in arg: # Basic check for comma as decimal separator
                processed_arg = arg.replace(',', '.')
            amount_cents = int(float(processed_arg) * 100) if processed_arg else None
            return await buy.run(pool, ctx, amount_cents, price, price_cents, sma30)
        except ValueError:
            await ctx.send(f"⚠️ Invalid amount for `!buy`. Please use a number like `100` or `100.50`.")
            return False # Indicate failure
            
    elif cmd == "sell":
        return await sell.run(pool, ctx, arg or "all", price, price_cents, sma30)
            
    elif cmd == "balance":
        return await balance.run(pool, ctx, price, price_cents, sma30)
    
    return False

async def main():
    """Main entry point"""
    try:
        # Initialize database connection using init_db from db.py
        pool = await init_db(settings.database_url)
        if not pool:
            print("Failed to create database pool via init_db")
            return

        # Start Discord client
        await start_discord_client(pool)

    except Exception as e:
        print(f"Fatal error: {e}")
        raise
    finally:
        if pool:
            await pool.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        raise