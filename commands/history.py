# commands/history.py
import asyncpg
from utils import fmt_btc, fmt_usd, fmt_datetime_local

SATOSHI = 100_000_000

async def run(pool: asyncpg.Pool, ctx, price: float, price_cents: int, sma: float):
    """
    Shows the user's last 10 transactions.
    """
    uid = ctx.author.id
    name = ctx.author.display_name

    async with pool.acquire() as conn:
        transactions = await conn.fetch("""
            SELECT transaction_type, btc_amount_sats, usd_amount_cents, price_at_transaction_cents, timestamp
            FROM transactions
            WHERE uid = $1
            ORDER BY timestamp DESC
            LIMIT 10
        """, uid)

    if not transactions:
        await ctx.send(f"📜 **{name}**, you have no transaction history yet.")
        return True

    history_message = f"📜 **{name}'s Last 10 Transactions:**\n\n"
    for tx in transactions:
        tx_type = tx['transaction_type'].capitalize()
        btc_val = fmt_btc(tx['btc_amount_sats'])
        usd_val = fmt_usd(tx['usd_amount_cents'])
        price_val = fmt_usd(tx['price_at_transaction_cents'])
        timestamp_val = fmt_datetime_local(tx['timestamp'])

        history_message += f"**{tx_type}**: {btc_val} for {usd_val} (Price: {price_val})\n"
        history_message += f"  *At: {timestamp_val}*\n"

    await ctx.send(history_message)
    return True 