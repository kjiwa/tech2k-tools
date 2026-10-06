import os
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
    from inventory_updater.credentials import get_user_config_dir

    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setenv("APPDATA", "C:\\Users\\Test\\AppData\\Roaming")
    assert "tech2k-tools" in str(get_user_config_dir())

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    assert "Application Support" in str(get_user_config_dir())


def _user_env():
    from inventory_updater.credentials import get_default_env_path

    return get_default_env_path()


def test_get_default_env_path_is_user_config_even_in_project_dir(isolated_workspace):
    from inventory_updater.credentials import get_user_config_dir

    (isolated_workspace / ".env").write_text("MARCONE_USERNAME=cwd\n")
    assert _user_env() == get_user_config_dir() / ".env"


def test_save_credentials_default_path_never_writes_to_cwd(isolated_workspace):
    before = sorted(p.name for p in isolated_workspace.iterdir())
    save_credentials("u", "p", "123")

    assert sorted(p.name for p in isolated_workspace.iterdir()) == before
    assert _user_env().exists()
    assert load_credentials()["username"] == "u"


def test_load_order_env_then_cwd_then_user_per_key(isolated_workspace, monkeypatch):
    user_env = _user_env()
    user_env.parent.mkdir(parents=True)
    user_env.write_text(
        "MARCONE_USERNAME=user\nMARCONE_PASSWORD=userpw\nMARCONE_ACCOUNT_NUMBER=9\n"
    )
    (isolated_workspace / ".env").write_text("MARCONE_USERNAME=cwd\nMARCONE_PASSWORD=cwdpw\n")
    monkeypatch.setenv("MARCONE_USERNAME", "envuser")

    creds = load_credentials()
    assert creds == {"username": "envuser", "password": "cwdpw", "account_number": "9"}


def test_save_empty_account_number_clears_file_and_environ(monkeypatch):
    save_credentials("u", "p", "123")
    assert load_credentials()["account_number"] == "123"

    save_credentials("u", "p", "")
    assert "MARCONE_ACCOUNT_NUMBER" not in os.environ
    assert "MARCONE_ACCOUNT_NUMBER" not in _user_env().read_text()
    assert load_credentials()["account_number"] == ""


def test_save_empty_account_number_without_existing_key_is_noop(caplog):
    save_credentials("u", "p", "")
    assert "MARCONE_ACCOUNT_NUMBER" not in _user_env().read_text()
    assert not caplog.records


def test_password_whitespace_preserved_username_stripped(monkeypatch):
    env_file = _user_env()
    save_credentials("  u  ", "  pw  ", env_path=env_file)
    monkeypatch.delenv("MARCONE_USERNAME")
    monkeypatch.delenv("MARCONE_PASSWORD")

    creds = load_credentials()
    assert creds["username"] == "u"
    assert creds["password"] == "  pw  "
