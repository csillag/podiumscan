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
