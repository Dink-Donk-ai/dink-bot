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
                        btc_s BIGINT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS prices (
                        ts TIMESTAMPTZ PRIMARY KEY DEFAULT now(),
                        price_c BIGINT NOT NULL
                    );
                """)
            print("Successfully connected to database")
            return pool
            
        except (asyncpg.PostgresError, asyncpg.InvalidCatalogNameError) as e:
            if attempt == max_retries - 1:
                print(f"Failed to connect to database after {max_retries} attempts: {str(e)}")
                raise
            print(f"Database connection attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            
    return None