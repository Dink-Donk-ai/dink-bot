# commands/buy.py
from discord import TextChannel
import asyncpg
from utils import fmt_btc, fmt_usd, pct
SATOSHI = 100_000_000