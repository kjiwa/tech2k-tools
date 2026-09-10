class MarconeError(Exception):
    """Base exception for all Marcone client errors."""


class AuthenticationError(MarconeError):
    """Raised when authentication to Marcone fails."""


class AccountSelectionRequiredError(AuthenticationError):
    """Raised when an account requires selecting a customer number."""

    def __init__(self, message: str, customer_numbers: list[str] | None = None) -> None:
        super().__init__(message)
        self.customer_numbers = customer_numbers or []


class PartNotFoundError(MarconeError):
    """Raised when a requested part is not found."""


class RateLimitError(MarconeError):
    """Raised when requests are rate-limited or throttled."""


class NetworkError(MarconeError):
    """Raised when an underlying network or HTTP error occurs."""
