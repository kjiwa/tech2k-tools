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
