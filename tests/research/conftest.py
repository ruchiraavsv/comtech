import os
from uuid import uuid4

import pytest
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from comtech.db import database, migrate


@pytest.fixture
async def unmigrated_pool():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to an isolated test database")
    name = "research_test_" + uuid4().hex
    async with database(url) as admin:
        async with admin.connection() as conn:
            await conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
        try:
            async with AsyncConnectionPool(
                url,
                open=False,
                min_size=1,
                max_size=6,
                kwargs={
                    "autocommit": True,
                    "row_factory": dict_row,
                    "options": f"-csearch_path={name}",
                },
            ) as pool:
                await pool.wait()
                yield pool
        finally:
            async with admin.connection() as conn:
                await conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))


@pytest.fixture
async def research_pool(unmigrated_pool):
    await migrate(unmigrated_pool)
    return unmigrated_pool
