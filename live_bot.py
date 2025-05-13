#!/usr/bin/env python3
"""
Dink‑Bot LIVE  –  integer‑precise play‑money BTC trader
• BTC amounts stored as satoshis  (int)
• USD amounts stored as cents     (int)
• Instant Discord command handling via discord.py v2
"""

import discord, aiohttp, asyncio, json, os, re, statistics
from datetime import datetime, timezone, date
from typing import Dict, Any

# ---------- CONFIG -------------------------------------------------
START_CASH_CENTS = 100_000            # $1 000
BUY_DISCOUNT     = 0.90
SELL_PREMIUM     = 1.15
DIGEST_HOUR      = 8                   # UTC
STATE_FILE       = "state.json"

TOKEN       = os.environ["DISCORD_BOT_TOKEN"]
CHAN_ID     = int(os.environ["DISCORD_CHANNEL_ID"])
WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    "?vs_currency=usd&days=90&interval=daily"
)

CMD_RE = re.compile(r"^(buy|sell|balance)(?:\s+([\d.]+|all))?$", re.I)
SATOSHI = 100_000_000
# ------------------------------------------------------------------

# ---------- UTILITIES ---------------------------------------------
def cents_from_usd(s: str) -> int:
    return int(round(float(s) * 100))

def sats_from_btc(s: str) -> int:
    return int(round(float(s) * SATOSHI))

def fmt_usd(cents: int) -> str:
    return f"${cents / 100:,.0f}"

def fmt_btc(sats: int) -> str:
    return f"{sats / SATOSHI:.8f} BTC"

async def fetch_prices() -> list[float]:
    async with aiohttp.ClientSession() as sess:
        async with sess.get(COINGECKO_URL, timeout=20) as r:
            data = await r.json()
    return [p for _, p in data["prices"]]

def pct(a: float, b: float) -> float:
    return (a / b - 1) * 100
# ------------------------------------------------------------------

# ---------- STATE --------------------------------------------------
def load_state() -> Dict[str, Any]:
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {
        "users": {},              # uid -> {name, cash_c:int, btc_s:int}
        "mode": "flat",
        "last_buy_cents": None,   # price of BTC at BUY, in cents
        "last_summary": None
    }

def save_state(state: Dict[str, Any]):
    json.dump(state, open(STATE_FILE, "w"), indent=2)

STATE = load_state()
# ------------------------------------------------------------------

# ---------- DISCORD CLIENT ----------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

def price_to_cents(price_float: float) -> int:
    return int(round(price_float * 100))

def fmt_stats(price: float, sma: float) -> str:
    gap = pct(price, sma)
    emoji = "📈" if gap > 0 else "📉"
    return f" | BTC ${price:,.0f} ({gap:+.1f}% vs SMA30){emoji}"

async def reply_and_delete(ch: discord.TextChannel, msg: discord.Message, text: str):
    await ch.send(text)
    try:
        await msg.delete()
    except discord.Forbidden:
        pass
# ------------------------------------------------------------------

async def handle_command(cmd: str, arg: str | None, author: discord.Member,
                         price: float, price_cents: int, sma: float,
                         ch: discord.TextChannel) -> bool:
    """
    Returns True if user's portfolio changed.
    """
    uid, name = str(author.id), author.display_name
    u = STATE["users"].setdefault(uid,
        {"name": name, "cash_c": START_CASH_CENTS, "btc_s": 0})
    changed = False

    # ------- BUY ---------------------------------------------------
    if cmd == "buy":
        if arg in (None, "all"):
            usd_c = u["cash_c"]
        else:
            try:
                usd_c = cents_from_usd(arg)
            except ValueError:
                usd_c = -1
        if usd_c <= 0 or usd_c > u["cash_c"]:
            await ch.send(f"⚠️ **{name}** invalid buy amount!{fmt_stats(price, sma)}")
            return False

        sats = usd_c * SATOSHI // price_cents
        if sats == 0:
            await ch.send(f"⚠️ **{name}** amount too small!{fmt_stats(price, sma)}")
            return False

        u["cash_c"] -= usd_c
        u["btc_s"]  += sats
        changed = True
        await ch.send(f"🆕 **{name}** bought {fmt_btc(sats)} for {fmt_usd(usd_c)}"
                      f"{fmt_stats(price, sma)}")

    # ------- SELL --------------------------------------------------
    elif cmd == "sell":
        if arg in (None, "all"):
            sats = u["btc_s"]
        else:
            try:
                val = float(arg)
            except ValueError:
                val = -1

            if val <= 0:
                sats = -1
            elif val < 1:                         # treat as BTC
                sats = sats_from_btc(arg)
            else:                                 # treat as USD
                usd_c = cents_from_usd(arg)
                sats  = usd_c * SATOSHI // price_cents

        if sats <= 0 or sats > u["btc_s"]:
            await ch.send(f"⚠️ **{name}** invalid sell amount!{fmt_stats(price, sma)}")
            return False

        usd_out_c = sats * price_cents // SATOSHI
        u["btc_s"]  -= sats
        u["cash_c"] += usd_out_c
        changed = True
        await ch.send(f"💰 **{name}** sold {fmt_btc(sats)} for {fmt_usd(usd_out_c)}"
                      f"{fmt_stats(price, sma)}")

    # ------- BALANCE ----------------------------------------------
    elif cmd == "balance":
        net_c = u["cash_c"] + u["btc_s"] * price_cents // SATOSHI
        await ch.send(f"📄 **{name}** balance: {fmt_usd(u['cash_c'])} cash, "
                      f"{fmt_btc(u['btc_s'])} (net {fmt_usd(net_c)})"
                      f"{fmt_stats(price, sma)}")

    return changed

# ---------- EVENT HANDLERS ----------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    asyncio.create_task(background_tasks())

@bot.event
async def on_message(message: discord.Message):
    if message.channel.id != CHAN_ID or message.author.bot:
        return

    m = CMD_RE.match(message.content.lower().lstrip('!'))
    if not m:
        return
    cmd, arg = m.groups()

    prices   = await fetch_prices()
    price    = prices[-1]
    price_c  = price_to_cents(price)
    sma      = sum(prices[-30:]) / 30
    channel  = message.channel

    changed = await handle_command(cmd, arg, message.author,
                                   price, price_c, sma, channel)
    try:
        await message.delete()
    except discord.Forbidden:
        pass
    if changed:
        save_state(STATE)

# ---------- BACKGROUND TASKS --------------------------------------
async def background_tasks():
    await bot.wait_until_ready()
    channel = bot.get_channel(CHAN_ID)
    while not bot.is_closed():
        now = datetime.now(timezone.utc)
        if now.hour == DIGEST_HOUR:
            today_iso = date.today().isoformat()
            if STATE["last_summary"] != today_iso:
                prices   = await fetch_prices()
                price    = prices[-1]
                price_c  = price_to_cents(price)
                sma      = sum(prices[-30:]) / 30

                # market alerts
                if STATE["mode"] == "flat" and price <= BUY_DISCOUNT * sma:
                    await channel.send(f"🟢 **BUY signal** — price ${price:,.0f}")
                    STATE["mode"], STATE["last_buy_cents"] = "long", price_c
                elif (STATE["mode"] == "long"
                      and price >= SELL_PREMIUM * STATE["last_buy_cents"] / 100):
                    await channel.send(f"🔴 **SELL signal** — price ${price:,.0f}")
                    STATE["mode"], STATE["last_buy_cents"] = "flat", None

                # digest
                yday, week = prices[-2], prices[-8]
                vol30 = statistics.pstdev(prices[-30:])
                gap = pct(price, sma)
                trend = "📈" if gap > 0 else "📉"

                ranks = sorted(STATE["users"].values(),
                               key=lambda u: u["cash_c"] + u["btc_s"]*price_c//SATOSHI,
                               reverse=True)[:5]
                lbtxt = ("\n".join(
                    f"**{i+1}. {u['name']}**  "
                    f"{fmt_usd(u['cash_c'] + u['btc_s']*price_c//SATOSHI)}"
                    for i, u in enumerate(ranks)) or "No players yet.")

                digest = (
                    f"📊 **BTC Daily Digest — {date.today()}**\n"
                    f"Price: **${price:,.0f}** "
                    f"({pct(price,yday):+.2f}% 24h, {pct(price,week):+.2f}% 7d) {trend}\n"
                    f"SMA30: ${sma:,.0f} (gap {gap:+.1f} %)\n"
                    f"30‑day σ: ${vol30:,.0f}\n"
                    f"Mode: {'🚀 long' if STATE['mode']=='long' else '💤 flat'}\n\n"
                    f"🏆 **Leaderboard**\n{lbtxt}"
                )
                await channel.send(digest)
                STATE["last_summary"] = today_iso
                save_state(STATE)
        await asyncio.sleep(60)

# ------------------------------------------------------------------
bot.run(TOKEN)