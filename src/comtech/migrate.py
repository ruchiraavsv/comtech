import asyncio

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from comtech.db import database, migrate
from comtech.settings import Settings


async def main():
    settings = Settings()
    async with database(settings.require_database()) as pool:
        await migrate(pool)
        await AsyncPostgresSaver(pool).setup()
    print("Application and LangGraph database migrations complete.")


if __name__ == "__main__":
    asyncio.run(main())
