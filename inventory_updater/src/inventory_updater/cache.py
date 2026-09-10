from __future__ import annotations

import json
import os
import platform
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from marcone.models import PartPricing


def get_user_cache_dir() -> Path:
    """Return platform user cache directory."""
    system = platform.system()
    if system == "Windows":
        base = os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        return Path(base) / "tech2k-tools"
    if system == "Darwin":
        return Path.home() / "Library" / "Caches" / "tech2k-tools"
    base = os.getenv("XDG_CACHE_HOME") or (Path.home() / ".cache")
    return Path(base) / "tech2k-tools"


def get_default_cache_path() -> str:
    """Return default SQLite cache path, preferring local workspace if present."""
    local_cache = Path.cwd() / ".cache"
    if local_cache.exists() or (Path.cwd() / "pyproject.toml").exists():
        return str(local_cache / "marcone_prices.sqlite")
    return str(get_user_cache_dir() / "marcone_prices.sqlite")


def _is_expired(
    updated_at_str: str | None,
    max_age_seconds: float | None,
    now: datetime | None = None,
) -> bool:
    """Return True if updated_at is missing, invalid, or older than max_age_seconds."""
    if max_age_seconds is None or not updated_at_str:
        return False
    try:
        updated_at = datetime.fromisoformat(updated_at_str)
        current_time = now or datetime.now(timezone.utc)
        return (current_time - updated_at).total_seconds() > max_age_seconds
    except ValueError:
        return True


def _row_to_pricing(
    part_number: str,
    make: str | None,
    customer_cost: float | None,
    list_price: float | None,
    core_charge: float | None,
    in_stock: int | None,
    description: str | None,
    metadata_json: str | None,
) -> PartPricing:
    """Deserialize database columns into a PartPricing instance."""
    metadata: dict[str, Any] = {}
    if metadata_json:
        try:
            metadata = json.loads(metadata_json)
        except ValueError:
            pass

    return PartPricing(
        part_number=part_number,
        make=make or "",
        description=description,
        customer_cost=customer_cost,
        list_price=list_price,
        core_charge=core_charge,
        in_stock=bool(in_stock) if in_stock is not None else None,
        metadata=metadata,
    )


class PriceCache:
    """SQLite-backed cache for Marcone part lookups."""

    def __init__(self, db_path: str | None = None, chunk_size: int = 500) -> None:
        self.db_path = db_path or get_default_cache_path()
        self.chunk_size = chunk_size
        self._write_lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        return sqlite3.connect(self.db_path, timeout=30.0)

    def _init_db(self) -> None:
        with self._write_lock, self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS part_cache (
                    part_number TEXT PRIMARY KEY,
                    make TEXT,
                    customer_cost REAL,
                    list_price REAL,
                    core_charge REAL,
                    in_stock INTEGER,
                    description TEXT,
                    metadata TEXT,
                    status TEXT,
                    updated_at TIMESTAMP
                )
                """
            )
            conn.commit()

    def get(
        self, part_number: str, max_age_seconds: float | None = None
    ) -> PartPricing | None:
        """Retrieve cached pricing if present and not expired."""
        clean_part = part_number.strip().upper()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT make, customer_cost, list_price, core_charge, in_stock, description, metadata, status, updated_at
                FROM part_cache
                WHERE part_number = ?
                """,
                (clean_part,),
            )
            row = cur.fetchone()

        if not row:
            return None

        (
            make,
            customer_cost,
            list_price,
            core_charge,
            in_stock,
            description,
            metadata_json,
            status,
            updated_at_str,
        ) = row

        if status != "ok" or _is_expired(updated_at_str, max_age_seconds):
            return None

        return _row_to_pricing(
            clean_part,
            make,
            customer_cost,
            list_price,
            core_charge,
            in_stock,
            description,
            metadata_json,
        )

    def get_many(
        self,
        part_numbers: list[str],
        max_age_seconds: float | None = None,
        chunk_size: int | None = None,
    ) -> tuple[dict[str, PartPricing], set[str]]:
        """Batch retrieve cached pricing and known missing parts.

        Returns (cached_map, missing_set), where cached_map maps uppercase part numbers
        to valid unexpired PartPricing, and missing_set contains uppercase part numbers
        marked not_found within TTL.
        """
        clean_parts = list(
            dict.fromkeys(
                p.strip().upper() for p in part_numbers if p and str(p).strip()
            )
        )
        if not clean_parts:
            return {}, set()

        cached_map: dict[str, PartPricing] = {}
        missing_set: set[str] = set()
        now = datetime.now(timezone.utc)
        step = max(1, chunk_size or self.chunk_size)

        with self._get_connection() as conn:
            cur = conn.cursor()
            for i in range(0, len(clean_parts), step):
                chunk = clean_parts[i : i + step]
                placeholders = ",".join("?" for _ in chunk)
                cur.execute(
                    f"""
                    SELECT part_number, make, customer_cost, list_price, core_charge,
                           in_stock, description, metadata, status, updated_at
                    FROM part_cache
                    WHERE part_number IN ({placeholders})
                    """,
                    chunk,
                )
                for row in cur.fetchall():
                    (
                        part_no,
                        make,
                        customer_cost,
                        list_price,
                        core_charge,
                        in_stock,
                        description,
                        metadata_json,
                        status,
                        updated_at_str,
                    ) = row

                    if _is_expired(updated_at_str, max_age_seconds, now=now):
                        continue

                    if status == "ok":
                        cached_map[part_no] = _row_to_pricing(
                            part_no,
                            make,
                            customer_cost,
                            list_price,
                            core_charge,
                            in_stock,
                            description,
                            metadata_json,
                        )
                    elif status == "not_found":
                        missing_set.add(part_no)

        return cached_map, missing_set

    def set(self, pricing: PartPricing, status: str = "ok") -> None:
        """Cache pricing for a part."""
        clean_part = pricing.part_number.strip().upper()
        now = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(pricing.metadata) if pricing.metadata else ""

        with self._write_lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO part_cache (
                    part_number, make, customer_cost, list_price, core_charge,
                    in_stock, description, metadata, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(part_number) DO UPDATE SET
                    make = excluded.make,
                    customer_cost = excluded.customer_cost,
                    list_price = excluded.list_price,
                    core_charge = excluded.core_charge,
                    in_stock = excluded.in_stock,
                    description = excluded.description,
                    metadata = excluded.metadata,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    clean_part,
                    pricing.make,
                    pricing.customer_cost,
                    pricing.list_price,
                    pricing.core_charge,
                    int(pricing.in_stock) if pricing.in_stock is not None else None,
                    pricing.description,
                    metadata_json,
                    status,
                    now,
                ),
            )
            conn.commit()

    def set_not_found(self, part_number: str) -> None:
        """Record that a part was not found to prevent redundant lookups."""
        clean_part = part_number.strip().upper()
        now = datetime.now(timezone.utc).isoformat()
        with self._write_lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO part_cache (part_number, status, updated_at)
                VALUES (?, 'not_found', ?)
                ON CONFLICT(part_number) DO UPDATE SET
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (clean_part, now),
            )
            conn.commit()

    def is_known_missing(
        self, part_number: str, max_age_seconds: float | None = None
    ) -> bool:
        """Check if part was previously marked not found."""
        clean_part = part_number.strip().upper()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT status, updated_at FROM part_cache WHERE part_number = ?",
                (clean_part,),
            )
            row = cur.fetchone()

        if not row:
            return False

        status, updated_at_str = row
        return status == "not_found" and not _is_expired(
            updated_at_str, max_age_seconds
        )
