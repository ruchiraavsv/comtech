"""Token measurement shared by tools and model calls; no semantic decisions."""

import hashlib
import json
import os
from pathlib import Path

import tiktoken
from pydantic import BaseModel


def plain(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def serialized(value):
    return json.dumps(plain(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class TokenCounter:
    def __init__(self, encoding="cl100k_base"):
        os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(Path(".cache/tiktoken").resolve()))
        self.encoding = tiktoken.get_encoding(encoding)

    def text(self, value):
        return len(self.encoding.encode(value, disallowed_special=()))

    def count(self, value):
        return self.text(serialized(value))

    def prefix(self, text, maximum):
        # Character slicing preserves exact Unicode source offsets.
        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if self.text(text[:mid]) <= maximum:
                low = mid
            else:
                high = mid - 1
        return text[:low]
