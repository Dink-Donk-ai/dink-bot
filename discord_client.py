"""
Discord client implementation
"""
import discord
from discord.ext import tasks
import asyncio
from datetime import datetime, timezone

from config import settings
from bot_utils import fetch_price_data, HODL_BUY_DIP_THRESHOLD, process_command
from utils import make_daily_digest, fmt_btc, fmt_usd

SATOSHI = 100_000_000

class DinkClient(discord.Client):
    def __init__(self, pool):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        
        self.pool = pool
        self.price = None
        self.price_cents = None
        self.sma30 = None
        self.series = None
        self.last_summary_date = None
        self.last_hodl_alert_date = None
        self.sma90 = None
        self.volume24h = None
        self.market_cap = None
        
        self.price_update_loop.start()
        
    async def setup_hook(self):
        """Called when the client is being set up"""
        await self.update_price_data()
        
    @tasks.loop(minutes=5)
    async def price_update_loop(self):
        """Update price data every 5 minutes"""
        await self.update_price_data()

        if not self.price_cents:
            print("Price data not available, skipping order processing and HODL alert.")
            return

        await self.process_open_orders(self.price_cents)

        if not all((self.series, self.price)):
            return

        try:
            now_utc = datetime.now(timezone.utc)
            today_iso_date = now_utc.date().isoformat()

            if self.last_hodl_alert_date != today_iso_date:
                ninety_day_high = max(self.series) if self.series else 0
                
                if ninety_day_high > 0 and self.price < (ninety_day_high * (1 - HODL_BUY_DIP_THRESHOLD)):
                    channel = self.get_channel(settings.channel_id)
                    if channel:
                        percentage_drop = (1 - (self.price / ninety_day_high)) * 100
                        alert_message = (
                            f"📉 **HODL Alert!** 📉\n"
                            f"Bitcoin is trading at **${self.price:,.2f}**.\n"
                            f"This is **{percentage_drop:.2f}%** below its 90-day high of ${ninety_day_high:,.2f}.\n"
                            f"Consider buying the dip!"
                        )
                        await channel.send(alert_message)
                        self.last_hodl_alert_date = today_iso_date
        except Exception as e:
            print(f"Error during HODL alert check: {e}")
            
    async def update_price_data(self):
        """Fetch and update price data"""
        try:
            fetched_data = await fetch_price_data()
            if fetched_data and fetched_data[1] is not None:
                self.series, self.price, self.sma30, self.sma90, self.volume24h, self.market_cap = fetched_data
                self.price_cents = int(self.price * 100)
            else:
                print("Failed to fetch or received None price from fetch_price_data")
                self.price_cents = None
        except Exception as e:
            print(f"Error updating price data: {e}")
            self.price_cents = None
            
    async def process_open_orders(self, current_market_price_cents: int):
        if current_market_price_cents is None or current_market_price_cents <= 0:
            print("Order processing skipped: Invalid market price.")
            return

        async with self.pool.acquire() as conn:
            open_sell_orders = await conn.fetch("""
                SELECT * FROM orders 
                WHERE status = 'open' AND order_type = 'sell' AND limit_price_cents <= $1
                ORDER BY limit_price_cents ASC, timestamp ASC
            """, current_market_price_cents)

            for order in open_sell_orders:
                async with conn.transaction():
                    try:
                        user_for_update = await conn.fetchrow("SELECT uid, name, cash_c, btc_c, cash_held_c, btc_held_c FROM users WHERE uid = $1 FOR UPDATE", order['uid'])
                        if not user_for_update: continue

                        sats_to_sell = order['btc_amount_sats']
                        
                        if user_for_update['btc_held_c'] < sats_to_sell:
                            print(f"Order {order['order_id']} inconsistency: Not enough held BTC for user {order['uid']}. Skipping.")
                            continue
                            
                        usd_received_at_market = sats_to_sell * current_market_price_cents // SATOSHI
                        
                        new_cash_c = user_for_update['cash_c'] + usd_received_at_market
                        new_btc_held_c = user_for_update['btc_held_c'] - sats_to_sell
                        
                        await conn.execute("UPDATE users SET cash_c = $1, btc_held_c = $2 WHERE uid = $3",
                                           new_cash_c, new_btc_held_c, order['uid'])
                        
                        await conn.execute("UPDATE orders SET status = 'filled', sats_filled = $1 WHERE order_id = $2",
                                           sats_to_sell, order['order_id'])

                        await conn.execute("""
                            INSERT INTO transactions (uid, name, transaction_type, btc_amount_sats, usd_amount_cents, price_at_transaction_cents)
                            VALUES ($1, $2, 'sell', $3, $4, $5)
                        """, order['uid'], user_for_update['name'], sats_to_sell, usd_received_at_market, current_market_price_cents)
                        
                        target_user = self.get_user(order['uid']) or await self.fetch_user(order['uid'])
                        if target_user:
                            embed = discord.Embed(title="💰 Sell Order Filled!", color=discord.Color.orange())
                            embed.add_field(name="Order ID", value=str(order['order_id']), inline=False)
                            embed.add_field(name="Sold", value=fmt_btc(sats_to_sell), inline=True)
                            embed.add_field(name="Price", value=fmt_usd(current_market_price_cents), inline=True)
                            embed.add_field(name="Received", value=fmt_usd(usd_received_at_market), inline=False)
                            try:
                                await target_user.send(embed=embed)
                            except discord.Forbidden:
                                print(f"Could not DM user {order['uid']} about filled sell order {order['order_id']}.")
                    except Exception as e:
                        print(f"Error processing sell order {order['order_id']}: {e}")

            open_buy_orders = await conn.fetch("""
                SELECT * FROM orders
                WHERE status = 'open' AND order_type = 'buy' AND limit_price_cents >= $1
                ORDER BY limit_price_cents DESC, timestamp ASC
            """, current_market_price_cents)

            for order in open_buy_orders:
                async with conn.transaction():
                    try:
                        user_for_update = await conn.fetchrow("SELECT uid, name, cash_c, btc_c, cash_held_c, btc_held_c FROM users WHERE uid = $1 FOR UPDATE", order['uid'])
                        if not user_for_update: continue

                        sats_to_buy = order['btc_amount_sats']
                        cash_held_for_order = order['usd_value_cents']

                        if user_for_update['cash_held_c'] < cash_held_for_order:
                            print(f"Order {order['order_id']} inconsistency: Not enough held cash for user {order['uid']}. Skipping.")
                            continue

                        actual_cost_at_market = sats_to_buy * current_market_price_cents // SATOSHI
                        refund_cents = cash_held_for_order - actual_cost_at_market
                        
                        new_btc_c = user_for_update['btc_c'] + sats_to_buy
                        new_cash_held_c = user_for_update['cash_held_c'] - cash_held_for_order
                        new_cash_c = user_for_update['cash_c'] + refund_cents
                        
                        await conn.execute("UPDATE users SET btc_c = $1, cash_held_c = $2, cash_c = $3 WHERE uid = $4",
                                           new_btc_c, new_cash_held_c, new_cash_c, order['uid'])

                        await conn.execute("UPDATE orders SET status = 'filled', sats_filled = $1 WHERE order_id = $2",
                                           sats_to_buy, order['order_id'])
                        
                        await conn.execute("""
                            INSERT INTO transactions (uid, name, transaction_type, btc_amount_sats, usd_amount_cents, price_at_transaction_cents)
                            VALUES ($1, $2, 'buy', $3, $4, $5)
                        """, order['uid'], user_for_update['name'], sats_to_buy, actual_cost_at_market, current_market_price_cents)

                        target_user = self.get_user(order['uid']) or await self.fetch_user(order['uid'])
                        if target_user:
                            embed = discord.Embed(title="✅ Buy Order Filled!", color=discord.Color.green())
                            embed.add_field(name="Order ID", value=str(order['order_id']), inline=False)
                            embed.add_field(name="Bought", value=fmt_btc(sats_to_buy), inline=True)
                            embed.add_field(name="Price", value=fmt_usd(current_market_price_cents), inline=True)
                            embed.add_field(name="Cost", value=fmt_usd(actual_cost_at_market), inline=False)
                            if refund_cents > 0:
                                embed.add_field(name="Price Improvement Refund", value=fmt_usd(refund_cents), inline=False)
                            try:
                                await target_user.send(embed=embed)
                            except discord.Forbidden:
                                print(f"Could not DM user {order['uid']} about filled buy order {order['order_id']}.")
                    except Exception as e:
                        print(f"Error processing buy order {order['order_id']}: {e}")

    @tasks.loop(minutes=1)
    async def digest_check_loop(self):
        """Check if it's time to send daily digest"""
        if not all((self.series, self.price, self.sma30, self.sma90, self.volume24h, self.market_cap)):
            return
            
        now_utc = datetime.now(timezone.utc)
        today_iso = now_utc.date().isoformat()
        
        if self.last_summary_date != today_iso and now_utc.hour == 8:  # 8 AM UTC
            channel = self.get_channel(settings.channel_id)
            if channel:
                digest_embed = make_daily_digest(self.series, self.price, self.sma30, self.sma90, self.volume24h, self.market_cap)
                await channel.send(embed=digest_embed)
                self.last_summary_date = today_iso
    
    async def on_ready(self):
        """Called when the client is ready"""
        print(f'Logged in as {self.user}')
        if not self.digest_check_loop.is_running():
            self.digest_check_loop.start()
        
    async def on_message(self, message):
        """Handle incoming messages"""
        # Ignore messages from self
        if message.author == self.user:
            return
            
        # Only process messages in the configured channel
        if message.channel.id != settings.channel_id:
            return
            
        # Check for command prefix
        if not message.content.startswith('!'):
            return
            
        # Split into command and argument
        parts = message.content[1:].lower().split(maxsplit=1)
        cmd = parts[0]
        arg = parts[1] if len(parts) > 1 else None
        
        # Process command
        if cmd in ('buy', 'sell', 'balance', 'stats', 'help', 'history', 'admin'):
            try:
                # Create a context object similar to what commands expect
                ctx = type('Context', (), {
                    'author': message.author,
                    'send': message.channel.send,
                    'message': message,
                    'guild': message.guild
                })
                
                await process_command(
                    self.pool,
                    ctx,
                    cmd,
                    arg,
                    self.price,
                    self.price_cents,
                    self.sma30,
                    self.series,
                    self.sma90,
                    self.volume24h,
                    self.market_cap
                )
                
                # Delete command message
                try:
                    await message.delete()
                except discord.errors.Forbidden:
                    print("Warning: Bot lacks permission to delete messages")
                    
            except Exception as e:
                print(f"Error processing command: {e}")
                # Send error to Discord channel
                error_embed = discord.Embed(title="⚠️ Command Error", description=f"Oops! Something went wrong processing `!{cmd}`.", color=discord.Color.red())
                error_embed.add_field(name="Details", value=str(e) if str(e) else "An unexpected error occurred.")
                try:
                    await message.channel.send(embed=error_embed)
                except Exception as send_e:
                    print(f"Additionally, failed to send error embed to channel: {send_e}")

async def start_discord_client(pool):
    """Start the Discord client"""
    client = DinkClient(pool)
    await client.start(settings.discord_token) 