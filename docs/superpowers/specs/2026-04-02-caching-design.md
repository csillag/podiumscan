# LLM Response Caching — Design Spec

## Overview

Cache LLM responses to avoid redundant API calls when reprocessing the same document with the same configuration.

## Cache Location

`~/.cache/booklet-reader/`

## Cache Key

SHA256 hash of the concatenation of:
- Config file content (raw bytes)
- Input document content (raw bytes)
- Full LLM prompt text (includes performer list and comment if any)
- Cascade level name ("raw document", "PDF", or "images")

## Cache Storage

One file per cached response:
- Filename: `{hash}.json` containing the raw LLM response text
- TTL determined by file mtime — no separate metadata file needed

## TTL

24 hours. On cache hit, if the file's mtime is older than 24 hours, treat as a miss and delete the stale file.

## Integration

In `run_cascade()`, at the per-level loop. Before calling `try_level()`:
1. Compute cache key from config content + document bytes for this level + prompt + level name
2. Check for cache hit (file exists + mtime within TTL)
3. If hit: parse the cached response using `parse_llm_response()`, print "Cache hit for {level_name}" on stderr, return results
4. If miss: call `try_level()` as normal

After `try_level()` returns successfully:
1. Write the raw LLM response to the cache file

To support this, `try_level()` returns `(results, raw_text)` on success instead of just `results`. `run_cascade()` uses `results` as before and caches `raw_text`.

Note: The cache stores the raw LLM response text, not the parsed JSON. This means `parse_llm_response()` is always used to extract results, keeping behavior consistent.

## Cache Key Inputs Per Level

The document bytes used in the cache key should match what's sent to the LLM at that level:
- Level 1 (raw document): the original file bytes
- Level 2 (PDF): the PDF bytes (converted or original)
- Level 3 (images): the PDF bytes used to render images (or original image bytes)

This ensures that if the conversion produces different output (e.g., libreoffice update), the cache is invalidated.

## Narration

- Cache hit: `"Cache hit for {level_name}"` on stderr
- Cache miss: no extra output (the existing "Attempting..." message suffices)

## No New CLI Flags

Caching is always on. Users clear the cache by deleting `~/.cache/booklet-reader/`.

## Affected Files

- Create: `booklet_reader/cache.py` — cache read/write/TTL logic
- Modify: `booklet_reader/llm.py` — integrate cache into `run_cascade()`
- Create: `tests/test_cache.py`
- Modify: `tests/test_llm.py` — update cascade tests to account for caching (mock or disable)
