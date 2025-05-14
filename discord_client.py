"""
Discord client implementation
"""
import discord
from discord.ext import tasks
import asyncio
from datetime import datetime, timezone

from config import settings
from bot_utils import process_command, fetch_price_data
from utils import make_daily_digest

class DinkClient(discord.Client):
    def __init__(self, pool):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.pool = pool
        self.price = None
        self.price_cents = None
        self.sma30 = None
        self.series = None
        self.last_summary_date = None
        
        # Start background tasks
        self.price_update_loop.start()
        
    async def setup_hook(self):
        """Called when the client is being set up"""
        await self.update_price_data()
        
    @tasks.loop(minutes=5)
    async def price_update_loop(self):
        """Update price data every 5 minutes"""
        await self.update_price_data()
        
    async def update_price_data(self):
        """Fetch and update price data"""
        try:
            self.series, self.price, self.sma30 = await fetch_price_data()
            if self.price:
                self.price_cents = int(self.price * 100)
        except Exception as e:
            print(f"Error updating price data: {e}")
            
    @tasks.loop(minutes=1)
    async def digest_check_loop(self):
        """Check if it's time to send daily digest"""
        if not all((self.series, self.price, self.sma30)):
            return
            
        now_utc = datetime.now(timezone.utc)
        today_iso = now_utc.date().isoformat()
        
        if self.last_summary_date != today_iso and now_utc.hour == 8:  # 8 AM UTC
            channel = self.get_channel(settings.channel_id)
            if channel:
                digest = make_daily_digest(self.series, self.price, self.sma30)
                await channel.send(digest)
                self.last_summary_date = today_iso
    
    async def on_ready(self):
        """Called when the client is ready"""
        print(f'Logged in as {self.user}')
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
        if cmd in ('buy', 'sell', 'balance', 'stats', 'help'):
            try:
                # Create a context object similar to what commands expect
                ctx = type('Context', (), {
                    'author': message.author,
                    'send': message.channel.send,
                    'message': message
                })
                
                await process_command(
                    self.pool,
                    ctx,
                    cmd,
                    arg,
                    self.price,
                    self.price_cents,
                    self.sma30,
                    self.series
                )
                
                # Delete command message
                try:
                    await message.delete()
                except discord.errors.Forbidden:
                    print("Warning: Bot lacks permission to delete messages")
                    
            except Exception as e:
                print(f"Error processing command: {e}")
                await message.channel.send(f"⚠️ Error processing command: {str(e)}")

async def start_discord_client(pool):
    """Start the Discord client"""
    client = DinkClient(pool)
    await client.start(settings.discord_token) 