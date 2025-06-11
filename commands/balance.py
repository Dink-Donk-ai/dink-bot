# commands/balance.py
import asyncpg
from utils import fmt_btc, fmt_usd, pct
import discord
SATOSHI = 100_000_000
INITIAL_CASH_CENTS = 100_000 # Starting cash for new users, in cents

async def run(pool: asyncpg.Pool, ctx, price: float, price_cents: int, sma: float):
    """
    Handles the balance command.
    """
    uid = ctx.author.id
    name = ctx.author.display_name
    
    # Check for valid price data
    if price_cents is None or price_cents <= 0:
        await ctx.send("⚠️ Unable to display balance because price data is currently unavailable. Please try again later.")
        return False

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

    embed_color = discord.Color.green() if portfolio_pnl_cents >= 0 else discord.Color.red()

    embed = discord.Embed(
        title=f"📄 {name}'s Balance",
        color=embed_color
    )
    embed.add_field(name="Cash 💵", value=fmt_usd(cash_c), inline=True)
    embed.add_field(name="Bitcoin ₿", value=fmt_btc(btc_c), inline=True)
    embed.add_field(name="BTC Value 💰", value=fmt_usd(btc_c * price_cents // SATOSHI), inline=True)
    embed.add_field(name="Total Net Worth 🏦", value=f"**{fmt_usd(net_c)}**", inline=False)
    embed.add_field(name=f"Portfolio P&L {pnl_emoji}", value=f"**{pnl_sign}{fmt_usd(portfolio_pnl_cents)}**", inline=False)
    embed.set_footer(text=f"Current BTC Price: ${price:,.0f} ({pct(price, sma):+.1f}% vs SMA30)")

    await ctx.send(embed=embed)
    return True # Changed to True as embed is sent