# commands/buy.py
from discord import TextChannel
import asyncpg
from utils import fmt_btc, fmt_usd, pct
SATOSHI = 100_000_000

async def run(pool: asyncpg.Pool, ctx, amount_cents: int, price: float, price_cents: int, sma: float):
    """
    Handles the buy command.
    """
    uid = ctx.author.id
    name = ctx.author.display_name

    async with pool.acquire() as conn:
        # Ensure user exists
        await conn.execute("""
            INSERT INTO users(uid, name, cash_c, btc_s)
            VALUES($1, $2, $3, $4)
            ON CONFLICT(uid) DO NOTHING
        """, uid, name, 100_000, 0)

        # Fetch current balances
        user = await conn.fetchrow("""
            SELECT cash_c, btc_s FROM users WHERE uid = $1
        """, uid)
        cash_c, btc_s = user['cash_c'], user['btc_s']

        if amount_cents <= 0 or amount_cents > cash_c:
            await ctx.send(f"⚠️ **{name}** invalid buy amount! | BTC ${price:.0f} ({pct(price, sma):+.1f}% vs SMA30)")
            return False

        sats = amount_cents * SATOSHI // price_cents
        if sats == 0:
            await ctx.send(f"⚠️ **{name}** amount too small! | BTC ${price:.0f} ({pct(price, sma):+.1f}% vs SMA30)")
            return False

        new_cash = cash_c - amount_cents
        new_btc = btc_s + sats

        # Update balances
        await conn.execute("""
            UPDATE users SET cash_c = $1, btc_s = $2 WHERE uid = $3
        """, new_cash, new_btc, uid)

    await ctx.send(f"🆕 **{name}** bought {fmt_btc(sats)} for {fmt_usd(amount_cents)} | BTC ${price:.0f} ({pct(price, sma):+.1f}% vs SMA30)")
    return True

# commands/sell.py
from discord import TextChannel
import asyncpg
from utils import fmt_btc, fmt_usd, pct
SATOSHI = 100_000_000

async def run(pool: asyncpg.Pool, ctx, arg: str, price: float, price_cents: int, sma: float):
    """
    Handles the sell command.
    """
    uid = ctx.author.id
    name = ctx.author.display_name

    async with pool.acquire() as conn:
        # Ensure user exists
        await conn.execute("""
            INSERT INTO users(uid, name, cash_c, btc_s)
            VALUES($1, $2, $3, $4)
            ON CONFLICT(uid) DO NOTHING
        """, uid, name, 100_000, 0)

        # Fetch current balances
        user = await conn.fetchrow("""
            SELECT cash_c, btc_s FROM users WHERE uid = $1
        """, uid)
        cash_c, btc_s = user['cash_c'], user['btc_s']

    # Determine sats to sell
    try:
        if arg.lower() == "all":
            sats = btc_s
        else:
            val = float(arg)
            if val < 1:
                sats = int(round(val * SATOSHI))
            else:
                sats = int(round(val * 100)) * SATOSHI // price_cents
    except ValueError:
        sats = -1

    if sats <= 0 or sats > btc_s:
        await ctx.send(f"⚠️ **{name}** invalid sell amount! | BTC ${price:.0f} ({pct(price, sma):+.1f}% vs SMA30)")
        return False

    usd_out = sats * price_cents // SATOSHI
    new_btc = btc_s - sats
    new_cash = cash_c + usd_out

    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE users SET cash_c = $1, btc_s = $2 WHERE uid = $3
        """, new_cash, new_btc, uid)

    await ctx.send(f"💰 **{name}** sold {fmt_btc(sats)} for {fmt_usd(usd_out)} | BTC ${price:.0f} ({pct(price, sma):+.1f}% vs SMA30)")
    return True

# commands/balance.py
import asyncpg
from utils import fmt_btc, fmt_usd, pct
SATOSHI = 100_000_000

async def run(pool: asyncpg.Pool, ctx, price: float, price_cents: int, sma: float):
    """
    Handles the balance command.
    """
    uid = ctx.author.id
    name = ctx.author.display_name

    async with pool.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT cash_c, btc_s FROM users WHERE uid = $1
        """, uid)
        if not user:
            # Initialize new user
            await conn.execute("""
                INSERT INTO users(uid, name, cash_c, btc_s)
                VALUES($1, $2, $3, $4)
            """, uid, name, 100_000, 0)
            cash_c, btc_s = 100_000, 0
        else:
            cash_c, btc_s = user['cash_c'], user['btc_s']

    net_c = cash_c + btc_s * price_cents // SATOSHI
    await ctx.send(
        f"📄 **{name}** balance: {fmt_usd(cash_c)} cash, "
        f"{fmt_btc(btc_s)} (net {fmt_usd(net_c)}) | BTC ${price:.0f} ({pct(price, sma):+.1f}% vs SMA30)"
    )
    return False

# commands/__init__.py
from .buy import run as buy
from .sell import run as sell
from .balance import run as balance