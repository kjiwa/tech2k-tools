from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PartPricing:
    """Pricing information for a Marcone part."""

    part_number: str
    make: str = ""
    description: str | None = None
    customer_cost: float | None = None
    list_price: float | None = None
    core_charge: float | None = None
    in_stock: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_pricing(self) -> bool:
        """Return True if at least customer cost or list price is known."""
        return self.customer_cost is not None or self.list_price is not None
