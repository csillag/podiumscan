import hashlib
import os
import time


CACHE_DIR = os.path.expanduser("~/.cache/booklet-reader")


def compute_cache_key(config_bytes, doc_bytes, prompt, level_name):
    """Compute a SHA256 cache key from the inputs."""
    h = hashlib.sha256()
    h.update(config_bytes)
    h.update(doc_bytes)
    h.update(prompt.encode("utf-8"))
    h.update(level_name.encode("utf-8"))
    return h.hexdigest()


def read_cache(key, ttl_seconds=86400):
    """Read a cached response. Returns the raw text or None on miss/expiry."""
    path = os.path.join(CACHE_DIR, f"{key}.txt")
    if not os.path.exists(path):
        return None
    mtime = os.path.getmtime(path)
    if time.time() - mtime > ttl_seconds:
        os.remove(path)
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_cache(key, raw_text):
    """Write a raw LLM response to the cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{key}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(raw_text)
