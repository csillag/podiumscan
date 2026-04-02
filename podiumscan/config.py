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
