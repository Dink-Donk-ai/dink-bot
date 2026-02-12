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
from commands.birthdays import handle_birthday_command

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

async def update_daily_price_stats(pool, price: float, volume24h: float = None, market_cap: float = None):
    """Update daily price statistics including proper 90-day high/low tracking"""
    from datetime import date, timedelta
    
    today = date.today()
    price_cents = int(price * 100)
    volume24h_cents = int(volume24h * 100) if volume24h else None
    market_cap_cents = int(market_cap * 100) if market_cap else None
    
    async with pool.acquire() as conn:
        # Check if we already have an entry for today
        existing_entry = await conn.fetchrow(
            "SELECT * FROM daily_price_stats WHERE date = $1", today
        )
        
        if existing_entry:
            # Update today's entry with current price
            current_high_90d = existing_entry['high_90d_cents']
            current_low_90d = existing_entry['low_90d_cents']
            
            # Update high/low if current price is new extreme
            new_high_90d = max(current_high_90d, price_cents)
            new_low_90d = min(current_low_90d, price_cents)
            
            await conn.execute("""
                UPDATE daily_price_stats 
                SET price_cents = $1, high_90d_cents = $2, low_90d_cents = $3, 
                    volume_24h_usd = $4, market_cap_usd = $5, updated_at = now()
                WHERE date = $6
            """, price_cents, new_high_90d, new_low_90d, volume24h_cents, market_cap_cents, today)
            
            return new_high_90d, new_low_90d
        else:
            # New day - calculate 90-day high/low from historical data
            ninety_days_ago = today - timedelta(days=90)
            
            # Get all prices from the last 90 days (including today's price)
            historical_data = await conn.fetch("""
                SELECT price_cents FROM daily_price_stats 
                WHERE date >= $1 AND date < $2
                ORDER BY date DESC
            """, ninety_days_ago, today)
            
            # Include today's price in the calculation
            all_prices = [price_cents] + [row['price_cents'] for row in historical_data]
            
            high_90d = max(all_prices)
            low_90d = min(all_prices)
            
            # Insert new entry
            await conn.execute("""
                INSERT INTO daily_price_stats 
                (date, price_cents, high_90d_cents, low_90d_cents, volume_24h_usd, market_cap_usd)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, today, price_cents, high_90d, low_90d, volume24h_cents, market_cap_cents)
            
            return high_90d, low_90d

async def initialize_daily_price_stats_if_empty(pool, series, price, volume24h=None, market_cap=None):
    """Initialize daily price stats table with historical data if it's empty"""
    from datetime import date, timedelta
    import aiohttp
    
    async with pool.acquire() as conn:
        # Check if table is empty
        count = await conn.fetchval("SELECT COUNT(*) FROM daily_price_stats")
        if count > 0:
            print("Daily price stats table already has data, skipping initialization.")
            return
        
        print("Initializing daily price stats table with historical data...")
        
        # If we have series data from CoinGecko (90 days), use it to populate historical records
        if series and len(series) > 0:
            today = date.today()
            
            # Insert records for each day in the series, working backwards
            for i, daily_price in enumerate(reversed(series)):
                record_date = today - timedelta(days=len(series) - 1 - i)
                price_cents = int(daily_price * 100)
                
                # Calculate rolling 90-day high/low up to this point
                # This gives us the high/low for each historical day
                relevant_prices = series[max(0, len(series) - 90 - i):len(series) - i] if i > 0 else series[:len(series)]
                hi90_cents = int(max(relevant_prices) * 100)
                lo90_cents = int(min(relevant_prices) * 100)
                
                volume_cents = int(volume24h * 100) if volume24h else None
                market_cap_cents = int(market_cap * 100) if market_cap else None
                
                await conn.execute("""
                    INSERT INTO daily_price_stats 
                    (date, price_cents, high_90d_cents, low_90d_cents, volume_24h_usd, market_cap_usd)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, record_date, price_cents, hi90_cents, lo90_cents, volume_cents, market_cap_cents)
            
            print(f"Initialized daily price stats with {len(series)} historical records.")
        else:
            # Fallback: just insert today's data
            today = date.today()
            price_cents = int(price * 100)
            volume_cents = int(volume24h * 100) if volume24h else None
            market_cap_cents = int(market_cap * 100) if market_cap else None
            
            await conn.execute("""
                INSERT INTO daily_price_stats 
                (date, price_cents, high_90d_cents, low_90d_cents, volume_24h_usd, market_cap_usd)
                VALUES ($1, $2, $2, $2, $3, $4)
            """, today, price_cents, volume_cents, market_cap_cents)
            
            print("Initialized daily price stats with current price data only.")

async def process_command(pool, ctx, cmd, arg, price, price_cents, sma30, series, sma90, volume24h, market_cap, client):
    """Process a single command"""
    if cmd == "buy":
        try:
            # Ensure arg is processed correctly for buy.run which expects amount_cents
            processed_arg = arg
            if arg and ',' in arg and '.' not in arg: 
                processed_arg = arg.replace(',', '.')
            amount_cents = int(float(processed_arg) * 100) if processed_arg else None
            return await buy(pool, ctx, amount_cents, price, price_cents, sma30)
        except ValueError:
            await ctx.send(f"⚠️ Invalid amount for `!buy`. Please use a number like `100` or `100.50`.")
            return False
            
    elif cmd == "sell":
        return await sell(pool, ctx, arg or "all", price, price_cents, sma30)
            
    elif cmd == "balance":
        return await balance(pool, ctx, price, price_cents, sma30)
        
    elif cmd == "stats":
        return await stats(pool, ctx, price, price_cents, sma30, series, sma90, volume24h, market_cap)
        
    elif cmd == "help":
        return await help(pool, ctx, price, price_cents, sma30)
    
    elif cmd == "history":
        return await history(pool, ctx, price, price_cents, sma30)
    
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
        return await list_my_orders(pool, ctx)

    elif cmd == "birthday":
        return await handle_birthday_command(pool, ctx, arg, client)
    
    return False 