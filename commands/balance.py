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