# Booklet Reader — Design Spec

## Overview

A Python CLI tool that extracts structured performance data from music competition program booklets (PDF, DOC, DOCX). It uses an LLM (via LiteLLM) to analyze documents and find performances by a configured list of performers, outputting predictable JSON to stdout.

## Components

### 1. `booklet-reader` — Main CLI

Accepts a single document file, analyzes it via an LLM, and outputs structured JSON for any matching performers.

**Usage:**
```
booklet-reader document.pdf
booklet-reader document.docx
booklet-reader document.doc
```

**Config location:** `~/.config/booklet-reader.conf`

**Exit codes:**
- 0: matches found, JSON written to stdout
- 1: no matches found
- 2: error (details on stderr)

### 2. `booklet-model-updater` — Model List Updater

Queries an LLM for currently available vision-capable models, cross-references with LiteLLM's model registry, and updates the available models list in the config file.

**Usage:**
```
booklet-model-updater
```

### 3. `config.example.yaml` — Example Configuration

Ships with the repo. Copied to `~/.config/booklet-reader.conf` automatically on first run of either script. Located relative to the script's own directory (i.e. the scripts resolve `config.example.yaml` from the same directory they live in).

---

## Config File Format

```yaml
# === Model Configuration ===
model: "openai/gpt-4o"
model_updater_model: "openai/gpt-4o"

# === Available Vision-Capable Models ===
# Copy a model identifier from this list to the 'model' field above.
# DO NOT edit this block manually — it is maintained by booklet-model-updater.
# --- BEGIN AVAILABLE MODELS ---
# available_models:
#   - anthropic/claude-sonnet-4-20250514
#   - openai/gpt-4o
#   - gemini/gemini-1.5-pro
# --- END AVAILABLE MODELS ---

# === Performers ===
performers:
  - name: "Csillag Kristóf"
    instruments:
      - names: "gordonka / cello"
        teachers:
          - name: "Bolykiné Kálló Eszter"
            from: 2020-09-01
            to: 2025-06-30
        accompanists:
          - name: "Szokolayné Pásztor Edina"
            from: 2023-09-01
      - names: "zongora / piano"
        teachers:
          - name: "Kiss Anna"
            from: 2021-09-01

  - name: "Csillag Mátyás"
    instruments:
      - names: "gordonka / cello"
        teachers:
          - name: "Salát Ildikó"
            from: 2022-09-01
        accompanists:
          - name: "Várterész Anna"
            from: 2023-09-01
```

### Config Field Details

- `model`: LiteLLM model identifier used by `booklet-reader` for document analysis. Must support PDF/vision input.
- `model_updater_model`: LiteLLM model identifier used by `booklet-model-updater` to query for available models.
- `available_models`: Auto-maintained commented list between `BEGIN`/`END` markers. Users copy identifiers from here to the `model` field. Never edited manually.
- `performers`: List of performers to search for.
  - `name`: Full name of the performer (used in output even if the document truncates it).
  - `instruments`: List of instruments the performer plays.
    - `names`: Slash-separated aliases (e.g. `"gordonka / cello"`). The first name is canonical and used in output.
    - `teachers`: List of teachers for this instrument, with `from`/`to` date ranges. `to` is optional (means current).
    - `accompanists`: List of accompanists for this instrument, with `from`/`to` date ranges. `to` is optional.

---

## Output Format

Always a JSON array to stdout, even for a single match.

```json
[
  {
    "event_name": "VI. Gyermek- és Ifjúsági Kamarazenei Fesztivál",
    "performance_date": "2025-12-06",
    "performer": "Csillag Kristóf",
    "instrument": "gordonka",
    "pieces": [
      {
        "composer": "Wolf Péter",
        "title": "Poéma"
      },
      {
        "composer": "Seiber Mátyás",
        "title": "Leichte Tänze / Ragtime, Slow Fox, Waltz, Foxtrot"
      }
    ],
    "teacher": "Bolykiné Kálló Eszter",
    "accompanist": "Szokolayné Pásztor Edina",
    "co_performers": [
      {
        "name": "Csillag Ilona",
        "instrument": "zongora"
      }
    ]
  }
]
```

### Output Field Details

- `event_name`: Name of the competition/festival, extracted from the document.
- `performance_date`: ISO 8601 date (`YYYY-MM-DD`) of the specific performance, not just the event date range. Inferred from schedule information in the document.
- `performer`: Full name from config (not the potentially truncated form in the document).
- `instrument`: Canonical instrument name (first alias from config).
- `pieces`: Array of objects with `composer` and `title`. Always an array, even for one piece.
- `teacher`: Extracted from document if present, otherwise filled from config based on performance date, otherwise `null`.
- `accompanist`: Same logic as teacher.
- `co_performers`: Other performers in the same entry (duo/trio/quartet partners). Array of objects with `name` and `instrument`. Empty array if solo.

---

## booklet-reader Pipeline

1. **Dependency check** — Verify Python package dependencies (LiteLLM, PyYAML) are installed. Print clear install instructions to stderr and exit 2 if missing.
2. **Config check** — If `~/.config/booklet-reader.conf` doesn't exist, copy `config.example.yaml` to that path, print message to stderr: `"Before reading, please fill in your configuration at ~/.config/booklet-reader.conf"`, exit 2. If exists but invalid, print validation errors to stderr, exit 2.
3. **Detect file type** — By extension: `.pdf`, `.doc`, `.docx`.
4. **System dependency check** — If DOC or DOCX, verify `libreoffice` is installed. Print install instructions to stderr and exit 2 if missing.
5. **Convert if needed** — DOC/DOCX to PDF via `libreoffice --headless --convert-to pdf` to a temp directory. Clean up temp files on exit.
6. **Send to LLM** — Via LiteLLM, send the PDF along with a prompt containing:
   - The list of performer names with all aliases to search for.
   - Instruction for flexible name matching (missing middle names, abbreviations).
   - The exact JSON schema for the response.
   - Instruction to extract the specific performance date from schedule info.
   - Instruction to identify co-performers, pieces, teacher, accompanist.
7. **Parse response** — Validate the returned JSON against the expected schema. If the LLM returns malformed JSON, retry once; if still malformed, print error to stderr, exit 2.
8. **Fill in gaps** — For each match: if `teacher` or `accompanist` is `null` in the LLM response, look up the config by instrument and performance date to fill in.
9. **Output** — Print JSON array to stdout. Exit 0 if array is non-empty, exit 1 if empty.

All error conditions in steps 1-7 exit with code 2.

---

## booklet-model-updater Pipeline

1. **Dependency check** — Verify Python package dependencies (LiteLLM, PyYAML) are installed. Print clear install instructions to stderr and exit 1 if missing.
2. **Config check:**
   - If `~/.config/booklet-reader.conf` doesn't exist: copy `config.example.yaml`, print reminder to stderr to fill in the config, exit 0.
   - If exists but invalid: print validation errors to stderr, exit 1.
3. **Read config** — Get `model_updater_model` value.
4. **Query LLM** — Ask the configured model for a list of currently available LLM models that support PDF/document/vision input as part of their API.
5. **Cross-reference with LiteLLM** — Validate each returned model name against LiteLLM's model registry. Discard any that aren't valid LiteLLM identifiers.
6. **Compare** — Diff against the current `available_models` list in the config file.
7. **Update if needed:**
   - If new models found: print new model names to stdout. Rewrite only the block between `--- BEGIN AVAILABLE MODELS ---` and `--- END AVAILABLE MODELS ---` markers in the config file, preserving all other content byte-for-byte.
   - If no new models: do nothing, exit 0.

---

## Dependencies

### Python packages
- `litellm` — Multi-provider LLM interface
- `PyYAML` — Config file parsing

### System dependencies
- `libreoffice` — Required only for DOC/DOCX conversion. Checked at runtime only when processing DOC/DOCX files. Not required for PDF-only usage.

---

## Project Structure

```
booklet-reader/
  booklet-reader          # Main CLI script (Python)
  booklet-model-updater   # Model list updater script (Python)
  config.example.yaml     # Example config, shipped with repo
  sample-data/            # Sample program booklets for testing
  docs/                   # Documentation
```

---

## Error Handling

All errors go to stderr. Stdout is reserved exclusively for JSON output (booklet-reader) or new model names (model-updater).

- Missing Python dependency: `"Error: Required package 'litellm' is not installed. Install it with: pip install litellm"`
- Missing libreoffice: `"Error: 'libreoffice' is required for DOC/DOCX conversion but was not found. Install it with: sudo apt install libreoffice"`
- Missing config: `"Before reading, please fill in your configuration at ~/.config/booklet-reader.conf"`
- Invalid config: Specific validation errors (e.g. `"Config error: 'model' field is required"`, `"Config error: 'performers' must be a non-empty list"`)
- LLM API error: Pass through the error message from LiteLLM
- Malformed LLM response: `"Error: LLM returned invalid JSON. Retrying..."` then `"Error: LLM returned invalid JSON after retry."`
- Unsupported file type: `"Error: Unsupported file type '.xyz'. Supported: .pdf, .doc, .docx"`
