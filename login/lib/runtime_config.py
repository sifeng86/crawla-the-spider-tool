import json
import os
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from dotenv import dotenv_values

from .cryptograpy import Crypto


CONFIG_PATH = Path(__file__).resolve().parents[1] / 'setting' / 'config.json'
DOTENV_PATH = Path(__file__).resolve().parents[1] / '.env'
crypto = Crypto()


def load_legacy_config() -> dict[str, Any]:
    try:
        with CONFIG_PATH.open(encoding='utf-8') as config_file:
            loaded = json.load(config_file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}

    return loaded if isinstance(loaded, dict) else {}


def load_local_env_config() -> dict[str, str]:
    try:
        loaded = dotenv_values(DOTENV_PATH)
    except OSError:
        return {}

    normalized: dict[str, str] = {}
    for key, value in loaded.items():
        if key is None or value is None:
            continue
        stripped = str(value).strip()
        if stripped:
            normalized[str(key)] = stripped
    return normalized


def _normalize_config_path(config_path: Optional[Sequence[str] | str]) -> tuple[str, ...]:
    if config_path is None:
        return ()
    if isinstance(config_path, str):
        return (config_path,)
    return tuple(config_path)


def get_config_path_value(config: dict[str, Any], config_path: Optional[Sequence[str] | str]) -> Any:
    path = _normalize_config_path(config_path)
    if not path:
        return None

    current: Any = config
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def get_env_value(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name)
    if value is not None:
        stripped = value.strip()
        if stripped:
            return stripped

    dotenv_value = load_local_env_config().get(name)
    if dotenv_value is not None:
        return dotenv_value

    return default


def get_env_file_value(name: str, default: Optional[str] = None) -> Optional[str]:
    file_path = get_env_value(f'{name}_FILE')
    if not file_path:
        return default
    try:
        value = Path(file_path).read_text(encoding='utf-8').strip()
    except OSError as exc:
        raise RuntimeError(f'Unable to read {name}_FILE at {file_path}') from exc
    return value if value else default


def get_setting(
    env_name: str,
    *,
    config_path: Optional[Sequence[str] | str] = None,
    default: Any = None,
) -> Any:
    env_value = get_env_value(env_name)
    if env_value is not None:
        return env_value

    config_value = get_config_path_value(load_legacy_config(), config_path)
    if config_value is None:
        return default
    if isinstance(config_value, str):
        stripped = config_value.strip()
        return stripped if stripped else default
    return config_value


def get_int_setting(
    env_name: str,
    *,
    config_path: Optional[Sequence[str] | str] = None,
    default: int,
) -> int:
    value = get_setting(env_name, config_path=config_path, default=default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_float_setting(
    env_name: str,
    *,
    config_path: Optional[Sequence[str] | str] = None,
    default: float,
) -> float:
    value = get_setting(env_name, config_path=config_path, default=default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_secret_setting(
    env_name: str,
    *,
    config_path: Optional[Sequence[str] | str] = None,
    decrypt_legacy: bool = False,
    default: Optional[str] = None,
) -> Optional[str]:
    file_value = get_env_file_value(env_name)
    if file_value is not None:
        return file_value

    env_value = get_env_value(env_name)
    if env_value is not None:
        return env_value

    config_value = get_config_path_value(load_legacy_config(), config_path)
    if config_value is None:
        return default

    legacy_value = str(config_value).strip()
    if not legacy_value:
        return default
    if not decrypt_legacy:
        return legacy_value

    try:
        return crypto.decrypt_message(legacy_value.encode('utf-8'))
    except Exception as exc:
        path_label = '.'.join(_normalize_config_path(config_path)) or env_name
        raise RuntimeError(
            f"Failed to decrypt legacy config value '{path_label}'. Prefer {env_name} or {env_name}_FILE."
        ) from exc


def require_settings(setting_pairs: Iterable[tuple[str, Any]], message_prefix: str) -> None:
    missing = [label for label, value in setting_pairs if value in (None, '')]
    if missing:
        missing_list = ', '.join(missing)
        raise RuntimeError(f'{message_prefix}: {missing_list}')