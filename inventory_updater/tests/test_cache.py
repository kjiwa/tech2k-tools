import time

from inventory_updater.cache import PriceCache
from marcone.models import PartPricing


def test_cache_set_and_get(tmp_path):
    db_file = tmp_path / "cache.sqlite"
    cache = PriceCache(db_path=str(db_file))

    pricing = PartPricing(
        part_number="WPW10321304",
        make="WPL",
        customer_cost=15.50,
        list_price=24.99,
        core_charge=0.0,
        in_stock=True,
    )
    cache.set(pricing)

    retrieved = cache.get("wpw10321304")
    assert retrieved is not None
    assert retrieved.part_number == "WPW10321304"
    assert retrieved.make == "WPL"
    assert retrieved.customer_cost == 15.50
    assert retrieved.list_price == 24.99
    assert retrieved.in_stock is True


def test_cache_ttl_expiration(tmp_path):
    db_file = tmp_path / "cache.sqlite"
    cache = PriceCache(db_path=str(db_file))

    pricing = PartPricing(part_number="EXP123", customer_cost=10.0)
    cache.set(pricing)

    time.sleep(0.05)
    # Check with very small max_age
    assert cache.get("EXP123", max_age_seconds=0.01) is None
    # Check with larger max_age
    assert cache.get("EXP123", max_age_seconds=10.0) is not None


def test_cache_not_found(tmp_path):
    db_file = tmp_path / "cache.sqlite"
    cache = PriceCache(db_path=str(db_file))

    assert cache.is_known_missing("MISSING1") is False
    cache.set_not_found("MISSING1")
    assert cache.is_known_missing("MISSING1") is True
    assert cache.get("MISSING1") is None


def test_cache_get_many(tmp_path):
    db_file = tmp_path / "cache.sqlite"
    cache = PriceCache(db_path=str(db_file))

    cache.set(PartPricing(part_number="PART1", customer_cost=10.0, list_price=20.0))
    cache.set(PartPricing(part_number="PART2", customer_cost=15.0, list_price=30.0))
    cache.set_not_found("PART3")

    cached_map, missing_set = cache.get_many(["part1", "PART2", "part3", "part4", ""])
    assert len(cached_map) == 2
    assert cached_map["PART1"].customer_cost == 10.0
    assert cached_map["PART2"].list_price == 30.0
    assert "PART3" in missing_set
    assert "PART4" not in missing_set
    assert "PART4" not in cached_map


def test_cache_concurrent_writes(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    db_file = tmp_path / "cache.sqlite"
    cache = PriceCache(db_path=str(db_file))

    def write_task(i):
        if i % 2 == 0:
            cache.set(PartPricing(part_number=f"P{i}", customer_cost=float(i)))
        else:
            cache.set_not_found(f"P{i}")

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(write_task, range(50)))

    cached_map, missing_set = cache.get_many([f"P{i}" for i in range(50)])
    assert len(cached_map) == 25
    assert len(missing_set) == 25


def test_user_cache_dir(monkeypatch, tmp_path):
    from inventory_updater.cache import get_default_cache_path, get_user_cache_dir

    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setenv("LOCALAPPDATA", "C:\\Users\\Test\\AppData\\Local")
    win_dir = get_user_cache_dir()
    assert "tech2k-tools" in str(win_dir)

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    mac_dir = get_user_cache_dir()
    assert "Caches" in str(mac_dir)

    monkeypatch.setattr("inventory_updater.cache.Path.cwd", lambda: tmp_path)
    cache_path = get_default_cache_path()
    assert cache_path == str(mac_dir / "marcone_prices.sqlite")


