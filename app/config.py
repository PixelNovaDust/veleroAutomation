import json
import os


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
        return os.path.expandvars(value)

    return value


def load_config():

    project_root = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )

    config_path = os.path.join(
        project_root,
        "config",
        "config.json"
    )

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            "Configuration file not found: {}".format(
                config_path
            )
        )

    with open(config_path, "r") as file:
        config = json.load(file)

    return _expand_environment_variables(config)