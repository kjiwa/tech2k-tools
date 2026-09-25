from __future__ import annotations

import contextlib
import logging
import re
import sys
import threading
import time
from types import TracebackType
from typing import Any
from urllib.parse import parse_qs, urlparse

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

import requests
from bs4 import BeautifulSoup, Tag

from marcone.exceptions import (
    AccountSelectionRequiredError,
    AuthenticationError,
    NetworkError,
    PartNotFoundError,
    RateLimitError,
)
from marcone.models import PartPricing

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://my.marcone.com"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_PRICE_RE = re.compile(r"(\d+(?:\.\d{1,4})?)")


class MarconeClient:
    """HTTP client for interacting with the Marcone appliance parts portal."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 30.0,
        throttle_seconds: float = 0.2,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.throttle_seconds = throttle_seconds
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.session.headers["User-Agent"] = user_agent
        self._is_logged_in = False
        self._last_request_time: float = 0.0
        self._owner_thread = threading.get_ident()
        self._local = threading.local()
        self._session_lock = threading.Lock()
        self._throttle_lock = threading.Lock()
        self._created_sessions: list[requests.Session] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self.session.close()
        with self._session_lock:
            for s in self._created_sessions:
                with contextlib.suppress(Exception):
                    s.close()
            self._created_sessions.clear()

    def _get_session(self) -> requests.Session:
        """Return a thread-safe Session instance for the calling thread."""
        if threading.get_ident() == self._owner_thread:
            return self.session
        sess = getattr(self._local, "session", None)
        if sess is None:
            sess = requests.Session()
            sess.headers.update(self.session.headers)
            with self._session_lock:
                sess.cookies.update(self.session.cookies)
                self._created_sessions.append(sess)
            self._local.session = sess
        return sess

    def _sync_cookies(self, source_session: requests.Session) -> None:
        """Propagate cookies from an authenticated session to other sessions."""
        with self._session_lock:
            if source_session is not self.session:
                self.session.cookies.update(source_session.cookies)
            for sess in self._created_sessions:
                if sess is not source_session:
                    sess.cookies.update(source_session.cookies)

    def _throttle(self) -> None:
        """Enforce request spacing across all threads to avoid overwhelming the server."""
        if self.throttle_seconds <= 0:
            return
        with self._throttle_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self.throttle_seconds:
                time.sleep(self.throttle_seconds - elapsed)
            self._last_request_time = time.monotonic()

    def _resolve_url(self, path: str) -> str:
        """Resolve a path or URL against the base URL."""
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _ajax_headers(self, referer_path: str | None = None) -> dict[str, str]:
        """Construct standard AJAX request headers."""
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Origin": self.base_url,
        }
        if referer_path is not None:
            headers["Referer"] = f"{self.base_url}/{referer_path.lstrip('/')}"
        return headers

    @staticmethod
    def _parse_retry_after(header_val: str | None, default: float = 2.0) -> float:
        """Safely extract retry delay seconds from a Retry-After header."""
        if not header_val:
            return default
        try:
            return max(float(header_val), 0.0)
        except (ValueError, TypeError):
            return default

    def _request(
        self,
        method: str,
        path: str,
        retries: int = 3,
        backoff_factor: float = 1.0,
        **kwargs: Any,
    ) -> requests.Response:
        """Send an HTTP request with retries and rate throttling."""
        url = self._resolve_url(path)
        kwargs.setdefault("timeout", self.timeout)
        max_attempts = max(retries, 1)

        for attempt in range(max_attempts):
            self._throttle()
            try:
                session = self._get_session()
                response = session.request(method, url, **kwargs)
                if response.status_code == 429:
                    if attempt == max_attempts - 1:
                        raise RateLimitError(
                            "Exceeded max retries due to server rate limiting"
                        )
                    retry_after = self._parse_retry_after(
                        response.headers.get("Retry-After")
                    )
                    logger.warning(
                        "Rate limited (429). Retrying after %.1f seconds...",
                        retry_after,
                    )
                    time.sleep(retry_after)
                    continue
                if response.status_code >= 500 and attempt < max_attempts - 1:
                    sleep_time = backoff_factor * (2**attempt)
                    logger.warning(
                        "Server error (%d). Retrying in %.1fs...",
                        response.status_code,
                        sleep_time,
                    )
                    time.sleep(sleep_time)
                    continue
                return response
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt == max_attempts - 1:
                    raise NetworkError(f"Network error accessing {url}: {exc}") from exc
                sleep_time = backoff_factor * (2**attempt)
                logger.warning("Connection failure. Retrying in %.1fs...", sleep_time)
                time.sleep(sleep_time)

        raise RateLimitError("Exceeded max retries due to server rate limiting")

    def login(
        self,
        username: str,
        password: str,
        customer_number: str | int | None = None,
    ) -> bool:
        """Authenticate with my.marcone.com using username and password."""
        logger.info("Initializing session at %s/UserLogin", self.base_url)
        self._load_login_page()
        data = self._submit_login(username, password)
        self._validate_login_response(data)
        self._handle_account_selection(data, customer_number)
        self._sync_cookies(self._get_session())
        self._is_logged_in = True
        logger.info("Successfully authenticated with Marcone as '%s'", username)
        return True

    def _load_login_page(self) -> None:
        init_resp = self._request("GET", "/UserLogin")
        if init_resp.status_code != 200:
            raise NetworkError(
                f"Failed to load login page: HTTP {init_resp.status_code}"
            )

    def _submit_login(self, username: str, password: str) -> dict[str, Any]:
        post_headers = self._ajax_headers("/UserLogin")
        post_headers["Content-Type"] = (
            "application/x-www-form-urlencoded; charset=UTF-8"
        )
        post_data = {
            "UserName": username,
            "Password": password,
            "RememberMe": "true",
            "code": "",
        }
        resp = self._request(
            "POST", "/UserLogin/DoLogin", headers=post_headers, data=post_data
        )
        if resp.status_code != 200:
            raise AuthenticationError(
                f"Login request failed with HTTP {resp.status_code}"
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise AuthenticationError(
                f"Unexpected non-JSON response from DoLogin: {resp.text[:200]}"
            ) from exc

    def _validate_login_response(self, data: dict[str, Any]) -> None:
        success = bool(data.get("Result"))
        message = str(data.get("Message") or "").strip()
        if not success:
            raise AuthenticationError(
                f"Authentication failed: {message or 'Invalid username or password'}"
            )
        if message.lower() in ("blocked", "subuserblocked"):
            raise AuthenticationError(f"Marcone account is blocked: {message}")

    def _handle_account_selection(
        self, data: dict[str, Any], customer_number: str | int | None
    ) -> None:
        if data.get("SetShipToReadOnly"):
            if customer_number is None:
                raise AccountSelectionRequiredError(
                    "Marcone login requires selecting an account/customer number. "
                    "Provide MARCONE_ACCOUNT_NUMBER."
                )
            self._set_customer_number(str(customer_number))

    def _set_customer_number(self, customer_number: str) -> None:
        """Select a customer/account number for multi-account logins."""
        headers = self._ajax_headers("/UserLogin")
        resp = self._request(
            "POST",
            "/UserLogin/SetCustomerNumber",
            headers=headers,
            data={"customerNumber": customer_number},
        )
        try:
            data = resp.json()
        except ValueError as exc:
            raise AuthenticationError(
                f"Non-JSON response from SetCustomerNumber: {resp.text[:200]}"
            ) from exc

        if not data.get("Result"):
            raise AuthenticationError(
                f"Failed to set customer number '{customer_number}': {data.get('Message', 'Unknown error')}"
            )

    @property
    def is_logged_in(self) -> bool:
        """Whether this client has successfully authenticated."""
        return self._is_logged_in

    @staticmethod
    def _parse_makes_from_html(html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        makes: list[str] = []
        for option in soup.find_all("option"):
            val = option.get("value")
            raw_text = val if val is not None else option.get_text()
            clean_val = str(raw_text).strip().strip("-").strip()
            if (
                clean_val
                and not clean_val.lower().startswith("select")
                and clean_val not in makes
            ):
                makes.append(clean_val)
        return makes

    def get_part_makes(self, part_number: str) -> list[str]:
        """Fetch available manufacturer (make) codes for a given part number."""
        clean_part = part_number.strip()
        if not clean_part:
            return []

        headers = self._ajax_headers()
        resp = self._request(
            "POST",
            "/Home/GetCartLookupParts",
            headers=headers,
            data={"partNumber": clean_part, "callFrom": "ExpressCart"},
        )
        if resp.status_code != 200:
            return []

        try:
            data = resp.json()
            html = data.get("Message") or ""
        except ValueError:
            html = resp.text

        return self._parse_makes_from_html(html)

    def get_customer_price(self, part_number: str, make: str) -> float | None:
        """Fetch the customer wholesale cost for a specific part and make."""
        clean_part = part_number.strip()
        clean_make = make.strip()
        if not clean_part or not clean_make:
            return None

        headers = self._ajax_headers()
        resp = self._request(
            "POST",
            "/Product/GetCustomerPrice",
            headers=headers,
            data={"part": clean_part, "make": clean_make},
        )
        if resp.status_code != 200:
            return None

        text = resp.text.strip().strip('"').strip("'")
        if not text or text == "-1":
            return None

        return self._clean_price(text)

    def get_product_detail(
        self, part_number: str, make: str = ""
    ) -> PartPricing | None:
        """Fetch detail page for part and make to retrieve retail price and stock status."""
        clean_part = part_number.strip()
        if not clean_part:
            return None

        clean_make = make.strip()
        params: dict[str, str] = {
            "Machine": "",
            "Category": "",
            "Part": clean_part,
        }
        if clean_make:
            params["Make"] = clean_make

        resp = self._request("GET", "/Product/Detail", params=params)
        if resp.status_code != 200:
            return None

        if "/UserLogin" in resp.url:
            raise AuthenticationError(
                "Session expired or unauthorized while viewing product details"
            )

        soup = BeautifulSoup(resp.text, "html.parser")
        return self._parse_detail_soup(soup, clean_part, clean_make)

    def search_part(self, part_number: str) -> PartPricing | None:
        """Search for a part and return its pricing and details."""
        clean_part = part_number.strip()
        if not clean_part:
            return None

        resp = self._request(
            "GET",
            "/Home/SearchPartModelList",
            params={"searchString": clean_part, "Type": "Part"},
        )
        if resp.status_code != 200:
            return None

        if "/UserLogin" in resp.url:
            raise AuthenticationError("Session expired or unauthorized while searching")

        soup = BeautifulSoup(resp.text, "html.parser")

        if "/Product/Detail" in resp.url:
            parsed_url = urlparse(resp.url)
            query_params = parse_qs(parsed_url.query)
            detected_make = query_params.get("Make", query_params.get("make", [""]))[0]
            return self._parse_detail_soup(soup, clean_part, detected_make)

        return self._parse_listing_soup(soup, clean_part)

    def lookup_part(self, part_number: str) -> PartPricing:
        """Look up part pricing across all available endpoints."""
        clean_part = part_number.strip()
        if not clean_part:
            raise ValueError("Part number cannot be empty")

        makes = self.get_part_makes(clean_part)
        primary_make = makes[0] if makes else ""
        customer_cost = (
            self.get_customer_price(clean_part, primary_make) if primary_make else None
        )

        detail = self.get_product_detail(clean_part, primary_make)
        if detail is None and customer_cost is None:
            detail = self.search_part(clean_part)

        if detail is not None:
            if customer_cost is None:
                customer_cost = detail.customer_cost
            list_price = detail.list_price
            core_charge = detail.core_charge
            in_stock = detail.in_stock
            description = detail.description
            if not primary_make and detail.make:
                primary_make = detail.make
        else:
            list_price = None
            core_charge = None
            in_stock = None
            description = None

        if customer_cost is None and list_price is None:
            raise PartNotFoundError(
                f"Part '{clean_part}' not found or pricing unavailable"
            )

        return PartPricing(
            part_number=clean_part,
            make=primary_make,
            description=description,
            customer_cost=customer_cost,
            list_price=list_price,
            core_charge=core_charge,
            in_stock=in_stock,
        )

    @staticmethod
    def _extract_detail_make(soup: BeautifulSoup, default_make: str) -> str:
        if default_make:
            return default_make
        make_input = soup.find("input", id="ProductDetailMake")
        if make_input and (val := make_input.get("value")):
            return str(val).strip()
        make_el = soup.select_one("tr.make_tr td.partbig, #ProductDetailMake")
        if make_el:
            return make_el.get_text(strip=True)
        return ""

    @staticmethod
    def _extract_customer_cost(soup: BeautifulSoup) -> float | None:
        price_row = soup.find(id="trPrice")
        if not price_row:
            return None
        price_td = price_row.select_one("td.priceblock_ourprice, td.green, td.red")
        return MarconeClient._clean_price(price_td.get_text()) if price_td else None

    @staticmethod
    def _extract_list_price(soup: BeautifulSoup) -> float | None:
        list_row = soup.find(id="trListPrice")
        if not list_row:
            return None
        list_b = list_row.select_one("td.green b, td.green, td")
        return MarconeClient._clean_price(list_b.get_text()) if list_b else None

    @staticmethod
    def _extract_core_charge(soup: BeautifulSoup) -> float | None:
        core_row = soup.find(id="trCoreCharge")
        if not core_row:
            return None
        return MarconeClient._clean_price(core_row.get_text())

    @staticmethod
    def _extract_stock_status(soup: BeautifulSoup) -> bool | None:
        stock_el = soup.select_one("span.a-color-success, span.spanInstock")
        if not stock_el:
            return None
        return "in stock" in stock_el.get_text().lower()

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str | None:
        desc_el = soup.select_one("h4.cross, h1.producttitle, .product_name")
        return desc_el.get_text(strip=True) if desc_el else None

    def _parse_detail_soup(
        self, soup: BeautifulSoup, part_number: str, make: str
    ) -> PartPricing | None:
        """Extract prices and metadata from a /Product/Detail page."""
        resolved_make = self._extract_detail_make(soup, make)
        customer_cost = self._extract_customer_cost(soup)
        list_price = self._extract_list_price(soup)
        core_charge = self._extract_core_charge(soup)
        in_stock = self._extract_stock_status(soup)
        description = self._extract_description(soup)

        if customer_cost is None and list_price is None:
            return None

        return PartPricing(
            part_number=part_number,
            make=resolved_make,
            description=description,
            customer_cost=customer_cost,
            list_price=list_price,
            core_charge=core_charge,
            in_stock=in_stock,
        )

    def _extract_listing_item(self, item: Tag, part_number: str) -> PartPricing | None:
        img = item.find("img", class_="productimage")
        item_part = ""
        item_make = ""
        if isinstance(img, Tag):
            raw_part = img.get("part", "")
            item_part = raw_part[0] if isinstance(raw_part, list) else str(raw_part)
            raw_make = img.get("make", "")
            item_make = raw_make[0] if isinstance(raw_make, list) else str(raw_make)

        if not item_part or item_part.strip().upper() == part_number.strip().upper():
            price_el = item.select_one("span.spanPrice, .price")
            cost = self._clean_price(price_el.get_text()) if price_el else None
            return PartPricing(
                part_number=part_number,
                make=item_make,
                customer_cost=cost,
            )
        return None

    def _parse_listing_soup(
        self, soup: BeautifulSoup, part_number: str
    ) -> PartPricing | None:
        """Extract prices from a search result item listing."""
        items = soup.select(".partResult_items, .search_item, .RepPartlist")
        for item in items:
            pricing = self._extract_listing_item(item, part_number)
            if pricing is not None:
                return pricing
        return None

    @staticmethod
    def _clean_price(val: str | None) -> float | None:
        if not val:
            return None
        stripped = val.strip()
        if stripped.startswith("-"):
            return None
        match = _PRICE_RE.search(stripped.replace(",", ""))
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None
