from __future__ import annotations

import os
import platform
from pathlib import Path

from dotenv import dotenv_values, set_key
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
    """Return default .env path in workspace or standard config directory."""
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        return cwd_env
    # Check parents
    for parent in Path.cwd().parents:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate
    user_env = get_user_config_dir() / ".env"
    if user_env.exists():
        return user_env
    if (Path.cwd() / "pyproject.toml").exists():
        return cwd_env
    return user_env


def load_credentials(env_path: Path | None = None) -> dict[str, str]:
    """Load credentials from environment variables or .env file."""
    path = env_path or get_default_env_path()
    file_vars: dict[str, str | None] = {}
    if path.exists():
        file_vars = dotenv_values(path)
    elif env_path is None:
        user_env = get_user_config_dir() / ".env"
        if user_env.exists():
            file_vars = dotenv_values(user_env)

    username = os.getenv("MARCONE_USERNAME") or str(
        file_vars.get("MARCONE_USERNAME") or ""
    )
    password = os.getenv("MARCONE_PASSWORD") or str(
        file_vars.get("MARCONE_PASSWORD") or ""
    )
    account_number = os.getenv("MARCONE_ACCOUNT_NUMBER") or str(
        file_vars.get("MARCONE_ACCOUNT_NUMBER") or ""
    )

    return {
        "username": username.strip(),
        "password": password.strip(),
        "account_number": account_number.strip(),
    }


def save_credentials(
    username: str,
    password: str,
    account_number: str = "",
    env_path: Path | None = None,
) -> None:
    """Save credentials to .env file."""
    path = env_path or get_default_env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch(mode=0o600)

    set_key(str(path), "MARCONE_USERNAME", username)
    set_key(str(path), "MARCONE_PASSWORD", password)
    if account_number:
        set_key(str(path), "MARCONE_ACCOUNT_NUMBER", account_number)

    os.environ["MARCONE_USERNAME"] = username
    os.environ["MARCONE_PASSWORD"] = password
    if account_number:
        os.environ["MARCONE_ACCOUNT_NUMBER"] = account_number


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
