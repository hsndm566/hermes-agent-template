import asyncpg
from .config import settings

pool: asyncpg.Pool | None = None

async def connect_db():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10, command_timeout=20)
    return pool

async def close_db():
    global pool
    if pool:
        await pool.close()
        pool = None

async def get_pool():
    return await connect_db()
