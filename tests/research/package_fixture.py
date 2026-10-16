"""Only for the isolated Compose readiness test; creates a synthetic published release."""

import asyncio
import os
from pathlib import Path

from comtech.db import database, migrate
from tests.retrieval.test_sources import BUILD, make_release


async def main():
    root = Path("/fixtures")
    if not (root / "releases" / BUILD).exists():
        make_release(root, ["Synthetic package readiness fixture."])
    os.chown("/artifacts", 10000, 10000)
    os.chmod("/artifacts", 0o700)
    async with database(os.environ["TEST_DATABASE_URL"]) as pool:
        await migrate(pool)


if __name__ == "__main__":
    asyncio.run(main())
