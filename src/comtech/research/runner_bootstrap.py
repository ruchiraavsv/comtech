"""Trusted fresh-process bootstrap. Not an API process or a language-only sandbox."""

import json
import os
import sys

sys.path.insert(0, "/opt/research")
from data_sdk import DataSDK  # noqa: E402
from runner_wire import MAX_FRAME, MAX_RESULT, encode  # noqa: E402
from sandbox import restrict, restrict_memory  # noqa: E402


def main():
    channel = os.fdopen(int(sys.argv[1]), "r+b", buffering=0)
    job = json.loads(channel.readline(MAX_FRAME + 1))
    os.mkdir("work", 0o700)
    os.chdir("work")
    # Install the boundary before native libraries create worker threads, so they inherit it.
    restrict(job["limits"])
    import numpy  # noqa: F401
    import pandas  # noqa: F401
    import pyarrow

    pyarrow.set_cpu_count(1)
    pyarrow.set_io_thread_count(1)
    restrict_memory(job["limits"])

    def request(operation, arguments):
        channel.write(encode({"type": "data", "operation": operation, "arguments": arguments}))
        raw = channel.readline(MAX_FRAME + 1)
        if not raw or len(raw) > MAX_FRAME:
            raise RuntimeError("Broker unavailable")
        return json.loads(raw)

    scope = {"data": DataSDK(request), "input_refs": job["input_refs"], "__name__": "__research__"}
    try:
        exec(compile(job["code"], "<research>", "exec"), scope)
        if "result" not in scope:
            raise ValueError("Assign a JSON-compatible value to result")
        frame = encode({"type": "result", "status": "success", "value": scope["result"]})
        if len(frame) > MAX_RESULT:
            raise ValueError("Structured result exceeds byte limit; use an artifact")
    except MemoryError:
        frame = encode({"type": "result", "status": "resource_limit", "error": "memory_limit"})
    except OSError as error:
        import errno

        resource_error = error.errno in (errno.ENOSPC, errno.EFBIG, errno.ENOMEM)
        frame = encode(
            {
                "type": "result",
                "status": "resource_limit" if resource_error else "error",
                "error": "resource_limit" if resource_error else type(error).__name__,
            }
        )
    except BaseException as error:
        # No traceback/local variables/source content in the control failure.
        frame = encode({"type": "result", "status": "error", "error": type(error).__name__})
    channel.write(frame)


if __name__ == "__main__":
    if sys.argv[1] == "cleanup":
        import shutil

        root = sys.argv[2]
        os.chmod(root, 0o700)
        for directory, dirs, _ in os.walk(root, followlinks=False):
            for name in dirs:
                path = os.path.join(directory, name)
                if not os.path.islink(path):
                    os.chmod(path, 0o700)
        shutil.rmtree(root)
    else:
        main()
