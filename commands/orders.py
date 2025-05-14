# commands/orders.py
import asyncpg
import discord
from utils import fmt_btc, fmt_usd, pct # We'll need these for messages
from discord.ext import commands # Using this for easier context if needed later

SATOSHI = 100_000_000
INITIAL_CASH_CENTS = 100_000 # May not be needed here directly but good for reference

# Placeholder for order processing logic that might be shared
# async def _process_order_placement():
#     pass

async def place_buy_order(pool: asyncpg.Pool, ctx, btc_amount_str: str, limit_price_str: str, current_market_price_cents: int):
    """Handles !buyorder <amount_btc> <price_usd>"""
    uid = ctx.author.id
    name = ctx.author.display_name

    try:
        btc_amount_float = float(btc_amount_str)
        if btc_amount_float <= 0:
            raise ValueError("BTC amount must be positive.")
        order_btc_sats = int(round(btc_amount_float * SATOSHI))
        if order_btc_sats == 0:
            await ctx.send(embed=discord.Embed(title="⚠️ Order Error", description="BTC amount is too small, rounds to 0 satoshis.", color=discord.Color.red()))
            return False

        limit_price_float = float(limit_price_str)
        if limit_price_float <= 0:
            raise ValueError("Limit price must be positive.")
        order_limit_price_cents = int(round(limit_price_float * 100))
        if order_limit_price_cents == 0:
            await ctx.send(embed=discord.Embed(title="⚠️ Order Error", description="Limit price is too small, rounds to 0 cents.", color=discord.Color.red()))
            return False

    except ValueError as e:
        await ctx.send(embed=discord.Embed(title="⚠️ Invalid Input", description=f"Please check your amounts and prices. {e}", color=discord.Color.red()))
        return False

    order_usd_value_cents = order_btc_sats * order_limit_price_cents // SATOSHI
    if order_usd_value_cents == 0:
        await ctx.send(embed=discord.Embed(title="⚠️ Order Error", description="Total order value is too small (less than 1 cent).", color=discord.Color.red()))
        return False

    async with pool.acquire() as conn:
        async with conn.transaction():
            user = await conn.fetchrow("SELECT cash_c, btc_c, cash_held_c, btc_held_c FROM users WHERE uid = $1 FOR UPDATE", uid)
            if not user:
                # This case should ideally be handled by user creation on first command, but as a fallback:
                await conn.execute("INSERT INTO users(uid, name, cash_c, btc_c) VALUES($1, $2, $3, $4)", uid, name, 0, 0) # Start with 0 if new during order
                user_cash_c = 0
            else:
                user_cash_c = user['cash_c']

            if user_cash_c < order_usd_value_cents:
                embed = discord.Embed(title="❌ Insufficient Funds", color=discord.Color.red())
                embed.add_field(name="Required", value=fmt_usd(order_usd_value_cents), inline=True)
                embed.add_field(name="Available", value=fmt_usd(user_cash_c), inline=True)
                await ctx.send(embed=embed)
                return False # Transaction will be rolled back

            # Hold funds
            new_cash_c = user_cash_c - order_usd_value_cents
            new_cash_held_c = (user['cash_held_c'] if user else 0) + order_usd_value_cents
            
            await conn.execute("UPDATE users SET cash_c = $1, cash_held_c = $2 WHERE uid = $3", 
                               new_cash_c, new_cash_held_c, uid)

            # Create order
            await conn.execute("""
                INSERT INTO orders (uid, name, order_type, btc_amount_sats, limit_price_cents, usd_value_cents, status)
                VALUES ($1, $2, 'buy', $3, $4, $5, 'open')
            """, uid, name, order_btc_sats, order_limit_price_cents, order_usd_value_cents)
    
    embed = discord.Embed(title="✅ Buy Order Placed", color=discord.Color.green())
    embed.add_field(name="User", value=name, inline=False)
    embed.add_field(name="Amount", value=fmt_btc(order_btc_sats), inline=True)
    embed.add_field(name="Limit Price", value=fmt_usd(order_limit_price_cents), inline=True)
    embed.add_field(name="Estimated Cost", value=fmt_usd(order_usd_value_cents), inline=False)
    embed.set_footer(text=f"Order is now open. Current market price: {fmt_usd(current_market_price_cents)}")
    await ctx.send(embed=embed)
    return True

async def place_sell_order(pool: asyncpg.Pool, ctx, btc_amount_str: str, limit_price_str: str, current_market_price_cents: int):
    """Handles !sellorder <amount_btc> <price_usd>"""
    uid = ctx.author.id
    name = ctx.author.display_name

    try:
        btc_amount_float = float(btc_amount_str)
        if btc_amount_float <= 0:
            raise ValueError("BTC amount must be positive.")
        order_btc_sats = int(round(btc_amount_float * SATOSHI))
        if order_btc_sats == 0:
            await ctx.send(embed=discord.Embed(title="⚠️ Order Error", description="BTC amount is too small, rounds to 0 satoshis.", color=discord.Color.red()))
            return False

        limit_price_float = float(limit_price_str)
        if limit_price_float <= 0:
            raise ValueError("Limit price must be positive.")
        order_limit_price_cents = int(round(limit_price_float * 100))
        if order_limit_price_cents == 0:
            await ctx.send(embed=discord.Embed(title="⚠️ Order Error", description="Limit price is too small, rounds to 0 cents.", color=discord.Color.red()))
            return False
            
    except ValueError as e:
        await ctx.send(embed=discord.Embed(title="⚠️ Invalid Input", description=f"Please check your amounts and prices. {e}", color=discord.Color.red()))
        return False

    # For sell orders, usd_value_cents is the expected proceeds at the limit price
    order_usd_value_cents = order_btc_sats * order_limit_price_cents // SATOSHI
    if order_usd_value_cents == 0: # Should be caught by limit_price_cents or order_btc_sats checks, but good to have
        await ctx.send(embed=discord.Embed(title="⚠️ Order Error", description="Total expected order value is too small (less than 1 cent).", color=discord.Color.red()))
        return False

    async with pool.acquire() as conn:
        async with conn.transaction():
            user = await conn.fetchrow("SELECT cash_c, btc_c, cash_held_c, btc_held_c FROM users WHERE uid = $1 FOR UPDATE", uid)
            if not user:
                # Ensure user exists, though they wouldn't have BTC to sell if brand new.
                await conn.execute("INSERT INTO users(uid, name, cash_c, btc_c) VALUES($1, $2, $3, $4)", uid, name, INITIAL_CASH_CENTS, 0)
                user_btc_c = 0 
            else:
                user_btc_c = user['btc_c']

            if user_btc_c < order_btc_sats:
                embed = discord.Embed(title="❌ Insufficient BTC", color=discord.Color.red())
                embed.add_field(name="Required", value=fmt_btc(order_btc_sats), inline=True)
                embed.add_field(name="Available", value=fmt_btc(user_btc_c), inline=True)
                await ctx.send(embed=embed)
                return False # Transaction will be rolled back

            # Hold BTC
            new_btc_c = user_btc_c - order_btc_sats
            new_btc_held_c = (user['btc_held_c'] if user else 0) + order_btc_sats
            
            await conn.execute("UPDATE users SET btc_c = $1, btc_held_c = $2 WHERE uid = $3", 
                               new_btc_c, new_btc_held_c, uid)

            # Create order
            await conn.execute("""
                INSERT INTO orders (uid, name, order_type, btc_amount_sats, limit_price_cents, usd_value_cents, status)
                VALUES ($1, $2, 'sell', $3, $4, $5, 'open')
            """, uid, name, order_btc_sats, order_limit_price_cents, order_usd_value_cents)

    embed = discord.Embed(title="✅ Sell Order Placed", color=discord.Color.orange()) # Orange for sell orders
    embed.add_field(name="User", value=name, inline=False)
    embed.add_field(name="Amount", value=fmt_btc(order_btc_sats), inline=True)
    embed.add_field(name="Limit Price", value=fmt_usd(order_limit_price_cents), inline=True)
    embed.add_field(name="Expected Value", value=fmt_usd(order_usd_value_cents), inline=False)
    embed.set_footer(text=f"Order is now open. Current market price: {fmt_usd(current_market_price_cents)}")
    await ctx.send(embed=embed)
    return True

async def cancel_order(pool: asyncpg.Pool, ctx, order_id_str: str):
    """Handles !cancelorder <order_id>"""
    uid = ctx.author.id
    name = ctx.author.display_name

    try:
        order_id = int(order_id_str)
        if order_id <= 0:
            raise ValueError("Order ID must be a positive integer.")
    except ValueError:
        await ctx.send(embed=discord.Embed(title="⚠️ Invalid Input", description="Order ID must be a valid positive number.", color=discord.Color.red()))
        return False

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Fetch the order and lock the user row to prevent race conditions with order execution
            order = await conn.fetchrow("SELECT * FROM orders WHERE order_id = $1 AND uid = $2 FOR UPDATE", order_id, uid)

            if not order:
                await ctx.send(embed=discord.Embed(title="❌ Order Not Found", description=f"Order ID {order_id} not found or you do not own it.", color=discord.Color.red()))
                return False # Rolls back

            if order['status'] != 'open':
                await ctx.send(embed=discord.Embed(title="❌ Cannot Cancel Order", description=f"Order ID {order_id} is already {order['status']}. Only 'open' orders can be cancelled.", color=discord.Color.red()))
                return False # Rolls back

            # Update order status to cancelled
            await conn.execute("UPDATE orders SET status = 'cancelled' WHERE order_id = $1", order_id)

            # Release held funds/BTC by updating user's balance
            # Lock the user row directly for update
            user = await conn.fetchrow("SELECT cash_c, btc_c, cash_held_c, btc_held_c FROM users WHERE uid = $1 FOR UPDATE", uid)
            if not user: # Should not happen if order exists for user
                await ctx.send(embed=discord.Embed(title="❌ Error", description="User not found while trying to release funds.", color=discord.Color.red()))
                return False # Rolls back

            if order['order_type'] == 'buy':
                released_cash = order['usd_value_cents']
                new_cash_c = user['cash_c'] + released_cash
                new_cash_held_c = user['cash_held_c'] - released_cash
                await conn.execute("UPDATE users SET cash_c = $1, cash_held_c = $2 WHERE uid = $3",
                                   new_cash_c, new_cash_held_c, uid)
            elif order['order_type'] == 'sell':
                released_btc = order['btc_amount_sats']
                new_btc_c = user['btc_c'] + released_btc
                new_btc_held_c = user['btc_held_c'] - released_btc
                await conn.execute("UPDATE users SET btc_c = $1, btc_held_c = $2 WHERE uid = $3",
                                   new_btc_c, new_btc_held_c, uid)
            
            # Transaction committed automatically if no exceptions

    embed = discord.Embed(title="✅ Order Cancelled", color=discord.Color.greyple())
    embed.add_field(name="Order ID", value=str(order_id), inline=False)
    embed.add_field(name="Type", value=order['order_type'].capitalize(), inline=True)
    embed.add_field(name="Amount", value=fmt_btc(order['btc_amount_sats']) if order['order_type'] == 'sell' else fmt_usd(order['usd_value_cents']), inline=True)
    await ctx.send(embed=embed)
    return True

async def list_my_orders(pool: asyncpg.Pool, ctx):
    """Handles !myorders"""
    print(f"[DEBUG commands/orders.py] list_my_orders function called by: {ctx.author.name}") # DEBUG LOG
    uid = ctx.author.id
    name = ctx.author.display_name

    async with pool.acquire() as conn:
        open_orders = await conn.fetch("""
            SELECT order_id, order_type, btc_amount_sats, limit_price_cents, usd_value_cents, timestamp, status
            FROM orders 
            WHERE uid = $1 AND status = 'open'
            ORDER BY timestamp DESC
        """, uid)

    if not open_orders:
        embed = discord.Embed(
            title=f"📂 {name}'s Open Orders",
            description="You have no open orders currently.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        return True

    embed = discord.Embed(
        title=f"📂 {name}'s Open Orders",
        color=discord.Color.blue()
    )

    for order in open_orders:
        order_id = order['order_id']
        order_type = order['order_type'].capitalize()
        btc_sats = order['btc_amount_sats']
        limit_cents = order['limit_price_cents']
        value_cents = order['usd_value_cents']
        # timestamp_val = fmt_datetime_local(order['timestamp']) # utils.py needs fmt_datetime_local to be imported or defined
        # For now, using basic string conversion for timestamp if fmt_datetime_local is not available here
        timestamp_val = order['timestamp'].strftime("%Y-%m-%d %H:%M:%S UTC")

        field_name = f"ID: {order_id} ({order_type}) - Placed: {timestamp_val}"
        field_value = f"Amount: {fmt_btc(btc_sats)} | Limit: {fmt_usd(limit_cents)} | Value: {fmt_usd(value_cents)}"
        embed.add_field(name=field_name, value=field_value, inline=False)
    
    if len(embed.fields) == 0: # Should be caught by `if not open_orders` but as a safeguard
        embed.description = "You have no open orders currently."

    await ctx.send(embed=embed)
    return True

# We might need a main 'run' function or register these commands differently
# For now, these are individual async functions.
# We will integrate them into the main command processing logic later. 