"""Repo-level invariants: versions agree, the changelog is current, shell scripts are
valid, console scripts resolve, and no machine-local path is tracked.
"""

import importlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
PYPROJECTS = [ROOT / "pyproject.toml", *sorted(ROOT.glob("*/pyproject.toml"))]
LEAK_RE = re.compile(r"/(?:Users|home)/([A-Za-z0-9_.-]+)")
ALLOWED_USER = "user"


def _in_work_tree() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT, capture_output=True, check=False
    )
    return result.returncode == 0


def _tracked_files() -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout
    return [ROOT / line for line in output.splitlines() if line]


def _version(pyproject: Path) -> str:
    match = re.search(r'^version = "([^"]+)"', pyproject.read_text(), re.MULTILINE)
    assert match, f"no version in {pyproject}"
    return match.group(1)


def _console_scripts(pyproject: Path) -> dict[str, str]:
    match = re.search(r"^\[project\.scripts\]\n((?:.+\n?)*)", pyproject.read_text(), re.MULTILINE)
    if not match:
        return {}
    return dict(re.findall(r'^(\S+) = "([^"]+)"', match.group(1), re.MULTILINE))


def test_pyproject_versions_are_equal():
    versions = {str(p.relative_to(ROOT)): _version(p) for p in PYPROJECTS}
    assert len(PYPROJECTS) == 3
    assert len(set(versions.values())) == 1, versions


def test_changelog_has_unreleased_and_current_version():
    headings = re.findall(r"^## (.+)$", (ROOT / "CHANGELOG.md").read_text(), re.MULTILINE)
    assert "Unreleased" in headings
    assert _version(ROOT / "pyproject.toml") in headings


def _shell_scripts() -> list[str]:
    return sorted(str(p.relative_to(ROOT)) for p in (ROOT / "scripts").glob("*.sh"))


def test_shell_scripts_parse():
    scripts = _shell_scripts()
    assert scripts
    for script in scripts:
        result = subprocess.run(
            ["sh", "-n", script], cwd=ROOT, capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, f"{script}: {result.stderr}"


@pytest.mark.skipif(not shutil.which("shellcheck"), reason="shellcheck is not installed")
def test_shell_scripts_pass_shellcheck():
    scripts = _shell_scripts()
    assert scripts
    result = subprocess.run(
        ["shellcheck", *scripts], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_console_scripts_resolve_to_callables():
    scripts = {name: target for p in PYPROJECTS for name, target in _console_scripts(p).items()}
    assert scripts
    for name, target in scripts.items():
        module, _, attr = target.partition(":")
        assert callable(getattr(importlib.import_module(module), attr)), name


@pytest.mark.skipif(not _in_work_tree(), reason="not inside a git work tree")
def test_no_tracked_file_names_a_real_home_directory():
    offenders = []
    for path in _tracked_files():
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\x00" in data[:8000]:
            continue
        for match in LEAK_RE.finditer(data.decode(errors="ignore")):
            if match.group(1) != ALLOWED_USER:
                offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)}")
    assert offenders == []
