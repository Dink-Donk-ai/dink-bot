import asyncpg

async def init_db(dsn: str):
    pool = await asyncpg.create_pool(dsn)
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
    return pool