"""
Shared utility functions for the Discord bot
"""
import aiohttp
from utils import fmt_btc, fmt_usd, pct, make_daily_digest
from commands import buy, sell, balance, stats, help, history, admin

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
                return series, price, sma30
    return None, None, None

async def process_command(pool, ctx, cmd, arg, price, price_cents, sma30, series=None):
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
        
    elif cmd == "stats":
        return await stats(pool, ctx, price, price_cents, sma30, series)
        
    elif cmd == "help":
        return await help(pool, ctx, price, price_cents, sma30)
    
    elif cmd == "history":
        return await history(pool, ctx, price, price_cents, sma30)
    
    elif cmd == "admin":
        # The admin command expects a list of arguments: [sub_command, target_user, ...values]
        # The 'arg' here is the string of all arguments after '!admin '
        admin_args = arg.split() if arg else []
        return await admin(pool, ctx, admin_args)
    
    return False 