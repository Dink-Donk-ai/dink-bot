# commands/help.py
import asyncpg
import discord

async def run(pool: asyncpg.Pool, ctx, price: float, price_cents: int, sma: float):
    """
    Shows help message with available commands.
    """
    embed = discord.Embed(
        title="📖 Dink-Bot Help",
        description="Here are the available commands:",
        color=discord.Color.blue() # Or any color you prefer for help
    )

    embed.add_field(
        name="`!balance`",
        value="Check your current balance of cash and BTC.",
        inline=False
    )
    embed.add_field(
        name="`!buy <amount>`",
        value="Buy BTC with USD amount (e.g. `!buy 100` or `!buy all`).",
        inline=False
    )
    embed.add_field(
        name="`!sell <amount>`",
        value="Sell BTC for USD amount (e.g. `!sell 0.001` or `!sell all`).",
        inline=False
    )
    embed.add_field(
        name="`!stats`",
        value="Show market stats and leaderboard.",
        inline=False
    )
    embed.add_field(
        name="`!history`",
        value="Show your last 10 transactions.",
        inline=False
    )
    embed.add_field(
        name="--- Order Commands ---",
        value="Place and manage limit orders:",
        inline=False 
    )
    embed.add_field(
        name="`!buyorder <usd_amount> <price_usd>`",
        value="Place a limit order to spend a specific USD amount (e.g., `100`) to buy BTC if the market price drops to or below your `price_usd` (e.g., `20000`).",
        inline=False
    )
    embed.add_field(
        name="`!sellorder <btc_amount> <price_usd>`",
        value="Place a limit order to sell a specific amount of BTC at a desired USD price per BTC (e.g., `!sellorder 0.05 22000`).",
        inline=False
    )
    embed.add_field(
        name="`!cancelorder <order_id>`",
        value="Cancel an open limit order using its ID.",
        inline=False
    )
    embed.add_field(
        name="`!myorders`",
        value="List all your currently open limit orders.",
        inline=False
    )
    embed.add_field(
        name="`!help`",
        value="Show this help message.",
        inline=False
    )

    embed.set_footer(text="All commands are deleted after processing to keep the channel clean.")

    await ctx.send(embed=embed)
    return True 