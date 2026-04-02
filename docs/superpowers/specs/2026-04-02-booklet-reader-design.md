# Booklet Reader — Design Spec

## Overview

A Python CLI tool that extracts structured performance data from music program booklets — competitions, concerts, recitals, festivals, and other public performances (PDF, DOC, DOCX, ODT, and images). It uses an LLM (via LiteLLM) to analyze documents and find performances by a configured list of performers, outputting predictable JSON to stdout.

## Components

### 1. `booklet-reader` — Main CLI

Accepts a single document file, analyzes it via an LLM, and outputs structured JSON for any matching performers.

**Usage:**
```
booklet-reader document.pdf
booklet-reader document.docx
booklet-reader document.doc
booklet-reader document.odt
booklet-reader poster.jpg
```

**Config location:** `~/.config/booklet-reader/config.yaml`

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

Ships with the repo. Copied to `~/.config/booklet-reader/config.yaml` automatically on first run of either script. Located relative to the script's own directory (i.e. the scripts resolve `config.example.yaml` from the same directory they live in).

---

## Config File Format

```yaml
# === Model Configuration ===
model: "xai/grok-4.20-0309-non-reasoning"
api_key: "your-api-key-here"
model_updater_model: "xai/grok-4.20-0309-non-reasoning"
model_updater_api_key: ""  # optional, defaults to api_key

# === Available Models (PDF and/or Vision-Capable) ===
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
  - name: "Nagy Eszter"
    instruments:
      - names: "hegedű / violin"
        teachers:
          - name: "Tóth Katalin"
            from: 2020-09-01
            to: 2025-06-30
        accompanists:
          - name: "Fekete Mária"
            from: 2023-09-01
      - names: "zongora / piano"
        teachers:
          - name: "Horváth László"
            from: 2021-09-01

  - name: "Szabó Bence"
    instruments:
      - names: "gordonka / cello"
        teachers:
          - name: "Varga Péter"
            from: 2022-09-01
        accompanists:
          - name: "Molnár Zsófia"
            from: 2023-09-01
```

### Config Field Details

- `model`: LiteLLM model identifier used by `booklet-reader` for document analysis. Must support PDF and/or image/vision input.
- `api_key`: API key for the provider of the configured model. Passed directly to LiteLLM, overriding any environment variables.
- `model_updater_model`: LiteLLM model identifier used by `booklet-model-updater` to query for available models.
- `model_updater_api_key`: Optional. API key for the model updater's provider. If empty or absent, falls back to `api_key`.
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
    "event_name": "III. Ifjúsági Kamarazenei Fesztivál",
    "performance_date": "2025-11-15",
    "performer": "Nagy Eszter",
    "instrument": "hegedű",
    "pieces": [
      {
        "composer": "J. S. Bach",
        "title": "Partita No. 2 in D minor, BWV 1004 / Sarabande"
      },
      {
        "composer": "Bartók Béla",
        "title": "Román népi táncok"
      }
    ],
    "teacher": "Tóth Katalin",
    "accompanist": "Fekete Mária",
    "co_performers": [
      {
        "name": "Kiss Dániel",
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

1. **Dependency check** — Verify Python package dependencies (LiteLLM, PyYAML, PyMuPDF) are installed. Print clear install instructions to stderr and exit 2 if missing.
2. **Config check** — If `~/.config/booklet-reader/config.yaml` doesn't exist, copy `config.example.yaml` to that path, print message to stderr: `"Before reading, please fill in your configuration at ~/.config/booklet-reader/config.yaml"`, exit 2. If exists but invalid, print validation errors to stderr, exit 2.
3. **Detect file type** — By extension: `.pdf`, `.doc`, `.docx`, `.odt`, `.png`, `.jpg`, `.jpeg`, `.webp`.
4. **System dependency check** — If DOC, DOCX, or ODT, verify `libreoffice` is installed. Print install instructions to stderr and exit 2 if missing.
5. **Build prompt** — Construct the LLM prompt containing:
   - The list of performer names with all aliases to search for.
   - Instruction for flexible name matching (missing middle names, abbreviations).
   - The exact JSON schema for the response.
   - Instruction to extract the specific performance date from schedule info.
   - Instruction to identify co-performers, pieces, teacher, accompanist.
6. **Cascading LLM submission** — Try progressively degraded input formats until a valid response is obtained:

   **Level 1: Raw document** (for DOC, DOCX, ODT only; skip for PDF and images)
   - Send the raw document file to the LLM.
   - If the LLM returns valid JSON → done.
   - If the LLM returns invalid JSON → retry once, asking for valid JSON with all required fields populated from the document.
   - If API error or second invalid JSON → fall to Level 2.

   **Level 2: PDF** (for DOC/DOCX/ODT: convert via libreoffice; for PDF: use original; skip for images)
   - Send the PDF file to the LLM.
   - If the LLM returns valid JSON → done.
   - If the LLM returns invalid JSON → retry once with the same nudge.
   - If API error or second invalid JSON → fall to Level 3.

   **Level 3: Images** (for PDF: render pages to PNG via pymupdf; for images: use original file)
   - Send page images to the LLM.
   - If the LLM returns valid JSON → done.
   - If the LLM returns invalid JSON → retry once with the same nudge.
   - If API error or second invalid JSON → hard fail, print error to stderr, exit 2.

7. **Fill in gaps** — For each match: if `teacher` or `accompanist` is `null` in the LLM response, look up the config by instrument and performance date to fill in.
8. **Output** — Print JSON array to stdout. Exit 0 if array is non-empty, exit 1 if empty.

All error conditions in steps 1-6 exit with code 2.

---

## booklet-model-updater Pipeline

1. **Dependency check** — Verify Python package dependencies (LiteLLM, PyYAML) are installed. Print clear install instructions to stderr and exit 1 if missing.
2. **Config check:**
   - If `~/.config/booklet-reader/config.yaml` doesn't exist: copy `config.example.yaml`, print reminder to stderr to fill in the config, exit 0.
   - If exists but invalid: print validation errors to stderr, exit 1.
3. **Read config** — Get `model_updater_model` value.
4. **Query LLM** — Ask the configured model for a list of currently available LLM models that support PDF and/or image/vision input as part of their API.
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
- `pymupdf` — PDF page rendering to images

### System dependencies
- `libreoffice` — Required only for DOC/DOCX/ODT conversion. Checked at runtime only when processing these file types. Not required for PDF or image input.

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
- Missing libreoffice: `"Error: 'libreoffice' is required for DOC/DOCX/ODT conversion but was not found. Install it with: sudo apt install libreoffice"`
- Missing config: `"Before reading, please fill in your configuration at ~/.config/booklet-reader/config.yaml"`
- Invalid config: Specific validation errors (e.g. `"Config error: 'model' field is required"`, `"Config error: 'performers' must be a non-empty list"`)
- LLM API error: Pass through the error message from LiteLLM
- Malformed LLM response (within a level): `"LLM returned invalid JSON. Retrying with guidance..."` on stderr, then retry asking for valid JSON with all required fields populated from the document.
- Cascade fallback: `"Level N failed, falling to next format..."` on stderr (informational, not an error).
- All levels exhausted: `"Error: All input format levels failed. LLM could not produce valid output."`
- Unsupported file type: `"Error: Unsupported file type '.xyz'. Supported: .pdf, .doc, .docx, .odt, .png, .jpg, .jpeg, .webp"`
