"""Bounded JSON frames, shared by the trusted client and minimal runner image."""

import json

MAX_FRAME = 33 * 1024**2
MAX_JOB = 128 * 1024
MAX_RESULT = 64 * 1024
DEFAULT_LIMITS = {"wall_seconds": 120, "cpu_seconds": 60, "memory_bytes": 512 * 1024**2}


def encode(value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    if len(raw) > MAX_FRAME:
        raise ValueError("Protocol frame exceeds limit")
    return raw + b"\n"


async def receive(reader, maximum=MAX_FRAME):
    raw = await reader.readline()
    if not raw:
        raise EOFError("Runner connection closed")
    if len(raw) > maximum or not raw.endswith(b"\n"):
        raise ValueError("Protocol frame exceeds limit")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Protocol object required")
    return value


async def send(writer, value):
    writer.write(encode(value))
    await writer.drain()


def job_request(value):
    if set(value) != {"execution_id", "code", "input_refs", "limits", "environment_digest"}:
        raise ValueError("Invalid runner request")
    if not isinstance(value["environment_digest"], str) or len(value["environment_digest"]) != 64:
        raise ValueError("Pinned runner environment required")
    from uuid import UUID

    UUID(value["execution_id"])
    if not isinstance(value["code"], str) or not 1 <= len(value["code"].encode()) <= 65536:
        raise ValueError("Generated code must fit 64 KiB")
    refs = value["input_refs"]
    if (
        not isinstance(refs, list)
        or len(refs) > 1000
        or any(not isinstance(x, str) or len(x) > 100 for x in refs)
    ):
        raise ValueError("Invalid input references")
    limits = value["limits"]
    if set(limits) != set(DEFAULT_LIMITS) or any(
        type(limits[k]) is not int or not 1 <= limits[k] <= cap for k, cap in DEFAULT_LIMITS.items()
    ):
        raise ValueError("Invalid execution limits")
    return value
