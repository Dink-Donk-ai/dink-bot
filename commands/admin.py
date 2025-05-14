import asyncpg
import discord # Required for user parsing
from config import settings
from utils import fmt_usd, fmt_btc

INITIAL_CASH_CENTS = 100_000 # Starting cash for new users, in cents
SATOSHI = 100_000_000

async def run(pool: asyncpg.Pool, ctx, args: list[str] = None):
    """
    Handles admin commands. Expects args: [sub_command, target_user, ...values]
    """
    if ctx.author.id not in settings.admin_user_ids:
        await ctx.send("⛔ You are not authorized to use admin commands.")
        return False

    if not args or len(args) < 1:
        await ctx.send("Usage: `!admin <sub_command> [arguments...]`")
        return False

    sub_command = args[0].lower()

    # Commands that don't require a target user first
    if sub_command not in ["resetuser", "givecash", "givebtc"]:
        await ctx.send(f"Unknown admin sub-command: `{sub_command}`. Available: `resetuser`, `givecash`, `givebtc`")
        return False

    if len(args) < 2:
        await ctx.send(f"Usage: `!admin {sub_command} <user_mention_or_id> [value]`")
        return False

    target_user_str = args[1]
    target_user_id = None
    target_user_name = "Unknown User"

    try:
        if target_user_str.startswith('<') and target_user_str.endswith('>'):
            target_user_id = int(target_user_str.strip('<@!>'))
        else:
            target_user_id = int(target_user_str)
    except ValueError:
        await ctx.send(f"⚠️ Invalid user: {target_user_str}. Please use a mention or a valid user ID.")
        return False

    try:
        target_member = await ctx.message.guild.fetch_member(target_user_id)
        if target_member:
            target_user_name = target_member.display_name
    except discord.NotFound:
        # User might not be in server, but we can still operate on their ID if they exist in DB
        # We'll use their provided ID as name if not found or if direct ID was given
        async with pool.acquire() as conn:
            db_user = await conn.fetchrow("SELECT name FROM users WHERE uid = $1", target_user_id)
            if db_user:
                target_user_name = db_user['name']
            else:
                 # If not in server and not in DB, it's an issue for commands that need to create user
                 pass # Handled by ON CONFLICT later
    except discord.HTTPException:
        await ctx.send(f"⚠️ Could not fetch user details for ID {target_user_id} from Discord. Will proceed with ID.")
        # Proceeding, name might remain "Unknown User" or be fetched from DB if exists

    if sub_command == "resetuser":
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("""
                    INSERT INTO users (uid, name, cash_c, btc_c)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (uid) DO UPDATE SET name = EXCLUDED.name, cash_c = EXCLUDED.cash_c, btc_c = EXCLUDED.btc_c
                """, target_user_id, target_user_name, INITIAL_CASH_CENTS, 0)
        await ctx.send(f"✅ User **{target_user_name}** (ID: {target_user_id}) has been reset to {fmt_usd(INITIAL_CASH_CENTS)} and 0 BTC.")
        return True

    elif sub_command == "givecash":
        if len(args) < 3:
            await ctx.send("Usage: `!admin givecash <user_mention_or_id> <usd_amount>`")
            return False
        try:
            amount_usd = float(args[2])
            if amount_usd == 0: # Allow giving 0 for some reason? Or make it > 0?
                 await ctx.send("⚠️ Cash amount cannot be zero. To remove cash, use a negative value (not yet implemented). ")
                 return False
            amount_cents = int(round(amount_usd * 100))
        except ValueError:
            await ctx.send("⚠️ Invalid cash amount.")
            return False

        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (uid, name, cash_c, btc_c)
                VALUES ($1, $2, $3, 0)  -- Initial BTC is 0 if new user
                ON CONFLICT (uid) DO UPDATE SET 
                    name = EXCLUDED.name, 
                    cash_c = users.cash_c + EXCLUDED.cash_c 
            """, target_user_id, target_user_name, amount_cents)
        action = "received" if amount_cents >=0 else "had deducted"
        await ctx.send(f"✅ User **{target_user_name}** {action} {fmt_usd(abs(amount_cents))}.")
        return True

    elif sub_command == "givebtc":
        if len(args) < 3:
            await ctx.send("Usage: `!admin givebtc <user_mention_or_id> <btc_amount>`")
            return False
        try:
            amount_btc_float = float(args[2])
            if amount_btc_float == 0:
                 await ctx.send("⚠️ BTC amount cannot be zero. To remove BTC, use a negative value (not yet implemented). ")
                 return False
            amount_sats = int(round(amount_btc_float * SATOSHI))
            if amount_sats == 0 and amount_btc_float != 0: # for very small float values that round to 0 sat
                await ctx.send("⚠️ BTC amount is too small, rounds to 0 satoshis.")
                return False
        except ValueError:
            await ctx.send("⚠️ Invalid BTC amount.")
            return False

        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (uid, name, cash_c, btc_c)
                VALUES ($1, $2, 0, $3) -- Initial cash is 0 if new user
                ON CONFLICT (uid) DO UPDATE SET 
                    name = EXCLUDED.name, 
                    btc_c = users.btc_c + EXCLUDED.btc_c
            """, target_user_id, target_user_name, amount_sats)
        action = "received" if amount_sats >=0 else "had deducted"
        await ctx.send(f"✅ User **{target_user_name}** {action} {fmt_btc(abs(amount_sats))}.")
        return True
    # This else should not be reached due to check at the top
    # else:
    #     await ctx.send(f"Unknown admin sub-command: `{sub_command}`. Available: `resetuser`, `givecash`, `givebtc`")
    #     return False

    return True # Default to true if a command was processed 