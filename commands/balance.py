# commands/balance.py
import asyncpg
from utils import fmt_btc, fmt_usd, pct
SATOSHI = 100_000_000
INITIAL_CASH_CENTS = 100_000 # Starting cash for new users, in cents

async def run(pool: asyncpg.Pool, ctx, price: float, price_cents: int, sma: float):
    """
    Handles the balance command.
    """
    uid = ctx.author.id
    name = ctx.author.display_name

    async with pool.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT cash_c, btc_c FROM users WHERE uid = $1
        """, uid)
        if not user:
            # Initialize new user
            await conn.execute("""
                INSERT INTO users(uid, name, cash_c, btc_c)
                VALUES($1, $2, $3, $4)
            """, uid, name, INITIAL_CASH_CENTS, 0)
            cash_c, btc_c = INITIAL_CASH_CENTS, 0
        else:
            cash_c, btc_c = user['cash_c'], user['btc_c']

    net_c = cash_c + btc_c * price_cents // SATOSHI
    portfolio_pnl_cents = net_c - INITIAL_CASH_CENTS
    pnl_sign = "+" if portfolio_pnl_cents >= 0 else ""
    pnl_emoji = "📈" if portfolio_pnl_cents >= 0 else "📉"

    balance_message = (
        f"📄 **{name}** balance:\n"
        f"   Cash: {fmt_usd(cash_c)}\n"
        f"   BTC: {fmt_btc(btc_c)} (current value: {fmt_usd(btc_c * price_cents // SATOSHI)})\n"
        f"   **Total Net Worth**: {fmt_usd(net_c)}\n"
        f"   **Portfolio P&L**: {pnl_emoji} {pnl_sign}{fmt_usd(portfolio_pnl_cents)}\n"
        f"   BTC Price: ${price:.0f} ({pct(price, sma):+.1f}% vs SMA30)"
    )
    await ctx.send(balance_message)
    return False