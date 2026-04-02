# LLM Output Handling Improvements — Design Spec

## Overview

Three improvements to how booklet-reader interacts with the LLM: better failure reporting in the prompt, stderr narration of cascade progress, and a CLI comment flag for user guidance.

## Changes

### 1. Prompt Updates (`booklet_reader/prompt.py`)

**Plain text fallback instruction:** Add to the main prompt's INSTRUCTIONS section:

> If you cannot extract the requested data — for example, because the document is unreadable, the format is unrecognizable, or none of the listed performers appear — do NOT return malformed JSON. Instead, return a plain text explanation of what went wrong and what you were able to see in the document.

**User comment support:** `build_prompt(performers, comment=None)` gains an optional `comment` parameter. When provided, append a section to the prompt:

```
=== ADDITIONAL GUIDANCE ===
{comment}
```

### 2. Stderr Narration (`booklet_reader/llm.py`)

**Cascade progress:** Before each level attempt, print to stderr:
- `"Attempting raw document submission..."` (Level 1)
- `"Attempting PDF submission..."` (Level 2)
- `"Attempting image submission..."` (Level 3)

**On fallback:** Print `"Moving to next format..."` to stderr.

**Plain text explanation handling:** In `try_level()`, when the LLM response fails JSON parsing, check if the response is a plain text explanation (any non-empty string that isn't garbled binary). Print it to stderr in cyan (`\033[36m...\033[0m`). Then continue the cascade (return None).

This applies both to the first attempt and the retry. The retry nudge still fires on the first invalid-JSON response. If the retry also returns non-JSON, print it in cyan and return None.

### 3. CLI Comment Flag (`booklet-reader`)

Add `-c` / `--comment` flag:

```
booklet-reader document.pdf -c "Look at page 3"
```

The comment string is passed to `build_prompt(performers, comment=args.comment)`.

Use `argparse` instead of manual `sys.argv` parsing to handle the new flag cleanly. The document path becomes a positional argument.

## Exit Codes

No changes. Exit codes remain: 0 (matches), 1 (no matches), 2 (error).

## Affected Files

- Modify: `booklet_reader/prompt.py` — add fallback instruction to prompt, add `comment` parameter
- Modify: `booklet_reader/llm.py` — add stderr narration, cyan output for plain text explanations
- Modify: `booklet-reader` — switch to argparse, add `-c`/`--comment` flag
- Modify: `tests/test_prompt.py` — test comment parameter
- Modify: `tests/test_llm.py` — test narration and plain text handling
