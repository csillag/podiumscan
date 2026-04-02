import pytest
from podiumscan.model_updater import (
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
