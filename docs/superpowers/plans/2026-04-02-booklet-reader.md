# Booklet Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool that extracts structured performance data from music program booklets using an LLM, with cascading input format fallback.

**Architecture:** Two CLI scripts (`booklet-reader`, `booklet-model-updater`) sharing a common Python package (`booklet_reader/`). The main script tries sending the document in progressively degraded formats (raw → PDF → images) until the LLM returns valid JSON. The updater script maintains a list of available PDF/vision-capable models in the config file.

**Tech Stack:** Python 3, LiteLLM, PyYAML, PyMuPDF, pytest

---

## File Structure

```
booklet-reader/
  booklet-reader                  # Main CLI entry point (executable)
  booklet-model-updater           # Model updater entry point (executable)
  config.example.yaml             # Example config, shipped with repo
  AGENTS.md                       # Agent rules
  booklet_reader/
    __init__.py                   # Package init
    config.py                     # Config loading, validation, example copying
    dependencies.py               # Python and system dependency checks
    converter.py                  # DOC/DOCX/ODT → PDF, PDF → PNG conversions
    prompt.py                     # LLM prompt construction (initial + retry nudge)
    llm.py                        # LLM calling via LiteLLM, response parsing, cascade logic
    gaps.py                       # Fill missing teacher/accompanist from config
    model_updater.py              # Query LLM for models, cross-ref, update config
  tests/
    __init__.py
    test_config.py
    test_dependencies.py
    test_converter.py
    test_prompt.py
    test_llm.py
    test_gaps.py
    test_model_updater.py
  sample-data/                    # Sample booklets (already present)
  docs/                           # Specs and plans
```

---

### Task 1: Project Scaffolding and Example Config

**Files:**
- Create: `config.example.yaml`
- Create: `booklet_reader/__init__.py`
- Create: `tests/__init__.py`
- Create: `requirements.txt`

- [ ] **Step 1: Create `config.example.yaml`**

```yaml
# === Model Configuration ===
# LiteLLM model identifier for document analysis. Must support PDF and/or image/vision input.
model: "xai/grok-4.20-0309-non-reasoning"

# API key for the provider of the configured model.
api_key: "your-api-key-here"

# LiteLLM model identifier used by booklet-model-updater to query for available models.
model_updater_model: "xai/grok-4.20-0309-non-reasoning"

# Optional API key for the model updater. If empty, falls back to api_key above.
model_updater_api_key: ""

# === Available Models (PDF and/or Vision-Capable) ===
# Copy a model identifier from this list to the 'model' field above.
# DO NOT edit this block manually — it is maintained by booklet-model-updater.
# --- BEGIN AVAILABLE MODELS ---
# available_models:
#   - anthropic/claude-opus-4-6
#   - anthropic/claude-sonnet-4-6
#   - openai/gpt-4o
#   - openai/gpt-4.1
#   - gemini/gemini-2.5-pro
#   - gemini/gemini-2.5-flash
#   - xai/grok-4.20-0309-non-reasoning
#   - xai/grok-4.20-0309-reasoning
# --- END AVAILABLE MODELS ---

# === Performers ===
# List of performers to search for in program booklets.
# Each performer has a name and a list of instruments.
# Each instrument has aliases (slash-separated), teachers, and accompanists.
# The first alias is the canonical name used in output.
# Teachers and accompanists have date ranges (from/to). 'to' is optional (means current).
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

- [ ] **Step 2: Create `requirements.txt`**

```
litellm
PyYAML
PyMuPDF
```

- [ ] **Step 3: Create package init files**

`booklet_reader/__init__.py`:
```python
```

`tests/__init__.py`:
```python
```

- [ ] **Step 4: Commit**

```bash
git add config.example.yaml requirements.txt booklet_reader/__init__.py tests/__init__.py
git commit -m "Add project scaffolding and example config"
```

---

### Task 2: Config Loading and Validation

**Files:**
- Create: `booklet_reader/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_config.py`:
```python
import os
import pytest
import yaml
from booklet_reader.config import load_config, validate_config, ensure_config, get_api_key, ConfigError

VALID_CONFIG = {
    "model": "xai/grok-4.20-0309-non-reasoning",
    "api_key": "test-key-123",
    "model_updater_model": "xai/grok-4.20-0309-non-reasoning",
    "performers": [
        {
            "name": "Nagy Eszter",
            "instruments": [
                {
                    "names": "hegedű / violin",
                    "teachers": [
                        {"name": "Tóth Katalin", "from": "2020-09-01"}
                    ],
                }
            ],
        }
    ],
}


class TestValidateConfig:
    def test_valid_config(self):
        validate_config(VALID_CONFIG)

    def test_missing_model(self):
        config = {**VALID_CONFIG}
        del config["model"]
        with pytest.raises(ConfigError, match="'model' field is required"):
            validate_config(config)

    def test_missing_api_key(self):
        config = {**VALID_CONFIG}
        del config["api_key"]
        with pytest.raises(ConfigError, match="'api_key' field is required"):
            validate_config(config)

    def test_placeholder_api_key(self):
        config = {**VALID_CONFIG, "api_key": "your-api-key-here"}
        with pytest.raises(ConfigError, match="set your API key"):
            validate_config(config)

    def test_missing_performers(self):
        config = {**VALID_CONFIG}
        del config["performers"]
        with pytest.raises(ConfigError, match="'performers' field is required"):
            validate_config(config)

    def test_empty_performers(self):
        config = {**VALID_CONFIG, "performers": []}
        with pytest.raises(ConfigError, match="'performers' must be a non-empty list"):
            validate_config(config)

    def test_performer_missing_name(self):
        config = {
            **VALID_CONFIG,
            "performers": [{"instruments": []}],
        }
        with pytest.raises(ConfigError, match="Performer.*missing 'name'"):
            validate_config(config)

    def test_performer_missing_instruments(self):
        config = {
            **VALID_CONFIG,
            "performers": [{"name": "Test"}],
        }
        with pytest.raises(ConfigError, match="Performer 'Test'.*missing 'instruments'"):
            validate_config(config)

    def test_instrument_missing_names(self):
        config = {
            **VALID_CONFIG,
            "performers": [
                {"name": "Test", "instruments": [{"teachers": []}]}
            ],
        }
        with pytest.raises(ConfigError, match="missing 'names'"):
            validate_config(config)


class TestGetApiKey:
    def test_main_api_key(self):
        config = {**VALID_CONFIG}
        assert get_api_key(config, "model") == "test-key-123"

    def test_updater_falls_back_to_main(self):
        config = {**VALID_CONFIG, "model_updater_api_key": ""}
        assert get_api_key(config, "model_updater") == "test-key-123"

    def test_updater_uses_own_key(self):
        config = {**VALID_CONFIG, "model_updater_api_key": "updater-key-456"}
        assert get_api_key(config, "model_updater") == "updater-key-456"


class TestLoadConfig:
    def test_load_valid_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(VALID_CONFIG))
        config = load_config(str(config_file))
        assert config["model"] == "xai/grok-4.20-0309-non-reasoning"
        assert len(config["performers"]) == 1

    def test_load_nonexistent_file(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            load_config(str(tmp_path / "nope.yaml"))

    def test_load_invalid_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(": : : bad yaml [")
        with pytest.raises(ConfigError, match="Failed to parse"):
            load_config(str(config_file))


class TestEnsureConfig:
    def test_copies_example_when_missing(self, tmp_path):
        config_path = str(tmp_path / "config" / "booklet-reader" / "config.yaml")
        example_path = str(tmp_path / "config.example.yaml")
        with open(example_path, "w") as f:
            yaml.dump(VALID_CONFIG, f)
        result = ensure_config(config_path, example_path)
        assert result is False
        assert os.path.exists(config_path)

    def test_returns_true_when_exists(self, tmp_path):
        config_path = str(tmp_path / "config.yaml")
        with open(config_path, "w") as f:
            yaml.dump(VALID_CONFIG, f)
        result = ensure_config(config_path, config_path)
        assert result is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'booklet_reader.config'`

- [ ] **Step 3: Write the implementation**

`booklet_reader/config.py`:
```python
import os
import shutil
import yaml


class ConfigError(Exception):
    pass


def ensure_config(config_path, example_path):
    """Check if config exists. If not, copy example and return False. If yes, return True."""
    if os.path.exists(config_path):
        return True
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    shutil.copy2(example_path, config_path)
    return False


def load_config(config_path):
    """Load and parse a YAML config file. Raises ConfigError on failure."""
    if not os.path.exists(config_path):
        raise ConfigError(f"Config error: '{config_path}' not found")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Config error: Failed to parse '{config_path}': {e}")
    if config is None:
        raise ConfigError(f"Config error: '{config_path}' is empty")
    return config


def validate_config(config):
    """Validate config structure. Raises ConfigError with specific messages."""
    if "model" not in config:
        raise ConfigError("Config error: 'model' field is required")
    if "api_key" not in config:
        raise ConfigError("Config error: 'api_key' field is required")
    if config["api_key"] == "your-api-key-here":
        raise ConfigError(
            "Config error: Please set your API key in the config file"
        )
    if "performers" not in config:
        raise ConfigError("Config error: 'performers' field is required")
    if not isinstance(config["performers"], list) or len(config["performers"]) == 0:
        raise ConfigError("Config error: 'performers' must be a non-empty list")
    for i, performer in enumerate(config["performers"]):
        if "name" not in performer:
            raise ConfigError(f"Config error: Performer at index {i} missing 'name'")
        name = performer["name"]
        if "instruments" not in performer:
            raise ConfigError(
                f"Config error: Performer '{name}' missing 'instruments'"
            )
        if not isinstance(performer["instruments"], list) or len(performer["instruments"]) == 0:
            raise ConfigError(
                f"Config error: Performer '{name}': 'instruments' must be a non-empty list"
            )
        for j, instrument in enumerate(performer["instruments"]):
            if "names" not in instrument:
                raise ConfigError(
                    f"Config error: Performer '{name}', instrument at index {j} missing 'names'"
                )


def get_api_key(config, role="model"):
    """Get the API key for the given role ('model' or 'model_updater').

    For 'model_updater', falls back to the main api_key if model_updater_api_key
    is empty or absent.
    """
    if role == "model_updater":
        key = config.get("model_updater_api_key", "")
        if key:
            return key
    return config["api_key"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add booklet_reader/config.py tests/test_config.py
git commit -m "Add config loading, validation, and API key resolution"
```

---

### Task 3: Dependency Checking

**Files:**
- Create: `booklet_reader/dependencies.py`
- Create: `tests/test_dependencies.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_dependencies.py`:
```python
import pytest
from unittest.mock import patch
from booklet_reader.dependencies import check_python_deps, check_libreoffice, DependencyError


class TestCheckPythonDeps:
    def test_all_present(self):
        check_python_deps()

    def test_missing_package(self):
        with patch("importlib.import_module", side_effect=ImportError("no module")):
            with pytest.raises(DependencyError, match="pip install"):
                check_python_deps()


class TestCheckLibreoffice:
    def test_found(self):
        with patch("shutil.which", return_value="/usr/bin/libreoffice"):
            check_libreoffice()

    def test_not_found(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(DependencyError, match="libreoffice"):
                check_libreoffice()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_dependencies.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`booklet_reader/dependencies.py`:
```python
import importlib
import shutil


class DependencyError(Exception):
    pass


REQUIRED_PACKAGES = {
    "litellm": "litellm",
    "yaml": "PyYAML",
    "fitz": "PyMuPDF",
}


def check_python_deps():
    """Check that all required Python packages are importable."""
    missing = []
    for module_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(pip_name)
    if missing:
        packages = " ".join(missing)
        raise DependencyError(
            f"Error: Required packages not installed. Install with: pip install {packages}"
        )


def check_libreoffice():
    """Check that libreoffice is available on PATH."""
    if shutil.which("libreoffice") is None:
        raise DependencyError(
            "Error: 'libreoffice' is required for DOC/DOCX/ODT conversion but was not found. "
            "Install it with: sudo apt install libreoffice"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_dependencies.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add booklet_reader/dependencies.py tests/test_dependencies.py
git commit -m "Add dependency checking"
```

---

### Task 4: Document Conversion Pipeline

**Files:**
- Create: `booklet_reader/converter.py`
- Create: `tests/test_converter.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_converter.py`:
```python
import os
import pytest
from unittest.mock import patch, MagicMock
from booklet_reader.converter import (
    detect_file_type,
    convert_to_pdf,
    render_pdf_to_images,
    read_image_file,
    ConversionError,
    FILE_TYPE_DOCUMENT,
    FILE_TYPE_PDF,
    FILE_TYPE_IMAGE,
)


class TestDetectFileType:
    def test_pdf(self):
        assert detect_file_type("document.pdf") == FILE_TYPE_PDF

    def test_doc(self):
        assert detect_file_type("document.doc") == FILE_TYPE_DOCUMENT

    def test_docx(self):
        assert detect_file_type("document.docx") == FILE_TYPE_DOCUMENT

    def test_odt(self):
        assert detect_file_type("document.odt") == FILE_TYPE_DOCUMENT

    def test_png(self):
        assert detect_file_type("poster.png") == FILE_TYPE_IMAGE

    def test_jpg(self):
        assert detect_file_type("poster.jpg") == FILE_TYPE_IMAGE

    def test_jpeg(self):
        assert detect_file_type("poster.jpeg") == FILE_TYPE_IMAGE

    def test_webp(self):
        assert detect_file_type("poster.webp") == FILE_TYPE_IMAGE

    def test_uppercase(self):
        assert detect_file_type("DOCUMENT.PDF") == FILE_TYPE_PDF

    def test_unsupported(self):
        with pytest.raises(ConversionError, match="Unsupported file type"):
            detect_file_type("document.txt")


class TestConvertToPdf:
    def test_pdf_passthrough(self, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        result = convert_to_pdf(str(pdf_file))
        assert result == str(pdf_file)

    def test_doc_conversion(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with patch("glob.glob", return_value=["/tmp/out/test.pdf"]):
                result = convert_to_pdf(str(tmp_path / "test.doc"))
            mock_run.assert_called_once()
            assert "libreoffice" in mock_run.call_args[0][0][0]

    def test_nonexistent_file(self):
        with pytest.raises(ConversionError, match="not found"):
            convert_to_pdf("/nonexistent/file.doc")


class TestRenderPdfToImages:
    def test_renders_pages(self):
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample-data")
        pdfs = [f for f in os.listdir(sample_dir) if f.endswith(".pdf")] if os.path.isdir(sample_dir) else []
        if not pdfs:
            pytest.skip("No sample PDFs available")
        pdf_path = os.path.join(sample_dir, pdfs[0])
        images = render_pdf_to_images(pdf_path)
        assert len(images) > 0
        for img in images:
            assert isinstance(img, bytes)
            assert img[:8] == b"\x89PNG\r\n\x1a\n"


class TestReadImageFile:
    def test_reads_png(self, tmp_path):
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\nfakedata")
        result = read_image_file(str(img_file))
        assert result == b"\x89PNG\r\n\x1a\nfakedata"

    def test_nonexistent(self):
        with pytest.raises(ConversionError, match="not found"):
            read_image_file("/nonexistent/poster.png")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_converter.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`booklet_reader/converter.py`:
```python
import glob
import os
import subprocess
import tempfile

import fitz  # PyMuPDF


class ConversionError(Exception):
    pass


FILE_TYPE_DOCUMENT = "document"  # DOC, DOCX, ODT
FILE_TYPE_PDF = "pdf"
FILE_TYPE_IMAGE = "image"

_DOCUMENT_EXTENSIONS = {".doc", ".docx", ".odt"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def detect_file_type(filepath):
    """Detect file type category by extension. Returns FILE_TYPE_* constant."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        return FILE_TYPE_PDF
    elif ext in _DOCUMENT_EXTENSIONS:
        return FILE_TYPE_DOCUMENT
    elif ext in _IMAGE_EXTENSIONS:
        return FILE_TYPE_IMAGE
    else:
        raise ConversionError(
            f"Error: Unsupported file type '{ext}'. "
            f"Supported: .pdf, .doc, .docx, .odt, .png, .jpg, .jpeg, .webp"
        )


def convert_to_pdf(filepath):
    """Convert DOC/DOCX/ODT to PDF using libreoffice. Returns path to PDF.

    If already a PDF, returns the original path.
    """
    if not os.path.exists(filepath):
        raise ConversionError(f"Error: File not found: '{filepath}'")

    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        return filepath

    tmp_dir = tempfile.mkdtemp(prefix="booklet-reader-")
    try:
        result = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                tmp_dir,
                filepath,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise ConversionError(
                f"Error: libreoffice conversion failed: {result.stderr}"
            )
        basename = os.path.splitext(os.path.basename(filepath))[0]
        pdf_files = glob.glob(os.path.join(tmp_dir, basename + ".pdf"))
        if not pdf_files:
            raise ConversionError(
                "Error: libreoffice conversion produced no output"
            )
        return pdf_files[0]
    except subprocess.TimeoutExpired:
        raise ConversionError("Error: libreoffice conversion timed out")


def render_pdf_to_images(pdf_path, dpi=200):
    """Render each page of a PDF to PNG bytes. Returns a list of PNG byte strings."""
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise ConversionError(f"Error: Failed to open PDF '{pdf_path}': {e}")

    images = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        images.append(pix.tobytes("png"))
    doc.close()
    return images


def read_image_file(filepath):
    """Read an image file and return its raw bytes."""
    if not os.path.exists(filepath):
        raise ConversionError(f"Error: File not found: '{filepath}'")
    with open(filepath, "rb") as f:
        return f.read()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_converter.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add booklet_reader/converter.py tests/test_converter.py
git commit -m "Add document conversion pipeline (DOC/DOCX/ODT→PDF→PNG, image read)"
```

---

### Task 5: LLM Prompt Construction

**Files:**
- Create: `booklet_reader/prompt.py`
- Create: `tests/test_prompt.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_prompt.py`:
```python
import pytest
from booklet_reader.prompt import build_prompt, build_retry_prompt


class TestBuildPrompt:
    def test_includes_performer_names(self):
        performers = [
            {
                "name": "Nagy Eszter",
                "instruments": [
                    {"names": "hegedű / violin", "teachers": [], "accompanists": []}
                ],
            }
        ]
        prompt = build_prompt(performers)
        assert "Nagy Eszter" in prompt

    def test_includes_all_aliases(self):
        performers = [
            {
                "name": "Test Player",
                "instruments": [
                    {"names": "gordonka / cello", "teachers": [], "accompanists": []}
                ],
            }
        ]
        prompt = build_prompt(performers)
        assert "gordonka" in prompt
        assert "cello" in prompt

    def test_includes_json_schema(self):
        performers = [
            {
                "name": "Test",
                "instruments": [
                    {"names": "zongora / piano", "teachers": [], "accompanists": []}
                ],
            }
        ]
        prompt = build_prompt(performers)
        assert "event_name" in prompt
        assert "performance_date" in prompt
        assert "co_performers" in prompt
        assert "pieces" in prompt

    def test_multiple_performers(self):
        performers = [
            {
                "name": "Player One",
                "instruments": [{"names": "hegedű", "teachers": [], "accompanists": []}],
            },
            {
                "name": "Player Two",
                "instruments": [{"names": "fuvola / flute", "teachers": [], "accompanists": []}],
            },
        ]
        prompt = build_prompt(performers)
        assert "Player One" in prompt
        assert "Player Two" in prompt

    def test_returns_string(self):
        performers = [
            {
                "name": "Test",
                "instruments": [{"names": "zongora", "teachers": [], "accompanists": []}],
            }
        ]
        prompt = build_prompt(performers)
        assert isinstance(prompt, str)
        assert len(prompt) > 100


class TestBuildRetryPrompt:
    def test_includes_previous_response(self):
        prompt = build_retry_prompt("bad json here")
        assert "bad json here" in prompt

    def test_asks_for_valid_json(self):
        prompt = build_retry_prompt("{invalid")
        assert "valid JSON" in prompt

    def test_asks_for_all_fields(self):
        prompt = build_retry_prompt("[]")
        assert "required" in prompt.lower() or "field" in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_prompt.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`booklet_reader/prompt.py`:
```python
import json


def build_prompt(performers):
    """Build the LLM prompt for extracting performance data from a program booklet.

    Args:
        performers: List of performer dicts from config, each with 'name' and 'instruments'.

    Returns:
        The prompt string to send alongside the document.
    """
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

    return f"""You are analyzing a music program booklet (műsorfüzet). These pages are from a document about a music competition, concert, recital, festival, or other public performance.

Your task: find any performances by the following performers and extract structured data.

=== PERFORMERS TO SEARCH FOR ===
{performers_block}

=== INSTRUCTIONS ===
1. Search the entire document for any of the listed performer names.
2. Be flexible with name matching: the document may omit middle names, use abbreviations, or use slightly different forms. Match on family name + first name even if middle names differ.
3. For each match, extract the specific performance date. The document may have a schedule at the beginning showing which day/time slot each category performs — use this to determine the exact date, not just the event date range.
4. Identify the instrument played. Use the canonical name (first alias) from the performer list above.
5. List ALL pieces performed (composer + title). Include opus numbers, movement names, and any other details mentioned.
6. If a teacher (felkészítő tanár, tanár) is mentioned for this performer's entry, include it.
7. If an accompanist (kísérő, zongorakísérő) is mentioned, include it.
8. If the performer is part of a duo, trio, quartet, or other ensemble, list the other members as co_performers with their instruments. If solo, use an empty array.
9. If a performer appears in multiple entries (e.g., different categories or rounds), return a separate object for each appearance.

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
"""


def build_retry_prompt(previous_response):
    """Build a follow-up prompt asking the LLM to fix its response.

    Args:
        previous_response: The raw text the LLM returned that failed JSON parsing.

    Returns:
        The retry prompt string.
    """
    return f"""Your previous response could not be parsed as valid JSON. Here is what you returned:

{previous_response}

Please try again. Return ONLY a valid JSON array with all required fields populated with data from the document:
- event_name (string)
- performance_date (YYYY-MM-DD string)
- performer (string)
- instrument (string)
- pieces (array of objects with composer and title)
- teacher (string or null)
- accompanist (string or null)
- co_performers (array of objects with name and instrument)

No markdown fences, no explanation. Just the JSON array."""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_prompt.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add booklet_reader/prompt.py tests/test_prompt.py
git commit -m "Add LLM prompt construction with retry nudge"
```

---

### Task 6: LLM Calling with Cascading Fallback

**Files:**
- Create: `booklet_reader/llm.py`
- Create: `tests/test_llm.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_llm.py`:
```python
import json
import base64
import pytest
from unittest.mock import patch, MagicMock
from booklet_reader.llm import (
    build_messages_with_document,
    build_messages_with_images,
    parse_llm_response,
    try_level,
    run_cascade,
    LLMError,
)


def _mock_response(content):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


class TestBuildMessagesWithDocument:
    def test_includes_prompt_and_file(self):
        messages = build_messages_with_document("Find performers", b"%PDF-fake", "application/pdf")
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        content = messages[0]["content"]
        text_parts = [c for c in content if c["type"] == "text"]
        doc_parts = [c for c in content if c["type"] == "image_url"]
        assert len(text_parts) == 1
        assert len(doc_parts) == 1
        assert text_parts[0]["text"] == "Find performers"


class TestBuildMessagesWithImages:
    def test_includes_prompt_and_images(self):
        images = [b"\x89PNG\r\n\x1a\nfake1", b"\x89PNG\r\n\x1a\nfake2"]
        messages = build_messages_with_images("Find performers", images)
        content = messages[0]["content"]
        text_parts = [c for c in content if c["type"] == "text"]
        image_parts = [c for c in content if c["type"] == "image_url"]
        assert len(text_parts) == 1
        assert len(image_parts) == 2

    def test_image_encoding(self):
        png_bytes = b"\x89PNG\r\n\x1a\nfakedata"
        messages = build_messages_with_images("prompt", [png_bytes])
        image_part = messages[0]["content"][1]
        expected_b64 = base64.b64encode(png_bytes).decode("utf-8")
        assert image_part["image_url"]["url"] == f"data:image/png;base64,{expected_b64}"


class TestParseLlmResponse:
    def test_valid_json_array(self):
        raw = json.dumps([{"event_name": "Test", "performer": "A"}])
        result = parse_llm_response(raw)
        assert isinstance(result, list)
        assert result[0]["event_name"] == "Test"

    def test_empty_array(self):
        result = parse_llm_response("[]")
        assert result == []

    def test_strips_markdown_fences(self):
        raw = '```json\n[{"event_name": "Test"}]\n```'
        result = parse_llm_response(raw)
        assert result[0]["event_name"] == "Test"

    def test_invalid_json(self):
        with pytest.raises(LLMError, match="invalid JSON"):
            parse_llm_response("not json at all")

    def test_not_an_array(self):
        with pytest.raises(LLMError, match="expected a JSON array"):
            parse_llm_response('{"event_name": "Test"}')


class TestTryLevel:
    def test_success_first_attempt(self):
        good = _mock_response('[{"event_name": "OK"}]')
        with patch("litellm.completion", return_value=good):
            result = try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt")
        assert result[0]["event_name"] == "OK"

    def test_retry_on_bad_json(self):
        bad = _mock_response("not json")
        good = _mock_response('[{"event_name": "OK"}]')
        with patch("litellm.completion", side_effect=[bad, good]):
            result = try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt")
        assert result[0]["event_name"] == "OK"

    def test_returns_none_after_two_bad_json(self):
        bad = _mock_response("not json")
        with patch("litellm.completion", return_value=bad):
            result = try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt")
        assert result is None

    def test_returns_none_on_api_error(self):
        with patch("litellm.completion", side_effect=Exception("API down")):
            result = try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt")
        assert result is None


class TestRunCascade:
    def test_succeeds_at_level_1(self):
        good = _mock_response('[{"event_name": "OK"}]')
        with patch("litellm.completion", return_value=good):
            result = run_cascade(
                model="model",
                api_key="key",
                prompt="find performers",
                document_bytes=b"fake doc",
                document_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                pdf_bytes=None,
                image_list=None,
            )
        assert result[0]["event_name"] == "OK"

    def test_falls_through_to_images(self):
        bad = _mock_response("not json")
        good = _mock_response('[{"event_name": "OK"}]')
        # Level 1 (doc): bad, bad. Level 2 (pdf): bad, bad. Level 3 (images): good.
        with patch("litellm.completion", side_effect=[bad, bad, bad, bad, good]):
            result = run_cascade(
                model="model",
                api_key="key",
                prompt="find performers",
                document_bytes=b"fake doc",
                document_mime="application/msword",
                pdf_bytes=b"fake pdf",
                image_list=[b"\x89PNGfake"],
            )
        assert result[0]["event_name"] == "OK"

    def test_hard_fail_all_levels(self):
        bad = _mock_response("not json")
        with patch("litellm.completion", return_value=bad):
            with pytest.raises(LLMError, match="All input format levels failed"):
                run_cascade(
                    model="model",
                    api_key="key",
                    prompt="find performers",
                    document_bytes=None,
                    document_mime=None,
                    pdf_bytes=b"fake pdf",
                    image_list=[b"\x89PNGfake"],
                )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`booklet_reader/llm.py`:
```python
import base64
import json
import os
import sys

import litellm

from booklet_reader.prompt import build_retry_prompt


class LLMError(Exception):
    pass


def build_messages_with_document(prompt, doc_bytes, mime_type):
    """Build messages with a raw document file attached."""
    b64 = base64.b64encode(doc_bytes).decode("utf-8")
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                },
            ],
        }
    ]


def build_messages_with_images(prompt, images):
    """Build messages with page images attached."""
    content = [{"type": "text", "text": prompt}]
    for img_bytes in images:
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
        )
    return [{"role": "user", "content": content}]


def parse_llm_response(raw_text):
    """Parse the raw LLM response text into a list of result dicts.

    Handles markdown code fences if present. Raises LLMError if invalid.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"Error: LLM returned invalid JSON: {e}")

    if not isinstance(result, list):
        raise LLMError("Error: LLM returned invalid JSON: expected a JSON array")

    return result


def try_level(model, api_key, messages, prompt):
    """Try sending messages to the LLM. Retry once on invalid JSON with a nudge.

    Returns parsed results list on success, or None on failure (API error or
    two consecutive invalid JSON responses).
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


_MIME_TYPES = {
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".pdf": "application/pdf",
}


def get_mime_type(filepath):
    """Get MIME type for a document file based on extension."""
    ext = os.path.splitext(filepath)[1].lower()
    return _MIME_TYPES.get(ext)


def run_cascade(model, api_key, prompt, document_bytes, document_mime, pdf_bytes, image_list):
    """Run the cascading LLM submission: raw document → PDF → images.

    Each level tries once, retries on invalid JSON with a nudge, then falls to next level.
    Raises LLMError if all levels fail.
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
        result = try_level(model, api_key, messages, prompt)
        if result is not None:
            return result
        if i < len(levels) - 1:
            print(
                f"Level {i + 1} ({level_name}) failed, falling to next format...",
                file=sys.stderr,
            )

    raise LLMError("Error: All input format levels failed. LLM could not produce valid output.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_llm.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add booklet_reader/llm.py tests/test_llm.py
git commit -m "Add LLM calling with cascading fallback (raw→PDF→images)"
```

---

### Task 7: Gap Filling (Teacher/Accompanist from Config)

**Files:**
- Create: `booklet_reader/gaps.py`
- Create: `tests/test_gaps.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_gaps.py`:
```python
import pytest
from booklet_reader.gaps import fill_gaps


PERFORMERS_CONFIG = [
    {
        "name": "Nagy Eszter",
        "instruments": [
            {
                "names": "hegedű / violin",
                "teachers": [
                    {"name": "Tóth Katalin", "from": "2020-09-01", "to": "2025-06-30"},
                    {"name": "Kovács Anna", "from": "2025-09-01"},
                ],
                "accompanists": [
                    {"name": "Fekete Mária", "from": "2023-09-01"},
                ],
            }
        ],
    }
]


class TestFillGaps:
    def test_leaves_existing_teacher(self):
        results = [
            {
                "performer": "Nagy Eszter",
                "instrument": "hegedű",
                "performance_date": "2024-03-15",
                "teacher": "Already Set",
                "accompanist": None,
            }
        ]
        filled = fill_gaps(results, PERFORMERS_CONFIG)
        assert filled[0]["teacher"] == "Already Set"
        assert filled[0]["accompanist"] == "Fekete Mária"

    def test_fills_teacher_by_date(self):
        results = [
            {
                "performer": "Nagy Eszter",
                "instrument": "hegedű",
                "performance_date": "2024-03-15",
                "teacher": None,
                "accompanist": None,
            }
        ]
        filled = fill_gaps(results, PERFORMERS_CONFIG)
        assert filled[0]["teacher"] == "Tóth Katalin"

    def test_fills_teacher_second_range(self):
        results = [
            {
                "performer": "Nagy Eszter",
                "instrument": "hegedű",
                "performance_date": "2025-11-01",
                "teacher": None,
                "accompanist": None,
            }
        ]
        filled = fill_gaps(results, PERFORMERS_CONFIG)
        assert filled[0]["teacher"] == "Kovács Anna"

    def test_no_match_leaves_null(self):
        results = [
            {
                "performer": "Unknown Player",
                "instrument": "hegedű",
                "performance_date": "2024-03-15",
                "teacher": None,
                "accompanist": None,
            }
        ]
        filled = fill_gaps(results, PERFORMERS_CONFIG)
        assert filled[0]["teacher"] is None

    def test_date_before_all_ranges(self):
        results = [
            {
                "performer": "Nagy Eszter",
                "instrument": "hegedű",
                "performance_date": "2019-01-01",
                "teacher": None,
                "accompanist": None,
            }
        ]
        filled = fill_gaps(results, PERFORMERS_CONFIG)
        assert filled[0]["teacher"] is None

    def test_instrument_alias_matching(self):
        results = [
            {
                "performer": "Nagy Eszter",
                "instrument": "hegedű",
                "performance_date": "2024-03-15",
                "teacher": None,
                "accompanist": None,
            }
        ]
        filled = fill_gaps(results, PERFORMERS_CONFIG)
        assert filled[0]["teacher"] == "Tóth Katalin"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_gaps.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`booklet_reader/gaps.py`:
```python
from datetime import date


def _parse_date(date_str):
    """Parse a YYYY-MM-DD date string."""
    if isinstance(date_str, date):
        return date_str
    return date.fromisoformat(str(date_str))


def _find_performer(name, performers_config):
    """Find a performer in config by name."""
    for p in performers_config:
        if p["name"] == name:
            return p
    return None


def _find_instrument(performer_config, instrument_name):
    """Find an instrument entry in a performer's config by canonical name or alias."""
    for inst in performer_config["instruments"]:
        aliases = [a.strip() for a in inst["names"].split("/")]
        if instrument_name in aliases:
            return inst
    return None


def _lookup_by_date(entries, performance_date):
    """Look up a teacher or accompanist entry that covers the given date."""
    if not entries:
        return None
    perf_date = _parse_date(performance_date)
    for entry in entries:
        start = _parse_date(entry["from"])
        end = _parse_date(entry["to"]) if "to" in entry and entry["to"] else None
        if perf_date >= start and (end is None or perf_date <= end):
            return entry["name"]
    return None


def fill_gaps(results, performers_config):
    """Fill in missing teacher and accompanist fields from config based on date.

    Args:
        results: List of result dicts from LLM (may have null teacher/accompanist).
        performers_config: The 'performers' list from config.

    Returns:
        The same list with nulls filled where possible.
    """
    for result in results:
        performer = _find_performer(result["performer"], performers_config)
        if performer is None:
            continue

        instrument = _find_instrument(performer, result["instrument"])
        if instrument is None:
            continue

        perf_date = result.get("performance_date")
        if perf_date is None:
            continue

        if result.get("teacher") is None:
            teachers = instrument.get("teachers", [])
            result["teacher"] = _lookup_by_date(teachers, perf_date)

        if result.get("accompanist") is None:
            accompanists = instrument.get("accompanists", [])
            result["accompanist"] = _lookup_by_date(accompanists, perf_date)

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_gaps.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add booklet_reader/gaps.py tests/test_gaps.py
git commit -m "Add gap filling for teacher/accompanist from config"
```

---

### Task 8: Main CLI Script (`booklet-reader`)

**Files:**
- Create: `booklet-reader` (executable)

- [ ] **Step 1: Write the main CLI script**

`booklet-reader`:
```python
#!/usr/bin/env python3
"""booklet-reader — Extract performance data from music program booklets."""

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

    # 2. Check args
    if len(sys.argv) != 2:
        print("Usage: booklet-reader <document>", file=sys.stderr)
        sys.exit(2)

    document_path = os.path.abspath(sys.argv[1])

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
            # Level 1: raw document
            with open(document_path, "rb") as f:
                document_bytes = f.read()
            document_mime = get_mime_type(document_path)

            # Level 2: convert to PDF
            pdf_path = convert_to_pdf(document_path)
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

            # Level 3: render PDF to images
            image_list = render_pdf_to_images(pdf_path)

        elif file_type == FILE_TYPE_PDF:
            # Level 2: PDF directly
            with open(document_path, "rb") as f:
                pdf_bytes = f.read()

            # Level 3: render to images
            image_list = render_pdf_to_images(document_path)

        elif file_type == FILE_TYPE_IMAGE:
            # Level 3: image directly
            img_bytes = read_image_file(document_path)
            image_list = [img_bytes]

    except ConversionError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    # 7. Build prompt and run cascade
    prompt = build_prompt(config["performers"])
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

- [ ] **Step 2: Make it executable**

```bash
chmod +x booklet-reader
```

- [ ] **Step 3: Smoke test with no args**

Run: `cd /home/csillag/private/booklet-reader && python booklet-reader`
Expected: `Usage: booklet-reader <document>` on stderr, exit 2

- [ ] **Step 4: Commit**

```bash
git add booklet-reader
git commit -m "Add main booklet-reader CLI with cascading fallback"
```

---

### Task 9: Model Updater Script (`booklet-model-updater`)

**Files:**
- Create: `booklet_reader/model_updater.py`
- Create: `tests/test_model_updater.py`
- Create: `booklet-model-updater` (executable)

- [ ] **Step 1: Write the failing tests**

`tests/test_model_updater.py`:
```python
import pytest
from booklet_reader.model_updater import (
    extract_model_block,
    build_updated_model_block,
    update_config_file_models,
)


SAMPLE_CONFIG = """# === Model Configuration ===
model: "xai/grok-4.20-0309-non-reasoning"
api_key: "test-key"
model_updater_model: "xai/grok-4.20-0309-non-reasoning"

# === Available Models (PDF and/or Vision-Capable) ===
# Copy a model identifier from this list to the 'model' field above.
# DO NOT edit this block manually — it is maintained by booklet-model-updater.
# --- BEGIN AVAILABLE MODELS ---
# available_models:
#   - openai/gpt-4o
#   - anthropic/claude-opus-4-6
# --- END AVAILABLE MODELS ---

# === Performers ===
performers:
  - name: "Test"
"""


class TestExtractModelBlock:
    def test_extracts_models(self):
        models = extract_model_block(SAMPLE_CONFIG)
        assert "openai/gpt-4o" in models
        assert "anthropic/claude-opus-4-6" in models
        assert len(models) == 2

    def test_no_markers(self):
        models = extract_model_block("no markers here")
        assert models == []


class TestBuildUpdatedModelBlock:
    def test_builds_commented_block(self):
        models = ["openai/gpt-4o", "anthropic/claude-opus-4-6", "xai/grok-4.20-0309-non-reasoning"]
        block = build_updated_model_block(models)
        assert "# --- BEGIN AVAILABLE MODELS ---" in block
        assert "# --- END AVAILABLE MODELS ---" in block
        assert "#   - openai/gpt-4o" in block
        assert "#   - xai/grok-4.20-0309-non-reasoning" in block


class TestUpdateConfigFileModels:
    def test_replaces_block(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(SAMPLE_CONFIG)
        new_models = ["openai/gpt-4o", "anthropic/claude-opus-4-6", "gemini/gemini-2.5-pro"]
        update_config_file_models(str(config_file), new_models)
        updated = config_file.read_text()
        assert "gemini/gemini-2.5-pro" in updated
        assert 'model: "xai/grok-4.20-0309-non-reasoning"' in updated
        assert "performers:" in updated
        assert '- name: "Test"' in updated

    def test_preserves_content_outside_markers(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(SAMPLE_CONFIG)
        new_models = ["openai/gpt-4o"]
        update_config_file_models(str(config_file), new_models)
        updated = config_file.read_text()
        assert "# === Model Configuration ===" in updated
        assert "# === Performers ===" in updated
        assert 'api_key: "test-key"' in updated
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_model_updater.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`booklet_reader/model_updater.py`:
```python
import json
import re
import sys

import litellm


BEGIN_MARKER = "# --- BEGIN AVAILABLE MODELS ---"
END_MARKER = "# --- END AVAILABLE MODELS ---"


def extract_model_block(config_text):
    """Extract the list of model identifiers from the config file's model block."""
    in_block = False
    models = []
    for line in config_text.splitlines():
        if BEGIN_MARKER in line:
            in_block = True
            continue
        if END_MARKER in line:
            break
        if in_block:
            match = re.match(r"^#\s+-\s+(.+)$", line)
            if match:
                models.append(match.group(1).strip())
    return models


def build_updated_model_block(models):
    """Build the commented model block text from a list of model identifiers."""
    lines = [BEGIN_MARKER, "# available_models:"]
    for model in sorted(models):
        lines.append(f"#   - {model}")
    lines.append(END_MARKER)
    return "\n".join(lines)


def update_config_file_models(config_path, new_models):
    """Replace the model block in the config file, preserving everything else."""
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_block = build_updated_model_block(new_models)

    pattern = re.compile(
        re.escape(BEGIN_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    updated = pattern.sub(new_block, content)

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(updated)


def query_llm_for_models(model, api_key):
    """Ask an LLM for current PDF/vision-capable model identifiers."""
    prompt = """List all currently available LLM models from major providers that support PDF and/or image/vision input via their API.

For each model, give me the identifier in LiteLLM format: provider/model-name
For example: openai/gpt-4o, anthropic/claude-sonnet-4-20250514, gemini/gemini-2.5-pro

Only include models that:
1. Accept PDF or image input as part of their API
2. Are currently available (not deprecated or preview-only)
3. Have a known LiteLLM provider prefix

Return ONLY a JSON array of strings. No explanation, no markdown fences. Example:
["openai/gpt-4o", "anthropic/claude-sonnet-4-20250514"]"""

    try:
        response = litellm.completion(
            model=model,
            api_key=api_key,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"Error: LLM API call failed: {e}", file=sys.stderr)
        sys.exit(1)

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    try:
        models = json.loads(raw)
    except json.JSONDecodeError:
        print("Error: LLM returned invalid JSON for model list.", file=sys.stderr)
        sys.exit(1)

    if not isinstance(models, list):
        print("Error: LLM returned non-list for model list.", file=sys.stderr)
        sys.exit(1)

    return [m for m in models if isinstance(m, str)]


def cross_reference_with_litellm(models):
    """Filter model list to only those known to LiteLLM."""
    valid = []
    for model in models:
        try:
            litellm.get_model_info(model)
            valid.append(model)
        except Exception:
            pass
    return valid
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/test_model_updater.py -v`
Expected: All PASS

- [ ] **Step 5: Write the `booklet-model-updater` CLI script**

`booklet-model-updater`:
```python
#!/usr/bin/env python3
"""booklet-model-updater — Update the list of available PDF/vision-capable LLM models."""

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
        sys.exit(1)
    except DependencyError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    from booklet_reader.config import load_config, validate_config, ensure_config, get_api_key, ConfigError
    from booklet_reader.model_updater import (
        extract_model_block,
        query_llm_for_models,
        cross_reference_with_litellm,
        update_config_file_models,
    )

    # 2. Config check
    config_path = os.path.expanduser("~/.config/booklet-reader/config.yaml")
    example_path = os.path.join(get_script_dir(), "config.example.yaml")

    try:
        exists = ensure_config(config_path, example_path)
        if not exists:
            print(
                f"Before reading, please fill in your configuration at {config_path}",
                file=sys.stderr,
            )
            sys.exit(0)
        config = load_config(config_path)
        validate_config(config)
    except ConfigError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    # 3. Get current models from config
    with open(config_path, "r", encoding="utf-8") as f:
        config_text = f.read()
    current_models = set(extract_model_block(config_text))

    # 4. Query LLM for available models
    model = config.get("model_updater_model", config["model"])
    api_key = get_api_key(config, "model_updater")
    llm_models = query_llm_for_models(model, api_key)

    # 5. Cross-reference with LiteLLM
    valid_models = cross_reference_with_litellm(llm_models)

    # 6. Compare and update
    all_models = current_models | set(valid_models)
    new_models = all_models - current_models

    if new_models:
        for m in sorted(new_models):
            print(m)
        update_config_file_models(config_path, sorted(all_models))


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Make it executable**

```bash
chmod +x booklet-model-updater
```

- [ ] **Step 7: Commit**

```bash
git add booklet_reader/model_updater.py tests/test_model_updater.py booklet-model-updater
git commit -m "Add model updater script and logic"
```

---

### Task 10: End-to-End Smoke Test

**Files:**
- No new files — uses existing sample data and scripts

- [ ] **Step 1: Install dependencies**

```bash
cd /home/csillag/private/booklet-reader && pip install -r requirements.txt
```

- [ ] **Step 2: Run full test suite**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Smoke test CLI with a sample PDF**

Run: `cd /home/csillag/private/booklet-reader && python booklet-reader "sample-data/VEGLEGES Musor_2025 KZF.pdf.pdf"`
Expected: Either JSON output to stdout (exit 0) or no matches (exit 1), depending on whether the example config performers match. This validates the full pipeline works end-to-end.

- [ ] **Step 4: Commit AGENTS.md and any remaining files**

```bash
git add AGENTS.md
git commit -m "Add agent rules"
```

- [ ] **Step 5: Run all tests one final time**

Run: `cd /home/csillag/private/booklet-reader && python -m pytest tests/ -v`
Expected: All PASS
