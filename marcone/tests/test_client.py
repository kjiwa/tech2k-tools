import pytest
import requests_mock
from marcone.client import MarconeClient
from marcone.exceptions import (
    AccountSelectionRequiredError,
    AuthenticationError,
    NetworkError,
    PartNotFoundError,
)


@pytest.fixture
def client() -> MarconeClient:
    return MarconeClient(base_url="https://test.marcone.com", throttle_seconds=0.0)


def test_clean_price():
    assert MarconeClient._clean_price("$16.37") == 16.37
    assert MarconeClient._clean_price("$1,234.56") == 1234.56
    assert MarconeClient._clean_price("100") == 100.0
    assert MarconeClient._clean_price("") is None
    assert MarconeClient._clean_price("N/A") is None


def test_login_success(client: MarconeClient):
    with requests_mock.Mocker() as m:
        m.get("https://test.marcone.com/UserLogin", text="<html>Login</html>", status_code=200)
        m.post(
            "https://test.marcone.com/UserLogin/DoLogin",
            json={"Result": True, "SetShipToReadOnly": False, "Message": ""},
        )

        assert client.login("user@example.com", "secret") is True
        assert client.is_logged_in is True


def test_login_requires_customer_number(client: MarconeClient):
    with requests_mock.Mocker() as m:
        m.get("https://test.marcone.com/UserLogin", text="<html>Login</html>")
        m.post(
            "https://test.marcone.com/UserLogin/DoLogin",
            json={"Result": True, "SetShipToReadOnly": True, "Message": ""},
        )

        with pytest.raises(AccountSelectionRequiredError):
            client.login("user@example.com", "secret")


def test_login_with_customer_number(client: MarconeClient):
    with requests_mock.Mocker() as m:
        m.get("https://test.marcone.com/UserLogin", text="<html>Login</html>")
        m.post(
            "https://test.marcone.com/UserLogin/DoLogin",
            json={"Result": True, "SetShipToReadOnly": True, "Message": ""},
        )
        m.post(
            "https://test.marcone.com/UserLogin/SetCustomerNumber",
            json={"Result": True, "Message": ""},
        )

        assert client.login("user@example.com", "secret", customer_number="123456") is True
        assert client.is_logged_in is True


def test_login_failed_credentials(client: MarconeClient):
    with requests_mock.Mocker() as m:
        m.get("https://test.marcone.com/UserLogin", text="<html>Login</html>")
        m.post(
            "https://test.marcone.com/UserLogin/DoLogin",
            json={"Result": False, "Message": "Invalid username or password"},
        )

        with pytest.raises(AuthenticationError, match="Invalid username or password"):
            client.login("user@example.com", "wrong")


def test_login_blocked_account(client: MarconeClient):
    with requests_mock.Mocker() as m:
        m.get("https://test.marcone.com/UserLogin", text="<html>Login</html>")
        m.post(
            "https://test.marcone.com/UserLogin/DoLogin",
            json={"Result": True, "Message": "blocked"},
        )

        with pytest.raises(AuthenticationError, match="blocked"):
            client.login("user@example.com", "secret")


def test_login_network_error(client: MarconeClient):
    with requests_mock.Mocker() as m:
        m.get("https://test.marcone.com/UserLogin", status_code=500)


def test_get_part_makes(client: MarconeClient):
    html = """
    <select id="Makeddl">
        <option value="">--Select--</option>
        <option value="WPL">WPL</option>
        <option value="FRG">FRG</option>
    </select>
    """
    with requests_mock.Mocker() as m:
        m.post(
            "https://test.marcone.com/Home/GetCartLookupParts",
            json={"Result": True, "Message": html},
        )

        makes = client.get_part_makes("240323002")
        assert makes == ["WPL", "FRG"]


def test_get_customer_price(client: MarconeClient):
    with requests_mock.Mocker() as m:
        m.post("https://test.marcone.com/Product/GetCustomerPrice", text='"$18.45"')
        price = client.get_customer_price("240323002", "FRG")
        assert price == 18.45

        m.post("https://test.marcone.com/Product/GetCustomerPrice", text='"-1"')
        assert client.get_customer_price("UNKNOWN", "FRG") is None


def test_get_product_detail(client: MarconeClient):
    html = """
    <input type="hidden" id="ProductDetailMake" value="FRG" />
    <h1 class="producttitle">DOOR BIN</h1>
    <table id="tblPricing">
        <tr id="trPrice"><td class="priceblock_ourprice">$18.45</td></tr>
        <tr id="trListPrice"><td class="green"><b>$26.99</b></td></tr>
        <tr id="trCoreCharge"><td>$5.00</td></tr>
    </table>
    <span class="a-color-success">In Stock</span>
    """
    with requests_mock.Mocker() as m:
        m.get("https://test.marcone.com/Product/Detail", text=html)
        detail = client.get_product_detail("240323002", "FRG")
        assert detail is not None
        assert detail.part_number == "240323002"
        assert detail.make == "FRG"
        assert detail.customer_cost == 18.45
        assert detail.list_price == 26.99
        assert detail.core_charge == 5.00
        assert detail.in_stock is True
        assert detail.description == "DOOR BIN"


def test_lookup_part_success(client: MarconeClient):
    makes_html = "<select><option value='WPL'>WPL</option></select>"
    detail_html = """
    <tr id="trPrice"><td class="priceblock_ourprice">$12.50</td></tr>
    <tr id="trListPrice"><td class="green"><b>$21.00</b></td></tr>
    """
    with requests_mock.Mocker() as m:
        m.post("https://test.marcone.com/Home/GetCartLookupParts", json={"Result": True, "Message": makes_html})
        m.post("https://test.marcone.com/Product/GetCustomerPrice", text="$12.50")
        m.get("https://test.marcone.com/Product/Detail", text=detail_html)

        pricing = client.lookup_part("WPW10321304")
        assert pricing.part_number == "WPW10321304"
        assert pricing.make == "WPL"
        assert pricing.customer_cost == 12.50
        assert pricing.list_price == 21.00
        assert pricing.has_pricing is True


def test_lookup_part_not_found(client: MarconeClient):
    with requests_mock.Mocker() as m:
        m.post("https://test.marcone.com/Home/GetCartLookupParts", json={"Result": True, "Message": ""})
        m.get("https://test.marcone.com/Product/Detail", text="<html>Not Found</html>")
        m.get("https://test.marcone.com/Home/SearchPartModelList", text="<html>No items</html>")

        with pytest.raises(PartNotFoundError):
            client.lookup_part("NONEXISTENT123")


def test_lookup_part_empty_input(client: MarconeClient):
    with pytest.raises(ValueError):
        client.lookup_part("   ")


        with pytest.raises(NetworkError):
            client.login("user@example.com", "secret")
