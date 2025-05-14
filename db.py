import asyncpg
import asyncio
from typing import Optional

async def init_db(dsn: str, max_retries: int = 5, retry_delay: int = 5) -> Optional[asyncpg.Pool]:
    """Initialize database with connection retries.
    
    Args:
        dsn: Database connection string
        max_retries: Maximum number of connection attempts
        retry_delay: Delay in seconds between retries
    """
    for attempt in range(max_retries):
        try:
            pool = await asyncpg.create_pool(
                dsn,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            
            async with pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        uid BIGINT PRIMARY KEY, 
                        name TEXT, 
                        cash_c BIGINT NOT NULL, 
                        btc_c BIGINT NOT NULL,
                        cash_held_c BIGINT NOT NULL DEFAULT 0,      -- Added for held cash
                        btc_held_c BIGINT NOT NULL DEFAULT 0,        -- Added for held btc
                        join_timestamp TIMESTAMPTZ DEFAULT now()    -- Added for join timestamp
                    );
                    CREATE TABLE IF NOT EXISTS prices (
                        ts TIMESTAMPTZ PRIMARY KEY DEFAULT now(),
                        price_c BIGINT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS transactions (
                        transaction_id SERIAL PRIMARY KEY,
                        uid BIGINT NOT NULL,
                        name TEXT NOT NULL,
                        transaction_type TEXT NOT NULL,                       -- 'buy' or 'sell'
                        btc_amount_sats BIGINT NOT NULL,
                        usd_amount_cents BIGINT NOT NULL,
                        price_at_transaction_cents BIGINT NOT NULL,         -- Price of 1 BTC in USD cents
                        timestamp TIMESTAMPTZ DEFAULT now()
                    );
                    CREATE TABLE IF NOT EXISTS orders (
                        order_id SERIAL PRIMARY KEY,
                        uid BIGINT NOT NULL REFERENCES users(uid) ON DELETE CASCADE, -- Foreign key to users
                        name TEXT,                                          -- User's name at time of order
                        order_type TEXT NOT NULL,                           -- 'buy' or 'sell'
                        btc_amount_sats BIGINT NOT NULL,
                        sats_filled BIGINT NOT NULL DEFAULT 0,
                        limit_price_cents BIGINT NOT NULL,                  -- Price of 1 BTC in USD cents
                        usd_value_cents BIGINT NOT NULL,                    -- Total USD value of order (cost for buy, expected for sell)
                        status TEXT NOT NULL DEFAULT 'open',                -- 'open', 'filled', 'cancelled', 'partially_filled'
                        timestamp TIMESTAMPTZ DEFAULT now()
                    );
                    
                    -- Add the join_timestamp column to users table if it doesn't exist
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS join_timestamp TIMESTAMPTZ DEFAULT now();
                """)
            print("Successfully connected to database and ensured schema.")
            return pool
            
        except (asyncpg.PostgresError, asyncpg.InvalidCatalogNameError) as e:
            if attempt == max_retries - 1:
                print(f"Failed to connect to database after {max_retries} attempts: {str(e)}")
                raise
            print(f"Database connection attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            
    return None