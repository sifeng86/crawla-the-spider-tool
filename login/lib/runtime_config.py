import os
from pathlib import Path
from typing import Any, Iterable, Optional

from dotenv import dotenv_values


DOTENV_PATH = Path(__file__).resolve().parents[1] / '.env'


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
    default: Any = None,
) -> Any:
    env_value = get_env_value(env_name)
    if env_value is not None:
        return env_value

    return default


def get_int_setting(
    env_name: str,
    *,
    default: int,
) -> int:
    value = get_setting(env_name, default=default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_float_setting(
    env_name: str,
    *,
    default: float,
) -> float:
    value = get_setting(env_name, default=default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_secret_setting(
    env_name: str,
    *,
    default: Optional[str] = None,
) -> Optional[str]:
    file_value = get_env_file_value(env_name)
    if file_value is not None:
        return file_value

    env_value = get_env_value(env_name)
    if env_value is not None:
        return env_value

    return default


def require_settings(setting_pairs: Iterable[tuple[str, Any]], message_prefix: str) -> None:
    missing = [label for label, value in setting_pairs if value in (None, '')]
    if missing:
        missing_list = ', '.join(missing)
        raise RuntimeError(f'{message_prefix}: {missing_list}')