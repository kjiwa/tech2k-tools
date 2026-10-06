import pytest

ENV_KEYS = ("MARCONE_USERNAME", "MARCONE_PASSWORD", "MARCONE_ACCOUNT_NUMBER")


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path, monkeypatch):
    """Run every test from a project-like cwd with home and XDG dirs redirected."""
    home = tmp_path / "home"
    work = tmp_path / "work"
    home.mkdir()
    work.mkdir()
    (work / "pyproject.toml").write_text('[project]\nname = "x"\n')
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / ".cache"))
    monkeypatch.setenv("APPDATA", str(home / "AppData" / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(home / "AppData" / "Local"))
    for key in ENV_KEYS:
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key)
    monkeypatch.chdir(work)
    return work
