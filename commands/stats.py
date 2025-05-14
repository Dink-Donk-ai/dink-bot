# commands/stats.py
import asyncpg
from utils import fmt_btc, fmt_usd, pct
from bot_utils import make_daily_digest
SATOSHI = 100_000_000

async def run(pool: asyncpg.Pool, ctx, price: float, price_cents: int, sma: float, series=None):
    """
    Shows stats and leaderboard.
    """
    # Get all users and their net worth
    async with pool.acquire() as conn:
        users = await conn.fetch("""
            SELECT 
                name,
                cash_c,
                btc_c,
                cash_c + (btc_c * $1 / $2) as net_worth_c
            FROM users 
            ORDER BY net_worth_c DESC
            LIMIT 5
        """, price_cents, SATOSHI)

    # Format leaderboard
    leaderboard = "\n🏆 **Leaderboard**\n"
    for i, user in enumerate(users, 1):
        btc = user['btc_c']
        cash = user['cash_c']
        net = user['net_worth_c']
        leaderboard += (
            f"{i}. **{user['name']}**: {fmt_usd(cash)} + {fmt_btc(btc)} "
            f"= {fmt_usd(net)}\n"
        )

    # Get daily digest if series is provided
    digest = ""
    if series:
        digest = make_daily_digest(series, price, sma, pool)

    # Combine messages
    await ctx.send(f"{digest}\n{leaderboard}")
    return True 