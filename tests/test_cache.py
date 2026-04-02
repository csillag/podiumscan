import os
import time
import pytest
from booklet_reader.cache import compute_cache_key, read_cache, write_cache, CACHE_DIR


class TestComputeCacheKey:
    def test_returns_hex_string(self):
        key = compute_cache_key(b"config", b"doc", "prompt", "PDF")
        assert isinstance(key, str)
        assert len(key) == 64  # SHA256 hex

    def test_same_inputs_same_key(self):
        k1 = compute_cache_key(b"config", b"doc", "prompt", "PDF")
        k2 = compute_cache_key(b"config", b"doc", "prompt", "PDF")
        assert k1 == k2

    def test_different_inputs_different_key(self):
        k1 = compute_cache_key(b"config", b"doc", "prompt", "PDF")
        k2 = compute_cache_key(b"config", b"doc", "prompt", "images")
        assert k1 != k2

    def test_comment_changes_key(self):
        k1 = compute_cache_key(b"config", b"doc", "prompt without comment", "PDF")
        k2 = compute_cache_key(b"config", b"doc", "prompt with comment", "PDF")
        assert k1 != k2


class TestWriteAndReadCache:
    def test_write_then_read(self, tmp_path, monkeypatch):
        monkeypatch.setattr("booklet_reader.cache.CACHE_DIR", str(tmp_path))
        key = "abc123"
        write_cache(key, "raw llm response text")
        result = read_cache(key, ttl_seconds=86400)
        assert result == "raw llm response text"

    def test_read_miss(self, tmp_path, monkeypatch):
        monkeypatch.setattr("booklet_reader.cache.CACHE_DIR", str(tmp_path))
        result = read_cache("nonexistent", ttl_seconds=86400)
        assert result is None

    def test_expired_entry(self, tmp_path, monkeypatch):
        monkeypatch.setattr("booklet_reader.cache.CACHE_DIR", str(tmp_path))
        key = "expired123"
        write_cache(key, "old data")
        cache_file = os.path.join(str(tmp_path), f"{key}.txt")
        old_time = time.time() - 86401
        os.utime(cache_file, (old_time, old_time))
        result = read_cache(key, ttl_seconds=86400)
        assert result is None
        assert not os.path.exists(cache_file)

    def test_creates_cache_dir(self, tmp_path, monkeypatch):
        cache_dir = os.path.join(str(tmp_path), "subdir", "cache")
        monkeypatch.setattr("booklet_reader.cache.CACHE_DIR", cache_dir)
        write_cache("key123", "data")
        assert os.path.exists(os.path.join(cache_dir, "key123.txt"))
