# marcone

Python client library for the Marcone appliance parts portal (`my.marcone.com`).

## Installation

Within the workspace:

```sh
uv sync
```

Standalone:

```sh
pip install -e ./marcone
```

Requires Python >= 3.10, `requests`, and `beautifulsoup4`.

## Usage

```python
from marcone import MarconeClient, PartNotFoundError

with MarconeClient() as client:
    client.login("user@example.com", "password", customer_number="12345")
    try:
        pricing = client.lookup_part("WD28X10128")
        print(pricing.customer_cost, pricing.list_price)
    except PartNotFoundError:
        print("Part not found")
```

## API Reference

### MarconeClient

```python
MarconeClient(
    base_url: str = "https://my.marcone.com",
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: float = 30.0,
    throttle_seconds: float = 0.2,
    session: requests.Session | None = None,
)
```

The client manages session cookies, request throttling across threads via a global lock and monotonic timestamp, and thread-local sessions for concurrent workers. Implements context manager protocol (`__enter__` and `__exit__`).

#### Parameters

- `base_url`: Marcone portal URL root.
- `user_agent`: Custom user agent header.
- `timeout`: Network request timeout in seconds (default: 30.0).
- `throttle_seconds`: Enforced minimum delay between consecutive HTTP requests across all worker threads (default: 0.2s, ~5 req/s peak).
- `session`: Optional custom `requests.Session` instance.

#### Methods

- `login(username, password, customer_number=None) -> bool`: Authenticate against `/UserLogin/DoLogin`. Raises `AuthenticationError` on invalid credentials or `AccountSelectionRequiredError` if multi-account selection is required.
- `lookup_part(part_number: str) -> PartPricing`: Perform full lookup combining make detection, customer cost, and product detail endpoints. Raises `PartNotFoundError` if part cannot be resolved.
- `get_part_makes(part_number: str) -> list[str]`: Return manufacturer codes matching a part number.
- `get_customer_price(part_number: str, make: str) -> float | None`: Return wholesale customer cost for part and manufacturer code.
- `get_product_detail(part_number: str, make: str = "") -> PartPricing | None`: Fetch product detail page for list price, core charge, description, and stock status.
- `search_part(part_number: str) -> PartPricing | None`: Fallback search query for parts without direct detail pages.
- `close() -> None`: Close primary and worker HTTP sessions.

### Models

#### PartPricing

Frozen dataclass containing resolved part attributes.

| Field | Type | Description |
| --- | --- | --- |
| `part_number` | `str` | Cleaned part number |
| `make` | `str` | Manufacturer code |
| `description` | `str \| None` | Item description or catalog title |
| `customer_cost` | `float \| None` | Wholesale customer purchase cost |
| `list_price` | `float \| None` | Suggested retail list price |
| `core_charge` | `float \| None` | Core deposit charge |
| `in_stock` | `bool \| None` | Inventory availability indicator |
| `metadata` | `dict[str, Any]` | Raw auxiliary data |

Property:
- `has_pricing`: Returns `True` if either `customer_cost` or `list_price` is populated.

### Exceptions

- `MarconeError`: Base exception for client errors.
- `AuthenticationError`: Invalid credentials, blocked account, or expired session.
- `AccountSelectionRequiredError`: Multi-account login requiring `customer_number`. Exposes `customer_numbers` attribute.
- `PartNotFoundError`: Requested part number does not exist in portal catalog.
- `RateLimitError`: HTTP 429 response or retry budget exceeded.
- `NetworkError`: HTTP connection failure, DNS resolution failure, or timeout.

