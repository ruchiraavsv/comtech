"""Trusted Unix transport; broker capabilities never cross into the generated-code process."""

import asyncio
import contextlib

from .runner_wire import MAX_FRAME, MAX_RESULT, receive, send


class RunnerClient:
    def __init__(self, path):
        self.path = str(path)

    async def connect(self):
        async with asyncio.timeout(3):
            return await asyncio.open_unix_connection(self.path, limit=MAX_FRAME + 1)

    async def describe(self):
        reader, writer = await self.connect()
        try:
            async with asyncio.timeout(3):
                await send(writer, {"operation": "describe"})
                return await receive(reader, MAX_RESULT)
        finally:
            writer.close()
            await writer.wait_closed()

    async def execute(self, job, data_call, check_active):
        async def exchange():
            reader, writer = await self.connect()
            try:
                await send(writer, job)
                sequence = 0
                while True:
                    frame = await receive(reader)
                    if frame.get("type") == "result":
                        return frame
                    sequence += 1
                    if frame.get("type") != "data" or frame.get("sequence") != sequence:
                        raise ValueError("Invalid runner data sequence")
                    reply = await data_call(frame["operation"], frame["arguments"], sequence)
                    await send(
                        writer, {"type": "data_result", "sequence": sequence, "reply": reply}
                    )
            finally:
                writer.close()  # EOF instructs the supervisor to kill/clean the execution.
                with contextlib.suppress(ConnectionError):
                    await writer.wait_closed()

        async def monitor():
            while True:
                await check_active()
                await asyncio.sleep(0.25)

        work, watch = asyncio.create_task(exchange()), asyncio.create_task(monitor())
        try:
            async with asyncio.timeout(job["limits"]["wall_seconds"] + 8):
                done, _ = await asyncio.wait([work, watch], return_when=asyncio.FIRST_COMPLETED)
                if watch in done:
                    watch.result()
                return work.result()
        finally:
            for task in (work, watch):
                task.cancel()
            await asyncio.gather(work, watch, return_exceptions=True)
