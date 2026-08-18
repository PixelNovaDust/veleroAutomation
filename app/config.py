import copy
import json
import os

from app.paths import (
    expand,
    get_base_directory,
    get_bundle_directory,
    is_frozen
)


CONFIG_PATH_VARIABLE = "VELERO_CONFIG_FILE"

CONFIG_FILE_NAME = "config.json"


DEFAULT_CONFIG = {

    "excel": {
        "file_path": "",
        "table_name": "",
        "save_retry_attempts": 5,
        "save_retry_delay_seconds": 3,
        "safe_save": True,
        "close_local_workbook": True,
        "confirm_before_close": True,
        "warn_when_opened_by_others": True,
        "backup": {
            "enabled": True,
            "directory": "backups",
            "retention_days": 14
        }
    },

    "processing": {
        "processed_value": "Yes",
        "failed_value": "No",
        "ledger": {
            "enabled": True,
            "file_path": "data/processed-ledger.json",
            "restore_missing": True,
            "retention_days": 90
        }
    },

    "logging": {
        "directory": "logs",
        "file_name": "velero-automation.log",
        "level": "DEBUG",
        "console_level": "DEBUG",
        "retention_days": 14
    },

    "console": {
        "pause_on_exit": True
    },

    "pagerduty": {
        "enabled": True,
        "base_url": "https://api.pagerduty.com",
        "api_token": "",
        "urgency": "low",
        "priority_id": "",
        "timeout_seconds": 30,
        "max_retries": 3,
        "retry_delay_seconds": 2
    }
}


def _expand_environment_variables(value):

    if isinstance(value, dict):
        return {
            key: _expand_environment_variables(val)
            for key, val in value.items()
        }

    if isinstance(value, list):
        return [
            _expand_environment_variables(item)
            for item in value
        ]

    if isinstance(value, str):
        return expand(value)

    return value


def _merge(defaults, overrides):
    """
    Overlay a config file on top of the defaults so a missing
    or partially filled config.json can never raise a KeyError
    halfway through a run.
    """

    merged = copy.deepcopy(defaults)

    if not isinstance(overrides, dict):
        return merged

    for key, value in overrides.items():

        if (
            isinstance(value, dict)
            and isinstance(merged.get(key), dict)
        ):
            merged[key] = _merge(merged[key], value)

        else:
            merged[key] = value

    return merged


def candidate_config_paths():
    """
    Locations searched for config.json, in priority order.

    The bundled copy comes last so a frozen build still starts
    when the config folder next to the executable is missing.
    """

    base_directory = get_base_directory()

    candidates = []

    override = expand(
        os.environ.get(CONFIG_PATH_VARIABLE)
    )

    if override:
        candidates.append(override)

    candidates.append(
        os.path.join(
            base_directory,
            "config",
            CONFIG_FILE_NAME
        )
    )

    candidates.append(
        os.path.join(
            base_directory,
            CONFIG_FILE_NAME
        )
    )

    if is_frozen():

        candidates.append(
            os.path.join(
                get_bundle_directory(),
                "config",
                CONFIG_FILE_NAME
            )
        )

    unique = []

    for candidate in candidates:

        normalized = os.path.normpath(candidate)

        if normalized not in unique:
            unique.append(normalized)

    return unique


def find_config_path():

    for candidate in candidate_config_paths():

        if os.path.isfile(candidate):
            return candidate

    return None


def default_config():
    """
    Defaults with runtime details filled in, used to reach a log
    file even when the config itself is what failed.
    """

    config = copy.deepcopy(DEFAULT_CONFIG)

    config["runtime"] = {
        "config_path": None,
        "base_directory": get_base_directory(),
        "frozen": is_frozen()
    }

    return config


def load_config():

    config_path = find_config_path()

    if not config_path:

        raise FileNotFoundError(
            "Configuration file not found. Searched:\n  {}".format(
                "\n  ".join(candidate_config_paths())
            )
        )

    try:

        with open(config_path, "r", encoding="utf-8") as file:
            raw_config = json.load(file)

    except ValueError as error:

        raise ValueError(
            "Configuration file is not valid JSON ({}): {}".format(
                config_path,
                error
            )
        )

    config = _merge(
        DEFAULT_CONFIG,
        _expand_environment_variables(raw_config)
    )

    config["runtime"] = {
        "config_path": config_path,
        "base_directory": get_base_directory(),
        "frozen": is_frozen()
    }

    _validate(config)

    return config


def _validate(config):

    if not config["excel"].get("file_path"):

        raise ValueError(
            "excel.file_path is not set in {}".format(
                config["runtime"]["config_path"]
            )
        )

    if not config["excel"].get("table_name"):

        raise ValueError(
            "excel.table_name is not set in {}".format(
                config["runtime"]["config_path"]
            )
        )
