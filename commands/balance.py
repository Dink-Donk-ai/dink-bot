# commands/balance.py
import asyncpg
from utils import fmt_btc, fmt_usd, pct
SATOSHI = 100_000_000