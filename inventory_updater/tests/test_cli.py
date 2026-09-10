from unittest.mock import patch

from inventory_updater.cli import main, parse_args


def test_parse_args_defaults():
    args = parse_args([])
    assert args.file == "Service Fusion Inventory.xlsx"
    assert args.output is None
    assert args.field == "both"
    assert args.dry_run is False
    assert args.cache_ttl_days == 7.0


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
        ]
    )
    assert args.file == "custom.xlsx"
    assert args.field == "cost"
    assert args.dry_run is True
    assert args.limit == 10
    assert args.set_supplier == "Marcone"


def test_main_missing_file(tmp_path):
    missing = tmp_path / "nonexistent.xlsx"
    code = main(["--file", str(missing)])
    assert code == 1


def test_main_missing_credentials(tmp_path):
    fake_file = tmp_path / "items.xlsx"
    fake_file.touch()

    with (
        patch("inventory_updater.cli.load_dotenv"),
        patch.dict("os.environ", {}, clear=True),
    ):
        code = main(["--file", str(fake_file)])
        assert code == 1
