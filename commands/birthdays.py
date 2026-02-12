# commands/birthdays.py
import asyncpg
import discord
from datetime import datetime, date

async def add_birthday(pool: asyncpg.Pool, ctx, name: str, date_str: str):
    """Add a birthday to the database."""
    uid = ctx.author.id
    
    # Parse date
    try:
        # Try DD/MM/YYYY first
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        day, month, year = dt.day, dt.month, dt.year
    except ValueError:
        try:
            # Try DD/MM
            dt = datetime.strptime(date_str, "%d/%m")
            day, month, year = dt.day, dt.month, None
        except ValueError:
            await ctx.send("⚠️ Invalid date format. Please use DD/MM or DD/MM/YYYY (e.g., `25/12` or `25/12/1990`).")
            return False

    async with pool.acquire() as conn:
        try:
            # Check if user exists first (integrity constraint)
            # This should generally be true if they are using the bot, but good to be safe if foreign key is strict
            # The FK is strictly to users(uid), so we must ensure user is in users table.
            # Usually buy/balance ensures this, but let's be safe.
            await conn.execute("""
                INSERT INTO users(uid, name, cash_c, btc_c)
                VALUES($1, $2, $3, $4)
                ON CONFLICT(uid) DO NOTHING
            """, uid, ctx.author.display_name, 100_000, 0) # Default values if new

            await conn.execute("""
                INSERT INTO birthdays (uid, name, day, month, year)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (uid, name) 
                DO UPDATE SET day = EXCLUDED.day, month = EXCLUDED.month, year = EXCLUDED.year
            """, uid, name, day, month, year)
            
            date_display = f"{day:02d}/{month:02d}" + (f"/{year}" if year else "")
            await ctx.send(f"✅ Birthday for **{name}** added/updated: {date_display}")
            return True
        except Exception as e:
            print(f"Error adding birthday: {e}")
            await ctx.send("⚠️ An error occurred while saving the birthday.")
            return False

async def remove_birthday(pool: asyncpg.Pool, ctx, name: str):
    """Remove a birthday from the database."""
    uid = ctx.author.id
    
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM birthdays WHERE uid = $1 AND name = $2", uid, name)
        
        if result == "DELETE 0":
            await ctx.send(f"⚠️ Could not find a birthday for **{name}** in your list.")
        else:
            await ctx.send(f"🗑️ Birthday for **{name}** removed.")
            return True

async def list_birthdays(pool: asyncpg.Pool, ctx):
    """List all birthdays for the user."""
    uid = ctx.author.id
    
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT name, day, month, year FROM birthdays 
            WHERE uid = $1 
            ORDER BY month ASC, day ASC
        """, uid)
        
    if not rows:
        await ctx.send("📅 You haven't added any birthdays yet! Use `!birthday add <Name> <DD/MM>`.")
        return True
        
    embed = discord.Embed(title="🎂 Your Birthday List", color=discord.Color.purple())
    
    description = ""
    for row in rows:
        date_str = f"{row['day']:02d}/{row['month']:02d}"
        if row['year']:
            date_str += f"/{row['year']}"
        description += f"**{row['name']}**: {date_str}\n"
        
    embed.description = description
    await ctx.send(embed=embed)
    return True

async def force_birthday_check(pool: asyncpg.Pool, ctx, client):
    """Manually trigger the birthday check for testing."""
    if not client:
        await ctx.send("⚠️ Internal error: Client reference missing.")
        return False
        
    # We need to import the check function here to avoid circular imports if possible, 
    # or rely on the client having the method.
    # Ideally, we call the method on the client if we attach it there, 
    # OR we import the logic from a utility file.
    # Since the check loop will be in discord_client.py, we might want to trigger it there.
    
    if hasattr(client, 'check_birthdays'):
        await ctx.send("🔄 Forcing birthday check...")
        await client.check_birthdays()
        await ctx.send("✅ Check completed. Check your DMs!")
        return True
    else:
        await ctx.send("⚠️ Birthday check function not found on client.")
        return False

async def handle_birthday_command(pool: asyncpg.Pool, ctx, args, client):
    """Dispatch birthday subcommands."""
    if not args:
        await ctx.send(
            "🎈 **Birthday Commands** 🎈\n"
            "`!birthday add <Name> <DD/MM>` - Add a friend's birthday\n"
            "`!birthday remove <Name>` - Remove a friend's birthday\n"
            "`!birthday list` - List all your saved birthdays\n"
            "`!birthday testcheck` - Test notifications now"
        )
        return False
        
    parts = args.split(maxsplit=1)
    subcmd = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else None
    
    if subcmd == "add":
        if not rest:
            await ctx.send("Usage: `!birthday add <Name> <DD/MM>`")
            return False
        # Split name and date. Date is last part.
        # Allow names with spaces: "Best Friend 25/12"
        # We assume the last whitespace-delimited token is the date.
        try:
            name_parts = rest.rsplit(maxsplit=1)
            if len(name_parts) != 2:
                await ctx.send("Usage: `!birthday add <Name> <DD/MM>`")
                return False
            name, date_str = name_parts[0], name_parts[1]
            return await add_birthday(pool, ctx, name, date_str)
        except Exception:
             await ctx.send("Usage: `!birthday add <Name> <DD/MM>`")
             return False
            
    elif subcmd == "remove":
        if not rest:
            await ctx.send("Usage: `!birthday remove <Name>`")
            return False
        return await remove_birthday(pool, ctx, rest)
        
    elif subcmd == "list":
        return await list_birthdays(pool, ctx)
        
    elif subcmd == "testcheck":
        return await force_birthday_check(pool, ctx, client)
        
    else:
        await ctx.send(f"⚠️ Unknown subcommand `{subcmd}`. Use `add`, `remove`, `list`, or `testcheck`.")
        return False
