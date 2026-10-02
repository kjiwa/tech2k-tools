from __future__ import annotations

import sys
from types import TracebackType

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from marcone.exceptions import PartNotFoundError
from marcone.models import PartPricing

DEFAULT_CANNED_PRICES: dict[str, PartPricing] = {
    "WPW10321304": PartPricing(
        part_number="WPW10321304",
        make="Whirlpool",
        description="WATER FILTER",
        customer_cost=15.50,
        list_price=24.99,
        in_stock=True,
    ),
    "240323002": PartPricing(
        part_number="240323002",
        make="Frigidaire",
        description="DOOR BIN",
        customer_cost=22.75,
        list_price=35.00,
        in_stock=True,
    ),
    "WB44T10010": PartPricing(
        part_number="WB44T10010",
        make="GE",
        description="BAKE ELEMENT",
        customer_cost=18.20,
        list_price=29.50,
        in_stock=True,
    ),
    "DA62-00914B": PartPricing(
        part_number="DA62-00914B",
        make="Samsung",
        description="WATER VALVE",
        customer_cost=31.40,
        list_price=48.00,
        in_stock=True,
    ),
    "4681EA2001T": PartPricing(
        part_number="4681EA2001T",
        make="LG",
        description="DRAIN PUMP MOTOR",
        customer_cost=27.90,
        list_price=42.50,
        in_stock=True,
    ),
    "5304506516": PartPricing(
        part_number="5304506516",
        make="Frigidaire",
        description="DOOR GASKET",
        customer_cost=45.10,
        list_price=68.00,
        in_stock=True,
    ),
    "W10837240": PartPricing(
        part_number="W10837240",
        make="Whirlpool",
        description="HEATING ELEMENT",
        customer_cost=19.80,
        list_price=31.25,
        in_stock=True,
    ),
    "DC97-16782A": PartPricing(
        part_number="DC97-16782A",
        make="Samsung",
        description="DRUM ROLLER",
        customer_cost=12.30,
        list_price=19.99,
        in_stock=True,
    ),
    "240356402": PartPricing(
        part_number="240356402",
        make="Frigidaire",
        description="CRISPER PAN",
        customer_cost=38.60,
        list_price=58.00,
        in_stock=True,
    ),
    "3387747": PartPricing(
        part_number="3387747",
        make="Whirlpool",
        description="DRYER THERMOSTAT",
        customer_cost=8.45,
        list_price=14.00,
        in_stock=True,
    ),
}


class FakeMarconeClient:
    """Fake Marcone client returning canned pricing for testing without credentials."""

    def __init__(
        self,
        canned_prices: dict[str, PartPricing] | None = None,
        throttle_seconds: float = 0.0,
    ) -> None:
        self.canned_prices: dict[str, PartPricing] = {}
        source = canned_prices if canned_prices is not None else DEFAULT_CANNED_PRICES
        for k, v in source.items():
            self.canned_prices[k.strip().upper()] = v
        self.throttle_seconds = throttle_seconds
        self._is_logged_in = False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def login(
        self,
        username: str = "",
        password: str = "",
        customer_number: str | None = None,
    ) -> bool:
        self._is_logged_in = True
        return True

    def lookup_part(self, part_number: str) -> PartPricing:
        clean_part = part_number.strip()
        if not clean_part:
            raise ValueError("Part number cannot be empty")
        pricing = self.canned_prices.get(clean_part.upper())
        if pricing is None:
            raise PartNotFoundError(
                f"Part '{clean_part}' not found or pricing unavailable"
            )
        return pricing

    def get_part_makes(self, part_number: str) -> list[str]:
        clean_part = part_number.strip().upper()
        pricing = self.canned_prices.get(clean_part)
        if pricing and pricing.make:
            return [pricing.make]
        return []

    def get_customer_price(
        self, part_number: str, make: str = ""
    ) -> float | None:
        clean_part = part_number.strip().upper()
        pricing = self.canned_prices.get(clean_part)
        return pricing.customer_cost if pricing else None

    def get_product_detail(
        self, part_number: str, make: str = ""
    ) -> PartPricing | None:
        clean_part = part_number.strip().upper()
        return self.canned_prices.get(clean_part)

    def search_part(self, query: str) -> PartPricing | None:
        clean_part = query.strip().upper()
        return self.canned_prices.get(clean_part)

    def close(self) -> None:
        pass
