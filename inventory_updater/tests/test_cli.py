from unittest.mock import patch

from inventory_updater.cache import get_default_cache_path
from inventory_updater.cli import main, parse_args
from inventory_updater.updater import MissingColumnsError, UpdateStats


def test_parse_args_defaults():
    args = parse_args([])
    assert args.file == "Service Fusion Inventory.xlsx"
    assert args.output is None
    assert args.field == "both"
    assert args.dry_run is False
    assert args.cache_ttl_days == 7.0
    assert args.supplier_filter == "Marcone"
    assert args.allow_blank_supplier is True
    assert args.workers == 3
    assert args.throttle_seconds == 0.2
    assert args.cache_chunk_size == 500
    assert args.lookahead is None


def test_parse_args_no_allow_blank_supplier():
    args = parse_args(["--no-allow-blank-supplier"])
    assert args.allow_blank_supplier is False


def test_parse_args_custom():
    args = parse_args(
        [
            "--file",
            "custom.xlsx",
            "--field",
            "cost",
            "--dry-run",
            "--limit",
            "10",
            "--set-supplier",
            "Marcone",
            "--workers",
            "5",
            "--throttle",
            "0.5",
            "--cache-chunk-size",
            "250",
            "--lookahead",
            "20",
        ]
    )
    assert args.file == "custom.xlsx"
    assert args.field == "cost"
    assert args.dry_run is True
    assert args.limit == 10
    assert args.set_supplier == "Marcone"
    assert args.workers == 5
    assert args.throttle_seconds == 0.5
    assert args.cache_chunk_size == 250
    assert args.lookahead == 20


def test_parse_args_aliases():
    args = parse_args(
        [
            "--throttle-seconds",
            "0.35",
            "--batch-size",
            "100",
        ]
    )
    assert args.throttle_seconds == 0.35
    assert args.cache_chunk_size == 100


def test_main_missing_file(tmp_path):
    missing = tmp_path / "nonexistent.xlsx"
    code = main(["--file", str(missing)])
    assert code == 1


def test_main_missing_credentials(tmp_path):
    fake_file = tmp_path / "items.xlsx"
    fake_file.touch()

    with (
        patch.dict("os.environ", {}, clear=True),
    ):
        code = main(["--file", str(fake_file)])
        assert code == 1


def test_main_typo_fallback(tmp_path, capsys):
    real_file = tmp_path / "Service Fusion Inventory.xlsx"
    real_file.touch()

    # Pass the .xslx typo
    typo_file = tmp_path / "Service Fusion Inventory.xslx"

    with (
        patch.dict("os.environ", {}, clear=True),
    ):
        code = main(["--file", str(typo_file)])
        # Falls back to .xlsx, fails at missing credentials rather than missing file
        captured = capsys.readouterr()
        assert "not found" not in captured.err
        assert "Marcone credentials required" in captured.err
        assert code == 1


def test_main_concurrency_wiring(tmp_path):
    excel_file = tmp_path / "Service Fusion Inventory.xlsx"
    excel_file.touch()

    with (
        patch.dict(
            "os.environ",
            {
                "MARCONE_USERNAME": "test_user",
                "MARCONE_PASSWORD": "test_password",
            },
            clear=True,
        ),
        patch("inventory_updater.cli._resolve_input_path", return_value=excel_file),
        patch("inventory_updater.cli.MarconeClient") as mock_client_cls,
        patch("inventory_updater.cli.PriceCache") as mock_cache_cls,
        patch("inventory_updater.cli.InventoryUpdater") as mock_updater_cls,
    ):
        mock_updater = mock_updater_cls.return_value
        mock_updater.update_file.return_value = UpdateStats()

        code = main(
            [
                "--file",
                str(excel_file),
                "--workers",
                "6",
                "--throttle",
                "0.4",
                "--cache-chunk-size",
                "300",
                "--lookahead",
                "15",
            ]
        )
        assert code == 0
        mock_client_cls.assert_called_once_with(throttle_seconds=0.4)
        mock_cache_cls.assert_called_once_with(db_path=get_default_cache_path(), chunk_size=300)
        assert mock_updater_cls.call_args.kwargs["workers"] == 6
        assert mock_updater_cls.call_args.kwargs["cache_chunk_size"] == 300
        assert mock_updater.update_file.call_args.kwargs["workers"] == 6
        assert mock_updater.update_file.call_args.kwargs["lookahead"] == 15


def test_main_missing_columns_prints_error_and_returns_1(tmp_path, capsys):
    excel_file = tmp_path / "Service Fusion Inventory.xlsx"
    excel_file.touch()

    with (
        patch.dict(
            "os.environ",
            {"MARCONE_USERNAME": "u", "MARCONE_PASSWORD": "p"},
            clear=True,
        ),
        patch("inventory_updater.cli._resolve_input_path", return_value=excel_file),
        patch("inventory_updater.cli.MarconeClient") as mock_client_cls,
        patch("inventory_updater.cli.PriceCache"),
        patch("inventory_updater.cli.InventoryUpdater") as mock_updater_cls,
    ):
        mock_updater_cls.return_value.update_file.side_effect = MissingColumnsError(["Price"])
        code = main(["--file", str(excel_file)])

    assert code == 1
    assert "Price" in capsys.readouterr().err
    mock_client_cls.return_value.close.assert_called_once()


def _run_with_mocks(excel_file, argv):
    with (
        patch("inventory_updater.cli._resolve_input_path", return_value=excel_file),
        patch("inventory_updater.cli.MarconeClient") as mock_client_cls,
        patch("inventory_updater.cli.PriceCache") as mock_cache_cls,
        patch("inventory_updater.cli.InventoryUpdater") as mock_updater_cls,
    ):
        mock_updater_cls.return_value.update_file.return_value = UpdateStats()
        code = main(["--file", str(excel_file), *argv])
    return code, mock_client_cls, mock_cache_cls


def test_main_uses_user_env_file_and_does_not_touch_cwd(tmp_path, isolated_workspace):
    from inventory_updater.credentials import save_credentials

    save_credentials("fileuser", "filepw", "42")
    excel_file = tmp_path / "items.xlsx"
    excel_file.touch()
    before = sorted(p.name for p in isolated_workspace.iterdir())

    code, client_cls, cache_cls = _run_with_mocks(excel_file, [])

    assert code == 0
    client_cls.return_value.login.assert_called_once_with(
        username="fileuser", password="filepw", customer_number="42"
    )
    assert cache_cls.call_args.kwargs["db_path"] == get_default_cache_path()
    assert sorted(p.name for p in isolated_workspace.iterdir()) == before


def test_main_flags_override_credentials_and_cache(tmp_path):
    excel_file = tmp_path / "items.xlsx"
    excel_file.touch()
    cache_file = str(tmp_path / "c.sqlite")

    code, client_cls, cache_cls = _run_with_mocks(
        excel_file,
        ["--username", "flaguser", "--password", "flagpw", "--cache-file", cache_file],
    )

    assert code == 0
    client_cls.return_value.login.assert_called_once_with(
        username="flaguser", password="flagpw", customer_number=None
    )
    assert cache_cls.call_args.kwargs["db_path"] == cache_file
