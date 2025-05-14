#!/usr/bin/env python3
"""
One-time script to update database schema to add missing columns
"""
import asyncio
import asyncpg
from config import settings

async def update_schema():
    print("Connecting to database...")
    conn = await asyncpg.connect(settings.database_url)
    
    try:
        # Check if cash_held_c column exists
        column_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'cash_held_c'
            )
        """)
        
        if not column_exists:
            print("Adding cash_held_c column to users table...")
            await conn.execute("ALTER TABLE users ADD COLUMN cash_held_c BIGINT NOT NULL DEFAULT 0")
            print("cash_held_c column added successfully!")
        else:
            print("cash_held_c column already exists.")
        
        # Check if btc_held_c column exists
        column_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'btc_held_c'
            )
        """)
        
        if not column_exists:
            print("Adding btc_held_c column to users table...")
            await conn.execute("ALTER TABLE users ADD COLUMN btc_held_c BIGINT NOT NULL DEFAULT 0")
            print("btc_held_c column added successfully!")
        else:
            print("btc_held_c column already exists.")
            
        # Check if join_timestamp column exists
        column_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'join_timestamp'
            )
        """)
        
        if not column_exists:
            print("Adding join_timestamp column to users table...")
            await conn.execute("ALTER TABLE users ADD COLUMN join_timestamp TIMESTAMPTZ DEFAULT now()")
            print("join_timestamp column added successfully!")
        else:
            print("join_timestamp column already exists.")
            
        print("Schema update completed successfully!")
        
    except Exception as e:
        print(f"Error updating schema: {e}")
    finally:
        await conn.close()
        print("Database connection closed.")

if __name__ == "__main__":
    asyncio.run(update_schema())