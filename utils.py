# utils.py

import statistics
from datetime import date, timezone, datetime
from zoneinfo import ZoneInfo
import discord

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

def make_daily_digest(series, today, sma30, sma90, volume24h, market_cap):
    """Generate daily market digest embed (HODLer focused)"""
    yday, week = series[-2], series[-8]
    vol30 = statistics.pstdev(series[-30:])
    lo90, hi90 = min(series), max(series)
    
    gap_sma90 = pct(today, sma90)
    trend_sma90 = "📈" if gap_sma90 > 0 else "📉"

    pct_from_hi90 = pct(today, hi90)
    pct_from_lo90 = pct(today, lo90)

    embed = discord.Embed(
        title=f"📊 BTC Daily HODL Digest — {date.today()}",
        color=discord.Color.gold()
    )
    embed.add_field(name="Price", value=f"**{fmt_usd(int(today*100))}** ({pct(today,yday):+.2f}% 24h, {pct(today,week):+.2f}% 7d)", inline=False)
    embed.add_field(name="Market Cap", value=f"**{fmt_usd(int(market_cap*100))}**", inline=True)
    embed.add_field(name="24h Volume", value=f"**{fmt_usd(int(volume24h*100))}**", inline=True)
    embed.add_field(name=f"SMA90 {trend_sma90}", value=f"**{fmt_usd(int(sma90*100))}** ({gap_sma90:+.1f}% vs price)", inline=False)
    embed.add_field(name="90D High", value=f"{fmt_usd(int(hi90*100))} ({pct_from_hi90:.2f}% from high)", inline=True)
    embed.add_field(name="90D Low", value=f"{fmt_usd(int(lo90*100))} ({pct_from_lo90:+.2f}% from low)", inline=True)
    embed.add_field(name="30D Volatility (σ)", value=f"{fmt_usd(int(vol30*100))}", inline=False)
    
    return embed

def fmt_datetime_local(dt_utc: datetime) -> str:
    """Formats a UTC datetime object to a local timezone string (Europe/Tallinn)."""
    if dt_utc is None:
        return "N/A"
    
    # Ensure the datetime object is timezone-aware (UTC)
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    else:
        dt_utc = dt_utc.astimezone(timezone.utc) # Convert to UTC if it's some other timezone

    # Convert UTC to Europe/Tallinn timezone
    tallinn_tz = ZoneInfo("Europe/Tallinn")
    dt_tallinn = dt_utc.astimezone(tallinn_tz)
    
    return dt_tallinn.strftime("%Y-%m-%d %I:%M:%S %p %Z")