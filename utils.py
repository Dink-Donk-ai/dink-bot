# utils.py

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