from unittest.mock import MagicMock, patch

from inventory_updater.credentials import (
    check_connection,
    load_credentials,
    save_credentials,
)
from marcone.exceptions import AuthenticationError


def test_load_credentials_from_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("MARCONE_USERNAME=testuser\nMARCONE_PASSWORD=secret\n")

    with patch.dict("os.environ", {}, clear=True):
        creds = load_credentials(env_path=env_file)
        assert creds["username"] == "testuser"
        assert creds["password"] == "secret"
        assert creds["account_number"] == ""


def test_save_credentials(tmp_path):
    env_file = tmp_path / ".env"
    with patch.dict("os.environ", {}, clear=True):
        save_credentials(
            username="newuser",
            password="newpassword",
            account_number="12345",
            env_path=env_file,
        )

        creds = load_credentials(env_path=env_file)
        assert creds["username"] == "newuser"
        assert creds["password"] == "newpassword"
        assert creds["account_number"] == "12345"


def test_check_connection_success():
    with patch("inventory_updater.credentials.MarconeClient") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        success, msg = check_connection("valid", "password")
        assert success is True
        assert "Successfully authenticated" in msg
        mock_instance.login.assert_called_once_with(
            username="valid", password="password", customer_number=None
        )
        mock_instance.close.assert_called_once()


def test_check_connection_failure():
    with patch("inventory_updater.credentials.MarconeClient") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.login.side_effect = AuthenticationError("Invalid login")
        mock_cls.return_value = mock_instance

        success, msg = check_connection("bad", "creds")
        assert success is False
        assert "Login failed: Invalid login" in msg


def test_get_default_env_path_ignores_parent_dirs(tmp_path, monkeypatch):
    from inventory_updater.credentials import get_default_env_path, get_user_config_dir

    parent_env = tmp_path / ".env"
    parent_env.write_text("MARCONE_USERNAME=parent\n")
    child_dir = tmp_path / "child"
    child_dir.mkdir()

    monkeypatch.setattr(
        "inventory_updater.credentials.Path.cwd", lambda: child_dir
    )

    env_path = get_default_env_path()
    assert env_path != parent_env
    assert env_path == get_user_config_dir() / ".env"


def test_save_credentials_chmod_0600_on_existing_file(tmp_path):
    import stat

    env_file = tmp_path / ".env"
    env_file.write_text("MARCONE_USERNAME=old\n")
    env_file.chmod(0o644)

    with patch.dict("os.environ", {}, clear=True):
        save_credentials(
            username="newuser",
            password="newpassword",
            env_path=env_file,
        )

    mode = stat.S_IMODE(env_file.stat().st_mode)
    assert mode == 0o600


def test_get_user_config_dir(monkeypatch):
    from pathlib import Path

    from inventory_updater.credentials import get_default_env_path, get_user_config_dir

    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setenv("APPDATA", "C:\\Users\\Test\\AppData\\Roaming")
    win_dir = get_user_config_dir()
    assert "tech2k-tools" in str(win_dir)

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    mac_dir = get_user_config_dir()
    assert "Application Support" in str(mac_dir)

    # Test get_default_env_path when cwd has no .env and no pyproject
    monkeypatch.setattr(
        "inventory_updater.credentials.Path.cwd",
        lambda: Path("/nonexistent/dir"),
    )
    env_path = get_default_env_path()
    assert env_path == mac_dir / ".env"
