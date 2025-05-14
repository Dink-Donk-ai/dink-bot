# utils.py

import statistics
from datetime import date, timezone, datetime
from zoneinfo import ZoneInfo

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
    """Generate daily market digest message (HODLer focused)"""
    yday, week = series[-2], series[-8]
    vol30 = statistics.pstdev(series[-30:]) # Still useful for context
    lo90, hi90 = min(series), max(series)
    
    # Trend based on SMA90 for HODLers
    gap_sma90 = pct(today, sma90)
    trend_sma90 = "📈" if gap_sma90 > 0 else "📉"

    # Percent from 90-day high and low
    pct_from_hi90 = pct(today, hi90)
    pct_from_lo90 = pct(today, lo90)
    
    return (
        f"📊 **BTC Daily HODL Digest — {date.today()}**\n"
        f"Price: **{fmt_usd(int(today*100))}** ({pct(today,yday):+.2f}% 24h, {pct(today,week):+.2f}% 7d)\n"
        f"Market Cap: **{fmt_usd(int(market_cap*100))}**\n"
        f"24h Volume: **{fmt_usd(int(volume24h*100))}**\n"
        f"SMA90: **{fmt_usd(int(sma90*100))}** ({gap_sma90:+.1f}% vs price) {trend_sma90}\n"
        f"90D High: {fmt_usd(int(hi90*100))} ({pct_from_hi90:.2f}% from high)\n"
        f"90D Low:  {fmt_usd(int(lo90*100))} ({pct_from_lo90:+.2f}% from low)\n"
        f"30D Volatility (σ): {fmt_usd(int(vol30*100))}\n"
        # f"Debug: SMA30: {fmt_usd(int(sma30*100))}" # Kept for debugging, can be removed
    )

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