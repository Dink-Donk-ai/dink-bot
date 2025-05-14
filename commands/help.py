# commands/help.py
import asyncpg

async def run(pool: asyncpg.Pool, ctx, price: float, price_cents: int, sma: float):
    """
    Shows help message with available commands.
    """
    help_text = """
📖 **Available Commands**

`!balance`
Check your current balance of cash and BTC

`!buy <amount>`
Buy BTC with USD amount (e.g. `!buy 100` or `!buy all`)

`!sell <amount>`
Sell BTC for USD amount (e.g. `!sell 0.001` or `!sell all`)

`!stats`
Show market stats and leaderboard

`!help`
Show this help message

All commands are deleted after processing to keep the channel clean.
"""
    await ctx.send(help_text)
    return True 