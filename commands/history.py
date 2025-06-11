# commands/history.py
import asyncpg
from utils import fmt_btc, fmt_usd, fmt_datetime_local
import discord

SATOSHI = 100_000_000

async def run(pool: asyncpg.Pool, ctx, price: float, price_cents: int, sma: float):
    """
    Shows the user's last 10 transactions.
    """
    uid = ctx.author.id
    name = ctx.author.display_name
    
    # While price data isn't directly used for calculations in this command,
    # check it for consistency with other commands
    if price_cents is None or price_cents <= 0:
        # For history we can still show results even without current price
        price_info = "⚠️ Note: Current price data is unavailable."
    else:
        price_info = f"Current BTC Price: ${price:,.0f}"

    async with pool.acquire() as conn:
        transactions = await conn.fetch("""
            SELECT transaction_type, btc_amount_sats, usd_amount_cents, price_at_transaction_cents, timestamp
            FROM transactions
            WHERE uid = $1
            ORDER BY timestamp DESC
            LIMIT 10
        """, uid)

    if not transactions:
        embed = discord.Embed(
            title=f"📜 {name}'s Transaction History",
            description="You have no transaction history yet.",
            color=discord.Color.light_grey()
        )
        if price_info.startswith("⚠️"):
            embed.set_footer(text=price_info)
        await ctx.send(embed=embed)
        return True

    embed = discord.Embed(
        title=f"📜 {name}'s Last 10 Transactions",
        color=discord.Color.purple()
    )

    for tx in transactions:
        tx_type = tx['transaction_type'].capitalize()
        btc_val = fmt_btc(tx['btc_amount_sats'])
        usd_val = fmt_usd(tx['usd_amount_cents'])
        price_val = fmt_usd(tx['price_at_transaction_cents'])
        timestamp_val = fmt_datetime_local(tx['timestamp'])

        field_name = f"**{tx_type}** - {timestamp_val}"
        field_value = f"{btc_val} for {usd_val} (Price: {price_val})"
        embed.add_field(name=field_name, value=field_value, inline=False)
    
    embed.set_footer(text=price_info)
    await ctx.send(embed=embed)
    return True 