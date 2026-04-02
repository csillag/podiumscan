# LLM Output Handling Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve LLM interaction with plain text failure explanations, stderr cascade narration, and a CLI comment flag.

**Architecture:** Three focused changes to existing files: prompt gains a fallback instruction and optional comment, llm.py gains narration and cyan plain-text output, CLI switches to argparse for the new `-c` flag.

**Tech Stack:** Python 3, argparse, ANSI escape codes, pytest

---

## File Structure

```
Modify: booklet_reader/prompt.py          — add fallback instruction, comment parameter
Modify: booklet_reader/llm.py             — add narration, cyan plain-text output
Modify: booklet-reader                    — switch to argparse, add -c flag
Modify: tests/test_prompt.py              — test comment parameter
Modify: tests/test_llm.py                 — test narration and plain-text handling
```

---

### Task 1: Prompt — Add Fallback Instruction and Comment Parameter

**Files:**
- Modify: `booklet_reader/prompt.py`
- Modify: `tests/test_prompt.py`

- [ ] **Step 1: Write failing tests for the comment parameter**

Add to `tests/test_prompt.py`:

```python
class TestBuildPromptComment:
    def test_no_comment_by_default(self):
        performers = [
            {
                "name": "Test",
                "instruments": [{"names": "zongora", "teachers": [], "accompanists": []}],
            }
        ]
        prompt = build_prompt(performers)
        assert "ADDITIONAL GUIDANCE" not in prompt

    def test_comment_included(self):
        performers = [
            {
                "name": "Test",
                "instruments": [{"names": "zongora", "teachers": [], "accompanists": []}],
            }
        ]
        prompt = build_prompt(performers, comment="Look at page 3")
        assert "ADDITIONAL GUIDANCE" in prompt
        assert "Look at page 3" in prompt

    def test_fallback_instruction_present(self):
        performers = [
            {
                "name": "Test",
                "instruments": [{"names": "zongora", "teachers": [], "accompanists": []}],
            }
        ]
        prompt = build_prompt(performers)
        assert "plain text explanation" in prompt.lower() or "plain text" in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_prompt.py::TestBuildPromptComment -v`
Expected: FAIL — `TestBuildPromptComment` not found or assertion errors

- [ ] **Step 3: Update `build_prompt` in `booklet_reader/prompt.py`**

Change the function signature from `def build_prompt(performers):` to `def build_prompt(performers, comment=None):`.

Add this instruction as item 10 in the INSTRUCTIONS section (after item 9):

```
10. If you cannot extract the requested data — for example, because the document is unreadable, the format is unrecognizable, or none of the listed performers appear — do NOT return malformed JSON. Instead, return a plain text explanation of what went wrong and what you were able to see in the document.
```

Add this block at the end of the prompt string, before the closing `"""`, conditionally:

```python
    comment_block = ""
    if comment:
        comment_block = f"""
=== ADDITIONAL GUIDANCE ===
{comment}
"""
```

And append `{comment_block}` at the end of the f-string, after the IMPORTANT section.

The full updated function should look like:

```python
def build_prompt(performers, comment=None):
    performer_lines = []
    for p in performers:
        aliases_by_instrument = []
        for inst in p["instruments"]:
            aliases = [a.strip() for a in inst["names"].split("/")]
            aliases_by_instrument.append(
                f"  - Instrument aliases: {' / '.join(aliases)} (canonical name: {aliases[0]})"
            )
        performer_lines.append(
            f"- {p['name']}\n" + "\n".join(aliases_by_instrument)
        )

    performers_block = "\n".join(performer_lines)

    output_schema = json.dumps(
        [
            {
                "event_name": "string — name of the event/competition/festival/concert",
                "performance_date": "string — ISO 8601 date (YYYY-MM-DD) of this specific performance",
                "performer": "string — full name of the matched performer (use exact name from the list above)",
                "instrument": "string — canonical instrument name (first alias from the list above)",
                "pieces": [
                    {
                        "composer": "string — composer name",
                        "title": "string — piece title, including movement/opus if mentioned",
                    }
                ],
                "teacher": "string or null — teacher name if mentioned in the document",
                "accompanist": "string or null — accompanist name if mentioned in the document",
                "co_performers": [
                    {
                        "name": "string — name of the co-performer",
                        "instrument": "string — instrument of the co-performer",
                    }
                ],
            }
        ],
        indent=2,
        ensure_ascii=False,
    )

    comment_block = ""
    if comment:
        comment_block = f"""
=== ADDITIONAL GUIDANCE ===
{comment}
"""

    return f"""You are analyzing a music program booklet (műsorfüzet). These pages are from a document about a music competition, concert, recital, festival, or other public performance.

Your task: find any performances by the following performers and extract structured data.

=== PERFORMERS TO SEARCH FOR ===
{performers_block}

=== INSTRUCTIONS ===
1. Search the entire document for any of the listed performer names.
2. Be flexible with name matching: the document may omit middle names, use abbreviations, or use slightly different forms. Match on family name + first name even if middle names differ.
3. For each match, extract the specific performance date. The document may have a schedule at the beginning showing which day/time slot each category performs — use this to determine the exact date, not just the event date range.
4. Identify the instrument played. Use the canonical name (first alias) from the performer list above.
5. List ALL pieces performed (composer + title). Include opus numbers, movement names, and any other details mentioned. Note: in competition booklets, the repertoire may not appear directly next to the performer's name. The allowed pieces are sometimes listed separately (e.g., in a preamble or category description), and performers' entries reference them using codes, numbers, or abbreviations. Cross-reference these to resolve the full composer and title.
6. If a teacher (felkészítő tanár, tanár) is mentioned for this performer's entry, include it.
7. If an accompanist (kísérő, zongorakísérő) is mentioned, include it.
8. If the performer is part of a duo, trio, quartet, or other ensemble, list the other members as co_performers with their instruments. If solo, use an empty array.
9. If a performer appears in multiple entries (e.g., different categories or rounds), return a separate object for each appearance.
10. If you cannot extract the requested data — for example, because the document is unreadable, the format is unrecognizable, or none of the listed performers appear — do NOT return malformed JSON. Instead, return a plain text explanation of what went wrong and what you were able to see in the document.

=== OUTPUT FORMAT ===
Return ONLY a valid JSON array. No markdown, no explanation, no code fences. Just the JSON.

If no matches are found, return an empty array: []

Schema:
{output_schema}

=== IMPORTANT ===
- Use the EXACT performer name from the list above in the "performer" field, not the form found in the document.
- Use the canonical instrument name (first alias) in the "instrument" field.
- performance_date must be ISO 8601 (YYYY-MM-DD). If you cannot determine the exact date, use the first day of the event.
- pieces must always be an array, even for a single piece.
- co_performers must always be an array, empty if solo.
- teacher and accompanist should be null if not mentioned in the document.
{comment_block}"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_prompt.py -v`
Expected: All PASS (both old and new tests)

- [ ] **Step 5: Commit**

```bash
git add booklet_reader/prompt.py tests/test_prompt.py
git commit -m "Add plain text fallback instruction and comment parameter to prompt"
```

---

### Task 2: LLM — Add Narration and Cyan Plain-Text Output

**Files:**
- Modify: `booklet_reader/llm.py`
- Modify: `tests/test_llm.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_llm.py`:

```python
class TestTryLevelPlainText:
    def test_plain_text_printed_cyan_on_stderr(self, capsys):
        explanation = "I could not find any of the listed performers in this document."
        bad = _mock_response(explanation)
        with patch("litellm.completion", return_value=bad):
            result = try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt")
        assert result is None
        captured = capsys.readouterr()
        assert explanation in captured.err
        assert "\033[36m" in captured.err  # cyan


class TestRunCascadeNarration:
    def test_narrates_levels_on_stderr(self, capsys):
        good = _mock_response('[{"event_name": "OK"}]')
        with patch("litellm.completion", return_value=good):
            run_cascade(
                model="model",
                api_key="key",
                prompt="find performers",
                document_bytes=None,
                document_mime=None,
                pdf_bytes=b"fake pdf",
                image_list=None,
            )
        captured = capsys.readouterr()
        assert "Attempting PDF submission" in captured.err

    def test_narrates_fallback_on_stderr(self, capsys):
        bad = _mock_response("I cannot read this document.")
        good = _mock_response('[{"event_name": "OK"}]')
        with patch("litellm.completion", side_effect=[bad, bad, good]):
            run_cascade(
                model="model",
                api_key="key",
                prompt="find performers",
                document_bytes=None,
                document_mime=None,
                pdf_bytes=b"fake pdf",
                image_list=[b"\x89PNGfake"],
            )
        captured = capsys.readouterr()
        assert "Moving to next format" in captured.err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_llm.py::TestTryLevelPlainText -v tests/test_llm.py::TestRunCascadeNarration -v`
Expected: FAIL — classes not found or assertion errors

- [ ] **Step 3: Update `try_level` in `booklet_reader/llm.py`**

Replace the `try_level` function:

```python
CYAN = "\033[36m"
RESET = "\033[0m"


def try_level(model, api_key, messages, prompt):
    """Try sending messages to the LLM. Retry once on invalid JSON with a nudge.

    If the LLM returns plain text (not JSON), print it in cyan to stderr.
    Returns parsed results list on success, or None on failure.
    """
    for attempt in range(2):
        try:
            response = litellm.completion(model=model, api_key=api_key, messages=messages)
        except Exception as e:
            print(f"API error: {e}", file=sys.stderr)
            return None

        raw_text = response.choices[0].message.content
        try:
            return parse_llm_response(raw_text)
        except LLMError:
            # Print the LLM's response in cyan — it's likely a plain text explanation
            print(f"{CYAN}{raw_text}{RESET}", file=sys.stderr)
            if attempt == 0:
                print(
                    "LLM returned invalid JSON. Retrying with guidance...",
                    file=sys.stderr,
                )
                retry_prompt = build_retry_prompt(raw_text)
                messages = messages + [
                    {"role": "assistant", "content": raw_text},
                    {"role": "user", "content": retry_prompt},
                ]
                continue
            return None
```

- [ ] **Step 4: Update `run_cascade` in `booklet_reader/llm.py`**

Replace the `run_cascade` function:

```python
_LEVEL_NAMES = {
    "raw document": "Attempting raw document submission...",
    "PDF": "Attempting PDF submission...",
    "images": "Attempting image submission...",
}


def run_cascade(model, api_key, prompt, document_bytes, document_mime, pdf_bytes, image_list):
    """Run the cascading LLM submission: raw document → PDF → images.

    Each level tries once, retries on invalid JSON with a nudge, then falls to next level.
    Narrates progress to stderr. Raises LLMError if all levels fail.
    """
    levels = []

    # Level 1: Raw document (DOC/DOCX/ODT only)
    if document_bytes is not None and document_mime is not None:
        messages = build_messages_with_document(prompt, document_bytes, document_mime)
        levels.append(("raw document", messages))

    # Level 2: PDF
    if pdf_bytes is not None:
        messages = build_messages_with_document(prompt, pdf_bytes, "application/pdf")
        levels.append(("PDF", messages))

    # Level 3: Images
    if image_list is not None:
        messages = build_messages_with_images(prompt, image_list)
        levels.append(("images", messages))

    for i, (level_name, messages) in enumerate(levels):
        print(_LEVEL_NAMES[level_name], file=sys.stderr)
        result = try_level(model, api_key, messages, prompt)
        if result is not None:
            return result
        if i < len(levels) - 1:
            print("Moving to next format...", file=sys.stderr)

    raise LLMError("Error: All input format levels failed. LLM could not produce valid output.")
```

- [ ] **Step 5: Run all llm tests to verify they pass**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_llm.py -v`
Expected: All PASS (old and new tests)

- [ ] **Step 6: Commit**

```bash
git add booklet_reader/llm.py tests/test_llm.py
git commit -m "Add stderr narration and cyan plain-text output for LLM explanations"
```

---

### Task 3: CLI — Switch to Argparse and Add Comment Flag

**Files:**
- Modify: `booklet-reader`

- [ ] **Step 1: Rewrite the argument handling section of `booklet-reader`**

Replace the imports and argument handling (lines 1-7 and the `# 2. Check args` block) with argparse. The full updated file:

```python
#!/usr/bin/env python3
"""booklet-reader — Extract performance data from music program booklets."""

import argparse
import json
import os
import sys


def get_script_dir():
    return os.path.dirname(os.path.realpath(__file__))


def main():
    # 1. Check Python dependencies
    try:
        from booklet_reader.dependencies import check_python_deps, DependencyError
        check_python_deps()
    except ImportError:
        print(
            "Error: booklet_reader package not found. Run from the project directory.",
            file=sys.stderr,
        )
        sys.exit(2)
    except DependencyError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    from booklet_reader.config import load_config, validate_config, ensure_config, get_api_key, ConfigError
    from booklet_reader.converter import (
        detect_file_type, convert_to_pdf, render_pdf_to_images, read_image_file,
        ConversionError, FILE_TYPE_DOCUMENT, FILE_TYPE_PDF, FILE_TYPE_IMAGE,
    )
    from booklet_reader.dependencies import check_libreoffice
    from booklet_reader.prompt import build_prompt
    from booklet_reader.llm import run_cascade, get_mime_type, LLMError
    from booklet_reader.gaps import fill_gaps

    # 2. Parse args
    parser = argparse.ArgumentParser(description="Extract performance data from music program booklets.")
    parser.add_argument("document", help="Path to the document file (PDF, DOC, DOCX, ODT, or image)")
    parser.add_argument("-c", "--comment", help="Additional guidance for the LLM (e.g. 'Look at page 3')")
    args = parser.parse_args()

    document_path = os.path.abspath(args.document)

    # 3. Config check
    config_path = os.path.expanduser("~/.config/booklet-reader/config.yaml")
    example_path = os.path.join(get_script_dir(), "config.example.yaml")

    try:
        exists = ensure_config(config_path, example_path)
        if not exists:
            print(
                f"Before reading, please fill in your configuration at {config_path}",
                file=sys.stderr,
            )
            sys.exit(2)
        config = load_config(config_path)
        validate_config(config)
    except ConfigError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    # 4. Detect file type
    try:
        file_type = detect_file_type(document_path)
    except ConversionError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    # 5. System dependency check for documents needing libreoffice
    if file_type == FILE_TYPE_DOCUMENT:
        try:
            check_libreoffice()
        except DependencyError as e:
            print(str(e), file=sys.stderr)
            sys.exit(2)

    # 6. Prepare cascade inputs
    document_bytes = None
    document_mime = None
    pdf_bytes = None
    image_list = None

    try:
        if file_type == FILE_TYPE_DOCUMENT:
            with open(document_path, "rb") as f:
                document_bytes = f.read()
            document_mime = get_mime_type(document_path)
            pdf_path = convert_to_pdf(document_path)
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            image_list = render_pdf_to_images(pdf_path)

        elif file_type == FILE_TYPE_PDF:
            with open(document_path, "rb") as f:
                pdf_bytes = f.read()
            image_list = render_pdf_to_images(document_path)

        elif file_type == FILE_TYPE_IMAGE:
            img_bytes = read_image_file(document_path)
            image_list = [img_bytes]

    except ConversionError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    # 7. Build prompt and run cascade
    prompt = build_prompt(config["performers"], comment=args.comment)
    api_key = get_api_key(config, "model")

    try:
        results = run_cascade(
            model=config["model"],
            api_key=api_key,
            prompt=prompt,
            document_bytes=document_bytes,
            document_mime=document_mime,
            pdf_bytes=pdf_bytes,
            image_list=image_list,
        )
    except LLMError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    # 8. Fill gaps
    if results:
        results = fill_gaps(results, config["performers"])

    # 9. Output
    if results:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test**

Run: `cd /home/csillag/private/booklet-reader && python booklet-reader --help`
Expected: Shows usage with `document` positional arg and `-c`/`--comment` option.

Run: `cd /home/csillag/private/booklet-reader && python booklet-reader 2>&1; echo "Exit: $?"`
Expected: argparse error about missing document argument, exit 2.

- [ ] **Step 3: Run full test suite**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add booklet-reader
git commit -m "Switch CLI to argparse, add -c/--comment flag"
```
