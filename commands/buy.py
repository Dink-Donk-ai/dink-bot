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
            INSERT INTO users(uid, name, cash_c, btc_c)
            VALUES($1, $2, $3, $4)
            ON CONFLICT(uid) DO NOTHING
        """, uid, name, 100_000, 0)

        # Fetch current balances
        user = await conn.fetchrow("""
            SELECT cash_c, btc_c FROM users WHERE uid = $1
        """, uid)
        cash_c, btc_c = user['cash_c'], user['btc_c']

        if amount_cents <= 0 or amount_cents > cash_c:
            await ctx.send(f"⚠️ **{name}** invalid buy amount! | BTC ${price:.0f} ({pct(price, sma):+.1f}% vs SMA30)")
            return False

        sats = amount_cents * SATOSHI // price_cents
        if sats == 0:
            await ctx.send(f"⚠️ **{name}** amount too small! | BTC ${price:.0f} ({pct(price, sma):+.1f}% vs SMA30)")
            return False

        new_cash = cash_c - amount_cents
        new_btc = btc_c + sats

        # Update balances
        await conn.execute("""
            UPDATE users SET cash_c = $1, btc_c = $2 WHERE uid = $3
        """, new_cash, new_btc, uid)

        # Log the transaction
        await conn.execute("""
            INSERT INTO transactions (uid, name, transaction_type, btc_amount_sats, usd_amount_cents, price_at_transaction_cents)
            VALUES ($1, $2, 'buy', $3, $4, $5)
        """, uid, name, sats, amount_cents, price_cents)

    await ctx.send(f"🆕 **{name}** bought {fmt_btc(sats)} for {fmt_usd(amount_cents)} | BTC ${price:.0f} ({pct(price, sma):+.1f}% vs SMA30)")
    return True