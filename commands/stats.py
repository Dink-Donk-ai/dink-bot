# commands/stats.py
import asyncpg
import discord
from utils import fmt_btc, fmt_usd, pct, make_daily_digest, fmt_datetime_local
SATOSHI = 100_000_000
INITIAL_CASH_CENTS = 100_000

async def run(pool: asyncpg.Pool, ctx, price: float, price_cents: int, sma30: float, series=None, sma90: float=None, volume24h: float=None, market_cap: float=None):
    """
    Shows Cash Kings leaderboard and market stats.
    """
    # Get top 5 users by cash, their P&L, trade count, and join date
    async with pool.acquire() as conn:
        users_data = await conn.fetch("""
            SELECT 
                u.uid,
                u.name,
                u.cash_c,
                u.btc_c,
                u.join_timestamp,
                (u.cash_c + (u.btc_c * $1 / $2)) AS net_worth_c,
                ((u.cash_c + (u.btc_c * $1 / $2)) - $3) AS pnl_c,
                COALESCE(t.trade_count, 0) AS trade_count
            FROM users u
            LEFT JOIN (
                SELECT uid, COUNT(*) AS trade_count 
                FROM transactions 
                GROUP BY uid
            ) t ON u.uid = t.uid
            ORDER BY u.cash_c DESC
            LIMIT 5
        """, price_cents, SATOSHI, INITIAL_CASH_CENTS)

    # Determine embed color based on #1 Cash King's P&L
    embed_color = discord.Color.gold()
    if users_data:
        top_user_pnl = users_data[0]['pnl_c']
        if top_user_pnl > 0:
            embed_color = discord.Color.green()
        elif top_user_pnl < 0:
            embed_color = discord.Color.red()

    leaderboard_embed = discord.Embed(
        title="🏆 Cash Kings Leaderboard 🏆",
        color=embed_color
    )

    if not users_data:
        leaderboard_embed.description = "No users found to display on the leaderboard yet."
    else:
        for i, user in enumerate(users_data, 1):
            pnl_val = user['pnl_c']
            pnl_sign = "+" if pnl_val >= 0 else ""
            pnl_emoji = "📈" if pnl_val >= 0 else "📉"
            active_since_str = fmt_datetime_local(user['join_timestamp']) if user['join_timestamp'] else "N/A"
            
            field_name = f"{i}. {user['name']}"
            field_value = (
                f"💰 Cash: **{fmt_usd(user['cash_c'])}**\n"
                f"{pnl_emoji} P&L: **{pnl_sign}{fmt_usd(pnl_val)}**\n"
                f"📊 Trades: {user['trade_count']}\n"
                f"⏳ Active Since: {active_since_str}\n"
                f"💼 Net Worth: {fmt_usd(user['net_worth_c'])}"
            )
            leaderboard_embed.add_field(name=field_name, value=field_value, inline=False)

    # Daily digest embed (existing logic)
    digest_embed = None
    if series and price is not None and sma30 is not None and sma90 is not None and volume24h is not None and market_cap is not None:
        digest_embed = make_daily_digest(series, price, sma30, sma90, volume24h, market_cap)

    if digest_embed:
        await ctx.send(embed=digest_embed)
    
    await ctx.send(embed=leaderboard_embed)
    return True 