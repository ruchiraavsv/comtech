"""Cache the pinned o200k tokenizer using system TLS trust (no verification bypass)."""

import hashlib
import os
import ssl
from pathlib import Path
from urllib.request import urlopen

URL = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
# tiktoken 0.14.0's pinned o200k_base content checksum.
SHA256 = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"


def main():
    directory = Path(os.environ.get("TIKTOKEN_CACHE_DIR", ".cache/tiktoken"))
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / hashlib.sha1(URL.encode()).hexdigest()
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == SHA256:
        print("o200k_base cache verified")
        return
    with urlopen(URL, context=ssl.create_default_context(), timeout=30) as response:
        data = response.read(10_000_000)
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Tokenizer checksum mismatch")
    path.write_bytes(data)
    print("o200k_base downloaded and checksum verified")


if __name__ == "__main__":
    main()
