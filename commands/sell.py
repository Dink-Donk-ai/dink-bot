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
            INSERT INTO users(uid, name, cash_c, btc_c)
            VALUES($1, $2, $3, $4)
            ON CONFLICT(uid) DO NOTHING
        """, uid, name, 100_000, 0)

        # Fetch current balances
        user = await conn.fetchrow("""
            SELECT cash_c, btc_c FROM users WHERE uid = $1
        """, uid)
        cash_c, btc_c = user['cash_c'], user['btc_c']

    # Determine sats to sell
    try:
        if arg.lower() == "all":
            sats = btc_c
        else:
            val = float(arg)
            if val < 1:
                sats = int(round(val * SATOSHI))
            else:
                sats = int(round(val * 100)) * SATOSHI // price_cents
    except ValueError:
        sats = -1

    if sats <= 0 or sats > btc_c:
        await ctx.send(f"⚠️ **{name}** invalid sell amount! | BTC ${price:.0f} ({pct(price, sma):+.1f}% vs SMA30)")
        return False

    usd_out = sats * price_cents // SATOSHI
    new_btc = btc_c - sats
    new_cash = cash_c + usd_out

    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE users SET cash_c = $1, btc_c = $2 WHERE uid = $3
        """, new_cash, new_btc, uid)

        # Log the transaction
        await conn.execute("""
            INSERT INTO transactions (uid, name, transaction_type, btc_amount_sats, usd_amount_cents, price_at_transaction_cents)
            VALUES ($1, $2, 'sell', $3, $4, $5)
        """, uid, name, sats, usd_out, price_cents)

    await ctx.send(f"💰 **{name}** sold {fmt_btc(sats)} for {fmt_usd(usd_out)} | BTC ${price:.0f} ({pct(price, sma):+.1f}% vs SMA30)")
    return True