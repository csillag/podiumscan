# podiumscan

Extract structured performance data from music program booklets using an LLM.

Reads competition schedules, concert programs, recital booklets, and event posters (PDF, DOC, DOCX, ODT, PNG, JPG, WEBP), finds performances by configured performers, and outputs structured JSON.

## Setup

```bash
pip install podiumscan
```

Or for development:

```bash
git clone <repo-url>
cd podiumscan
make install-dev
```

On first run, the tool copies the example config to `~/.config/podiumscan/config.yaml` automatically.

Edit `~/.config/podiumscan/config.yaml`:
- Set `model` to a vision-capable LLM (default: `anthropic/claude-opus-4-6`)
- Set `api_key` to your provider's API key
- Add your performers under `performers`

## Usage

```bash
podiumscan document.pdf
podiumscan concert-poster.jpg
podiumscan -c "Look at page 3" program.pdf
podiumscan -v document.docx
```

### Options

| Flag | Description |
|------|-------------|
| `-c`, `--comment` | Additional guidance sent to the LLM (e.g. `"Look at page 3"`) |
| `-v`, `--verbose` | Show LLM explanation text on stderr |

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Matches found, JSON written to stdout |
| 1 | No matches found |
| 2 | Error (details on stderr) |

## Output

JSON array to stdout. Example:

```json
[
  {
    "event_name": "III. Ifjusagi Kamarazenei Fesztival",
    "performance_date": "2025-11-15",
    "performer": "Nagy Eszter",
    "instrument": "hegedu",
    "pieces": [
      { "composer": "J. S. Bach", "title": "Partita No. 2 in D minor, BWV 1004 / Sarabande" },
      { "composer": "Bartok Bela", "title": "Roman nepi tancok" }
    ],
    "teacher": "Toth Katalin",
    "accompanist": "Fekete Maria",
    "co_performers": [
      { "name": "Kiss Daniel", "instrument": "zongora" }
    ]
  }
]
```

## Config format

See `config.example.yaml` for the full format. Key sections:

- **model** / **api_key**: LLM provider configuration
- **performers**: list of people to search for, with instruments (including aliases), teachers, and accompanists with date ranges

## How it works

1. Detects file type and prepares the document
2. Tries sending it to the LLM in progressively degraded formats: raw document, then PDF, then page images
3. At each level, if the LLM returns invalid output, retries once with guidance
4. Fills in missing teacher/accompanist data from config based on performance date
5. Outputs JSON to stdout

## Model updater

```bash
podiumscan-update-models
```

Queries an LLM for currently available PDF/vision-capable models, cross-references with LiteLLM's registry, and updates the commented model list in your config file.

## Supported file types

PDF, DOC, DOCX, ODT, PNG, JPG, JPEG, WEBP

DOC/DOCX/ODT conversion requires `libreoffice` installed on the system.

## Dependencies

- Python 3
- [LiteLLM](https://github.com/BerriAI/litellm)
- [PyYAML](https://pyyaml.org/)
- [PyMuPDF](https://pymupdf.readthedocs.io/)
- libreoffice (only for DOC/DOCX/ODT)
