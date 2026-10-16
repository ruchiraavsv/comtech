"""Single-slot, offline Linux process supervisor. Only trusted Unix clients can submit work."""

import asyncio
import contextlib
import ctypes
import hashlib
import json
import os
import socket
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/opt/research")
from runner_wire import MAX_FRAME, MAX_JOB, job_request, receive, send  # noqa: E402
from sandbox import assert_container  # noqa: E402

CONTROL = Path("/run/research-control")
BOOTSTRAP = "/opt/research/runner_bootstrap.py"
ENV = {
    "PATH": "/opt/venv/bin:/usr/bin:/bin",
    "HOME": "/nonexistent",
    "LANG": "C.UTF-8",
    "OPENBLAS_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
}


class Runner:
    def __init__(self):
        self.busy = False
        self.active = set()
        self.environment = json.loads(Path("/opt/research/environment.json").read_text())
        self.environment_digest = hashlib.sha256(
            json.dumps(self.environment, sort_keys=True).encode()
        ).hexdigest()

    async def serve(self, reader, writer):
        current = asyncio.current_task()
        self.active.add(current)
        acquired = False
        try:
            async with asyncio.timeout(5):
                request = await receive(reader, MAX_JOB)
            if request == {"operation": "describe"}:
                await send(
                    writer,
                    {
                        "environment": self.environment,
                        "environment_digest": self.environment_digest,
                        "busy": self.busy,
                    },
                )
                return
            job = job_request(request)
            if job["environment_digest"] != self.environment_digest:
                raise ValueError("Runner environment changed")
            if self.busy:
                await send(writer, {"type": "result", "status": "error", "error": "runner_busy"})
                return
            self.busy = acquired = True
            result = await self.execute(job, reader, writer)
            await send(
                writer,
                {
                    **result,
                    "execution_id": job["execution_id"],
                    "environment_digest": self.environment_digest,
                },
            )
        except (EOFError, ConnectionError, ValueError, TimeoutError):
            pass  # Control disconnects never become successful execution receipts.
        finally:
            if acquired:
                self.busy = False
            self.active.discard(current)
            writer.close()
            with contextlib.suppress(ConnectionError):
                await writer.wait_closed()

    async def execute(self, job, control_reader, control_writer):
        started = time.monotonic()
        workspace = Path(tempfile.mkdtemp(prefix="research-", dir="/tmp"))
        workspace.chmod(0o777)  # noqa: ASYNC240 - local bounded tmpfs metadata
        parent, child = socket.socketpair()
        process = None
        tasks = []
        data_writer = None
        output = {"stdout": bytearray(), "stderr": bytearray()}
        failure = asyncio.get_running_loop().create_future()
        responses = asyncio.Queue(maxsize=1)
        result = {"type": "result", "status": "error", "error": "bootstrap_failure"}
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",
                BOOTSTRAP,
                str(child.fileno()),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                pass_fds=(child.fileno(),),
                cwd=workspace,
                env=ENV,
                user=10002,
                group=10002,
                extra_groups=[],
                start_new_session=True,
            )
            child.close()
            data_reader, data_writer = await asyncio.open_connection(
                sock=parent, limit=MAX_FRAME + 1
            )
            await send(data_writer, job)

            async def capture(name, stream):
                while chunk := await stream.read(4096):
                    remaining = 16384 - len(output[name])
                    output[name].extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        if not failure.done():
                            failure.set_result("output_limit")
                        return

            async def control():
                while True:
                    response = await receive(control_reader)
                    if response.get("type") != "data_result":
                        raise EOFError("Execution cancelled")
                    await responses.put(response)

            async def run():
                sequence = 0
                while True:
                    frame = await receive(data_reader)
                    if frame.get("type") == "result":
                        if frame.get("status") not in ("success", "error", "resource_limit"):
                            raise ValueError("Invalid result status")
                        await process.wait()
                        await asyncio.gather(*captures)
                        if process.returncode:
                            return {
                                "type": "result",
                                "status": "resource_limit",
                                "error": "process_exit",
                                "exit_code": process.returncode,
                            }
                        return frame
                    if set(frame) != {"type", "operation", "arguments"} or frame["type"] != "data":
                        raise ValueError("Invalid generated request")
                    sequence += 1
                    if sequence > 120:
                        raise ValueError("Execution data request limit")
                    await send(control_writer, {**frame, "sequence": sequence})
                    response = await responses.get()
                    if response.get("sequence") != sequence:
                        raise ValueError("Mismatched data receipt")
                    await send(data_writer, response["reply"])

            captures = [
                asyncio.create_task(capture(name, getattr(process, name))) for name in output
            ]
            work, monitor = asyncio.create_task(run()), asyncio.create_task(control())
            tasks = [*captures, work, monitor]
            async with asyncio.timeout(job["limits"]["wall_seconds"]):
                done, _ = await asyncio.wait(
                    [work, monitor, failure], return_when=asyncio.FIRST_COMPLETED
                )
                if failure in done:
                    result = {
                        "type": "result",
                        "status": "resource_limit",
                        "error": failure.result(),
                    }
                elif monitor in done:
                    with contextlib.suppress(EOFError, ConnectionError, ValueError):
                        monitor.result()
                    result = {
                        "type": "result",
                        "status": "cancelled",
                        "error": "control_disconnected",
                    }
                else:
                    result = work.result()
        except TimeoutError:
            result = {"type": "result", "status": "timeout", "error": "wall_limit"}
        except (EOFError, ConnectionError, ValueError):
            result = {"type": "result", "status": "error", "error": "execution_channel_closed"}
            if process:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(process.wait(), 0.2)
        finally:
            killed = False
            if process and process.returncode is None:
                killed = True
                process.kill()  # Kernel disallows generated children; kills the entire allowed job.
            if process:
                await process.wait()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if data_writer:
                data_writer.close()
            parent.close()
            child.close()
            if (workspace / "work").exists():
                clean = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-I",
                    BOOTSTRAP,
                    "cleanup",
                    str(workspace / "work"),
                    env=ENV,
                    user=10002,
                    group=10002,
                    extra_groups=[],
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                async with asyncio.timeout(5):
                    if await clean.wait():
                        os._exit(70)  # Never accept another job with uncertain cleanup.
            workspace.rmdir()  # noqa: ASYNC240 - local bounded tmpfs metadata
        if (
            not killed
            and result.get("error") == "execution_channel_closed"
            and process.returncode
            in (
                -9,
                -24,
                -25,
            )
        ):
            result.update(status="resource_limit", error="process_resource_limit")
        return {
            **result,
            **{k: v.decode("utf-8", errors="replace") for k, v in output.items()},
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }


async def main():
    assert_container()
    if ctypes.CDLL(None).prctl(4, 0, 0, 0, 0):
        raise RuntimeError("Cannot protect supervisor process")
    CONTROL.mkdir(mode=0o700, exist_ok=True)  # noqa: ASYNC240 - startup only
    CONTROL.chmod(0o700)  # noqa: ASYNC240 - startup only
    path = CONTROL / "runner.sock"
    path.unlink(missing_ok=True)
    runner = Runner()
    server = await asyncio.start_unix_server(runner.serve, str(path), limit=MAX_FRAME + 1)
    path.chmod(0o600)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
