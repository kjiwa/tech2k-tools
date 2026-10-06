import pytest
from marcone.exceptions import PartNotFoundError
from marcone.fake import FakeMarconeClient
from marcone.models import PartPricing


def test_lookup_part_default_canned():
    client = FakeMarconeClient()
    pricing = client.lookup_part("WPW10321304")
    assert pricing.part_number == "WPW10321304"
    assert pricing.customer_cost == 15.50
    assert pricing.list_price == 24.99
    assert pricing.make == "Whirlpool"
    assert pricing.in_stock is True


def test_lookup_part_case_and_whitespace():
    client = FakeMarconeClient()
    pricing = client.lookup_part("  wpw10321304  ")
    assert pricing.part_number == "WPW10321304"
    assert pricing.customer_cost == 15.50


def test_lookup_part_not_found():
    client = FakeMarconeClient()
    with pytest.raises(PartNotFoundError) as exc_info:
        client.lookup_part("NONEXISTENT_PART_123")
    assert "not found" in str(exc_info.value)


def test_lookup_part_empty():
    client = FakeMarconeClient()
    with pytest.raises(ValueError):
        client.lookup_part("   ")


def test_login_and_close():
    client = FakeMarconeClient()
    assert not client.is_logged_in
    assert client.login("any_user", "any_pass", "12345") is True
    assert client.is_logged_in is True
    client.close()


def test_context_manager():
    with FakeMarconeClient() as client:
        pricing = client.lookup_part("240323002")
        assert pricing.customer_cost == 22.75


def test_custom_canned_prices():
    custom = {
        "CUSTOM-01": PartPricing(
            part_number="CUSTOM-01",
            customer_cost=99.99,
            list_price=149.99,
            make="CustomMake",
        )
    }
    client = FakeMarconeClient(canned_prices=custom)
    pricing = client.lookup_part("custom-01")
    assert pricing.customer_cost == 99.99
    assert pricing.make == "CustomMake"

    with pytest.raises(PartNotFoundError):
        client.lookup_part("WPW10321304")


def test_auxiliary_query_methods():
    client = FakeMarconeClient()
    assert client.get_part_makes("WPW10321304") == ["Whirlpool"]
    assert client.get_part_makes("NONEXISTENT") == []

    assert client.get_customer_price("WPW10321304") == 15.50
    assert client.get_customer_price("NONEXISTENT") is None

    detail = client.get_product_detail("WPW10321304")
    assert detail is not None
    assert detail.list_price == 24.99
    assert client.get_product_detail("NONEXISTENT") is None

    search = client.search_part("WPW10321304")
    assert search is not None
    assert search.customer_cost == 15.50
    assert client.search_part("NONEXISTENT") is None
