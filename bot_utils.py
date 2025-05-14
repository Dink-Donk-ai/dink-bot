"""
Shared utility functions for the Discord bot
"""
import aiohttp
from utils import fmt_btc, fmt_usd, pct, make_daily_digest
from commands import buy, sell, balance, stats, help, history, admin
# Import new order commands
from commands.orders import (
    place_buy_order,
    place_sell_order,
    cancel_order,
    list_my_orders
)

# Constants
START_CASH = 100_000
DIGEST_HOUR = 8
HODL_BUY_DIP_THRESHOLD = 0.30 # Percentage drop from 90-day high to trigger HODL alert

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
                sma90 = sum(series) / len(series) if series else 0 # Calculate SMA90
                volume24h = data["total_volumes"][-1][1] if data["total_volumes"] else 0 # Get last 24h volume
                market_cap = data["market_caps"][-1][1] if data["market_caps"] else 0 # Get last market cap
                return series, price, sma30, sma90, volume24h, market_cap
    return None, None, None, None, None, None

async def process_command(pool, ctx, cmd, arg, price, price_cents, sma30, series=None, sma90=None, volume24h=None, market_cap=None):
    """Process a single command"""
    if cmd == "buy":
        try:
            amount_cents = int(float(arg) * 100) if arg else None
            return await buy.run(pool, ctx, amount_cents, price, price_cents, sma30)
        except ValueError:
            return False
            
    elif cmd == "sell":
        return await sell.run(pool, ctx, arg or "all", price, price_cents, sma30)
            
    elif cmd == "balance":
        return await balance.run(pool, ctx, price, price_cents, sma30)
        
    elif cmd == "stats":
        return await stats.run(pool, ctx, price, price_cents, sma30, series, sma90, volume24h, market_cap)
        
    elif cmd == "help":
        return await help.run(pool, ctx, price, price_cents, sma30)
    
    elif cmd == "history":
        return await history.run(pool, ctx, price, price_cents, sma30)
    
    elif cmd == "admin":
        admin_args = arg.split() if arg else []
        return await admin.run(pool, ctx, admin_args)

    # New order commands
    elif cmd == "buyorder":
        if not arg or len(arg.split()) != 2:
            await ctx.send("Usage: `!buyorder <amount_btc> <price_usd>`")
            return False
        btc_amount_str, limit_price_str = arg.split()
        return await place_buy_order(pool, ctx, btc_amount_str, limit_price_str, price_cents)

    elif cmd == "sellorder":
        if not arg or len(arg.split()) != 2:
            await ctx.send("Usage: `!sellorder <amount_btc> <price_usd>`")
            return False
        btc_amount_str, limit_price_str = arg.split()
        return await place_sell_order(pool, ctx, btc_amount_str, limit_price_str, price_cents)

    elif cmd == "cancelorder":
        if not arg:
            await ctx.send("Usage: `!cancelorder <order_id>`")
            return False
        return await cancel_order(pool, ctx, arg)

    elif cmd == "myorders":
        return await list_my_orders(pool, ctx)
    
    return False 