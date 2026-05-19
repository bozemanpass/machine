import os
import re
from pathlib import Path
from machine.di import d
from machine.factory import yaml
from machine.log import fatal_error, debug
from machine.types import Config, MachineConfig
from machine import constants
from machine.providers import KNOWN_PROVIDERS

_env_var_pattern = re.compile(r"\$\{([^}]+)\}")


def _expand_env_vars(value):
    if isinstance(value, str):

        def _replace(match):
            expr = match.group(1)
            if ":-" in expr:
                var_name, default = expr.split(":-", 1)
                return os.environ.get(var_name, default)
            else:
                if expr not in os.environ:
                    fatal_error(f"Environment variable '{expr}' referenced in config is not set")
                return os.environ[expr]

        return _env_var_pattern.sub(_replace, value)
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


class _loaded_config:
    c: any = None


def resolve_config_file_path(config_file_name: str) -> str:
    if not config_file_name:
        config_file_name = constants.default_config_file_path
    return str(Path(os.path.expanduser(config_file_name)))


def _load_config_data(config_file_name: str):
    config_path = Path(resolve_config_file_path(config_file_name))
    if not config_path.exists():
        fatal_error(f"Error: Config file: {config_path} not found")
    config = _expand_env_vars(yaml().load(open(config_path, "r")))
    if d.opt.debug:
        debug(f"Loaded config file: {config_path}")
        debug(f"Parsed config: {config}")
    _loaded_config.c = config
    return config


def _require_key(d, key, section_name):
    if key not in d:
        fatal_error(f"Required key '{key}' not found in '{section_name}' section of config file")
    return d[key]


def _get_ssh_keys(provider_config, section_name) -> list:
    """Read the 'ssh-key' config value, accepting either a single name (a
    string) or a list of names. Always returns a non-empty list of names."""
    value = _require_key(provider_config, "ssh-key", section_name)
    if isinstance(value, str):
        keys = [value]
    elif isinstance(value, list):
        keys = [str(k) for k in value]
    else:
        fatal_error(f"Config key 'ssh-key' in '{section_name}' section must be a name or a list of names")
    if not keys:
        fatal_error(f"Config key 'ssh-key' in '{section_name}' section must specify at least one SSH key")
    return keys


def get(config_file_name: str) -> Config:
    config = _load_config_data(config_file_name)

    # Auto-detect provider from config sections
    provider_name = config.get("provider")
    if not provider_name:
        found = [p for p in KNOWN_PROVIDERS if p in config]
        if len(found) == 0:
            fatal_error(
                "No provider section found in config file. Expected one of: " + ", ".join(KNOWN_PROVIDERS)
            )
        if len(found) > 1:
            fatal_error(
                "Multiple provider sections found in config file. Please add a 'provider:' key to select one."
            )
        provider_name = found[0]

    if provider_name not in config:
        fatal_error(f"Provider '{provider_name}' specified but no '{provider_name}' section found in config file")

    provider_config = config[provider_name]
    return Config(
        provider_name=provider_name,
        provider_config=provider_config,
        ssh_keys=_get_ssh_keys(provider_config, provider_name),
        dns_zone=provider_config.get("dns-zone"),
        machine_size=_require_key(provider_config, "machine-size", provider_name),
        image=_require_key(provider_config, "image", provider_name),
        region=_require_key(provider_config, "region", provider_name),
        project=provider_config.get("project"),
    )


def get_machine(name: str) -> MachineConfig:
    if not _loaded_config.c:
        fatal_error("Attempt to fetch machine data before config loaded")
    config = _loaded_config.c
    if "machines" not in config:
        fatal_error("Required 'machines' section not found in config file")
    config_machines = config["machines"]
    if name not in config_machines:
        fatal_error(f"Machine type '{name}' not found in config file. Available types: {', '.join(config_machines.keys())}")
    target_config = config_machines[name]
    return MachineConfig(
        _require_key(target_config, "new-user-name", f"machines.{name}"),
        target_config.get("script-url"),
        target_config.get("script-dir"),
        target_config.get("script-path"),
        target_config.get("script-args"),
    )


def get_machines():
    if not _loaded_config.c:
        fatal_error("Attempt to fetch machine data before config loaded")
    config = _loaded_config.c

    if "machines" not in config:
        fatal_error("Required 'machines' section not found in config file")
    ret = {}
    for name in config["machines"]:
        ret[name] = get_machine(name)
    return ret
