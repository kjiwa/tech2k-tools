from __future__ import annotations

import os
import platform
from pathlib import Path

from dotenv import dotenv_values, set_key, unset_key
from marcone.client import MarconeClient
from marcone.exceptions import AuthenticationError, MarconeError


def get_user_config_dir() -> Path:
    """Return platform user config directory."""
    system = platform.system()
    if system == "Windows":
        base = os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return Path(base) / "tech2k-tools"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "tech2k-tools"
    base = os.getenv("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "tech2k-tools"


def get_default_env_path() -> Path:
    """Return the user-config .env path used for saving credentials."""
    return get_user_config_dir() / ".env"


def _read_env_file(path: Path) -> dict[str, str | None]:
    return dotenv_values(path) if path.exists() else {}


def _credential_sources(env_path: Path | None) -> list[Path]:
    if env_path is not None:
        return [env_path]
    return [Path.cwd() / ".env", get_default_env_path()]


def _resolve_key(key: str, files: list[dict[str, str | None]]) -> str:
    value = os.getenv(key)
    if value:
        return value
    for file_vars in files:
        if file_vars.get(key):
            return str(file_vars[key])
    return ""


def load_credentials(env_path: Path | None = None) -> dict[str, str]:
    """Load credentials: environment variables, then cwd .env, then user .env, per key."""
    files = [_read_env_file(p) for p in _credential_sources(env_path)]
    return {
        "username": _resolve_key("MARCONE_USERNAME", files).strip(),
        "password": _resolve_key("MARCONE_PASSWORD", files),
        "account_number": _resolve_key("MARCONE_ACCOUNT_NUMBER", files).strip(),
    }


def save_credentials(
    username: str,
    password: str,
    account_number: str = "",
    env_path: Path | None = None,
) -> None:
    """Save credentials to the user-config .env file."""
    path = env_path or get_default_env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch(mode=0o600)

    set_key(str(path), "MARCONE_USERNAME", username)
    set_key(str(path), "MARCONE_PASSWORD", password)
    if account_number:
        set_key(str(path), "MARCONE_ACCOUNT_NUMBER", account_number)
        os.environ["MARCONE_ACCOUNT_NUMBER"] = account_number
    else:
        if "MARCONE_ACCOUNT_NUMBER" in dotenv_values(path):
            unset_key(str(path), "MARCONE_ACCOUNT_NUMBER")
        os.environ.pop("MARCONE_ACCOUNT_NUMBER", None)
    path.chmod(0o600)

    os.environ["MARCONE_USERNAME"] = username
    os.environ["MARCONE_PASSWORD"] = password


def check_connection(
    username: str,
    password: str,
    account_number: str = "",
) -> tuple[bool, str]:
    """Test login to Marcone with the supplied credentials."""
    if not username or not password:
        return False, "Username and password cannot be empty."

    client = MarconeClient()
    try:
        client.login(
            username=username,
            password=password,
            customer_number=account_number or None,
        )
        return True, "Successfully authenticated with Marcone."
    except AuthenticationError as exc:
        return False, f"Login failed: {exc}"
    except MarconeError as exc:
        return False, f"Marcone service error: {exc}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Connection failed: {exc}"
    finally:
        client.close()
