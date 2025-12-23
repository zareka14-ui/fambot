import asyncpg
import os
import logging

DATABASE_URL = os.getenv("DATABASE_URL")
pool = None

async def init_pool():
    global pool
    if pool is None:
        try:
            pool = await asyncpg.create_pool(DATABASE_URL)
            logging.info("DB Pool initialized successfully")
        except Exception as e:
            logging.error(f"Failed to create DB pool: {e}")
            raise

async def get_db():
    if pool is None:
        await init_pool()
    return pool
