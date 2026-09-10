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

