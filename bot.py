#!/usr/bin/env python3
"""
Dink‑Bot  ‑  BTC watcher + play‑money game

* Schedule: every 30 min via GitHub Actions
* Data: CoinGecko free JSON API
* Alerts: Discord incoming webhook
* Game input: Discord REST poll for !buy / !sell
"""

import json, os, statistics, requests
from datetime import datetime, timezone, date

# ---------- CONFIG -------------------------------------------------
START_CASH   = 1_000                      # initial bankroll for each player
BUY_DISCOUNT = 0.90                       # buy when price ≤ 90 % of SMA30
SELL_PREMIUM = 1.15                       # sell when price ≥ 115 % of entry
DIGEST_HOUR  = 8                          # UTC hour to emit daily digest
STATE_FILE   = "state.json"

COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    "?vs_currency=usd&days=90&interval=daily"
)

WEBHOOK_URL  = os.environ["DISCORD_WEBHOOK_URL"]      # incoming
BOT_TOKEN    = os.environ["DISCORD_BOT_TOKEN"]        # bot token for reads
CHANNEL_ID   = os.environ["DISCORD_CHANNEL_ID"]
HEADERS      = {"Authorization": f"Bot {BOT_TOKEN}"}
API_BASE     = "https://discord.com/api/v10"
# -------------------------------------------------------------------

# ---------- helpers ------------------------------------------------
def price_series(days=90):
    data = requests.get(COINGECKO_URL, timeout=20).json()
    return [p for _, p in data["prices"]]

def pct(a, b):
    return (a / b - 1.0) * 100.0

def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "mode": "flat",          # or "long"
            "last_buy": None,        # float price
            "last_summary": None,    # "YYYY‑MM‑DD"
            "last_msg_id": None,     # Discord message ID processed
            "users": {}              # uid -> {name,cash,btc}
        }
    return json.load(open(STATE_FILE))

def save_state(state):
    json.dump(state, open(STATE_FILE, "w"), indent=2)

def post(content):
    requests.post(WEBHOOK_URL, json={"content": content}, timeout=10)

# ---------- Discord game ------------------------------------------
def fetch_new_commands(state):
    """Return list of (uid, name, cmd) for !buy / !sell since last_msg_id."""
    params = {"limit": 100}
    if state["last_msg_id"]:
        params["after"] = state["last_msg_id"]

    url  = f"{API_BASE}/channels/{CHANNEL_ID}/messages"
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)

    if resp.status_code != 200:
        post(f"⚠️ Discord API error {resp.status_code}: {resp.text[:120]}")
        return []                        # don't crash the bot

    data = resp.json()
    if not isinstance(data, list):      # e.g. {'message':'401:…'}
        post(f"⚠️ Unexpected Discord payload: {data}")
        return []

    cmds, newest = [], state["last_msg_id"]
    for m in reversed(data):
        newest = m["id"]
        txt = m["content"].strip().lower()
        if txt in ("!buy", "!sell"):
            cmds.append((m["author"]["id"], m["author"]["username"], txt[1:]))
    state["last_msg_id"] = newest
    return cmds

def process_commands(cmds, price, users):
    """Mutate players' cash / btc based on commands."""
    for uid, name, action in cmds:
        pl = users.setdefault(uid, {"name": name, "cash": START_CASH, "btc": 0.0})

        if action == "buy":
            if pl["cash"] > 0:
                btc = pl["cash"] / price
                pl["btc"], pl["cash"] = pl["btc"] + btc, 0.0
                post(f"🆕 **{name}** bought {btc:.6f} BTC at ${price:,.0f}")
            else:
                post(f"⚠️ **{name}** tried to *buy* but has no cash left!")

        elif action == "sell":
            if pl["btc"] > 0:
                cash = pl["btc"] * price
                pl["cash"], pl["btc"] = pl["cash"] + cash, 0.0
                post(f"💰 **{name}** sold all BTC for ${cash:,.0f}")
            else:
                post(f"⚠️ **{name}** tried to *sell* but holds no BTC!")

def leaderboard(users, price, top=5):
    ranking = sorted(
        users.values(),
        key=lambda u: u["cash"] + u["btc"] * price,
        reverse=True
    )[:top]
    if not ranking:
        return "No players yet."
    lines = [
        f"**{i+1}. {u['name']}**   ${u['cash'] + u['btc'] * price:,.0f}"
        for i, u in enumerate(ranking)
    ]
    return "\n".join(lines)

# ---------- Digest message ----------------------------------------
def make_daily_digest(series, today, sma30, state):
    yday   = series[-2]
    week   = series[-8]
    vol30  = statistics.pstdev(series[-30:])
    hi90   = max(series)
    lo90   = min(series)
    gap    = pct(today, sma30)
    trend  = "📈" if gap > 0 else "📉"

    lb_text = leaderboard(state["users"], today)

    return (
        f"📊 **BTC Daily Digest — {date.today()}**\n"
        f"Price: **${today:,.0f}** ({pct(today, yday):+.2f}% 24h, "
        f"{pct(today, week):+.2f}% 7d) {trend}\n"
        f"SMA30: ${sma30:,.0f}  (gap {gap:+.1f} %)\n"
        f"30-day σ: ${vol30:,.0f}\n"
        f"90-day range: ${lo90:,.0f} → ${hi90:,.0f}\n"
        f"Mode: {'🚀 long' if state['mode']=='long' else '💤 flat'}\n\n"
        f"🏆 **Leaderboard**\n{lb_text}"
    )

# ---------- main loop --------------------------------------------
def main():
    series = price_series()
    today  = series[-1]
    sma30  = sum(series[-30:]) / 30

    now_utc   = datetime.now(timezone.utc)
    today_iso = date.today().isoformat()

    st = load_state()

    # 1) process player commands
    cmds = fetch_new_commands(st)
    if cmds:
        process_commands(cmds, today, st["users"])
        print("DEBUG cmds found:", cmds)
        print("Players:", st["users"])

    # 2) trading signals
    if st["mode"] == "flat" and today <= BUY_DISCOUNT * sma30:
        post(f"🟢 **BUY signal** — price ${today:,.0f} (≤ {int((1-BUY_DISCOUNT)*100)} % below SMA30)")
        st["mode"], st["last_buy"] = "long", today

    elif st["mode"] == "long" and today >= SELL_PREMIUM * st["last_buy"]:
        gain = pct(today, st["last_buy"])
        post(f"🔴 **SELL signal** — price ${today:,.0f}  (gain {gain:.1f} %)")
        st["mode"], st["last_buy"] = "flat", None

    # 3) daily digest once per UTC day
    if st["last_summary"] != today_iso and now_utc.hour == DIGEST_HOUR:
        post(make_daily_digest(series, today, sma30, st))
        st["last_summary"] = today_iso

    save_state(st)

# -----------------------------------------------------------------
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        post(f"⚠️ Dink-Bot error: `{e}`")
        raise