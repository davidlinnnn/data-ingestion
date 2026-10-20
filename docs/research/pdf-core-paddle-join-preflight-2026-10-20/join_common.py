"""Small evidence helpers for this zero-inference experiment only."""
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def verify_registration():
    registration = read(HERE / "registration.json")
    for path, digest in registration["hashes"].items():
        assert sha(path) == digest, path
    return registration


def deny_network():
    os.environ.update(PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK="True",
        PADDLE_PDX_CACHE_HOME="/private/tmp/pdf-core-paddle-join-20261020/cache",
        HF_HOME="/private/tmp/pdf-core-paddle-join-20261020/hf", HF_HUB_OFFLINE="1")
    os.environ.pop("OPENAI_API_KEY", None)
    attempts = []

    def guard(event, args):
        if event in ("socket.connect", "socket.getaddrinfo"):
            attempts.append(event)
            raise RuntimeError("Network forbidden in zero-inference worker")

    sys.addaudithook(guard)
    return attempts
