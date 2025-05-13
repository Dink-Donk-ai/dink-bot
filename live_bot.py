"""
Dink‑Bot LIVE  (discord.py)

• Instant command handling
• Saves state to ./state.json on Railway Volume
• Fires daily digest at 08:00 UTC
• Re‑uses the play‑money logic you already love
"""

import discord, aiohttp, asyncio, json, os, statistics, re
from datetime import datetime, timezone, date

# ------- ENV VARS --------------------------------------------------
TOKEN       = os.environ["DISCORD_BOT_TOKEN"]
CHAN_ID     = int(os.environ["DISCORD_CHANNEL_ID"])
WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]      # same as before
START_CASH  = 1_000
BUY_DISCOUNT = 0.90
SELL_PREMIUM = 1.15
DIGEST_HOUR  = 8
STATE_FILE   = "state.json"
COINGECKO    = "https://api.coingecko.com/api/v3/coins/bitcoin" \
               "/market_chart?vs_currency=usd&days=90&interval=daily"
CMD_RE = re.compile(r"^(buy|sell|balance)(?:\s+([\d.]+|all))?$", re.I)

# ------- STATE LOAD/SAVE ------------------------------------------
def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {"users":{}, "mode":"flat", "last_buy":None, "last_summary":None}

def save_state(state):
    json.dump(state, open(STATE_FILE,"w"), indent=2)

STATE = load_state()

# ------- DISCORD CLIENT -------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# ------- MARKET HELPERS -------------------------------------------
async def fetch_prices():
    async with aiohttp.ClientSession() as s:
        async with s.get(COINGECKO, timeout=20) as r:
            data = await r.json()
    return [p for _, p in data["prices"]]

def pct(a,b): return (a/b-1)*100
def fmt_stats(price,sma):
    gap = pct(price,sma); emoji = "📈" if gap>0 else "📉"
    return f" | BTC ${price:,.0f} ({gap:+.1f}% vs SMA30){emoji}"

# ------- COMMAND LOGIC --------------------------------------------
async def process_cmd(cmd, arg, author, price, sma):
    uid, name = author.id, author.display_name
    user = STATE["users"].setdefault(uid, {"name":name,"cash":START_CASH,"btc":0.0})
    changed, reply = False, ""

    if cmd=="buy":
        usd = user["cash"] if arg in (None,"all") else float(arg)
        if usd<=0 or usd>user["cash"]:
            reply=f"⚠️ **{name}** invalid buy amount!{fmt_stats(price,sma)}"
        else:
            btc=usd/price; user["btc"]+=btc; user["cash"]-=usd; changed=True
            reply=f"🆕 **{name}** bought {btc:.6f} BTC for ${usd:,.0f}{fmt_stats(price,sma)}"

    elif cmd=="sell":
        btc_amt=user["btc"] if arg in (None,"all") else float(arg)
        if btc_amt<=0 or btc_amt>user["btc"]:
            reply=f"⚠️ **{name}** invalid sell amount!{fmt_stats(price,sma)}"
        else:
            usd=btc_amt*price; user["btc"]-=btc_amt; user["cash"]+=usd; changed=True
            reply=f"💰 **{name}** sold {btc_amt:.6f} BTC for ${usd:,.0f}{fmt_stats(price,sma)}"

    elif cmd=="balance":
        net=user['cash']+user['btc']*price
        reply=f"📄 **{name}** balance: ${user['cash']:,.0f} cash, {user['btc']:.6f} BTC (net ${net:,.0f}){fmt_stats(price,sma)}"

    return changed, reply

# ------- EVENT HANDLERS -------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(msg):
    if msg.channel.id!=CHAN_ID or msg.author.bot: return
    m=CMD_RE.match(msg.content.lower().lstrip('!'))
    if not m: return

    cmd,arg=m.groups()
    prices=await fetch_prices(); price=prices[-1]; sma=sum(prices[-30:])/30
    changed, text = await process_cmd(cmd,arg,msg.author,price,sma)
    if text: await msg.channel.send(text)
    try: await msg.delete()
    except discord.Forbidden: pass
    if changed: save_state(STATE)

# ------- BACKGROUND TASKS -----------------------------------------
async def background_tasks():
    await bot.wait_until_ready()
    chan=bot.get_channel(CHAN_ID)
    while not bot.is_closed():
        now=datetime.now(timezone.utc)
        if now.hour==DIGEST_HOUR and STATE["last_summary"]!=date.today().isoformat():
            prices=await fetch_prices(); price=prices[-1]; sma=sum(prices[-30:])/30
            # market BUY/SELL alerts
            if STATE["mode"]=="flat" and price<=BUY_DISCOUNT*sma:
                await chan.send(f"🟢 **BUY signal** — price ${price:,.0f}")
                STATE["mode"],STATE["last_buy"]="long",price
            elif STATE["mode"]=="long" and price>=SELL_PREMIUM*STATE["last_buy"]:
                await chan.send(f"🔴 **SELL signal** — price ${price:,.0f}")
                STATE["mode"],STATE["last_buy"]="flat",None
            # digest
            yday,week=prices[-2],prices[-8]
            vol30=statistics.pstdev(prices[-30:]); gap=pct(price,sma); trend="📈" if gap>0 else "📉"
            lb=sorted(STATE["users"].values(),
                      key=lambda u:u['cash']+u['btc']*price, reverse=True)[:5]
            lbtxt="\n".join(f"**{i+1}. {u['name']}**  ${u['cash']+u['btc']*price:,.0f}" for i,u in enumerate(lb)) or "No players yet."
            msg=(f"📊 **BTC Daily Digest — {date.today()}**\n"
                 f"Price: **${price:,.0f}** ({pct(price,yday):+.2f}% 24h, {pct(price,week):+.2f}% 7d) {trend}\n"
                 f"SMA30: ${sma:,.0f} (gap {gap:+.1f} %)\n"
                 f"30‑day σ: ${vol30:,.0f}\n"
                 f"Mode: {'🚀 long' if STATE['mode']=='long' else '💤 flat'}\n\n"
                 f"🏆 **Leaderboard**\n{lbtxt}")
            await chan.send(msg)
            STATE["last_summary"]=date.today().isoformat()
            save_state(STATE)
        await asyncio.sleep(60)          # loop every minute

bot.loop.create_task(background_tasks())
bot.run(TOKEN)