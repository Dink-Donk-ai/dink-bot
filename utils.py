# utils.py

import statistics
from datetime import date

SATOSHI = 100_000_000

def fmt_usd(cents: int) -> str:
    """Format integer cents as a USD string, e.g. 12345 → “$123.45”."""
    return f"${cents / 100:,.2f}"

def fmt_btc(sats: int) -> str:
    """Format satoshis as BTC string, e.g. 1000000 → “0.01000000 BTC”."""
    return f"{sats / SATOSHI:.8f} BTC"

def pct(current: float, reference: float) -> float:
    """Compute percentage change of current vs reference."""
    return (current / reference - 1) * 100

def make_daily_digest(series, today, sma30):
    """Generate daily market digest message"""
    yday, week = series[-2], series[-8]
    vol30 = statistics.pstdev(series[-30:])
    lo90, hi90 = min(series), max(series)
    gap = pct(today, sma30)
    trend = "📈" if gap > 0 else "📉"
    
    return (
        f"📊 **BTC Daily Digest — {date.today()}**\n"
        f"Price: **${today:,.0f}** ({pct(today,yday):+.2f}% 24h, {pct(today,week):+.2f}% 7d) {trend}\n"
        f"SMA30: ${sma30:,.0f} (gap {gap:+.1f}%)\n"
        f"30‑day σ: ${vol30:,.0f}\n"
        f"90‑day range: ${lo90:,.0f} → ${hi90:,.0f}\n"
    )