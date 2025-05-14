#!/usr/bin/env python3
"""
Dink‑Bot - A Discord bot for simulated Bitcoin trading
"""
import asyncio
from db import init_db

from config import settings
from discord_client import start_discord_client
from update_schema import update_schema

async def main():
    """Main entry point"""
    pool = None # Initialize pool to None for finally block
    try:
        print("Running database schema update...")
        await update_schema()
        print("Schema update completed, initializing main database connection...")
        
        pool = await init_db(settings.database_url)
        if not pool:
            print("Failed to create database pool via init_db. Bot cannot start.")
            return

        await start_discord_client(pool)

    except Exception as e:
        print(f"Fatal error in main: {e}")
        raise # Re-raise the exception to ensure it's logged by the environment
    finally:
        if pool:
            print("Closing database pool...")
            await pool.close()
            print("Database pool closed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        print(f"Fatal error in __main__: {e}")
        raise