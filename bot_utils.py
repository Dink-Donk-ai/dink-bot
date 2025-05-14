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
                if not data or "prices" not in data or not data["prices"]:
                    print("Price data from Coingecko is empty or malformed.")
                    return None, None, None, None, None, None
                series = [p for _, p in data["prices"]]
                price = series[-1] if series else None
                if price is None:
                    print("Could not determine current price from series.")
                    return None, None, None, None, None, None
                sma30 = sum(series[-30:]) / 30 if len(series) >= 30 else None
                sma90 = sum(series) / len(series) if series else None 
                volume24h = data["total_volumes"][-1][1] if data.get("total_volumes") and data["total_volumes"] else None
                market_cap = data["market_caps"][-1][1] if data.get("market_caps") and data["market_caps"] else None
                return series, price, sma30, sma90, volume24h, market_cap
    print("Failed to fetch price data from Coingecko, HTTP error.")
    return None, None, None, None, None, None

async def process_command(pool, ctx, cmd, arg, price, price_cents, sma30, series, sma90, volume24h, market_cap, client):
    """Process a single command"""
    print(f"[DEBUG bot_utils.py process_command] Received cmd: '{cmd}', arg: '{arg}' for user: {ctx.author.name}") # DEBUG LOG

    if cmd == "buy":
        try:
            # Ensure arg is processed correctly for buy.run which expects amount_cents
            processed_arg = arg
            if arg and ',' in arg and '.' not in arg: 
                processed_arg = arg.replace(',', '.')
            amount_cents = int(float(processed_arg) * 100) if processed_arg else None
            return await buy.run(pool, ctx, amount_cents, price, price_cents, sma30)
        except ValueError:
            await ctx.send(f"⚠️ Invalid amount for `!buy`. Please use a number like `100` or `100.50`.")
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
        return await admin(pool, ctx, admin_args, client)

    # New order commands
    elif cmd == "buyorder":
        if not arg or len(arg.split()) != 2:
            await ctx.send("Usage: `!buyorder <usd_amount_to_spend> <price_usd>`")
            return False
        usd_amount_to_spend_str, limit_price_str = arg.split()
        return await place_buy_order(pool, ctx, usd_amount_to_spend_str, limit_price_str, price_cents)

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
        print(f"[DEBUG bot_utils.py] Entered 'myorders' processing branch for user: {ctx.author.name}") # DEBUG LOG
        return await list_my_orders(pool, ctx)
    
    return False 