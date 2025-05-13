#!/usr/bin/env python3
"""
Dink‑Bot v3  –  adds partial !buy <usd> and !sell <btc>
"""

import json, os, statistics, requests, re
from datetime import datetime, timezone, date

# ---------- CONFIG -------------------------------------------------
START_CASH   = 1_000
BUY_DISCOUNT = 0.90
SELL_PREMIUM = 1.15
DIGEST_HOUR  = 8
STATE_FILE   = "state.json"

COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    "?vs_currency=usd&days=90&interval=daily"
)

WEBHOOK_URL  = os.environ["DISCORD_WEBHOOK_URL"]
BOT_TOKEN    = os.environ["DISCORD_BOT_TOKEN"]
CHANNEL_ID   = os.environ["DISCORD_CHANNEL_ID"]
HEADERS      = {"Authorization": f"Bot {BOT_TOKEN}"}
API_BASE     = "https://discord.com/api/v10"
# ------------------------------------------------------------------

# ---------- helpers ------------------------------------------------
def price_series():
    return [p for _, p in requests.get(COINGECKO_URL, timeout=20).json()["prices"]]

def pct(a, b): return (a / b - 1) * 100

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"mode":"flat","last_buy":None,"last_summary":None,
                "last_msg_id":None,"users":{}}
    return json.load(open(STATE_FILE))

def save_state(s): json.dump(s, open(STATE_FILE,"w"), indent=2)

def post(msg): requests.post(WEBHOOK_URL, json={"content":msg}, timeout=10)

def delete(msg_id):
    requests.delete(f"{API_BASE}/channels/{CHANNEL_ID}/messages/{msg_id}",
                    headers=HEADERS, timeout=10)

def format_price_stats(price, sma30):
    gap = pct(price, sma30)
    emoji = "📈" if gap > 0 else "📉"
    return f" | BTC ${price:,.0f} ({gap:+.1f}% vs SMA30){emoji}"
# ------------------------------------------------------------------

# ---------- Discord polling ---------------------------------------
CMD_RE = re.compile(r"^!(buy|sell|balance)(?:\s+([\d.]+|all))?$", re.I)

def fetch_new_commands(state):
    """return [(msg_id, uid, name, cmd, arg)]"""
    params = {"limit": 100}
    if state["last_msg_id"]:
        params["after"] = state["last_msg_id"]

    r = requests.get(f"{API_BASE}/channels/{CHANNEL_ID}/messages",
                     headers=HEADERS, params=params, timeout=15)
    if r.status_code != 200:
        post(f"⚠️ Discord API error {r.status_code}: {r.text[:120]}")
        return []
    data = r.json()
    if not isinstance(data, list):
        post(f"⚠️ Unexpected Discord payload: {data}")
        return []

    cmds, newest = [], state["last_msg_id"]
    for m in reversed(data):
        newest = m["id"]
        mtext = m["content"].strip()
        mres  = CMD_RE.match(mtext)
        if mres:
            cmd, arg = mres.group(1).lower(), mres.group(2)
            cmds.append((m["id"], m["author"]["id"], m["author"]["username"], cmd, arg))
    state["last_msg_id"] = newest
    return cmds
# ------------------------------------------------------------------

def process_commands(cmds, price, sma30, users):
    changed = False
    for msg_id, uid, name, action, arg in cmds:
        pl = users.setdefault(uid, {"name": name, "cash": START_CASH, "btc": 0.0})
        reply = ""

        if action == "buy":
            # determine USD amount to spend
            spend_all = arg is None or arg.lower() == "all"
            if spend_all:
                usd = pl["cash"]
            else:
                try:
                    usd = float(arg)
                except ValueError:
                    usd = -1
            if usd <= 0 or usd > pl["cash"]:
                reply = f"⚠️ **{name}** invalid buy amount!{format_price_stats(price, sma30)}"
            else:
                btc = usd / price
                pl["btc"] += btc
                pl["cash"] -= usd
                changed = True
                reply = (f"🆕 **{name}** bought {btc:.6f} BTC for ${usd:,.0f}"
                         f"{format_price_stats(price, sma30)}")

        elif action == "sell":
            sell_all = arg is None or arg.lower() == "all"
            if sell_all:
                btc_amt = pl["btc"]
            else:
                try:
                    btc_amt = float(arg)
                except ValueError:
                    btc_amt = -1
            if btc_amt <= 0 or btc_amt > pl["btc"]:
                reply = f"⚠️ **{name}** invalid sell amount!{format_price_stats(price, sma30)}"
            else:
                usd_out = btc_amt * price
                pl["btc"] -= btc_amt
                pl["cash"] += usd_out
                changed = True
                reply = (f"💰 **{name}** sold {btc_amt:.6f} BTC for ${usd_out:,.0f}"
                         f"{format_price_stats(price, sma30)}")

        elif action == "balance":
            net = pl["cash"] + pl["btc"] * price
            reply = (f"📄 **{name}** balance: ${pl['cash']:,.0f} cash, "
                     f"{pl['btc']:.6f} BTC (net ${net:,.0f})"
                     f"{format_price_stats(price, sma30)}")

        if reply:
            post(reply)
        delete(msg_id)

    return changed
# ------------------------------------------------------------------

def leaderboard(users, price, top=5):
    rank = sorted(users.values(),
                  key=lambda u: u["cash"] + u["btc"]*price,
                  reverse=True)[:top]
    return ("\n".join(f"**{i+1}. {u['name']}**  ${u['cash']+u['btc']*price:,.0f}"
                      for i,u in enumerate(rank))
            if rank else "No players yet.")

def make_daily_digest(series, today, sma30, st):
    yday, week = series[-2], series[-8]
    vol30 = statistics.pstdev(series[-30:])
    lo90, hi90 = min(series), max(series)
    gap = pct(today, sma30)
    trend = "📈" if gap > 0 else "📉"
    return (
        f"📊 **BTC Daily Digest — {date.today()}**\n"
        f"Price: **${today:,.0f}** ({pct(today,yday):+.2f}% 24h, {pct(today,week):+.2f}% 7d) {trend}\n"
        f"SMA30: ${sma30:,.0f} (gap {gap:+.1f} %)\n"
        f"30‑day σ: ${vol30:,.0f}\n"
        f"90‑day range: ${lo90:,.0f} → ${hi90:,.0f}\n"
        f"Mode: {'🚀 long' if st['mode']=='long' else '💤 flat'}\n\n"
        f"🏆 **Leaderboard**\n{leaderboard(st['users'], today)}"
    )
# ------------------------------------------------------------------

def main():
    series = price_series()
    today  = series[-1]
    sma30  = sum(series[-30:]) / 30
    nowUTC = datetime.now(timezone.utc)
    today_iso = date.today().isoformat()

    st = load_state()

    # 1) commands
    cmds = fetch_new_commands(st)
    changed_portfolio = process_commands(cmds, today, sma30, st["users"])

    # 2) market buy/sell alerts
    if st["mode"] == "flat" and today <= BUY_DISCOUNT * sma30:
        post(f"🟢 **BUY signal** — price ${today:,.0f} (≤ {int((1-BUY_DISCOUNT)*100)} % below SMA30)")
        st["mode"], st["last_buy"] = "long", today
    elif st["mode"] == "long" and today >= SELL_PREMIUM * st["last_buy"]:
        post(f"🔴 **SELL signal** — price ${today:,.0f}  (gain {pct(today, st['last_buy']):.1f} %)")
        st["mode"], st["last_buy"] = "flat", None

    # 3) daily digest
    if st["last_summary"] != today_iso and nowUTC.hour == DIGEST_HOUR:
        post(make_daily_digest(series, today, sma30, st))
        st["last_summary"] = today_iso

    if changed_portfolio or nowUTC.hour == DIGEST_HOUR or cmds:
        save_state(st)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        post(f"⚠️ Dink‑Bot error: `{e}`")
        raise