#!/usr/bin/env python3
"""
Very small BTC “dip / rip” notifier.

Logic (tweak at will):
• BUY signal  – today’s close ≤ 15 % below the 30‑day SMA
• SELL signal – today’s close ≥ 20 % above your last BUY price
State is kept in state.json in the repo.
"""
import json, os, sys, time
from datetime import datetime, timezone
import requests
STATE_FILE = "state.json"
API = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
PARAMS = {"vs_currency": "usd", "days": "90", "interval": "daily"}

def price_series():
    data = requests.get(API, params=PARAMS, timeout=15).json()
    # [[timestamp, price], ...] daily
    return [p for _, p in data["prices"]]

def sma(values, n):
    return sum(values[-n:]) / n

def post_discord(msg):
    wh = os.environ["DISCORD_WEBHOOK_URL"]
    requests.post(wh, json={"content": msg}, timeout=10)

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"mode": "flat", "last_buy": None}
    return json.load(open(STATE_FILE))

def save_state(s):
    json.dump(s, open(STATE_FILE, "w"), indent=2)

def main():
    series = price_series()
    today = series[-1]
    sma30 = sma(series, 30)
    st = load_state()

    now = datetime.now(timezone.utc).strftime("%Y‑%m‑%d")
    if st["mode"] == "flat" and today <= 0.85 * sma30:       # BUY
        post_discord(f"🟢 **BUY signal** {now}: price ${today:,.0f} (≥15 % below 30‑day SMA ${sma30:,.0f})")
        st = {"mode": "long", "last_buy": today}
    elif st["mode"] == "long" and today >= 1.20 * st["last_buy"]:  # SELL
        gain = (today / st["last_buy"] - 1) * 100
        post_discord(f"🔴 **SELL signal** {now}: price ${today:,.0f} (≈{gain:.1f}% over buy price)")
        st = {"mode": "flat", "last_buy": None}

    save_state(st)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        post_discord(f"⚠️ Bot error: {e}")
        sys.exit(1)